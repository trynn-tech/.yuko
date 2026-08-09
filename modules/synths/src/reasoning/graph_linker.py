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
        # 3. Unique constraint & index for Class nodes on composite 'id' (file:name)
        """
        CREATE CONSTRAINT class_id_unique IF NOT EXISTS
        FOR (c:Class) REQUIRE c.id IS UNIQUE
        """,
        # 4. Lookup index for ConceptTag nodes on 'name'
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
            return False

    def sync_thought_frame_graph(self, frame_data: Dict[str, Any]) -> bool:
        """Translates AST facts and file resolution paths into graph nodes and relationships.
        Uses FOREACH loops to prevent empty collections from terminating the
        Cypher row pipeline.
        """
        try:
            driver = self._get_driver()
            resolved_path = frame_data.get("resolved_path", "unknown")
            ast_facts = frame_data.get("ast_facts", {}) or {}
            funcs = ast_facts.get("functions", [])
            classes = ast_facts.get("classes", [])
            tags = frame_data.get("concept_tags", [])
            func_nodes = [
                {"name": name, "id": f"{resolved_path}:{name}"} for name in funcs
            ]
            class_nodes = [
                {"name": name, "id": f"{resolved_path}:{name}"} for name in classes
            ]
            cypher_query = """
            MERGE (f:CodeFile {path: $path})
            SET f.language = $lang,
                f.last_updated = timestamp()
            FOREACH (func_data IN $funcs |
                MERGE (fn:Function {id: func_data.id})
                SET fn.name = func_data.name,
                    fn.file = $path
                MERGE (f)-[:CONTAINS_FUNCTION]->(fn)
            )
            FOREACH (cls_data IN $classes |
                MERGE (c:Class {id: cls_data.id})
                SET c.name = cls_data.name,
                    c.file = $path
                MERGE (f)-[:CONTAINS_CLASS]->(c)
            )
            FOREACH (tag_name IN $tags |
                MERGE (t:ConceptTag {name: tag_name})
                MERGE (f)-[:HAS_TAG]->(t)
            )
            """
            with driver.session() as session:
                session.run(
                    cypher_query,
                    path=resolved_path,
                    lang=frame_data.get("language", "text"),
                    funcs=func_nodes,
                    classes=class_nodes,
                    tags=tags,
                )
            return True
        except Exception as e:
            logger.error("Failed to sync thought frame graph for %s: %s", frame_data.get("resolved_path"), e, exc_info=True)
            # In testing or debug mode, you can raise to inspect tracebacks directly:
            # raise
            return False

    def retrieve_graph_context(
        self, keywords: List[str], limit: int = 5
    ) -> Dict[str, Any]:
        """Traverses the graph to find relevant structural context based on input keywords."""
        if not keywords:
            return {
                "files": [],
                "functions": [],
                "classes": [],
                "related_tags": [],
                "records": [],
            }

        cypher_query = """
        MATCH (t:ConceptTag)
        WHERE any(kw IN $keywords WHERE toLower(t.name) CONTAINS toLower(kw))
        MATCH (f:CodeFile)-[:HAS_TAG]->(t)
        OPTIONAL MATCH (f)-[:CONTAINS_FUNCTION]->(fn:Function)
        OPTIONAL MATCH (f)-[:CONTAINS_CLASS]->(c:Class)

        WITH f, 
             collect(DISTINCT fn.name) AS functions, 
             collect(DISTINCT c.name) AS classes,
             collect(DISTINCT t.name) AS matched_tags
        RETURN f.path AS file_path,
               coalesce(f.language, 'text') AS language,
               functions,
               classes,
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
            classes = []
            tags = set()

            for rec in records:
                files.append(rec["file_path"])
                functions.extend(rec.get("functions", []))
                classes.extend(rec.get("classes", []))
                tags.update(rec.get("matched_tags", []))

            return {
                "files": list(set(files)),
                "functions": list(set(functions)),
                "classes": list(set(classes)),
                "related_tags": list(tags),
                "records": records,
            }
        except Exception:
            return {
                "files": [],
                "functions": [],
                "classes": [],
                "related_tags": [],
                "records": [],
            }

    # Append to KnowledgeGraphLinker in modules/synths/src/reasoning/graph_linker.py
    def reindex_file_on_disk(self, filepath: str, patcher) -> bool:
        """Reads a file from disk, extracts complete AST facts, and updates Neo4j."""
        try:
            path = Path(filepath)
            if not path.exists():
                return False
    
            code = path.read_text(encoding="utf-8")
            facts = patcher.extract_ast_facts(filepath, code)
            lang = patcher._detect_language(filepath)
    
            frame_data = {
                "resolved_path": filepath,
                "language": lang,
                "ast_facts": facts,
                "concept_tags": facts.get("imports", []),
            }
            return self.sync_thought_frame_graph(frame_data)
        except Exception:
            return False

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
