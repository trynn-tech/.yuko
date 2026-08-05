#!/usr/bin/env python3
# modules/synths/src/reasoning/graph_linker.py

from typing import Any, Dict, List, Optional

try:
    from neo4j import GraphDatabase

    HAS_NEO4J = True
except ImportError:
    HAS_NEO4J = False


class KnowledgeGraphLinker:
    """Neo4j Graph Database Driver & Schema Engine.

    Maps file structures, AST facts, and documentation relationships.
    """

    # -------------------------------------------------------------------
    # CYPHER SCHEMA INITIALIZATION QUERIES (Neo4j 5.x Syntax)
    # Enforces node uniqueness and builds range indexes on startup.
    # -------------------------------------------------------------------
    SCHEMA_QUERIES = [
        # 1. Unique constraint & index for CodeFile nodes on 'path'
        """
        CREATE CONSTRAINT code_file_path_unique IF NOT EXISTS
        FOR (f:CodeFile) REQUIRE f.path IS UNIQUE
        """,
        # 2. Unique constraint & index for Function nodes on composite 'id' (file:name)
        """
        CREATE CONSTRAINT function_id_unique IF NOT EXISTS
        FOR (fn:Function) REQUIRE fn.id IS UNIQUE
        """,
        # 3. Lookup index for ConceptTag nodes on 'name'
        """
        CREATE INDEX concept_tag_name_idx IF NOT EXISTS
        FOR (t:ConceptTag) ON (t.name)
        """,
    ]

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "password",
    ):
        self.uri = uri
        self.user = user
        self.password = password
        self._driver = None
        self._initialized = False

    def _get_driver(self):
        if self._driver is None:
            if not HAS_NEO4J:
                raise ImportError("neo4j Python driver is required.")
            self._driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )

        # Ensure init_schema doesn't trigger recursive _get_driver calls
        if not self._initialized:
            self._initialized = True
            self.init_schema()

        return self._driver

    def init_schema(self) -> bool:
        """Runs Cypher initialization queries to set up database constraints and indexes."""
        try:
            driver = self._get_driver()
            with driver.session() as session:
                for query in self.SCHEMA_QUERIES:
                    session.run(query)
            return True
        except Exception:
            # Degrade gracefully if service is still warming up or unreachable
            return False

    def sync_thought_frame_graph(self, frame_data: Dict[str, Any]) -> bool:
        """Translates AST facts and file resolution paths into graph nodes and relationships.

        Leverages constraints for fast MERGE operations.
        """
        try:
            driver = self._get_driver()
            resolved_path = frame_data.get("resolved_path", "unknown")
            funcs = frame_data.get("ast_facts", {}).get("functions", [])
            tags = frame_data.get("concept_tags", [])

            # Prepare structured payload for Cypher execution
            func_nodes = [
                {"name": name, "id": f"{resolved_path}:{name}"} for name in funcs
            ]

            cypher_query = """
            MERGE (f:CodeFile {path: $path})
            SET f.language = $lang, 
                f.last_updated = timestamp()

            WITH f
            UNWIND $funcs AS func_data
            MERGE (fn:Function {id: func_data.id})
            SET fn.name = func_data.name, 
                fn.file = $path
            MERGE (f)-[:CONTAINS_FUNCTION]->(fn)

            WITH f
            UNWIND $tags AS tag_name
            MERGE (t:ConceptTag {name: tag_name})
            MERGE (f)-[:HAS_TAG]->(t)
            """

            with driver.session() as session:
                session.run(
                    cypher_query,
                    path=resolved_path,
                    lang=frame_data.get("language", "text"),
                    funcs=func_nodes,
                    tags=tags,
                )
            return True
        except Exception:
            return False

    def retrieve_graph_context(
        self, keywords: List[str], limit: int = 5
    ) -> Dict[str, Any]:
        """Traverses the graph to find relevant structural context based on input keywords.

        Returns matching files, contained functions, and associated concept tags.
        """
        if not keywords:
            return {
                "files": [],
                "functions": [],
                "related_tags": [],
                "records": [],
            }

        cypher_query = """
        MATCH (t:ConceptTag)
        WHERE any(kw IN $keywords WHERE toLower(t.name) CONTAINS toLower(kw))
        MATCH (f:CodeFile)-[:HAS_TAG]->(t)
        OPTIONAL MATCH (f)-[:CONTAINS_FUNCTION]->(fn:Function)
        
        WITH f, collect(DISTINCT fn.name) AS functions, collect(DISTINCT t.name) AS matched_tags
        RETURN f.path AS file_path, 
               f.language AS language, 
               functions, 
               matched_tags
        LIMIT $limit
        """

        try:
            driver = self._get_driver()
            with driver.session() as session:
                result = session.run(cypher_query, keywords=keywords, limit=limit)
                records = [record.data() for record in result]

            files = []
            functions = []
            tags = set()

            for rec in records:
                files.append(rec["file_path"])
                functions.extend(rec["functions"])
                tags.update(rec["matched_tags"])

            return {
                "files": list(set(files)),
                "functions": list(set(functions)),
                "related_tags": list(tags),
                "records": records,
            }
        except Exception:
            return {
                "files": [],
                "functions": [],
                "related_tags": [],
                "records": [],
            }

    def flush_graph(self) -> bool:
        """Deletes all nodes and relationships from the active Neo4j database."""
        try:
            driver = self._get_driver()
            with driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
            return True
        except Exception:
            return False

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None
