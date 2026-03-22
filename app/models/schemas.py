from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Provenance(BaseModel):
    source_url: str | None = None
    source_type: str
    source_id: str
    extracted_at: str
    extraction_method: str  # "api_metadata" | "llm_few_shot"
    confidence: str = "high"  # "high" | "medium" | "low"
    text_span: str | None = None


class Author(BaseModel):
    name: str
    semantic_scholar_id: str | None = None
    affiliations: list[str] = Field(default_factory=list)


class Paper(BaseModel):
    paper_id: str
    title: str
    abstract: str | None = None
    publication_date: str | None = None
    venue: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    semantic_scholar_id: str | None = None
    source_url: str | None = None
    authors: list[Author] = Field(default_factory=list)
    citation_ids: list[str] = Field(default_factory=list)
    provenance: Provenance
    embedding: list[float] | None = None


class Method(BaseModel):
    name: str
    canonical_name: str
    category: str | None = None  # "retry-based" | "verification-based" | "planning-based" | etc.
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)
    provenance: Provenance
    embedding: list[float] | None = None


class Claim(BaseModel):
    claim_id: str
    statement: str
    evidence_span: str | None = None
    confidence: str = "medium"  # "high" | "medium" | "low"
    method_name: str | None = None
    paper_id: str | None = None
    provenance: Provenance
    embedding: list[float] | None = None


class Topic(BaseModel):
    name: str
    description: str | None = None


class Briefing(BaseModel):
    briefing_id: str
    topic: str
    start_date: str
    end_date: str
    summary: str
    citations: list[str] = Field(default_factory=list)


class IngestionResult(BaseModel):
    topic: str
    start_date: str
    end_date: str
    requested_papers: int
    ingested_papers: int
    run_id: str = "latest"
    corpus_mode: str = "latest"
    benchmark_seeded_papers: int = 0
    extracted_methods: int = 0
    extracted_claims: int = 0
    cached_files: list[str] = Field(default_factory=list)


class IngestionRequest(BaseModel):
    topic: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    target_papers: int | None = None
    corpus_mode: str = "auto"  # "auto" | "latest" | "benchmark" | "hybrid"


class QueryRequest(BaseModel):
    question: str
    start_date: str | None = None
    end_date: str | None = None
    search_mode: str = "auto"  # "entity" | "theme" | "comparative" | "auto"


class EvidenceItem(BaseModel):
    title: str
    paper_id: str
    citation: str
    snippet: str | None = None
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    answer: str
    search_mode: str = "auto"
    evidence: list[EvidenceItem] = Field(default_factory=list)
    related_methods: list[str] = Field(default_factory=list)
    graph_paths: list[list[str]] = Field(default_factory=list)
    tool_trace: list[dict[str, Any]] = Field(default_factory=list)
    confidence_note: str | None = None


class BriefingRequest(BaseModel):
    topic: str
    start_date: str
    end_date: str
    max_sources: int = 12


class TopicSummary(BaseModel):
    topic: str
    methods: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    paper_count: int = 0
    date_range: str | None = None


class ExtractedMethod(BaseModel):
    name: str
    category: str | None = None
    description: str | None = None


class ExtractedClaim(BaseModel):
    statement: str
    method_name: str | None = None
    confidence: str = "medium"
    evidence_span: str | None = None


class ExtractionResult(BaseModel):
    """Structured output from LLM extraction of a single paper."""

    methods: list[ExtractedMethod] = Field(default_factory=list)
    claims: list[ExtractedClaim] = Field(default_factory=list)
