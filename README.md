# AI Research Intelligence Copilot

This project solves a simple problem: teams tracking fast-moving AI research do not just need paper search, they need a way to trace **papers, methods, claims, and topics** across a connected knowledge base and ask evidence-backed questions over that graph.

Standard keyword or vector search can find relevant abstracts. It is much weaker at questions like:
- Which papers support a method and what claims are connected to it?
- How are two methods related through shared topic structure?
- What graph path links a paper to a method or claim?

This app solves that by building a **Neo4j knowledge graph** from a research corpus, exposing deterministic retrieval and path tools through **MCP**, and letting an LLM client synthesize answers from those tool results.

## What The Project Does

- Ingests papers from **Semantic Scholar** and **arXiv**
- Extracts methods and claims with **OpenRouter**
- Stores papers, authors, methods, claims, topics, and edges in **Neo4j**
- Exposes deterministic graph tools through a custom **MCP server**
- Supports:
  - a custom **Streamlit** app
  - **Claude Desktop** via MCP stdio
- Provides a seeded benchmark corpus plus gold evaluation questions

## Problem

Research teams, AI engineers, and consultants need to answer questions that are relational, not just semantic:
- Compare two methods using linked evidence
- See which claims connect to a method
- Trace a path from a paper to a method
- Summarize a bounded topic over a date range

Without a graph layer, these become brittle prompt-engineering exercises over chunks of text.

## Solution

The system is split into two runtime layers:

- **MCP server**
  - deterministic graph and retrieval tools only
  - no runtime answer generation
- **LLM client**
  - uses OpenRouter for planning and answer synthesis
  - calls MCP tools to fetch structured evidence

This makes the architecture easy to explain:
- Neo4j is the graph system of record
- MCP is the tool boundary
- the LLM client is the reasoning layer

## Core Tools And Stack

- **Python / FastAPI**
- **Neo4j**
- **OpenRouter**
- **MCP**
- **Streamlit**
- **Semantic Scholar API**
- **arXiv API**

## Main Capabilities

- Topic-selectable ingestion
- Date-bounded corpus building
- Method and claim extraction
- Graph-backed retrieval
- MCP tool access for Claude Desktop
- Benchmark questions with expected papers, tools, and relationships
- Interactive graph viewer

## Current MCP Tools

- `search_papers`
- `get_topic_summary`
- `get_method_papers`
- `get_claims_for_method`
- `get_paper_neighborhood`
- `compare_methods_structured`
- `get_graph_paths`
- `get_relationship_counts`
- `get_corpus_stats`

## Local Setup

1. Copy `.env.example` to `.env`
2. Add your `OPENROUTER_API_KEY`
3. Start Neo4j:

```bash
docker compose up -d
```

4. Install dependencies:

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

5. Start the API:

```bash
uvicorn app.main:app --reload
```

6. Start the UI:

```bash
streamlit run streamlit_app/app.py
```

## Ingestion

You can ingest the default benchmark topic or any custom topic.

Example:

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

Supported fields:
- `topic`
- `start_date`
- `end_date`
- `target_papers`
- `corpus_mode`: `auto`, `latest`, `benchmark`, `hybrid`

Run artifacts are written to:
- `data/raw/runs/<run_id>`
- `data/processed/runs/<run_id>`

## Benchmark Assets

- `data/benchmark/paper_seeds.json`
- `data/benchmark/gold_questions.json`

API endpoints:
- `GET /api/benchmark/papers`
- `GET /api/evaluation/questions`

## Claude Desktop

Claude Desktop acts as the MCP client/host. This repo provides the MCP server.

Run the server entrypoint with:

```bash
python -m app.mcp_runner
```

Then point Claude Desktop at that command using stdio transport.

## Verification

Local checks used in this repo:

```bash
./.venv/bin/ruff check app tests streamlit_app
./.venv/bin/pytest tests -q
PYTHONPYCACHEPREFIX=.pycache-local python3 -m compileall app tests streamlit_app
```

## Status

This is a working prototype with:
- a functioning Neo4j graph
- a real MCP server
- a custom app client
- Claude Desktop interoperability

The strongest current use case is **evidence-backed research analysis over a graph of papers, methods, claims, and topics**.
