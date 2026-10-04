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
| Retrieval  | Vector + keyword search, Reciprocal Rank Fusion    |
| Reranker   | MiniLM cross-encoder, run locally with fastembed   |
| PDF parsing| pdfplumber (text and tables)                       |
| Embeddings | BGE small, run locally with fastembed              |
| Evaluation | pytest and a hand-checked question set             |
| Frontend   | React, Vite, TypeScript                            |
| Tooling    | uv, Ruff, mypy, Docker Compose, GitHub Actions     |

## Roadmap

- [x] Repository skeleton
- [x] Backend runs: FastAPI health endpoint, PostgreSQL with pgvector in Docker
- [x] Ingest one report end to end
- [x] Plain question answering with page citations
- [x] Evaluation set and baseline accuracy score
- [x] Hybrid search and reranking
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
uv run alembic upgrade head        # creates the tables
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
uv run mypy app tests migrations
uv run pytest
```

The database tests run when PostgreSQL is up and are skipped when it is not.

## Ingest reports

Company websites block scripted downloads, so reports are downloaded by hand:

1. Download the annual report PDF from the company's investor page into
   `data/raw/`.
2. Add an entry for it to `data/reports.yaml`.
3. From `backend/`, run:

```bash
uv run python -m app.cli ingest
```

Each report is parsed page by page, split into text and table chunks,
embedded locally and stored with its page number. Running the command again
skips reports whose file has not changed.

## Ask a question

Put a Gemini API key in `backend/.env` as `GOOGLE_API_KEY`, start the API and
post a question:

```bash
curl -X POST localhost:8000/ask \
  -H 'content-type: application/json' \
  -d '{"question": "What dividend per share was recommended?"}'
```

The response holds the answer, with `[n]` markers, and a `citations` list
giving the report, page and excerpt behind each marker. Each question is one
retrieval and one model call.

## Evaluation

`backend/evals/questions.yaml` holds 35 questions about the Infosys 2025-26
report. Each answer was read off a specific page, and three questions have no
answer in the report. From `backend/`, run:

```bash
uv run python -m app.cli eval
```

Each question is scored three ways:

- **Correct**: the answer contains the accepted figure or text. For a question
  with no answer in the report, correct means the system said so and cited
  nothing.
- **Retrieved**: the accepted answer was somewhere in the sources shown to the
  model.
- **Supported**: the answer was correct and a source it cited contains the
  accepted answer.

### Baseline (4 October 2026)

Plain vector search over 8 sources, one call to `gemini-3.5-flash`, embeddings
from `BAAI/bge-small-en-v1.5`.

| Category             | Correct      | Retrieved    | Supported    |
| -------------------- | ------------ | ------------ | ------------ |
| Financial statements | 10/12 (83%)  | 10/12 (83%)  | 10/12 (83%)  |
| Highlights           | 11/12 (92%)  | 11/12 (92%)  | 11/12 (92%)  |
| People               | 4/8 (50%)    | 4/8 (50%)    | 4/8 (50%)    |
| Not in the report    | 3/3 (100%)   | n/a          | n/a          |
| **Overall**          | **28/35 (80%)** | 25/32 (78%) | 25/32 (78%) |

All seven misses were retrieval misses: the page holding the answer was not
among the 8 sources, and the model said the sources did not contain it rather
than guessing. Whenever the right page was retrieved, the answer was correct.
Retrieval is therefore the first thing to improve.

### Retrieval comparison (4 October 2026)

Same questions, model and 8 sources per question; only the retrieval changes.
Choose a mode with `--retrieval vector|hybrid|hybrid_rerank`.

| Retrieval                                   | Correct         | Retrieved   | Time per question |
| ------------------------------------------- | --------------- | ----------- | ----------------- |
| Vector search (baseline)                    | 28/35 (80%)     | 25/32 (78%) | 3.3 s             |
| Hybrid: vector + keyword, rank fusion       | 27/35 (77%)     | 24/32 (75%) | 3.6 s             |
| **Hybrid + reranker (default)**             | **32/35 (91%)** | 29/32 (91%) | 5.6 s             |

- Fusing keyword results in without a reranker made things slightly worse
  (two financial-statement questions lost, one people question gained). The
  cause has not been traced; keyword matches on words common to many pages
  are the likely one.
- Reranking the top 30 fused results recovered every people question
  (4/8 to 8/8) and cost about two seconds per question on a laptop CPU.
- The three remaining misses are candidate misses: the right chunk ranks
  below 30 in both searches, so the reranker never sees it. They are dense
  statement pages (balance sheet, cash flow, five-year summary) where a chunk
  is mostly figures. Query rewriting in the agent is the next attempt at them.

## Repository layout

```
backend/    Python API, agent, ingestion, retrieval, evaluation
frontend/   React web app
data/       list of report links (the PDFs themselves are not committed)
```

## Licence

MIT. See [LICENSE](LICENSE).
