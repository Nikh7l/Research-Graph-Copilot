"""Run the MCP server as a standalone process.

Usage:
    python -m app.mcp_runner

Or with uvx / mcp dev:
    mcp dev app/mcp_runner.py
"""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.services.graph_query import GraphQueryService
from app.services.mcp_server import build_mcp_server
from app.services.neo4j_graph import Neo4jGraphStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)-6s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Initialize services and start MCP server."""
    settings = Settings()

    # Neo4j
    graph_store = None
    try:
        graph_store = Neo4jGraphStore(
            uri=settings.neo4j_uri,
            username=settings.neo4j_username,
            password=settings.neo4j_password,
        )
        logger.info("Neo4j connected at %s", settings.neo4j_uri)
    except Exception:
        logger.warning("Neo4j not available, running without graph")

    graph_query_service = GraphQueryService(graph_store=graph_store)

    # Build and run
    server = build_mcp_server(
        settings=settings,
        graph_query_service=graph_query_service,
    )

    logger.info("Starting MCP server: research-intelligence-copilot")
    server.run()


if __name__ == "__main__":
    main()
