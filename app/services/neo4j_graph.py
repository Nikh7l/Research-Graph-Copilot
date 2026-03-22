from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from neo4j import GraphDatabase

from app.models.schemas import Claim, Method, Paper, TopicSummary

logger = logging.getLogger(__name__)


class Neo4jGraphStore:
    """Neo4j graph store with full relationship management and vector index support."""

    def __init__(self, uri: str, username: str, password: str) -> None:
        self.driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self) -> None:
        self.driver.close()

    # ── Schema & Index Setup ──────────────────────────────────────────

    def ensure_schema(self) -> None:
        """Create constraints, full-text indexes, and vector indexes."""
        statements = [
            # Uniqueness constraints
            "CREATE CONSTRAINT paper_id IF NOT EXISTS FOR (p:Paper) REQUIRE p.paper_id IS UNIQUE",
            (
                "CREATE CONSTRAINT method_name IF NOT EXISTS"
                " FOR (m:Method) REQUIRE m.canonical_name IS UNIQUE"
            ),
            ("CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (c:Claim) REQUIRE c.claim_id IS UNIQUE"),
            (
                "CREATE CONSTRAINT author_name IF NOT EXISTS"
                " FOR (a:Author) REQUIRE a.name_key IS UNIQUE"
            ),
            "CREATE CONSTRAINT topic_name IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE",
        ]
        with self.driver.session() as session:
            for statement in statements:
                try:
                    session.run(statement)
                except Exception as exc:
                    logger.warning("Schema statement skipped: %s — %s", statement[:60], exc)

    def ensure_vector_indexes(self) -> None:
        """Create HNSW vector indexes for embedding-based retrieval.

        These must be created separately because they require embedding data to exist first.
        """
        vector_indexes = [
            """CREATE VECTOR INDEX paper_embedding_index IF NOT EXISTS
            FOR (p:Paper) ON (p.embedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: 1536,
                `vector.similarity_function`: 'cosine'
            }}""",
            """CREATE VECTOR INDEX method_embedding_index IF NOT EXISTS
            FOR (m:Method) ON (m.embedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: 1536,
                `vector.similarity_function`: 'cosine'
            }}""",
            """CREATE VECTOR INDEX claim_embedding_index IF NOT EXISTS
            FOR (c:Claim) ON (c.embedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: 1536,
                `vector.similarity_function`: 'cosine'
            }}""",
        ]

        fulltext_indexes = [
            """CREATE FULLTEXT INDEX paper_fulltext_index IF NOT EXISTS
            FOR (p:Paper) ON EACH [p.title, p.abstract]""",
        ]

        with self.driver.session() as session:
            for statement in [*vector_indexes, *fulltext_indexes]:
                try:
                    session.run(statement)
                except Exception as exc:
                    logger.warning("Index creation skipped: %s", exc)

    # ── Node Upserts ──────────────────────────────────────────────────

    def upsert_papers(self, papers: Iterable[Paper]) -> None:
        """Upsert Paper nodes with all properties including embeddings."""
        statement = """
        MERGE (p:Paper {paper_id: $paper_id})
        SET p.title = $title,
            p.abstract = $abstract,
            p.publication_date = $publication_date,
            p.venue = $venue,
            p.doi = $doi,
            p.arxiv_id = $arxiv_id,
            p.semantic_scholar_id = $semantic_scholar_id,
            p.source_url = $source_url,
            p.source_type = $source_type,
            p.extraction_method = $extraction_method
        """
        statement_with_embedding = statement + ", p.embedding = $embedding"

        with self.driver.session() as session:
            for paper in papers:
                params = {
                    "paper_id": paper.paper_id,
                    "title": paper.title,
                    "abstract": paper.abstract,
                    "publication_date": paper.publication_date,
                    "venue": paper.venue,
                    "doi": paper.doi,
                    "arxiv_id": paper.arxiv_id,
                    "semantic_scholar_id": paper.semantic_scholar_id,
                    "source_url": paper.source_url,
                    "source_type": paper.provenance.source_type,
                    "extraction_method": paper.provenance.extraction_method,
                }
                if paper.embedding:
                    params["embedding"] = paper.embedding
                    session.run(statement_with_embedding, **params)
                else:
                    session.run(statement, **params)

    def upsert_methods(self, methods: Iterable[Method]) -> None:
        """Upsert Method nodes."""
        statement = """
        MERGE (m:Method {canonical_name: $canonical_name})
        SET m.name = $name,
            m.category = $category,
            m.description = $description,
            m.aliases = $aliases
        """
        statement_with_embedding = statement + ", m.embedding = $embedding"

        with self.driver.session() as session:
            for method in methods:
                params = {
                    "canonical_name": method.canonical_name,
                    "name": method.name,
                    "category": method.category,
                    "description": method.description,
                    "aliases": method.aliases,
                }
                if method.embedding:
                    params["embedding"] = method.embedding
                    session.run(statement_with_embedding, **params)
                else:
                    session.run(statement, **params)

    def upsert_claims(self, claims: Iterable[Claim]) -> None:
        """Upsert Claim nodes."""
        statement = """
        MERGE (c:Claim {claim_id: $claim_id})
        SET c.statement = $statement,
            c.evidence_span = $evidence_span,
            c.confidence = $confidence,
            c.method_name = $method_name,
            c.paper_id = $paper_id
        """
        statement_with_embedding = statement + ", c.embedding = $embedding"

        with self.driver.session() as session:
            for claim in claims:
                params = {
                    "claim_id": claim.claim_id,
                    "statement": claim.statement,
                    "evidence_span": claim.evidence_span,
                    "confidence": claim.confidence,
                    "method_name": claim.method_name,
                    "paper_id": claim.paper_id,
                }
                if claim.embedding:
                    params["embedding"] = claim.embedding
                    session.run(statement_with_embedding, **params)
                else:
                    session.run(statement, **params)

    def upsert_topic(self, name: str, description: str | None = None) -> None:
        """Upsert a Topic node."""
        with self.driver.session() as session:
            session.run(
                "MERGE (t:Topic {name: $name}) SET t.description = $description",
                name=name,
                description=description,
            )

    # ── Relationship Creation ─────────────────────────────────────────

    def create_authored_edges(self, papers: Iterable[Paper]) -> None:
        """Create (Author)-[:AUTHORED]->(Paper) relationships."""
        with self.driver.session() as session:
            for paper in papers:
                for author in paper.authors:
                    name_key = author.name.lower().strip()
                    session.run(
                        """
                        MERGE (a:Author {name_key: $name_key})
                        SET a.name = $name,
                            a.semantic_scholar_id = $ss_id
                        WITH a
                        MATCH (p:Paper {paper_id: $paper_id})
                        MERGE (a)-[:AUTHORED]->(p)
                        """,
                        name_key=name_key,
                        name=author.name,
                        ss_id=author.semantic_scholar_id,
                        paper_id=paper.paper_id,
                    )
                    # Affiliations
                    for affiliation in author.affiliations:
                        if affiliation:
                            session.run(
                                """
                                MERGE (o:Organization {name: $org_name})
                                WITH o
                                MATCH (a:Author {name_key: $name_key})
                                MERGE (a)-[:AFFILIATED_WITH]->(o)
                                """,
                                org_name=affiliation,
                                name_key=name_key,
                            )

    def create_proposes_edges(self, papers: Iterable[Paper], methods: list[Method]) -> None:
        """Create (Paper)-[:PROPOSES]->(Method) relationships based on extraction results."""
        method_to_papers: dict[str, list[str]] = {}
        for method in methods:
            paper_id = method.provenance.source_id
            canonical = method.canonical_name
            method_to_papers.setdefault(canonical, []).append(paper_id)

        with self.driver.session() as session:
            for canonical, paper_ids in method_to_papers.items():
                for paper_id in paper_ids:
                    session.run(
                        """
                        MATCH (p:Paper {paper_id: $paper_id})
                        MATCH (m:Method {canonical_name: $canonical_name})
                        MERGE (p)-[:PROPOSES]->(m)
                        """,
                        paper_id=paper_id,
                        canonical_name=canonical,
                    )

    def create_supports_edges(self, claims: Iterable[Claim]) -> None:
        """Create (Paper)-[:SUPPORTS]->(Claim) relationships."""
        with self.driver.session() as session:
            for claim in claims:
                if claim.paper_id:
                    session.run(
                        """
                        MATCH (p:Paper {paper_id: $paper_id})
                        MATCH (c:Claim {claim_id: $claim_id})
                        MERGE (p)-[:SUPPORTS]->(c)
                        """,
                        paper_id=claim.paper_id,
                        claim_id=claim.claim_id,
                    )
                if claim.method_name:
                    session.run(
                        """
                        MATCH (m:Method {canonical_name: $method_name})
                        MATCH (c:Claim {claim_id: $claim_id})
                        MERGE (c)-[:ABOUT]->(m)
                        """,
                        method_name=claim.method_name,
                        claim_id=claim.claim_id,
                    )

    def create_about_edges(self, papers: Iterable[Paper], topic_name: str) -> None:
        """Create (Paper)-[:ABOUT]->(Topic) relationships."""
        with self.driver.session() as session:
            for paper in papers:
                session.run(
                    """
                    MATCH (p:Paper {paper_id: $paper_id})
                    MATCH (t:Topic {name: $topic_name})
                    MERGE (p)-[:ABOUT]->(t)
                    """,
                    paper_id=paper.paper_id,
                    topic_name=topic_name,
                )

    def create_citation_edges(self, papers: Iterable[Paper]) -> None:
        """Create (Paper)-[:CITES]->(Paper) relationships."""
        with self.driver.session() as session:
            for paper in papers:
                for cited_id in paper.citation_ids:
                    session.run(
                        """
                        MATCH (p1:Paper {paper_id: $paper_id})
                        MATCH (p2:Paper {paper_id: $cited_id})
                        MERGE (p1)-[:CITES]->(p2)
                        """,
                        paper_id=paper.paper_id,
                        cited_id=cited_id,
                    )

    # ── Vector Search ─────────────────────────────────────────────────

    def vector_search_papers(self, embedding: list[float], top_k: int = 10) -> list[dict[str, Any]]:
        """Search papers by vector similarity."""
        query = """
        CALL db.index.vector.queryNodes('paper_embedding_index', $top_k, $embedding)
        YIELD node, score
        RETURN node.paper_id AS paper_id,
               node.title AS title,
               node.abstract AS abstract,
               node.publication_date AS publication_date,
               score
        ORDER BY score DESC
        """
        with self.driver.session() as session:
            result = session.run(query, top_k=top_k, embedding=embedding)
            return [dict(record) for record in result]

    def vector_search_methods(self, embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        """Search methods by vector similarity."""
        query = """
        CALL db.index.vector.queryNodes('method_embedding_index', $top_k, $embedding)
        YIELD node, score
        RETURN node.canonical_name AS canonical_name,
               node.name AS name,
               node.category AS category,
               node.description AS description,
               score
        ORDER BY score DESC
        """
        with self.driver.session() as session:
            result = session.run(query, top_k=top_k, embedding=embedding)
            return [dict(record) for record in result]

    def vector_search_claims(self, embedding: list[float], top_k: int = 10) -> list[dict[str, Any]]:
        """Search claims by vector similarity."""
        query = """
        CALL db.index.vector.queryNodes('claim_embedding_index', $top_k, $embedding)
        YIELD node, score
        RETURN node.claim_id AS claim_id,
               node.statement AS statement,
               node.confidence AS confidence,
               node.method_name AS method_name,
               node.paper_id AS paper_id,
               score
        ORDER BY score DESC
        """
        with self.driver.session() as session:
            result = session.run(query, top_k=top_k, embedding=embedding)
            return [dict(record) for record in result]

    # ── Graph Traversal Retrieval ─────────────────────────────────────

    def get_paper_neighborhood(self, paper_id: str) -> dict[str, Any]:
        """Get a paper and its connected nodes (methods, claims, authors)."""
        query = """
        MATCH (p:Paper {paper_id: $paper_id})
        OPTIONAL MATCH (a:Author)-[:AUTHORED]->(p)
        OPTIONAL MATCH (p)-[:PROPOSES]->(m:Method)
        OPTIONAL MATCH (p)-[:SUPPORTS]->(c:Claim)
        OPTIONAL MATCH (p)-[:CITES]->(cited:Paper)
        RETURN p.title AS title,
               p.paper_id AS paper_id,
               p.abstract AS abstract,
               p.publication_date AS publication_date,
               collect(DISTINCT a.name) AS authors,
               collect(DISTINCT m.canonical_name) AS methods,
               collect(DISTINCT {statement: c.statement, confidence: c.confidence}) AS claims,
               collect(DISTINCT cited.paper_id) AS cited_papers
        """
        with self.driver.session() as session:
            record = session.run(query, paper_id=paper_id).single()
            if not record:
                return {}
            payload = dict(record)
            return {
                "paper": {
                    "paper_id": payload.get("paper_id"),
                    "title": payload.get("title"),
                    "abstract": payload.get("abstract"),
                    "publication_date": payload.get("publication_date"),
                },
                "authors": payload.get("authors", []),
                "methods": payload.get("methods", []),
                "claims": payload.get("claims", []),
                "cited_papers": payload.get("cited_papers", []),
            }

    def get_method_papers(
        self,
        method_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get all papers that propose a given method, optionally filtered by date."""
        query = """
        MATCH (p:Paper)-[:PROPOSES]->(m:Method {canonical_name: $method_name})
        WHERE ($start_date IS NULL OR p.publication_date >= $start_date)
          AND ($end_date IS NULL OR p.publication_date <= $end_date)
        OPTIONAL MATCH (p)-[:SUPPORTS]->(c:Claim)-[:ABOUT]->(m)
        RETURN p.paper_id AS paper_id,
               p.title AS title,
               p.publication_date AS publication_date,
               collect(DISTINCT c.statement) AS claims
        ORDER BY p.publication_date DESC
        """
        with self.driver.session() as session:
            result = session.run(
                query,
                method_name=method_name,
                start_date=start_date,
                end_date=end_date,
            )
            return [dict(record) for record in result]

    def get_claims_for_method(
        self,
        method_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        query = """
        MATCH (c:Claim)-[:ABOUT]->(m:Method {canonical_name: $method_name})
        MATCH (p:Paper)-[:SUPPORTS]->(c)
        WHERE ($start_date IS NULL OR p.publication_date >= $start_date)
          AND ($end_date IS NULL OR p.publication_date <= $end_date)
        RETURN c.claim_id AS claim_id,
               c.statement AS statement,
               c.evidence_span AS evidence_span,
               c.confidence AS confidence,
               p.paper_id AS paper_id,
               p.title AS paper_title,
               p.publication_date AS publication_date
        ORDER BY p.publication_date DESC
        """
        with self.driver.session() as session:
            result = session.run(
                query,
                method_name=method_name,
                start_date=start_date,
                end_date=end_date,
            )
            return [dict(record) for record in result]

    def get_papers_by_date_range(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Get papers in a date range with their methods and claims."""
        query = """
        MATCH (p:Paper)
        WHERE p.publication_date >= $start_date AND p.publication_date <= $end_date
        OPTIONAL MATCH (p)-[:PROPOSES]->(m:Method)
        OPTIONAL MATCH (p)-[:SUPPORTS]->(c:Claim)
        RETURN p.paper_id AS paper_id,
               p.title AS title,
               p.publication_date AS publication_date,
               collect(DISTINCT m.canonical_name) AS methods,
               collect(DISTINCT {statement: c.statement, confidence: c.confidence}) AS claims
        ORDER BY p.publication_date DESC
        """
        with self.driver.session() as session:
            result = session.run(query, start_date=start_date, end_date=end_date)
            return [dict(record) for record in result]

    def get_comparative_data(
        self,
        method_a: str,
        method_b: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Get papers and claims for two methods for comparison."""
        result: dict[str, list[dict[str, Any]]] = {}
        for method_name in [method_a, method_b]:
            query = """
            MATCH (p:Paper)-[:PROPOSES]->(m:Method {canonical_name: $method_name})
            WHERE ($start_date IS NULL OR p.publication_date >= $start_date)
              AND ($end_date IS NULL OR p.publication_date <= $end_date)
            OPTIONAL MATCH (p)-[:SUPPORTS]->(c:Claim)-[:ABOUT]->(m)
            RETURN p.paper_id AS paper_id,
                   p.title AS title,
                   p.publication_date AS publication_date,
                   collect(DISTINCT c.statement) AS claims
            """
            with self.driver.session() as session:
                records = session.run(
                    query,
                    method_name=method_name,
                    start_date=start_date,
                    end_date=end_date,
                )
                result[method_name] = [dict(r) for r in records]
        return result

    # ── Topic Summary ─────────────────────────────────────────────────

    def fetch_topic_summary(
        self,
        topic: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> TopicSummary:
        """Get a summary of the corpus for a given topic."""
        query = """
        MATCH (t:Topic {name: $topic})
        OPTIONAL MATCH (p:Paper)-[:ABOUT]->(t)
        WHERE ($start_date IS NULL OR p.publication_date >= $start_date)
          AND ($end_date IS NULL OR p.publication_date <= $end_date)
        OPTIONAL MATCH (p)-[:PROPOSES]->(m:Method)
        OPTIONAL MATCH (p)-[:SUPPORTS]->(c:Claim)
        WITH t, collect(DISTINCT p) AS papers,
             collect(DISTINCT m.canonical_name) AS methods,
             collect(DISTINCT c.statement) AS claims
        RETURN methods,
               claims[0..10] AS top_claims,
               size(papers) AS paper_count
        """
        with self.driver.session() as session:
            record = session.run(
                query,
                topic=topic,
                start_date=start_date,
                end_date=end_date,
            ).single()

        if not record:
            return TopicSummary(topic=topic)

        methods = [m for m in record["methods"] if m]
        claims = [c for c in record["top_claims"] if c]
        return TopicSummary(
            topic=topic,
            methods=methods,
            claims=claims,
            paper_count=record["paper_count"],
            date_range=f"{start_date or 'min'} to {end_date or 'max'}",
        )

    def search_papers_by_text(
        self,
        search_query: str,
        limit: int = 10,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        fulltext_cypher = """
        CALL db.index.fulltext.queryNodes('paper_fulltext_index', $search_query)
        YIELD node, score
        WHERE ($start_date IS NULL OR node.publication_date >= $start_date)
          AND ($end_date IS NULL OR node.publication_date <= $end_date)
        RETURN node.paper_id AS paper_id,
               node.title AS title,
               node.publication_date AS publication_date,
               node.abstract AS abstract,
               score
        ORDER BY score DESC
        LIMIT $limit
        """
        fallback_cypher = """
        MATCH (p:Paper)
        WHERE ($start_date IS NULL OR p.publication_date >= $start_date)
          AND ($end_date IS NULL OR p.publication_date <= $end_date)
          AND (
            toLower(p.title) CONTAINS toLower($search_query)
            OR toLower(coalesce(p.abstract, '')) CONTAINS toLower($search_query)
          )
        RETURN p.paper_id AS paper_id,
               p.title AS title,
               p.publication_date AS publication_date,
               p.abstract AS abstract,
               0.0 AS score
        LIMIT $limit
        """
        with self.driver.session() as session:
            try:
                result = session.run(
                    fulltext_cypher,
                    search_query=search_query,
                    limit=limit,
                    start_date=start_date,
                    end_date=end_date,
                )
            except Exception:
                result = session.run(
                    fallback_cypher,
                    search_query=search_query,
                    limit=limit,
                    start_date=start_date,
                    end_date=end_date,
                )
            return [dict(record) for record in result]

    def get_relationship_counts(self) -> list[dict[str, Any]]:
        query = """
        MATCH ()-[r]->()
        RETURN type(r) AS relationship_type, count(*) AS count
        ORDER BY count DESC
        """
        with self.driver.session() as session:
            result = session.run(query)
            return [dict(record) for record in result]

    def get_graph_paths(
        self,
        entity_type_a: str,
        entity_id_a: str,
        entity_type_b: str,
        entity_id_b: str,
        max_hops: int = 4,
    ) -> list[list[str]]:
        label_map = {
            "paper": ("Paper", "paper_id"),
            "method": ("Method", "canonical_name"),
            "claim": ("Claim", "claim_id"),
            "topic": ("Topic", "name"),
            "author": ("Author", "name_key"),
        }
        start = label_map.get(entity_type_a.lower())
        end = label_map.get(entity_type_b.lower())
        if not start or not end:
            return []
        start_label, start_key = start
        end_label, end_key = end
        query = f"""
        MATCH p = shortestPath(
            (a:{start_label} {{{start_key}: $entity_id_a}})
            -[*..{max_hops}]-
            (b:{end_label} {{{end_key}: $entity_id_b}})
        )
        RETURN [node IN nodes(p) |
            labels(node)[0] + ':' +
            coalesce(
                node.paper_id,
                node.canonical_name,
                node.claim_id,
                node.name,
                node.title
            )
        ] AS node_path
        LIMIT 5
        """
        with self.driver.session() as session:
            result = session.run(
                query,
                entity_id_a=entity_id_a,
                entity_id_b=entity_id_b,
            )
            return [record["node_path"] for record in result]

    # ── Stats ─────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, int]:
        """Get basic corpus statistics."""
        query = """
        OPTIONAL MATCH (p:Paper)
        WITH count(p) AS papers
        OPTIONAL MATCH (m:Method)
        WITH papers, count(m) AS methods
        OPTIONAL MATCH (c:Claim)
        WITH papers, methods, count(c) AS claims
        OPTIONAL MATCH (a:Author)
        RETURN papers, methods, claims, count(a) AS authors
        """
        with self.driver.session() as session:
            record = session.run(query).single()
            if not record:
                return {
                    "papers": 0,
                    "methods": 0,
                    "claims": 0,
                    "authors": 0,
                }
            return dict(record)

    def get_graph_data(self, limit: int = 50) -> dict[str, list]:
        """Return nodes and edges for graph visualization."""
        query = """
        MATCH (p:Paper)
        WITH p LIMIT $limit
        OPTIONAL MATCH (p)-[:PROPOSES]->(m:Method)
        OPTIONAL MATCH (p)-[:SUPPORTS]->(c:Claim)
        OPTIONAL MATCH (a:Author)-[:AUTHORED]->(p)
        RETURN p.paper_id AS paper_id,
               p.title AS paper_title,
               p.year AS year,
               collect(DISTINCT {
                 name: m.canonical_name,
                 category: m.category
               }) AS methods,
               collect(DISTINCT {
                 id: c.claim_id,
                 statement: c.statement
               }) AS claims,
               collect(DISTINCT a.name_key) AS authors
        """
        nodes = []
        edges = []
        seen_methods = set()
        seen_claims = set()
        seen_authors = set()

        with self.driver.session() as session:
            records = session.run(query, limit=limit)
            for rec in records:
                pid = rec["paper_id"]
                title = rec["paper_title"] or "Untitled"
                short_title = (title[:40] + "...") if len(title) > 40 else title

                # Paper node
                nodes.append(
                    {
                        "id": pid,
                        "label": short_title,
                        "type": "paper",
                        "year": rec["year"],
                    }
                )

                # Method nodes + edges
                for m in rec["methods"]:
                    mname = m.get("name")
                    if not mname:
                        continue
                    if mname not in seen_methods:
                        nodes.append(
                            {
                                "id": f"m:{mname}",
                                "label": mname,
                                "type": "method",
                                "category": m.get("category", ""),
                            }
                        )
                        seen_methods.add(mname)
                    edges.append(
                        {
                            "from": pid,
                            "to": f"m:{mname}",
                            "label": "PROPOSES",
                        }
                    )

                # Claim nodes + edges
                for c in rec["claims"]:
                    cid = c.get("id")
                    if not cid:
                        continue
                    if cid not in seen_claims:
                        stmt = c.get("statement", "")
                        short_stmt = (stmt[:50] + "...") if len(stmt) > 50 else stmt
                        nodes.append(
                            {
                                "id": f"c:{cid}",
                                "label": short_stmt,
                                "type": "claim",
                            }
                        )
                        seen_claims.add(cid)
                    edges.append(
                        {
                            "from": pid,
                            "to": f"c:{cid}",
                            "label": "SUPPORTS",
                        }
                    )

                # Author nodes + edges
                for aname in rec["authors"]:
                    if not aname:
                        continue
                    if aname not in seen_authors:
                        nodes.append(
                            {
                                "id": f"a:{aname}",
                                "label": aname,
                                "type": "author",
                            }
                        )
                        seen_authors.add(aname)
                    edges.append(
                        {
                            "from": f"a:{aname}",
                            "to": pid,
                            "label": "AUTHORED",
                        }
                    )

        return {"nodes": nodes, "edges": edges}
