from __future__ import annotations

import logging

from fastapi import FastAPI

from app.adapters.arxiv import ArxivAdapter
from app.adapters.semantic_scholar import SemanticScholarAdapter
from app.api.routes import build_router
from app.core.config import get_settings
from app.repositories.file_store import FileStore
from app.services.agent_client import AgentClientService
from app.services.benchmark_assets import BenchmarkAssetsService
from app.services.briefings import BriefingService
from app.services.extraction import ExtractionService
from app.services.graph_query import GraphQueryService
from app.services.ingestion import IngestionService
from app.services.neo4j_graph import Neo4jGraphStore
from app.services.openrouter import OpenRouterClient
from app.services.pipeline import PipelineService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# ── Storage ───────────────────────────────────────────────────────────
raw_store = FileStore(settings.raw_dir)
processed_store = FileStore(settings.processed_dir)

# ── Adapters ──────────────────────────────────────────────────────────
semantic_scholar = SemanticScholarAdapter(settings.semantic_scholar_base_url)
arxiv = ArxivAdapter(settings.arxiv_base_url)

# ── LLM Client ────────────────────────────────────────────────────────
llm_client: OpenRouterClient | None = None
if settings.openrouter_api_key:
    llm_client = OpenRouterClient(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        chat_model=settings.openrouter_chat_model,
        embedding_model=settings.openrouter_embedding_model,
    )
    logger.info("OpenRouter client initialized with model=%s", settings.openrouter_chat_model)
else:
    logger.warning("No OPENROUTER_API_KEY set — extraction and retrieval will be limited")

# ── Graph Store ───────────────────────────────────────────────────────
graph_store: Neo4jGraphStore | None = None
try:
    graph_store = Neo4jGraphStore(
        settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password
    )
    logger.info("Neo4j connection initialized at %s", settings.neo4j_uri)
except Exception as exc:
    logger.warning("Neo4j connection failed: %s — graph features disabled", exc)

# ── Services ──────────────────────────────────────────────────────────
ingestion_service = IngestionService(
    semantic_scholar,
    arxiv,
    raw_store,
    benchmark_manifest_path=settings.benchmark_manifest_path,
    corpus_mode=settings.corpus_mode,
    default_topic=settings.corpus_topic,
)
extraction_service = ExtractionService(llm_client=llm_client)
graph_query_service = GraphQueryService(graph_store=graph_store)
agent_client_service = AgentClientService(settings=settings, llm_client=llm_client)
briefing_service = BriefingService(agent_client_service=agent_client_service)
benchmark_assets_service = BenchmarkAssetsService(
    manifest_path=settings.benchmark_manifest_path,
    questions_path=settings.benchmark_questions_path,
)
pipeline_service = PipelineService(
    ingestion_service=ingestion_service,
    extraction_service=extraction_service,
    graph_store=graph_store,
    processed_store=processed_store,
    llm_client=llm_client,
)

# ── FastAPI App ───────────────────────────────────────────────────────
app = FastAPI(
    title="AI Research Intelligence Copilot",
    version="0.1.0",
    description=(
        "Research intelligence tool for agent tool-call reliability using GraphRAG-style retrieval."
    ),
)

app.include_router(
    build_router(
        pipeline_service=pipeline_service,
        graph_query_service=graph_query_service,
        agent_client_service=agent_client_service,
        briefing_service=briefing_service,
        benchmark_assets_service=benchmark_assets_service,
        graph_store=graph_store,
        corpus_topic=settings.corpus_topic,
        corpus_start_date=settings.corpus_start_date,
        corpus_end_date=settings.corpus_end_date,
        corpus_target_papers=settings.corpus_target_papers,
    )
)
