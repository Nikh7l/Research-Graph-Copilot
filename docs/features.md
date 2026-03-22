# Features

## v1 Features

- Topic-scoped paper ingestion from Semantic Scholar and arXiv
- User-selectable topic, date range, paper budget, and corpus mode per ingestion run
- 100-paper curated default corpus limited by topic and date range
- Raw payload caching for reproducibility
- Run-scoped raw and processed artifacts for multiple topic runs
- Deterministic normalization for papers, authors, organizations, and methods
- OpenRouter-powered method and claim extraction (few-shot structured output)
- OpenRouter embeddings for hybrid retrieval
- Neo4j graph persistence with provenance fields
- Neo4j HNSW vector indexes on Paper, Method, and Claim nodes
- Full-text indexes for hybrid keyword + semantic search
- Custom hybrid retrieval: entity search, theme search, comparative search
- Evidence-backed question answering with citation provenance
- Streamlit UI with topic, paper, method, query, and graph views
- Custom MCP server with narrow domain tools
- Claude Desktop compatibility over stdio
- Query history and saved briefings
- CI/CD via GitHub Actions (lint, type-check, test)

## Phase 2 Features

- Curated GitHub repository ingestion
- Repo relevance heuristics
- Repo quality scoring
- Paper-to-repo linking
- Research-to-implementation dashboards

## Non-goals

- Full arXiv indexing
- Broad web crawling
- Arbitrary Cypher execution by the model
- Unsupported production-adoption claims
- Automatic repo discovery in v1
- Separate vector database (embeddings stay in Neo4j)
