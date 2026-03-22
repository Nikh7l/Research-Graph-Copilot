from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from app.models.schemas import Claim, IngestionResult, Method, Paper
from app.repositories.file_store import FileStore
from app.services.extraction import ExtractionService
from app.services.ingestion import IngestionService
from app.services.neo4j_graph import Neo4jGraphStore
from app.services.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


class PipelineService:
    """Orchestrates the full ingest → extract → embed → load pipeline.

    Saves extraction results incrementally to disk so progress
    survives server restarts.
    """

    def __init__(
        self,
        ingestion_service: IngestionService,
        extraction_service: ExtractionService,
        graph_store: Neo4jGraphStore | None,
        processed_store: FileStore,
        llm_client: OpenRouterClient | None = None,
    ) -> None:
        self.ingestion_service = ingestion_service
        self.extraction_service = extraction_service
        self.graph_store = graph_store
        self.processed_store = processed_store
        self.llm_client = llm_client

    async def ingest_and_index(
        self,
        topic: str,
        start_date: str,
        end_date: str,
        target_papers: int,
        corpus_mode: str | None = None,
    ) -> IngestionResult:
        """Run the full pipeline with incremental checkpointing."""
        # 1. Ingest papers from APIs
        logger.info("Step 1/5: Ingesting papers")
        papers, result = await self.ingestion_service.ingest(
            topic,
            start_date,
            end_date,
            target_papers,
            corpus_mode=corpus_mode,
        )

        # 2. Extract methods and claims, saving incrementally
        logger.info(
            "Step 2/5: Extracting methods and claims from %d papers",
            len(papers),
        )
        methods, claims = await self._extract_with_checkpoints(papers, result.run_id)
        logger.info(
            "Extraction done: %d succeeded, %d failed, %d methods, %d claims",
            self.extraction_service.successes,
            self.extraction_service.failures,
            len(methods),
            len(claims),
        )

        # 3. Generate embeddings
        logger.info("Step 3/5: Generating embeddings")
        if self.llm_client:
            papers = await self._embed_papers(papers)
            methods = await self._embed_methods(methods)
            claims = await self._embed_claims(claims)

        # 4. Persist final processed data
        logger.info("Step 4/5: Saving processed data")
        self._save_processed(papers, methods, claims, result.run_id)

        # 5. Load into Neo4j
        logger.info("Step 5/5: Loading graph into Neo4j")
        if self.graph_store:
            self._load_graph(papers, methods, claims, topic)

        result.extracted_methods = len(methods)
        result.extracted_claims = len(claims)
        logger.info(
            "Pipeline complete: %d papers, %d methods, %d claims",
            len(papers),
            len(methods),
            len(claims),
        )
        return result

    async def _extract_with_checkpoints(
        self,
        papers: list[Paper],
        run_id: str,
    ) -> tuple[list[Method], list[Claim]]:
        """Extract with incremental saves every 10 papers.

        If a previous checkpoint exists, reload it and skip
        already-extracted papers.
        """
        checkpoint_path = (
            Path(self.processed_store.root) / "runs" / run_id / "extraction_checkpoint.json"
        )

        # Try to resume from checkpoint
        methods: list[Method] = []
        claims: list[Claim] = []
        start_idx = 0

        if checkpoint_path.exists():
            try:
                with open(checkpoint_path) as f:
                    checkpoint = json.load(f)
                start_idx = checkpoint.get("completed", 0)
                methods = [Method(**m) for m in checkpoint.get("methods", [])]
                claims = [Claim(**c) for c in checkpoint.get("claims", [])]
                logger.info(
                    "  Resuming from checkpoint: %d papers already done (%d methods, %d claims)",
                    start_idx,
                    len(methods),
                    len(claims),
                )
            except Exception:
                logger.warning("  Could not load checkpoint, starting fresh")
                start_idx = 0

        for i in range(start_idx, len(papers)):
            paper = papers[i]
            title_short = (paper.title[:60] + "...") if len(paper.title) > 60 else paper.title
            logger.info(
                '  [%d/%d] Extracting: "%s"',
                i + 1,
                len(papers),
                title_short,
            )
            paper_methods, paper_claims = await self.extraction_service.extract(paper)
            methods.extend(paper_methods)
            claims.extend(paper_claims)

            logger.info(
                "  [%d/%d] → %d methods, %d claims",
                i + 1,
                len(papers),
                len(paper_methods),
                len(paper_claims),
            )

            # Checkpoint + pause every 10 papers
            if (i + 1) % 10 == 0:
                self._save_checkpoint(checkpoint_path, i + 1, methods, claims)
                if i + 1 < len(papers):
                    logger.info(
                        "  --- Checkpoint saved (%d/%d done, %d methods, %d claims) ---",
                        i + 1,
                        len(papers),
                        len(methods),
                        len(claims),
                    )
                    await asyncio.sleep(3)

        # Final checkpoint + cleanup
        self._save_checkpoint(checkpoint_path, len(papers), methods, claims)
        return methods, claims

    def _save_checkpoint(
        self,
        path: Path,
        completed: int,
        methods: list[Method],
        claims: list[Claim],
    ) -> None:
        """Save extraction progress to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "completed": completed,
            "methods": [m.model_dump() for m in methods],
            "claims": [c.model_dump() for c in claims],
        }
        with open(path, "w") as f:
            json.dump(data, f)

    def _save_processed(
        self,
        papers: list[Paper],
        methods: list[Method],
        claims: list[Claim],
        run_id: str,
    ) -> None:
        """Save final processed data (without embeddings)."""
        self.processed_store.write_json(
            "papers/latest.json",
            [p.model_dump(exclude={"embedding"}) for p in papers],
        )
        self.processed_store.write_json(
            "methods/latest.json",
            [m.model_dump(exclude={"embedding"}) for m in methods],
        )
        self.processed_store.write_json(
            "claims/latest.json",
            [c.model_dump(exclude={"embedding"}) for c in claims],
        )
        self.processed_store.write_json(
            f"runs/{run_id}/papers.json",
            [p.model_dump(exclude={"embedding"}) for p in papers],
        )
        self.processed_store.write_json(
            f"runs/{run_id}/methods.json",
            [m.model_dump(exclude={"embedding"}) for m in methods],
        )
        self.processed_store.write_json(
            f"runs/{run_id}/claims.json",
            [c.model_dump(exclude={"embedding"}) for c in claims],
        )

    async def _embed_papers(self, papers: list[Paper]) -> list[Paper]:
        """Generate embeddings for papers."""
        llm_client = self.llm_client
        if llm_client is None:
            return papers

        texts = []
        for paper in papers:
            text = paper.title
            if paper.abstract:
                text += f" {paper.abstract[:500]}"
            texts.append(text)

        if not texts:
            return papers

        embeddings = await llm_client.embed_batch(texts)
        for paper, embedding in zip(papers, embeddings, strict=True):
            paper.embedding = embedding

        logger.info("  Embedded %d papers", len(papers))
        return papers

    async def _embed_methods(self, methods: list[Method]) -> list[Method]:
        """Generate embeddings for methods."""
        llm_client = self.llm_client
        if llm_client is None:
            return methods

        texts = []
        for method in methods:
            text = method.canonical_name
            if method.description:
                text += f": {method.description}"
            texts.append(text)

        if not texts:
            return methods

        embeddings = await llm_client.embed_batch(texts)
        for method, embedding in zip(methods, embeddings, strict=True):
            method.embedding = embedding

        logger.info("  Embedded %d methods", len(methods))
        return methods

    async def _embed_claims(self, claims: list[Claim]) -> list[Claim]:
        """Generate embeddings for claims."""
        llm_client = self.llm_client
        if llm_client is None:
            return claims

        texts = [claim.statement for claim in claims]

        if not texts:
            return claims

        embeddings = await llm_client.embed_batch(texts)
        for claim, embedding in zip(claims, embeddings, strict=True):
            claim.embedding = embedding

        logger.info("  Embedded %d claims", len(claims))
        return claims

    def _load_graph(
        self,
        papers: list[Paper],
        methods: list[Method],
        claims: list[Claim],
        topic: str,
    ) -> None:
        """Load all data into Neo4j with relationships."""
        graph_store = self.graph_store
        if graph_store is None:
            return

        graph_store.ensure_schema()

        graph_store.upsert_topic(name=topic)
        graph_store.upsert_papers(papers)
        graph_store.upsert_methods(methods)
        graph_store.upsert_claims(claims)

        graph_store.create_authored_edges(papers)
        graph_store.create_proposes_edges(papers, methods)
        graph_store.create_supports_edges(claims)
        graph_store.create_about_edges(papers, topic)
        graph_store.create_citation_edges(papers)

        graph_store.ensure_vector_indexes()
        logger.info("Graph loaded with all nodes and relationships")
