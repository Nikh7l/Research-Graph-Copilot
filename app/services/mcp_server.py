"""Deterministic MCP server for graph-backed research retrieval."""

from __future__ import annotations

from app.core.config import Settings
from app.services.graph_query import GraphQueryService


def build_mcp_server(
    settings: Settings,
    graph_query_service: GraphQueryService,
):
    """Build and return the MCP server with all tools registered."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(
        "research-intelligence-copilot",
        instructions=(
            "AI Research Intelligence Copilot. "
            "Expose deterministic graph and retrieval tools over "
            "a Neo4j knowledge graph for agent tool-call reliability research. "
            "Return structured data only; do not synthesize prose answers."
        ),
    )

    @server.tool()
    def search_papers(
        query: str,
        limit: int = 5,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """Return paper matches and scores for a text query."""
        return graph_query_service.search_papers(
            query=query,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
        )

    @server.tool()
    def get_topic_summary(
        topic: str = "agent tool-call reliability",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """Return topic aggregates, top methods, and top claims."""
        return graph_query_service.get_topic_summary(topic, start_date, end_date)

    @server.tool()
    def get_method_papers(
        method_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """Return papers linked to a canonical method."""
        return graph_query_service.get_method_papers(method_name, start_date, end_date)

    @server.tool()
    def get_claims_for_method(
        method_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """Return claim records tied to a canonical method."""
        return graph_query_service.get_claims_for_method(method_name, start_date, end_date)

    @server.tool()
    def get_paper_neighborhood(paper_id: str) -> dict:
        """Return the paper neighborhood: authors, methods, claims, citations."""
        return graph_query_service.get_paper_neighborhood(paper_id)

    @server.tool()
    def compare_methods_structured(
        method_a: str,
        method_b: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """Return structured side-by-side evidence for two methods."""
        return graph_query_service.compare_methods_structured(
            method_a=method_a,
            method_b=method_b,
            start_date=start_date,
            end_date=end_date,
        )

    @server.tool()
    def get_graph_paths(
        entity_type_a: str,
        entity_id_a: str,
        entity_type_b: str,
        entity_id_b: str,
        max_hops: int = 4,
    ) -> dict:
        """Return graph paths between two entities."""
        return graph_query_service.get_graph_paths(
            entity_type_a=entity_type_a,
            entity_id_a=entity_id_a,
            entity_type_b=entity_type_b,
            entity_id_b=entity_id_b,
            max_hops=max_hops,
        )

    @server.tool()
    def get_relationship_counts() -> dict:
        """Return counts per relationship type in the graph."""
        return graph_query_service.get_relationship_counts()

    @server.tool()
    def get_corpus_stats() -> dict:
        """Return corpus counts."""
        return graph_query_service.get_corpus_stats()

    return server
