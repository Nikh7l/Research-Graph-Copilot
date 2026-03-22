# Implementation Plan

## Summary

Build a local-first AI research intelligence copilot using OpenRouter, Neo4j, custom hybrid retrieval (graph + embeddings), and a custom MCP server. The default benchmark domain is agent tool-call reliability, but the ingestion pipeline supports custom user-selected topics, date windows, corpus modes, and paper budgets. The first working slice indexes 100 papers by default and answers date-bounded research questions with evidence.

## Technical Decisions

### Retrieval Approach

Custom hybrid retrieval built on `neo4j-graphrag`, **not** Microsoft GraphRAG or LightRAG as a library dependency. We borrow the local/global search concepts and implement them directly on Neo4j using:

- `VectorCypherRetriever` for entity search (vector similarity → graph traversal)
- Cypher-based theme search across date-bounded subgraphs
- Comparative search combining vector matches for multiple method terms

Embeddings are stored as Neo4j node properties with HNSW vector indexes. No separate vector database.

### Extraction Strategy

Few-shot structured extraction via `gpt-4o-mini` through OpenRouter. Each paper abstract is processed to extract methods, claims, and relationships into a JSON schema. Extraction is batched at 5 papers per minute to stay within rate limits.

### Cost Estimate

| Step | Est. Cost |
|---|---|
| Method + Claim extraction (100 papers) | ~$0.02 |
| Embeddings (~500 texts) | ~$0.01 |
| Query-time synthesis (~50 dev queries) | ~$0.02 |
| **Total estimated dev cost** | **$0.05 – $0.50** |

## Data Flow

```
Semantic Scholar / arXiv API
        ↓
   Raw JSON → data/raw/runs/<run_id>/
        ↓
   Normalization (dedup, alias mapping, org resolution)
        ↓
   OpenRouter extraction (methods + claims)
        ↓
   Processed JSON → data/processed/runs/<run_id>/
        ↓
   OpenRouter embeddings (batch embed)
        ↓
   Neo4j graph load (nodes + edges + vector indexes)
        ↓
   Retrieval layer (entity / theme / comparative)
        ↓
   API + MCP + Streamlit UI
```

## Phases

1. Documentation scaffold and schema definition
2. Source ingestion and caching
3. Normalization and extraction
4. Neo4j graph load
5. Retrieval and hybrid search layer
6. MCP server and FastAPI endpoints
7. Streamlit UI
8. CI/CD pipeline
9. Evaluation and demo polish

## Acceptance Criteria

- Ingest exactly 100 papers within the configured topic/date bounds.
- Allow users to choose a topic and corpus mode per ingestion run.
- Persist raw source payloads and processed entities locally.
- Preserve run-scoped artifacts so multiple topic runs do not overwrite each other.
- Load the canonical graph into Neo4j with embedding vector indexes.
- Return evidence-backed answers through API and MCP.
- Support the same core prompts in the Streamlit app and Claude Desktop.
- CI pipeline passes lint, type-check, and unit tests on every push.

## Risks

- Topic drift in source search results
- Method alias normalization creating duplicates
- Sparse or noisy claim extraction from abstracts alone
- Rate limits on Semantic Scholar free tier (100 req / 5 min)
- Neo4j vector index performance on small corpus (mitigated by corpus size)
