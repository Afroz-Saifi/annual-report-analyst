# Annual Report Analyst

Ask questions across the annual reports of Indian listed companies (currently
Infosys 2025-26 and 2024-25, and TCS 2025-26) and get
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
   lists with Reciprocal Rank Fusion, reranks, then hands the model the whole
   page each hit came from.
3. **The agent** (LangGraph) first works out which companies, and which fiscal
   years when two are named, the question is about, and searches each one's
   reports separately so a comparison gets sources from every side. It then
   retrieves and answers. If the model reports that
   the sources do not hold the answer, it rewrites the query and searches
   again. It then checks every figure in the answer against the cited pages,
   without a model call, and searches again if one is missing. A figure the
   answer worked out itself passes only when it is the sum, difference or
   percentage change of two figures the answer states and the pages contain.
4. **The API** (FastAPI) streams the agent's progress and the final answer to
   the web app as server-sent events.
5. **The web app** (React) shows each step as it happens, the answer with its
   sources, and the cited page of the PDF with the answer's figures
   highlighted.

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
- [x] LangGraph agent with query rewriting and number verification
- [x] Web app: chat, live progress and cited-page viewer
- [x] A second year's report, with search split by company and year
- [x] A second company (TCS) and cross-company questions
- [x] Model comparison
- [ ] More companies, live demo

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
skips reports whose file has not changed; `--force` re-ingests them anyway.

Some reports draw the ₹ sign with a font that extracts as a letter, such as
"H2,67,021 crore" in the TCS report. List those letters for that report under
`rupee_glyphs` in `data/reports.yaml`; they are replaced only before a figure
or in a unit label such as "(H crore)". A backtick drawn for ₹ is always
replaced.

## Run the web app

With the database and API running as above, start the frontend in a second
terminal:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The dev server forwards `/api` requests to the
API on port 8000. The page viewer reads the PDFs from `data/raw/`, so a report
must be downloaded there for its pages to show.

Frontend checks, from `frontend/`:

```bash
npm run typecheck && npm run lint && npm test && npm run build
```

## Ask a question

Put a Gemini API key in `backend/.env` as `GOOGLE_API_KEY`, start the API and
post a question:

```bash
curl -X POST localhost:8000/ask \
  -H 'content-type: application/json' \
  -d '{"question": "What dividend per share was recommended?"}'
```

`POST /ask/stream` takes the same body and sends a `step` event as each agent
step finishes, then one `answer` event. `POST /ask` waits and returns the
answer in one piece. The answer holds:

- `answer`, with `[n]` markers after each claim
- `citations`: the report, page and excerpt behind each marker
- `verified`: true when every figure in the answer appears on a cited page
- `unverified_figures`: any figures that do not
- `steps`: what the agent did (retrieve, answer, rewrite, verify)

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

| Retrieval                                   | Correct         | Retrieved   | Mean time per question |
| ------------------------------------------- | --------------- | ----------- | ---------------------- |
| Vector search (baseline)                    | 28/35 (80%)     | 25/32 (78%) | 3.2 s                  |
| Hybrid: vector + keyword, rank fusion       | 27/35 (77%)     | 24/32 (75%) | 3.5 s                  |
| **Hybrid + reranker (default)**             | **32/35 (91%)** | 29/32 (91%) | 4.5 s                  |

- Fusing keyword results in without a reranker made things slightly worse
  (two financial-statement questions lost, one people question gained). The
  cause has not been traced; keyword matches on words common to many pages
  are the likely one.
- Reranking the top 30 fused results recovered every people question
  (4/8 to 8/8) and cost about one extra second per question on a laptop CPU.
- The three remaining misses are candidate misses: the right chunk ranks
  below 30 in both searches, so the reranker never sees it. They are dense
  statement pages (balance sheet, cash flow, five-year summary) where a chunk
  is mostly figures. Query rewriting in the agent is the next attempt at them.

### Agent comparison (4 October 2026)

Same questions and model, hybrid retrieval with the reranker throughout.
Choose with `--pipeline baseline|agent` and `--expand-pages/--no-expand-pages`.

| Setup                                   | Correct          | Figures verified | Median time | Mean time |
| --------------------------------------- | ---------------- | ---------------- | ----------- | --------- |
| Plain pipeline, chunk sources           | 32/35 (91%)      | not checked      | 4.2 s       | 4.7 s     |
| Agent, chunk sources                    | 33/35 (94%)      | 30 of 31         | 4.6 s       | 8.9 s     |
| Plain pipeline, whole-page sources      | 34/35 (97%)      | not checked      | 4.4 s       | 4.7 s     |
| **Agent, whole-page sources (default)** | **35/35 (100%)** | 32 of 32         | 4.9 s       | 8.0 s     |

- Whole pages mattered most. A financial statement spans several chunks, and
  the chunk that matches the question is often not the one holding the
  figure. Showing the model the full page of each hit fixed two of the three
  remaining misses on its own.
- Query rewriting recovered the last one: the cash flow statement was only
  found after the agent searched for the statement by name.
- With chunk sources, the figure check flagged the one answer in which the
  model had worked a figure out for itself instead of reading it from a
  source. It raised no flag on any correct answer.
- Rewrites are costly when they happen: a question with no answer in the
  report takes two rewrites and about 25 to 30 seconds before the agent gives
  up. Typical questions need none.

**How far to trust these numbers.** This is 35 questions on one report, and
the same questions were used to decide what to build next, so the score is
optimistic. The held-out set below is the fairer measure.

### Held-out questions (4 October 2026)

`backend/evals/heldout.yaml` holds 19 questions written after the system was
built, from pages the first set did not use (standalone statements, the
liquidity section, the CSR annexure, directors' remuneration). They are never
used to decide what to change. Run them with
`uv run python -m app.cli eval --dataset evals/heldout.yaml`.

| Run                                  | Correct          | Figures verified | Rewrites needed          |
| ------------------------------------ | ---------------- | ---------------- | ------------------------ |
| Agent, default settings, single run  | **19/19 (100%)** | 17 of 17         | Only on the 2 with no answer |

What this does and does not show:

- It shows the system finds and reads single facts across this report
  reliably, including from table-heavy pages, and declines to answer what is
  not there.
- Every question asks for one fact from one page.
- It is still one company. Other reports are laid out differently and may
  parse worse.

**After adding the 2024-25 report.** With two years loaded, four questions
that named no year were given one before the set was run again. The rerun
scored **17/19**. Both misses are CSR questions where the search returned the
CSR pages of the wrong year's report, which repeats the same section:

- One answer declined, correctly, to give a 2025 figure as 2026's.
- The other added two other figures to stand in for the missing total
  (₹558.04 + ₹19.00 = ₹577.04 crore, against 577.36 on the page), and the
  figure check accepted it as a worked figure. The answer prompt now forbids
  combining figures to stand in for one the sources do not state.

That prompt change was prompted by this run, so this set is no longer fully
held out. A fresh set comes with the next company.

### With a second company: TCS (4 October 2026)

Adding the TCS 2025-26 report needed two parser changes: a wider character
spacing tolerance, because TCS's fonts space the digits of a figure so widely
that "6,17,437" was extracted as "6,17 ,437", and the per-report ₹ letters
above. Neither changed the text extracted from the Infosys reports.

Questions that named no company were prefixed "For Infosys," before any run
with TCS loaded.

| Question set                                   | Questions | Correct           |
| ---------------------------------------------- | --------- | ----------------- |
| **Second held-out set, single run**            | 15        | **15/15 (100%)**  |
| Infosys versus TCS (`cross_company.yaml`)      | 9         | 7/9 (78%)         |
| Infosys across years (`comparison.yaml`)       | 11        | 9/11 (82%)        |
| Original questions (`questions.yaml`)          | 35        | 35/35 (100%)      |
| First held-out set (`heldout.yaml`)            | 19        | 18/19 (95%)       |

The second held-out set (`backend/evals/heldout_v2.yaml`) was written after
TCS was added and before the system was run on it, and has not been used to
change anything. It covers single facts from the TCS report, single facts from
pages of the Infosys 2024-25 report no other set uses, three Infosys-versus-TCS
comparisons and two questions the reports cannot answer. Like the first set,
every answerable question asks for figures printed on a page.

The two cross-company misses picked a different line item from the one asked
for, both on the Infosys side:

- Asked for consolidated profit for the year (₹29,474 crore), it gave net
  profit attributable to owners from the IFRS highlights page (₹29,440 crore),
  labelled as such.
- Asked for consolidated employee benefit expenses (₹95,094 crore), it gave
  ₹96,383 crore from a note that adds the Labour Codes exceptional item.

Known gaps in the TCS text: 64 chunks, including the CSR annexure, come from
pages whose font pdfplumber cannot decode at all, and the attrition figure sits
inside a graphic whose text is scrambled. No question relies on them.

### Model comparison (5 October 2026)

The same 55 questions (`questions.yaml`, `comparison.yaml` and
`cross_company.yaml`) run once on each model, with the agent, hybrid retrieval
with the reranker, and whole-page sources throughout. Choosing a model is a
design decision, so the held-out sets were left out. Run one model with
`uv run python -m app.cli eval --model <name> --dataset <file> --dataset <file>`.

| Model                    | Correct     | Median time | Input tokens | Output tokens | Cost for 55 questions |
| ------------------------ | ----------- | ----------- | ------------ | ------------- | --------------------- |
| `gemini-3.5-flash-lite`  | 51/55 (93%) | 3.2 s       | 574,920      | 5,477         | $0.19                 |
| `gemini-3.5-flash`       | 50/55 (91%) | 6.5 s       | 577,477      | 60,016        | $1.41                 |
| `gemini-3.8-flash`       | 52/55 (95%) | 4.7 s       | 576,528      | 38,885        | $0.58 ($1.16 from 2027) |
| `gemini-3.1-pro-preview` | 48/55 (87%) | 7.6 s       | 603,454      | 59,361        | $1.92                 |

Cost uses Google's paid-tier list prices per million tokens as of 5 October
2026: Flash-Lite $0.30 in and $2.50 out; 3.5 Flash $1.50 and $9.00; 3.8 Flash
$0.75 and $3.75 until 31 December 2026, then $1.50 and $7.50; 3.1 Pro Preview
$2.00 and $12.00. Output includes the models' reasoning tokens, which are
billed as output. Embeddings and the reranker run locally and cost nothing.

- The three Flash models are within run-to-run noise of each other: the same
  model and questions have scored one question apart on different runs. The
  ranking among them should not be read from one run each.
- Flash-Lite spends almost no output tokens because it does not reason before
  answering, which makes it about 7 times cheaper than 3.5 Flash and the
  fastest, at no measured loss on these questions.
- Pro scored lowest. On year-on-year questions it declined more often, saying
  one year's figure was not stated where the other models read it from pages
  whose text is partly scrambled, such as infographics.
- Every model got all 35 single-fact questions right. The differences are all
  in comparisons and calculations, which is also where retrieval misses
  concentrate.

### Comparison questions (4 October 2026)

`backend/evals/comparison.yaml` holds 11 questions about Infosys across fiscal
years, most needing one figure from each of the 2025-26 and 2024-25 reports,
and three needing a difference no page states. It is used to improve the
system, so it is not held out.

| Category                          | Correct     |
| --------------------------------- | ----------- |
| Two years, one figure from each report | 6/7    |
| Two years, both in one report     | 1/1         |
| A difference to work out          | 2/3         |
| **Overall**                       | **9/11 (82%)** |

- The first run scored 8/11. Between the two runs the search was split by
  year, the figure check learned to accept worked figures, and two ambiguous
  questions were tightened, so the gain is not down to one change alone.
- Both misses are retrieval misses: the page for one of the two years was not
  among the sources, and the agent said so rather than guessing.
- "Retrieved" and "supported" are not meaningful for the difference questions,
  since the answer is a number no page prints.

The original 35 questions still score 35/35 with both reports loaded.

## Repository layout

```
backend/    Python API, agent, ingestion, retrieval, evaluation
frontend/   React web app
data/       list of report links (the PDFs themselves are not committed)
```

## Licence

MIT. See [LICENSE](LICENSE).
