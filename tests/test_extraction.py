import json

from app.services.extraction import ExtractionService


def test_parse_json_response_valid() -> None:
    from app.models.schemas import Paper, Provenance

    service = ExtractionService(llm_client=None)
    paper = Paper(
        paper_id="test-001",
        title="Test Paper",
        abstract="We propose a retry mechanism that reduces errors by 30%.",
        provenance=Provenance(
            source_type="test",
            source_id="test-001",
            extracted_at="2026-01-01T00:00:00Z",
            extraction_method="api_metadata",
        ),
    )

    response = json.dumps(
        {
            "methods": [
                {
                    "name": "retry mechanism",
                    "category": "retry-based",
                    "description": "Retries on failure",
                }
            ],
            "claims": [
                {
                    "statement": "Retry reduces errors by 30%",
                    "method_name": "retry mechanism",
                    "confidence": "high",
                    "evidence_span": "reduces errors by 30%",
                }
            ],
        }
    )

    methods, claims = service._parse_json_response(paper, response)
    assert len(methods) == 1
    assert methods[0].canonical_name == "retry strategies"
    assert methods[0].category == "retry-based"
    assert len(claims) == 1
    assert claims[0].confidence == "high"
    assert claims[0].evidence_span == "reduces errors by 30%"


def test_parse_json_response_invalid_json() -> None:
    from app.models.schemas import Paper, Provenance

    service = ExtractionService(llm_client=None)
    paper = Paper(
        paper_id="test-002",
        title="Bad Paper",
        abstract="No useful data.",
        provenance=Provenance(
            source_type="test",
            source_id="test-002",
            extracted_at="2026-01-01T00:00:00Z",
            extraction_method="api_metadata",
        ),
    )

    methods, claims = service._parse_json_response(paper, "not valid json {{")
    assert methods == []
    assert claims == []


def test_parse_json_response_empty() -> None:
    from app.models.schemas import Paper, Provenance

    service = ExtractionService(llm_client=None)
    paper = Paper(
        paper_id="test-003",
        title="Empty Paper",
        abstract="Nothing here.",
        provenance=Provenance(
            source_type="test",
            source_id="test-003",
            extracted_at="2026-01-01T00:00:00Z",
            extraction_method="api_metadata",
        ),
    )

    methods, claims = service._parse_json_response(paper, '{"methods": [], "claims": []}')
    assert methods == []
    assert claims == []
