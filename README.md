# AI Research Intelligence Copilot

Portfolio-grade research intelligence tool focused on graph-backed research retrieval. The default corpus is agent tool-call reliability, but the ingestion pipeline now supports custom user-selected topics, date windows, and paper budgets. The app extracts methods and claims, persists the graph in Neo4j, exposes domain-safe MCP tools, and serves a Streamlit UI plus Claude Desktop compatibility.

The corpus supports two tracks:
- a curated benchmark slice for stable demos and gold evaluation
- a latest-paper slice for fresh ingestion

## Stack

- Python 3.12 + FastAPI
- OpenRouter for chat and embeddings
- Neo4j for graph storage + vector indexes
- Custom hybrid retrieval layer (entity, theme, comparative search) via `neo4j-graphrag`
- MCP server for safe tool access
- Streamlit frontend

## Local Setup

1. Copy `.env.example` to `.env` and provide `OPENROUTER_API_KEY`.
2. Start Neo4j:

```bash
docker compose up -d
```

3. Install backend deps:

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

4. Run the API:

```bash
uvicorn app.main:app --reload
```

5. Run the Streamlit UI:

```bash
streamlit run streamlit_app/app.py
```

## Repo Layout

- `docs/` planning, features, tasks, schema, evaluation
- `app/` backend services, adapters, API, MCP
- `streamlit_app/` Streamlit UI
- `tests/` focused unit tests
- `data/` local raw, processed, and index artifacts
- `.github/workflows/` CI pipeline

## v1 Scope

- 100 papers by default, configurable per ingestion run
- default topic is `agent tool-call reliability`, but the pipeline supports custom topics
- date range defaults to 2025-01-01 through 2026-03-22
- no GitHub or repo ingestion yet
- benchmark and hybrid modes are intended for the default topic
- custom topics automatically fall back to `latest` when benchmark seeds would be unrelated

## Key Questions

- What changed in agent tool-call reliability between 2025-01-01 and 2026-03-22?
- Which methods for reducing tool-call errors appear most often in recent papers?
- Which papers support structured tool outputs as a reliability technique?
- Generate a briefing on recent approaches to preventing tool-call failures.
- What changed in my chosen topic over a specific date range?
- Which papers and methods dominate a custom topic corpus?

## First Test Flow

1. Start Neo4j with Docker.
2. Add `OPENROUTER_API_KEY` to `.env`.
3. Start the API and call `POST /api/ingest/run` with your chosen topic.
4. Inspect `data/raw/runs/<run_id>` and `data/processed/runs/<run_id>`.
5. Use `GET /api/topics/agent-tool-call-reliability` and `POST /api/query`.
6. Connect Claude Desktop to the MCP server once the Python dependencies are installed.

Example ingestion request:

```bash
curl -X POST http://localhost:8000/api/ingest/run \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "structured tool outputs for LLM agents",
    "start_date": "2025-01-01",
    "end_date": "2026-03-22",
    "target_papers": 60,
    "corpus_mode": "latest"
  }'
```

The response now includes:
- `run_id`
- `corpus_mode`
- `benchmark_seeded_papers`
- `cached_files`

## Benchmark Assets

- `data/benchmark/paper_seeds.json` contains curated Semantic Scholar paper IDs for the stable benchmark slice.
- `data/benchmark/gold_questions.json` contains demo and evaluation questions with expected evidence targets.
- `GET /api/benchmark/papers` returns the benchmark manifest.
- `GET /api/evaluation/questions` returns the gold question set.

## Claude Desktop MCP

The backend exposes a custom MCP server with narrow tools. Use the stdio transport entrypoint in `app/services/mcp_server.py` once dependencies are installed and the graph has data.

## Topic-Selectable Ingestion

You can run the ingestion pipeline from either:
- the Streamlit `⚙️ Pipeline` page
- `POST /api/ingest/run`

Supported ingestion parameters:
- `topic`
- `start_date`
- `end_date`
- `target_papers`
- `corpus_mode`: `auto`, `latest`, `benchmark`, `hybrid`

Behavior notes:
- `auto` keeps the benchmark/hybrid workflow for the default topic and switches custom topics to `latest`
- `benchmark` and `hybrid` use the curated benchmark seed manifest
- each ingestion run writes raw and processed artifacts to a run-specific directory so multiple topics do not overwrite each other

## CI/CD

GitHub Actions runs on every push to `main` and on pull requests:
- **Lint**: `ruff check` + `ruff format --check`
- **Type-check**: `mypy app/`
- **Test**: `pytest tests/ -v`
- **Build**: `pip install -e ".[dev]"` verification
