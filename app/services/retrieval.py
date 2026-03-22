from __future__ import annotations

import logging

from app.models.schemas import EvidenceItem, QueryResponse, TopicSummary
from app.services.neo4j_graph import Neo4jGraphStore
from app.services.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


SYNTHESIS_SYSTEM_PROMPT = (
    "You are an AI research analyst answering questions "
    "about agent tool-call reliability.\n\n"
    "You are given a question and relevant evidence from "
    "academic papers. Your job is to:\n"
    "1. Synthesize a clear, evidence-backed answer\n"
    "2. Cite specific papers by their titles\n"
    "3. Acknowledge uncertainty when evidence is sparse\n"
    "4. Group findings by method/approach when relevant\n\n"
    "If the evidence is insufficient to answer the question "
    "fully, say so explicitly.\n"
    "Do NOT make up information not supported by the "
    "provided evidence."
)


class RetrievalService:
    """Hybrid retrieval service combining vector search and graph traversal.

    Supports three search modes:
    - entity: Vector search → graph neighborhood traversal
    - theme: Date-bounded graph traversal → thematic synthesis
    - comparative: Multi-method graph traversal → side-by-side analysis
    - auto: Automatically selects the best mode based on the query
    """

    def __init__(
        self,
        graph_store: Neo4jGraphStore | None,
        llm_client: OpenRouterClient | None,
    ) -> None:
        self.graph_store = graph_store
        self.llm_client = llm_client

    async def answer(
        self,
        question: str,
        start_date: str | None = None,
        end_date: str | None = None,
        search_mode: str = "auto",
    ) -> QueryResponse:
        """Answer a question using hybrid graph + vector retrieval."""
        if not self.graph_store or not self.llm_client:
            return self._placeholder_response()

        # Auto-detect search mode
        if search_mode == "auto":
            search_mode = self._detect_mode(question)

        try:
            if search_mode == "theme":
                return await self._theme_search(question, start_date, end_date)
            elif search_mode == "comparative":
                return await self._comparative_search(question)
            else:
                return await self._entity_search(question, start_date, end_date)
        except Exception:
            logger.exception("Retrieval failed for question: %s", question[:100])
            return self._placeholder_response()

    async def _entity_search(
        self,
        question: str,
        start_date: str | None,
        end_date: str | None,
    ) -> QueryResponse:
        """Entity search: vector similarity → graph neighborhood → synthesis."""
        # 1. Embed the query
        query_embedding = await self.llm_client.embed(question)

        # 2. Vector search across papers, methods, and claims
        paper_hits = self.graph_store.vector_search_papers(query_embedding, top_k=8)
        method_hits = self.graph_store.vector_search_methods(query_embedding, top_k=5)
        claim_hits = self.graph_store.vector_search_claims(query_embedding, top_k=8)

        # 3. Get graph neighborhoods for top papers
        neighborhoods = []
        for hit in paper_hits[:5]:
            neighborhood = self.graph_store.get_paper_neighborhood(hit["paper_id"])
            if neighborhood:
                neighborhoods.append(neighborhood)

        # 4. Build context and synthesize
        context = self._build_entity_context(paper_hits, method_hits, claim_hits, neighborhoods)
        evidence = self._build_evidence(paper_hits, claim_hits)
        related_methods = [h["canonical_name"] for h in method_hits if h.get("canonical_name")]

        answer = await self._synthesize(question, context)

        return QueryResponse(
            answer=answer,
            search_mode="entity",
            evidence=evidence,
            related_methods=related_methods,
            graph_paths=[["Query", "Paper", "Method", "Claim"]],
        )

    async def _theme_search(
        self,
        question: str,
        start_date: str | None,
        end_date: str | None,
    ) -> QueryResponse:
        """Theme search: date-bounded graph traversal → thematic synthesis."""
        if not start_date or not end_date:
            start_date = start_date or "2025-01-01"
            end_date = end_date or "2026-12-31"

        # Get all papers in the date range with their methods and claims
        papers_data = self.graph_store.get_papers_by_date_range(start_date, end_date)

        # Build context grouped by method
        context = self._build_theme_context(papers_data)
        evidence = [
            EvidenceItem(
                title=p.get("title", ""),
                paper_id=p.get("paper_id", ""),
                citation=f"{p.get('title', '')} ({p.get('publication_date', 'n.d.')})",
                metadata={"methods": p.get("methods", [])},
            )
            for p in papers_data[:12]
        ]

        # Extract related methods
        all_methods: list[str] = []
        for p in papers_data:
            all_methods.extend(p.get("methods", []))
        related_methods = list(set(m for m in all_methods if m))

        answer = await self._synthesize(question, context)

        return QueryResponse(
            answer=answer,
            search_mode="theme",
            evidence=evidence,
            related_methods=related_methods,
            graph_paths=[["Topic", "Paper", "Method", "Claim"]],
        )

    async def _comparative_search(self, question: str) -> QueryResponse:
        """Comparative search: find two methods and compare their evidence."""
        # Ask LLM to extract the two methods being compared
        extract_prompt = (
            "Extract exactly two method/approach names being compared in this question. "
            'Return them as a JSON object: {"method_a": "...", "method_b": "..."}. '
            "Use lowercase, concise names."
        )
        try:
            methods_json = await self.llm_client.chat_json(extract_prompt, question)
            import json

            methods = json.loads(methods_json)
            method_a = methods.get("method_a", "")
            method_b = methods.get("method_b", "")
        except Exception:
            # Fall back to entity search
            return await self._entity_search(question, None, None)

        if not method_a or not method_b:
            return await self._entity_search(question, None, None)

        # Normalize method names
        from app.services.normalization import canonicalize_method

        method_a = canonicalize_method(method_a)
        method_b = canonicalize_method(method_b)

        # Get comparative data from graph
        comparative_data = self.graph_store.get_comparative_data(method_a, method_b)

        context = self._build_comparative_context(method_a, method_b, comparative_data)
        answer = await self._synthesize(question, context)

        # Build evidence from both methods
        evidence: list[EvidenceItem] = []
        for method_name, papers in comparative_data.items():
            for p in papers[:5]:
                evidence.append(
                    EvidenceItem(
                        title=p.get("title", ""),
                        paper_id=p.get("paper_id", ""),
                        citation=f"{p.get('title', '')} [re: {method_name}]",
                        metadata={"method": method_name, "claims": p.get("claims", [])},
                    )
                )

        return QueryResponse(
            answer=answer,
            search_mode="comparative",
            evidence=evidence,
            related_methods=[method_a, method_b],
            graph_paths=[
                ["Method A", "Paper", "Claim"],
                ["Method B", "Paper", "Claim"],
            ],
        )

    # ── Helpers ────────────────────────────────────────────────────────

    def _detect_mode(self, question: str) -> str:
        """Auto-detect the best search mode based on question patterns."""
        q = question.lower()
        comparative_words = ["compare", "versus", "vs", "difference between", "comparison"]
        if any(word in q for word in comparative_words):
            return "comparative"
        theme_words = ["changed", "trend", "between", "over time", "evolution", "briefing"]
        if any(word in q for word in theme_words):
            return "theme"
        return "entity"

    def _build_entity_context(
        self,
        paper_hits: list[dict],
        method_hits: list[dict],
        claim_hits: list[dict],
        neighborhoods: list[dict],
    ) -> str:
        """Build context string from entity search results."""
        parts: list[str] = []

        if method_hits:
            parts.append("## Relevant Methods")
            for h in method_hits:
                desc = h.get("description") or "No description"
                parts.append(f"- **{h.get('name', '')}** ({h.get('category', 'unknown')}): {desc}")

        if paper_hits:
            parts.append("\n## Relevant Papers")
            for h in paper_hits[:8]:
                parts.append(f"- {h.get('title', '')} (score: {h.get('score', 0):.3f})")
                abstract = h.get("abstract", "")
                if abstract:
                    parts.append(f"  Abstract: {abstract[:300]}...")

        if claim_hits:
            parts.append("\n## Relevant Claims")
            for h in claim_hits[:8]:
                confidence = h.get("confidence", "unknown")
                parts.append(f"- [{confidence}] {h.get('statement', '')}")

        if neighborhoods:
            parts.append("\n## Paper Details")
            for n in neighborhoods[:3]:
                parts.append(f"\n### {n.get('title', '')}")
                if n.get("authors"):
                    parts.append(f"Authors: {', '.join(n['authors'][:5])}")
                if n.get("methods"):
                    parts.append(f"Methods: {', '.join(n['methods'])}")
                if n.get("claims"):
                    for claim in n["claims"][:3]:
                        if isinstance(claim, dict):
                            parts.append(f"- Claim: {claim.get('statement', '')}")

        return "\n".join(parts)

    def _build_theme_context(self, papers_data: list[dict]) -> str:
        """Build context string from theme search results."""
        # Group by method
        method_papers: dict[str, list[dict]] = {}
        for p in papers_data:
            for method in p.get("methods", []):
                if method:
                    method_papers.setdefault(method, []).append(p)

        parts: list[str] = [f"## Thematic Overview ({len(papers_data)} papers)\n"]

        for method, papers in sorted(method_papers.items(), key=lambda x: -len(x[1]))[:10]:
            parts.append(f"### {method} ({len(papers)} papers)")
            for p in papers[:3]:
                parts.append(f"- {p.get('title', '')} ({p.get('publication_date', 'n.d.')})")
                claims = p.get("claims", [])
                for claim in claims[:2]:
                    if isinstance(claim, dict):
                        parts.append(f"  - {claim.get('statement', '')}")

        return "\n".join(parts)

    def _build_comparative_context(self, method_a: str, method_b: str, data: dict) -> str:
        """Build context for comparative search."""
        parts: list[str] = []

        for method_name in [method_a, method_b]:
            papers = data.get(method_name, [])
            parts.append(f"## {method_name} ({len(papers)} papers)")
            for p in papers[:5]:
                parts.append(f"- {p.get('title', '')}")
                for claim in p.get("claims", [])[:3]:
                    parts.append(f"  - {claim}")
            parts.append("")

        return "\n".join(parts)

    async def _synthesize(self, question: str, context: str) -> str:
        """Synthesize an answer from context using the LLM."""
        if not context.strip():
            return (
                "No relevant evidence found in the corpus. "
                "Try running the ingestion pipeline to populate the graph."
            )

        user_prompt = f"Question: {question}\n\nEvidence:\n{context}"
        return await self.llm_client.chat(
            system_prompt=SYNTHESIS_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.2,
        )

    def _build_evidence(self, paper_hits: list[dict], claim_hits: list[dict]) -> list[EvidenceItem]:
        """Build EvidenceItem list from search hits."""
        evidence: list[EvidenceItem] = []
        for hit in paper_hits[:8]:
            evidence.append(
                EvidenceItem(
                    title=hit.get("title", ""),
                    paper_id=hit.get("paper_id", ""),
                    citation=f"{hit.get('title', '')} ({hit.get('publication_date', 'n.d.')})",
                    score=hit.get("score"),
                )
            )
        return evidence

    def topic_summary(self, topic: str) -> TopicSummary:
        """Get topic summary from the graph."""
        if not self.graph_store:
            return TopicSummary(topic=topic)
        return self.graph_store.fetch_topic_summary(topic)

    def _placeholder_response(self) -> QueryResponse:
        """Return a placeholder response when graph/LLM is unavailable."""
        return QueryResponse(
            answer="The retrieval service requires both Neo4j and an OpenRouter API key. "
            "Please configure these and run the ingestion pipeline.",
            search_mode="none",
            evidence=[],
            confidence_note="No indexed corpus available.",
        )
