"""The question-answering agent.

    retrieve -> answer -> verify -> done
       ^          |          |
       |          v          v
       +------ rewrite <-----+

The answer step doubles as the grader: when it reports that the sources do not
contain the answer, the graph rewrites the query and searches again. The verify
step checks every figure in the answer against the cited sources without
calling the model, and a figure it cannot find also sends the graph back to
search again. Both loops share one limit on rewrites.
"""

import operator
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Any, Literal, TypedDict, cast

from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.rewrite import QueryRewriter
from app.agent.verify import unsupported_figures
from app.qa.baseline import (
    NO_REPORTS_ANSWER,
    AnswerGenerationError,
    AnswerGenerator,
    DraftAnswer,
    FinalAnswer,
    build_response,
)
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.retriever import Retriever
from app.retrieval.types import RetrievedChunk
from app.schemas.ask import AgentStep


@dataclass(frozen=True)
class AgentContext:
    session: AsyncSession
    top_k: int


class AgentState(TypedDict):
    question: str
    queries: list[str]
    tried: Annotated[list[str], operator.add]
    rewrites: int
    sources: list[RetrievedChunk]
    draft: DraftAnswer | None
    unverified: list[str]
    steps: Annotated[list[AgentStep], operator.add]


Agent = CompiledStateGraph[AgentState, AgentContext, AgentState, AgentState]


def build_agent(
    retriever: Retriever, generator: AnswerGenerator, rewriter: QueryRewriter, max_rewrites: int
) -> Agent:
    async def retrieve(state: AgentState, runtime: Runtime[AgentContext]) -> dict[str, Any]:
        context = runtime.context
        rankings = [
            await retriever.retrieve(context.session, query, context.top_k)
            for query in state["queries"]
        ]
        sources = reciprocal_rank_fusion(rankings)[: context.top_k]
        detail = f"Found {len(sources)} sources for: {'; '.join(state['queries'])}"
        return {
            "sources": sources,
            "tried": state["queries"],
            "steps": [AgentStep(step="retrieve", detail=detail)],
        }

    async def answer(state: AgentState) -> dict[str, Any]:
        if not state["sources"]:
            draft = DraftAnswer(answer=NO_REPORTS_ANSWER, citations=[], found=False)
        else:
            draft = await generator.generate(state["question"], state["sources"])
        detail = (
            "Answered from the sources." if draft.found else "The sources did not hold the answer."
        )
        return {"draft": draft, "steps": [AgentStep(step="answer", detail=detail)]}

    def after_answer(state: AgentState) -> Literal["rewrite", "verify"]:
        draft = state["draft"]
        answered = draft is not None and draft.found
        if answered or not state["sources"] or state["rewrites"] >= max_rewrites:
            return "verify"
        return "rewrite"

    async def rewrite(state: AgentState) -> dict[str, Any]:
        queries = await rewriter.rewrite(state["question"], state["tried"])
        return {
            "queries": queries,
            "rewrites": state["rewrites"] + 1,
            "steps": [AgentStep(step="rewrite", detail=f"New searches: {'; '.join(queries)}")],
        }

    async def verify(state: AgentState) -> dict[str, Any]:
        draft, sources = state["draft"], state["sources"]
        if draft is None or not draft.found:
            return {"unverified": []}
        cited = [sources[n - 1] for n in draft.citations if 1 <= n <= len(sources)]
        unverified = unsupported_figures(draft.answer, state["question"], cited)
        detail = (
            f"Not found in the cited sources: {', '.join(unverified)}"
            if unverified
            else "Every figure in the answer appears in a cited source."
        )
        return {"unverified": unverified, "steps": [AgentStep(step="verify", detail=detail)]}

    def after_verify(state: AgentState) -> Literal["rewrite", "__end__"]:
        if state["unverified"] and state["rewrites"] < max_rewrites:
            return "rewrite"
        return "__end__"

    graph = StateGraph(AgentState, context_schema=AgentContext)
    graph.add_node("retrieve", retrieve)
    graph.add_node("answer", answer)
    graph.add_node("rewrite", rewrite)
    graph.add_node("verify", verify)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "answer")
    graph.add_conditional_edges("answer", after_answer)
    graph.add_edge("rewrite", "retrieve")
    graph.add_conditional_edges("verify", after_verify)
    return graph.compile()


class AgentPipeline:
    def __init__(self, agent: Agent) -> None:
        self._agent = agent

    async def stream(
        self, session: AsyncSession, question: str, top_k: int
    ) -> AsyncIterator[AgentStep | FinalAnswer]:
        state: AgentState = {
            "question": question,
            "queries": [question],
            "tried": [],
            "rewrites": 0,
            "sources": [],
            "draft": None,
            "unverified": [],
            "steps": [],
        }
        # "updates" carries what each node just did, so its steps can be sent
        # on at once; "values" carries the whole state, which the answer needs.
        async for mode, chunk in self._agent.astream(
            state, context=AgentContext(session, top_k), stream_mode=["updates", "values"]
        ):
            if mode == "values":
                state = cast(AgentState, chunk)
                continue
            for update in cast(dict[str, dict[str, Any]], chunk).values():
                for step in update.get("steps", []):
                    yield step

        draft, sources = state["draft"], state["sources"]
        if draft is None:
            raise AnswerGenerationError("The agent ended without an answer.")
        response = build_response(draft, sources)
        response.steps = state["steps"]
        if draft.found:
            response.verified = not state["unverified"]
            response.unverified_figures = state["unverified"]
        yield FinalAnswer(response, sources)
