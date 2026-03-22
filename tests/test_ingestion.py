from pathlib import Path

from app.services.ingestion import IngestionService


class _DummySemanticScholar:
    async def search_papers(
        self,
        query: str,
        start_year: int,
        end_year: int,
        limit: int,
    ) -> list[dict]:
        return []

    async def get_paper_details(self, paper_id: str) -> dict | None:
        return {"paperId": paper_id, "title": f"Seed {paper_id}"}


class _DummyArxiv:
    async def search(self, query: str, max_results: int) -> list[dict]:
        return []


class _DummyStore:
    def write_json(self, relative_path: str, payload: object) -> Path:
        return Path("/tmp") / relative_path


def test_custom_topic_auto_mode_falls_back_to_latest() -> None:
    service = IngestionService(
        semantic_scholar=_DummySemanticScholar(),
        arxiv=_DummyArxiv(),
        raw_store=_DummyStore(),
        corpus_mode="hybrid",
        default_topic="agent tool-call reliability",
    )

    assert service._resolve_corpus_mode("medical agent safety", "auto") == "latest"


def test_default_topic_auto_mode_preserves_default_corpus_mode() -> None:
    service = IngestionService(
        semantic_scholar=_DummySemanticScholar(),
        arxiv=_DummyArxiv(),
        raw_store=_DummyStore(),
        corpus_mode="hybrid",
        default_topic="agent tool-call reliability",
    )

    assert service._resolve_corpus_mode("agent tool-call reliability", "auto") == "hybrid"
