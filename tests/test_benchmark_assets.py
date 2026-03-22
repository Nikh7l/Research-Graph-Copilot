import json
from pathlib import Path

from app.services.benchmark_assets import BenchmarkAssetsService


def test_benchmark_assets_service_reads_manifest_and_questions(tmp_path: Path) -> None:
    manifest_path = tmp_path / "paper_seeds.json"
    questions_path = tmp_path / "gold_questions.json"
    manifest_path.write_text(json.dumps([{"semantic_scholar_id": "paper-1"}]), encoding="utf-8")
    questions_path.write_text(json.dumps([{"id": "q1", "question": "Test?"}]), encoding="utf-8")

    service = BenchmarkAssetsService(manifest_path=manifest_path, questions_path=questions_path)

    assert service.get_seed_manifest()[0]["semantic_scholar_id"] == "paper-1"
    assert service.get_gold_questions()[0]["id"] == "q1"
