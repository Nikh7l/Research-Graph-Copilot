from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from hashlib import sha1
from pathlib import Path

from app.adapters.arxiv import ArxivAdapter
from app.adapters.semantic_scholar import SemanticScholarAdapter
from app.models.schemas import Author, IngestionResult, Paper, Provenance
from app.repositories.file_store import FileStore
from app.services.normalization import dedupe_papers_by_title, normalize_author_name

logger = logging.getLogger(__name__)


class IngestionService:
    """Ingests papers from Semantic Scholar and arXiv, deduplicates, and caches raw data."""

    def __init__(
        self,
        semantic_scholar: SemanticScholarAdapter,
        arxiv: ArxivAdapter,
        raw_store: FileStore,
        benchmark_manifest_path: Path | None = None,
        corpus_mode: str = "hybrid",
        default_topic: str = "agent tool-call reliability",
    ) -> None:
        self.semantic_scholar = semantic_scholar
        self.arxiv = arxiv
        self.raw_store = raw_store
        self.benchmark_manifest_path = benchmark_manifest_path
        self.corpus_mode = corpus_mode
        self.default_topic = default_topic

    async def ingest(
        self,
        topic: str,
        start_date: str,
        end_date: str,
        target_papers: int,
        corpus_mode: str | None = None,
    ) -> tuple[list[Paper], IngestionResult]:
        """Fetch papers from both sources, deduplicate, normalize, and cache."""
        start_year = int(start_date[:4])
        end_year = int(end_date[:4])
        effective_corpus_mode = self._resolve_corpus_mode(topic, corpus_mode)
        topic_slug = self._slugify_topic(topic)
        run_timestamp = datetime.now(UTC)
        run_id = f"{run_timestamp.strftime('%Y%m%dT%H%M%SZ')}-{topic_slug}"

        logger.info(
            "Ingesting papers for topic=%s, dates=%s to %s, target=%d, mode=%s",
            topic,
            start_date,
            end_date,
            target_papers,
            effective_corpus_mode,
        )

        benchmark_results = await self._fetch_benchmark_seed_papers(effective_corpus_mode)
        remaining = max(target_papers - len(benchmark_results), 0)

        ss_results: list[dict] = []
        arxiv_results: list[dict] = []
        if effective_corpus_mode in {"latest", "hybrid"} and remaining > 0:
            ss_results = await self.semantic_scholar.search_papers(
                query=topic,
                start_year=start_year,
                end_year=end_year,
                limit=remaining,
            )
            arxiv_results = await self.arxiv.search(
                query=topic,
                max_results=remaining,
            )

        timestamp = run_timestamp.isoformat()

        # Cache raw responses
        cached_files = []
        if benchmark_results:
            cached_files.append(
                str(
                    self.raw_store.write_json(
                        f"runs/{run_id}/semantic_scholar/benchmark.json",
                        benchmark_results,
                    )
                )
            )
        if ss_results:
            cached_files.append(
                str(
                    self.raw_store.write_json(
                        f"runs/{run_id}/semantic_scholar/latest.json",
                        ss_results,
                    )
                )
            )
        if arxiv_results:
            cached_files.append(
                str(
                    self.raw_store.write_json(
                        f"runs/{run_id}/arxiv/latest.json",
                        arxiv_results,
                    )
                )
            )
        cached_files.append(
            str(
                self.raw_store.write_json(
                    f"runs/{run_id}/metadata.json",
                    {
                        "run_id": run_id,
                        "topic": topic,
                        "topic_slug": topic_slug,
                        "start_date": start_date,
                        "end_date": end_date,
                        "target_papers": target_papers,
                        "corpus_mode": effective_corpus_mode,
                        "benchmark_seeded_papers": len(benchmark_results),
                    },
                )
            )
        )

        # Convert Semantic Scholar results
        papers: list[Paper] = []
        for item in benchmark_results:
            paper = self._convert_semantic_scholar(item, timestamp)
            if paper:
                papers.append(paper)

        for item in ss_results:
            paper = self._convert_semantic_scholar(item, timestamp)
            if paper:
                papers.append(paper)

        # Convert arXiv results (supplement, not duplicate)
        for item in arxiv_results:
            paper = self._convert_arxiv(item, timestamp, start_date, end_date)
            if paper:
                papers.append(paper)

        # Deduplicate by normalized title
        raw_dicts = [{"title": p.title, "paper": p} for p in papers]
        deduped = dedupe_papers_by_title(raw_dicts)
        papers = [item["paper"] for item in deduped][:target_papers]

        logger.info(
            "Ingested %d papers (from %d SS + %d arXiv, after dedup)",
            len(papers),
            len(ss_results),
            len(arxiv_results),
        )

        result = IngestionResult(
            topic=topic,
            start_date=start_date,
            end_date=end_date,
            requested_papers=target_papers,
            ingested_papers=len(papers),
            run_id=run_id,
            corpus_mode=effective_corpus_mode,
            benchmark_seeded_papers=len(benchmark_results),
            cached_files=cached_files,
        )
        return papers, result

    async def _fetch_benchmark_seed_papers(self, corpus_mode: str) -> list[dict]:
        if corpus_mode not in {"benchmark", "hybrid"}:
            return []
        if not self.benchmark_manifest_path or not self.benchmark_manifest_path.exists():
            return []

        manifest = json.loads(self.benchmark_manifest_path.read_text(encoding="utf-8"))
        seeded_results: list[dict] = []
        for entry in manifest:
            paper_id = entry.get("semantic_scholar_id")
            if not paper_id:
                continue
            detail = await self.semantic_scholar.get_paper_details(paper_id)
            if detail:
                seeded_results.append(detail)
        logger.info("Loaded %d seeded benchmark papers", len(seeded_results))
        return seeded_results

    def _resolve_corpus_mode(self, topic: str, corpus_mode: str | None) -> str:
        requested = (corpus_mode or self.corpus_mode).strip().lower()
        if requested == "auto":
            return self.corpus_mode if self._is_default_topic(topic) else "latest"
        if requested in {"latest", "benchmark", "hybrid"}:
            if requested in {"benchmark", "hybrid"} and not self._is_default_topic(topic):
                logger.info(
                    "Custom topic '%s' requested with mode=%s; "
                    "falling back to latest to avoid unrelated benchmark seeds",
                    topic,
                    requested,
                )
                return "latest"
            return requested
        logger.warning("Unknown corpus mode '%s'; falling back to latest", requested)
        return "latest"

    def _is_default_topic(self, topic: str) -> bool:
        return self._slugify_topic(topic) == self._slugify_topic(self.default_topic)

    def _slugify_topic(self, topic: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
        return slug or "topic"

    def _convert_semantic_scholar(self, item: dict, timestamp: str) -> Paper | None:
        """Convert a Semantic Scholar API result to a Paper model."""
        paper_id = item.get("paperId")
        if not paper_id:
            return None

        title = item.get("title", "")
        if not title:
            return None

        external_ids = item.get("externalIds") or {}
        authors = []
        for author_data in item.get("authors", []):
            name = author_data.get("name", "")
            if name:
                authors.append(
                    Author(
                        name=normalize_author_name(name),
                        semantic_scholar_id=author_data.get("authorId"),
                    )
                )

        # Extract citation IDs from the citation list
        citation_ids = []
        for citation in item.get("citations", []):
            if isinstance(citation, dict) and citation.get("paperId"):
                citation_ids.append(citation["paperId"])

        return Paper(
            paper_id=paper_id,
            title=title,
            abstract=item.get("abstract"),
            publication_date=item.get("publicationDate")
            or (str(item.get("year")) if item.get("year") else None),
            venue=item.get("venue"),
            doi=external_ids.get("DOI"),
            arxiv_id=external_ids.get("ArXiv"),
            semantic_scholar_id=paper_id,
            source_url=item.get("url"),
            authors=authors,
            citation_ids=citation_ids,
            provenance=Provenance(
                source_url=item.get("url"),
                source_type="semantic_scholar",
                source_id=paper_id,
                extracted_at=timestamp,
                extraction_method="api_metadata",
                confidence="high",
            ),
        )

    def _convert_arxiv(
        self,
        item: dict,
        timestamp: str,
        start_date: str,
        end_date: str,
    ) -> Paper | None:
        """Convert an arXiv API result to a Paper model."""
        title = item.get("title", "")
        if not title:
            return None

        # Filter by date range
        published = item.get("published", "")
        if published:
            pub_date = published[:10]  # YYYY-MM-DD
            if pub_date < start_date or pub_date > end_date:
                return None
        else:
            pub_date = None

        arxiv_id = item.get("arxiv_id") or ""
        paper_id = f"arxiv:{arxiv_id}" if arxiv_id else sha1(title.encode("utf-8")).hexdigest()[:12]

        authors = []
        for author_data in item.get("authors", []):
            name = (
                author_data.get("name", "") if isinstance(author_data, dict) else str(author_data)
            )
            if name:
                affiliations = []
                if isinstance(author_data, dict) and author_data.get("affiliation"):
                    affiliations = [author_data["affiliation"]]
                authors.append(
                    Author(
                        name=normalize_author_name(name),
                        affiliations=affiliations,
                    )
                )

        return Paper(
            paper_id=paper_id,
            title=title,
            abstract=item.get("summary"),
            publication_date=pub_date,
            arxiv_id=arxiv_id or None,
            source_url=item.get("id"),
            authors=authors,
            provenance=Provenance(
                source_url=item.get("id"),
                source_type="arxiv",
                source_id=paper_id,
                extracted_at=timestamp,
                extraction_method="api_metadata",
                confidence="high",
            ),
        )
