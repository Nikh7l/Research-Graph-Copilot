import json

from app.models.schemas import (
    Author,
    Claim,
    EvidenceItem,
    Method,
    Paper,
    Provenance,
    QueryRequest,
    QueryResponse,
)


def _sample_provenance() -> Provenance:
    return Provenance(
        source_type="test",
        source_id="test-001",
        extracted_at="2026-01-01T00:00:00Z",
        extraction_method="api_metadata",
    )


def test_paper_model_creation() -> None:
    paper = Paper(
        paper_id="test-001",
        title="Test Paper",
        abstract="A test abstract.",
        authors=[
            Author(name="Alice", semantic_scholar_id="a1"),
            Author(name="Bob", affiliations=["MIT"]),
        ],
        provenance=_sample_provenance(),
    )
    assert paper.paper_id == "test-001"
    assert len(paper.authors) == 2
    assert paper.authors[0].name == "Alice"
    assert paper.authors[1].affiliations == ["MIT"]
    assert paper.embedding is None


def test_paper_with_embedding() -> None:
    paper = Paper(
        paper_id="test-002",
        title="Embedded Paper",
        provenance=_sample_provenance(),
        embedding=[0.1, 0.2, 0.3],
    )
    assert paper.embedding == [0.1, 0.2, 0.3]


def test_method_model() -> None:
    method = Method(
        name="Tool Calling",
        canonical_name="tool calling",
        category="core-mechanism",
        description="Direct invocation of external tools",
        provenance=_sample_provenance(),
    )
    assert method.canonical_name == "tool calling"
    assert method.category == "core-mechanism"


def test_claim_model() -> None:
    claim = Claim(
        claim_id="c001",
        statement="Structured outputs reduce errors by 40%",
        evidence_span="reduce errors by 40%",
        confidence="high",
        method_name="structured outputs",
        paper_id="test-001",
        provenance=_sample_provenance(),
    )
    assert claim.confidence == "high"
    assert claim.evidence_span == "reduce errors by 40%"


def test_query_request_defaults() -> None:
    req = QueryRequest(question="What methods exist?")
    assert req.search_mode == "auto"
    assert req.start_date is None


def test_query_response_serializable() -> None:
    resp = QueryResponse(
        answer="Test answer",
        search_mode="entity",
        evidence=[
            EvidenceItem(
                title="Paper A",
                paper_id="p1",
                citation="Paper A (2025)",
                score=0.95,
            )
        ],
        related_methods=["tool calling"],
    )
    data = json.loads(resp.model_dump_json())
    assert data["search_mode"] == "entity"
    assert data["evidence"][0]["score"] == 0.95


def test_provenance_confidence_string() -> None:
    prov = Provenance(
        source_type="openrouter",
        source_id="test",
        extracted_at="2026-01-01",
        extraction_method="llm_few_shot",
        confidence="medium",
    )
    assert prov.confidence == "medium"
