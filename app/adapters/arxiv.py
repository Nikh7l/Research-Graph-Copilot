from __future__ import annotations

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ArxivAdapter:
    """Adapter for the arXiv API.

    Uses the Atom feed export endpoint. Parses XML without heavy dependencies.
    """

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.base_url = base_url
        self.timeout = timeout

    async def search(self, query: str, max_results: int = 50) -> list[dict[str, Any]]:
        """Search arXiv for papers matching the query.

        arXiv API returns max 2000 per request. We paginate if needed.
        """
        all_results: list[dict[str, Any]] = []
        start = 0
        page_size = min(max_results, 200)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while len(all_results) < max_results:
                params: dict[str, str | int] = {
                    "search_query": f"all:{query}",
                    "start": start,
                    "max_results": page_size,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                }
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()

                entries = self._parse_feed(response.text)
                if not entries:
                    break

                all_results.extend(entries)
                start += len(entries)

                if len(entries) < page_size:
                    break

        return all_results[:max_results]

    def _parse_feed(self, xml_text: str) -> list[dict[str, Any]]:
        """Parse arXiv Atom feed XML into structured dicts."""
        entries = xml_text.split("<entry>")[1:]
        parsed: list[dict[str, Any]] = []

        for entry in entries:
            title = self._extract(entry, "title")
            summary = self._extract(entry, "summary")
            entry_id = self._extract(entry, "id")
            published = self._extract(entry, "published")

            # Extract authors
            authors = []
            for author_match in re.finditer(
                r"<author>\s*<name>(.*?)</name>(?:\s*<arxiv:affiliation[^>]*>(.*?)</arxiv:affiliation>)?",
                entry,
                flags=re.DOTALL,
            ):
                name = " ".join(author_match.group(1).split())
                affiliation = (
                    " ".join(author_match.group(2).split()) if author_match.group(2) else None
                )
                authors.append({"name": name, "affiliation": affiliation})

            # Extract categories
            categories = re.findall(r'<category[^>]*term="([^"]+)"', entry)

            # Extract arXiv ID from the URL
            arxiv_id = None
            if entry_id:
                id_match = re.search(r"abs/(\d+\.\d+)", entry_id)
                if id_match:
                    arxiv_id = id_match.group(1)

            parsed.append(
                {
                    "id": entry_id,
                    "arxiv_id": arxiv_id,
                    "title": title,
                    "summary": summary,
                    "published": published,
                    "authors": authors,
                    "categories": categories,
                }
            )

        return parsed

    def _extract(self, text: str, tag: str) -> str | None:
        match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", text, flags=re.DOTALL)
        if not match:
            return None
        return " ".join(match.group(1).split())
