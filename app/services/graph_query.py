from __future__ import annotations

from typing import Any

from app.services.neo4j_graph import Neo4jGraphStore


class GraphQueryService:
    """Deterministic graph queries used by the MCP server."""

    def __init__(self, graph_store: Neo4jGraphStore | None) -> None:
        self.graph_store = graph_store

    def get_corpus_stats(self) -> dict[str, Any]:
        if not self.graph_store:
            return {"papers": 0, "methods": 0, "claims": 0, "authors": 0}
        return self.graph_store.get_stats()

    def get_relationship_counts(self) -> dict[str, Any]:
        if not self.graph_store:
            return {"relationship_counts": []}
        return {"relationship_counts": self.graph_store.get_relationship_counts()}

    def get_topic_summary(
        self,
        topic: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        if not self.graph_store:
            return {"topic": topic, "methods": [], "claims": [], "paper_count": 0}
        summary = self.graph_store.fetch_topic_summary(
            topic,
            start_date=start_date,
            end_date=end_date,
        )
        return summary.model_dump()

    def search_papers(
        self,
        query: str,
        limit: int = 10,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        if not self.graph_store:
            return {"query": query, "papers": []}
        return {
            "query": query,
            "papers": self.graph_store.search_papers_by_text(
                search_query=query,
                limit=limit,
                start_date=start_date,
                end_date=end_date,
            ),
        }

    def get_paper_neighborhood(self, paper_id: str) -> dict[str, Any]:
        if not self.graph_store:
            return {"paper_id": paper_id, "paper": None, "authors": [], "methods": [], "claims": []}
        payload = self.graph_store.get_paper_neighborhood(paper_id)
        return {"paper_id": paper_id, **payload}

    def get_method_papers(
        self,
        method_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        if not self.graph_store:
            return {"method_name": method_name, "papers": []}
        return {
            "method_name": method_name,
            "papers": self.graph_store.get_method_papers(method_name, start_date, end_date),
        }

    def get_claims_for_method(
        self,
        method_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        if not self.graph_store:
            return {"method_name": method_name, "claims": []}
        return {
            "method_name": method_name,
            "claims": self.graph_store.get_claims_for_method(method_name, start_date, end_date),
        }

    def compare_methods_structured(
        self,
        method_a: str,
        method_b: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        if not self.graph_store:
            return {"method_a": method_a, "method_b": method_b, "comparison": {}}
        data = self.graph_store.get_comparative_data(method_a, method_b, start_date, end_date)
        return {
            "method_a": method_a,
            "method_b": method_b,
            "comparison": {
                method_a: {
                    "paper_count": len(data.get(method_a, [])),
                    "papers": data.get(method_a, []),
                },
                method_b: {
                    "paper_count": len(data.get(method_b, [])),
                    "papers": data.get(method_b, []),
                },
            },
        }

    def get_graph_paths(
        self,
        entity_type_a: str,
        entity_id_a: str,
        entity_type_b: str,
        entity_id_b: str,
        max_hops: int = 4,
    ) -> dict[str, Any]:
        if not self.graph_store:
            return {"paths": []}
        return {
            "paths": self.graph_store.get_graph_paths(
                entity_type_a=entity_type_a,
                entity_id_a=entity_id_a,
                entity_type_b=entity_type_b,
                entity_id_b=entity_id_b,
                max_hops=max_hops,
            )
        }
