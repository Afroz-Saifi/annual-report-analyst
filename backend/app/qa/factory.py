from typing import Literal

from pydantic import SecretStr

from app.agent.graph import AgentPipeline, build_agent
from app.agent.rewrite import GeminiQueryRewriter
from app.core.config import Settings
from app.ingestion.embed import LocalEmbeddings
from app.qa.baseline import BaselinePipeline, GeminiAnswerGenerator, Pipeline
from app.retrieval.pages import PageExpandingRetriever
from app.retrieval.retriever import RetrievalMode, Retriever, build_retriever

PipelineName = Literal["baseline", "agent"]


def build_pipeline(
    settings: Settings,
    api_key: SecretStr,
    name: PipelineName,
    retrieval_mode: RetrievalMode,
    expand_pages: bool,
) -> Pipeline:
    retriever: Retriever = build_retriever(
        retrieval_mode, LocalEmbeddings(settings.embedding_model), settings.reranker_model
    )
    if expand_pages:
        retriever = PageExpandingRetriever(retriever)
    generator = GeminiAnswerGenerator(settings.llm_model, api_key)
    if name == "baseline":
        return BaselinePipeline(retriever, generator)
    rewriter = GeminiQueryRewriter(settings.llm_model, api_key)
    return AgentPipeline(build_agent(retriever, generator, rewriter, settings.max_rewrites))
