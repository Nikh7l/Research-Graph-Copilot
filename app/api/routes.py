from __future__ import annotations

from fastapi import APIRouter

from app.models.schemas import (
    BriefingRequest,
    IngestionRequest,
    IngestionResult,
    QueryRequest,
    QueryResponse,
    TopicSummary,
)
from app.services.agent_client import AgentClientService
from app.services.benchmark_assets import BenchmarkAssetsService
from app.services.briefings import BriefingService
from app.services.graph_query import GraphQueryService
from app.services.neo4j_graph import Neo4jGraphStore
from app.services.pipeline import PipelineService


def build_router(
    pipeline_service: PipelineService,
    graph_query_service: GraphQueryService,
    agent_client_service: AgentClientService,
    briefing_service: BriefingService,
    benchmark_assets_service: BenchmarkAssetsService,
    graph_store: Neo4jGraphStore | None,
    corpus_topic: str,
    corpus_start_date: str,
    corpus_end_date: str,
    corpus_target_papers: int,
) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/api/ingest/run", response_model=IngestionResult)
    async def run_ingestion(payload: IngestionRequest) -> IngestionResult:
        result = await pipeline_service.ingest_and_index(
            topic=payload.topic or corpus_topic,
            start_date=payload.start_date or corpus_start_date,
            end_date=payload.end_date or corpus_end_date,
            target_papers=payload.target_papers or corpus_target_papers,
            corpus_mode=payload.corpus_mode,
        )
        return result

    @router.get("/api/topics/{topic}", response_model=TopicSummary)
    async def get_topic(topic: str) -> TopicSummary:
        return TopicSummary.model_validate(graph_query_service.get_topic_summary(topic))

    @router.post("/api/query", response_model=QueryResponse)
    async def query(payload: QueryRequest) -> QueryResponse:
        return await agent_client_service.answer(
            question=payload.question,
            start_date=payload.start_date,
            end_date=payload.end_date,
            search_mode=payload.search_mode,
        )

    @router.post("/api/briefings")
    async def create_briefing(payload: BriefingRequest) -> dict:
        briefing = await briefing_service.generate(payload)
        return briefing.model_dump()

    @router.get("/api/stats")
    async def get_stats() -> dict:
        if graph_store:
            return graph_store.get_stats()
        return {
            "papers": 0,
            "methods": 0,
            "claims": 0,
            "authors": 0,
        }

    @router.get("/api/graph")
    async def get_graph(limit: int = 50) -> dict:
        """Return graph data (nodes + edges) for visualization."""
        if not graph_store:
            return {"nodes": [], "edges": []}
        return graph_store.get_graph_data(limit=limit)

    @router.get("/api/evaluation/questions")
    async def get_gold_questions() -> list[dict]:
        return benchmark_assets_service.get_gold_questions()

    @router.get("/api/benchmark/papers")
    async def get_benchmark_manifest() -> list[dict]:
        return benchmark_assets_service.get_seed_manifest()

    return router
