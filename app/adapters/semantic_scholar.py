from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

import httpx

logger = logging.getLogger(__name__)


class SemanticScholarAdapter:
    """Adapter for Semantic Scholar Academic Graph API.

    Handles pagination, rate limiting (100 req / 5 min), and date filtering.
    """

    FIELDS = (
        "paperId,title,abstract,year,venue,authors,externalIds,"
        "url,citationCount,referenceCount,citations.paperId,publicationDate"
    )

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def search_papers(
        self,
        query: str,
        start_year: int,
        end_year: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Search for papers with pagination to hit the target limit.

        Semantic Scholar returns max 100 per request and supports offset-based pagination.
        """
        year_filter = f"{start_year}-" if end_year is None else f"{start_year}-{end_year}"
        all_results: list[dict[str, Any]] = []
        offset = 0
        page_size = min(limit, 100)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while len(all_results) < limit:
                params: dict[str, str | int] = {
                    "query": query,
                    "limit": page_size,
                    "offset": offset,
                    "fields": self.FIELDS,
                    "year": year_filter,
                }
                try:
                    response = await client.get(f"{self.base_url}/paper/search", params=params)
                    response.raise_for_status()
                    payload = response.json()
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 429:
                        logger.warning("Rate limited by Semantic Scholar, waiting 10s")
                        await asyncio.sleep(10)
                        continue
                    raise

                data = payload.get("data", [])
                if not data:
                    break

                all_results.extend(data)
                offset += len(data)

                total = payload.get("total", 0)
                if offset >= total:
                    break

                # Rate limit: ~1 request per 3 seconds to stay safe
                await asyncio.sleep(3)

        return all_results[:limit]

    async def get_paper_details(self, paper_id: str) -> dict[str, Any] | None:
        """Fetch detailed info for a single paper by its Semantic Scholar ID."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/paper/{paper_id}",
                    params={"fields": self.FIELDS},
                )
                response.raise_for_status()
                return cast(dict[str, Any], response.json())
            except httpx.HTTPStatusError:
                logger.warning("Failed to fetch paper %s", paper_id)
                return None
