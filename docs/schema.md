# Schema

## Node Types

- `Paper` — title, abstract, published_date, source_url, embedding
- `Author` — name, semantic_scholar_id
- `Organization` — name, country
- `Method` — name, category, description, embedding
- `Topic` — name, summary, embedding
- `Claim` — statement, evidence_span, confidence, embedding
- `Briefing` — title, content, created_at
- `SourceDocument` — raw_path, processed_path, source_type

## Relationship Types

- `AUTHORED` — (Author)-[:AUTHORED]->(Paper)
- `AFFILIATED_WITH` — (Author)-[:AFFILIATED_WITH]->(Organization)
- `CITES` — (Paper)-[:CITES]->(Paper)
- `PROPOSES` — (Paper)-[:PROPOSES]->(Method)
- `RELATES_TO` — (Method)-[:RELATES_TO]->(Method)
- `SUPPORTS` — (Paper)-[:SUPPORTS]->(Claim)
- `ABOUT` — (Paper)-[:ABOUT]->(Topic)
- `DESCRIBES` — (SourceDocument)-[:DESCRIBES]->(Paper)

## Indexes

### Vector Indexes (HNSW, cosine similarity, 1536 dimensions)

- `paper_embedding_index` on `Paper.embedding`
- `method_embedding_index` on `Method.embedding`
- `claim_embedding_index` on `Claim.embedding`

### Full-Text Indexes

- `paper_fulltext_index` on `Paper.title`, `Paper.abstract`

### Uniqueness Constraints

- `Paper.source_url`
- `Author.semantic_scholar_id`
- `Method.name`

## Provenance Fields

All extracted nodes carry:

- `source_url` — where the data originated
- `source_type` — `semantic_scholar` | `arxiv`
- `source_id` — external identifier
- `extracted_at` — ISO timestamp
- `extraction_method` — `api_metadata` | `llm_few_shot`
- `confidence` — `high` | `medium` | `low` (LLM extractions only)
- `text_span` — source text that supports the extraction (claims only)

## Notes

- Deterministic facts (from API metadata) and inferred facts (from LLM extraction) must remain separable via `extraction_method`.
- LLM-derived methods and claims are stored with explicit `extraction_method = llm_few_shot`.
- v1 stores no repository entities.
- Embeddings are generated via OpenRouter `text-embedding-3-small` (1536 dims) and stored as `List<Float>` node properties in Neo4j.
