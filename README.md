# Annual Report Analyst

Ask questions across the annual reports of Indian listed companies and get
answers with page-level citations, where every number is checked against its
source page.

> **Status:** early development. The roadmap below shows what is built so far.

## What it will do

- Answer questions that span many long reports, such as "compare TCS and
  Infosys attrition over the last three years".
- Pull figures out of tables, not only from running text.
- Cite the report and page behind every claim, and link to the original PDF.
- Report its own accuracy on a hand-checked set of questions.

It answers from the documents only. It does not give investment advice.

## How it works

1. **Ingestion** parses each PDF (text and tables), splits it into chunks,
   embeds them and stores them in PostgreSQL.
2. **Retrieval** combines keyword and vector search, merges the two result
   lists with Reciprocal Rank Fusion, then reranks.
3. **The agent** (LangGraph) routes the question, retrieves, grades the
   results, rewrites the query when they are weak, writes the answer and
   verifies each number against the source.
4. **The API** (FastAPI) streams the agent's progress and the final answer to
   the web app.

## Tech stack

| Layer      | Choice                                             |
| ---------- | -------------------------------------------------- |
| Language   | Python 3.12                                        |
| API        | FastAPI, Pydantic                                  |
| Agent      | LangGraph, LangChain                               |
| LLM        | Gemini (provider is a config setting)              |
| Database   | PostgreSQL with pgvector, SQLAlchemy, Alembic      |
| Retrieval  | Hybrid search, Reciprocal Rank Fusion, reranker    |
| PDF parsing| PyMuPDF, Docling                                   |
| Evaluation | pytest and a hand-checked question set             |
| Frontend   | React, Vite, TypeScript                            |
| Tooling    | uv, Ruff, mypy, Docker Compose, GitHub Actions     |

## Roadmap

- [x] Repository skeleton
- [x] Backend runs: FastAPI health endpoint, PostgreSQL with pgvector in Docker
- [ ] Ingest one report end to end
- [ ] Plain question answering with page citations
- [ ] Evaluation set and baseline accuracy score
- [ ] Hybrid search and reranking
- [ ] LangGraph agent with grading, rewriting and number verification
- [ ] Web app: chat, live progress and cited-page viewer
- [ ] 10–15 companies, model comparison, live demo

## Run locally

You need Docker and [uv](https://docs.astral.sh/uv/).

```bash
docker compose up -d db            # PostgreSQL with pgvector on port 5440
cd backend
cp .env.example .env
uv sync                            # installs Python 3.12 and the dependencies
uv run uvicorn app.main:app --reload
```

Then open <http://localhost:8000/docs> for the API docs, or check that the
API can reach the database:

```bash
curl localhost:8000/health/ready
```

Run the checks from `backend/`:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy app tests
uv run pytest
```

## Repository layout

```
backend/    Python API, agent, ingestion, retrieval, evaluation
frontend/   React web app
data/       list of report links (the PDFs themselves are not committed)
```

## Licence

MIT. See [LICENSE](LICENSE).
