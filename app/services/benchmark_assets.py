from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast


class BenchmarkAssetsService:
    def __init__(self, manifest_path: Path, questions_path: Path) -> None:
        self.manifest_path = manifest_path
        self.questions_path = questions_path

    def get_seed_manifest(self) -> list[dict[str, Any]]:
        if not self.manifest_path.exists():
            return []
        data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return cast(list[dict[str, Any]], data)

    def get_gold_questions(self) -> list[dict[str, Any]]:
        if not self.questions_path.exists():
            return []
        data = json.loads(self.questions_path.read_text(encoding="utf-8"))
        return cast(list[dict[str, Any]], data)
