from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    data_dir: Path = Field(default=Path("./data"), alias="DATA_DIR")

    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_chat_model: str = Field(default="openai/gpt-4o-mini", alias="OPENROUTER_CHAT_MODEL")
    openrouter_embedding_model: str = Field(
        default="text-embedding-3-small", alias="OPENROUTER_EMBEDDING_MODEL"
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL"
    )

    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_username: str = Field(default="neo4j", alias="NEO4J_USERNAME")
    neo4j_password: str = Field(default="graph-rag-dev", alias="NEO4J_PASSWORD")

    semantic_scholar_base_url: str = Field(
        default="https://api.semanticscholar.org/graph/v1",
        alias="SEMANTIC_SCHOLAR_BASE_URL",
    )
    arxiv_base_url: str = Field(
        default="https://export.arxiv.org/api/query", alias="ARXIV_BASE_URL"
    )

    corpus_topic: str = Field(default="agent tool-call reliability", alias="CORPUS_TOPIC")
    corpus_start_date: str = Field(default="2025-01-01", alias="CORPUS_START_DATE")
    corpus_end_date: str = Field(default="2026-03-22", alias="CORPUS_END_DATE")
    corpus_target_papers: int = Field(default=100, alias="CORPUS_TARGET_PAPERS")
    corpus_mode: str = Field(default="hybrid", alias="CORPUS_MODE")
    benchmark_manifest_path: Path = Field(
        default=Path("./data/benchmark/paper_seeds.json"),
        alias="BENCHMARK_MANIFEST_PATH",
    )
    benchmark_questions_path: Path = Field(
        default=Path("./data/benchmark/gold_questions.json"),
        alias="BENCHMARK_QUESTIONS_PATH",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def index_dir(self) -> Path:
        return self.data_dir / "index"

    @property
    def benchmark_dir(self) -> Path:
        return self.data_dir / "benchmark"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
