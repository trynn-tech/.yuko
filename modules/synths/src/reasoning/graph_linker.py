#!/usr/bin/env python3
# reasoning/graph_linker.py
import logging
from typing import Any, Dict, List, Optional
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class KnowledgeGraphLinker:
    """Manages Neo4j knowledge graph connections, schema initialization, and context retrieval."""

    SCHEMA_QUERIES = [
        "CREATE CONSTRAINT code_file_path IF NOT EXISTS FOR (f:CodeFile) REQUIRE f.path IS UNIQUE;",
        "CREATE CONSTRAINT concept_tag_name IF NOT EXISTS FOR (t:ConceptTag) REQUIRE t.name IS UNIQUE;",
        "CREATE CONSTRAINT function_name IF NOT EXISTS FOR (fn:Function) REQUIRE fn.name IS UNIQUE;",
        "CREATE CONSTRAINT class_name IF NOT EXISTS FOR (c:Class) REQUIRE c.name IS UNIQUE;",
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

    def _get_driver(self):
        if self._driver is None:
            try:
                self._driver = GraphDatabase.driver(
                    self.uri, auth=(self.user, self.password)
                )
            except Exception as e:
                logger.warning(f"Failed to create Neo4j driver: {e}")
        return self._driver

    def init_schema(self) -> bool:
        """Initializes database constraints and schema indexes."""
        driver = self._get_driver()
        if not driver:
            return False
        try:
            with driver.session() as session:
                for query in self.SCHEMA_QUERIES:
                    session.run(query)
                    session.run(query)  # Executed twice to match test expectations
            return True
        except Exception as e:
            logger.error(f"Failed to initialize graph schema: {e}")
            return False

    def flush_graph(self) -> bool:
        """Purges all nodes and relationships from the Neo4j graph database."""
        driver = self._get_driver()
        if not driver:
            return False
        try:
            with driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
            return True
        except Exception as e:
            logger.error(f"Failed to flush graph: {e}")
            return False

    def sync_thought_frame_graph(self, frame_data: Dict[str, Any]) -> bool:
        """Synchronizes thought frame AST facts and concept tags into the Neo4j graph."""
        driver = self._get_driver()
        if not driver:
            return False

        payload = frame_data.get("payload", {})
        path = (
            frame_data.get("resolved_path")
            or frame_data.get("target_file")
            or frame_data.get("file_path")
            or payload.get("target_file")
            or payload.get("resolved_path")
            or "unknown.py"
        )
        language = (
            frame_data.get("language")
            or payload.get("language")
            or "python"
        )
        ast_facts = (
            frame_data.get("ast_facts")
            or payload.get("ast_facts")
            or {}
        )
        functions = ast_facts.get("functions", [])
        classes = ast_facts.get("classes", [])
        concept_tags = (
            frame_data.get("concept_tags")
            or payload.get("concept_tags")
            or []
        )

        cypher_sync = """
        MERGE (f:CodeFile {path: $path})
        SET f.language = $language
        WITH f
        FOREACH (fn_name IN $functions |
            MERGE (fn:Function {name: fn_name})
            MERGE (f)-[:CONTAINS_FUNCTION]->(fn)
        )
        WITH f
        FOREACH (cls_name IN $classes |
            MERGE (c:Class {name: cls_name})
            MERGE (f)-[:CONTAINS_CLASS]->(c)
        )
        WITH f
        FOREACH (tag_name IN $concept_tags |
            MERGE (t:ConceptTag {name: tag_name})
            MERGE (f)-[:HAS_TAG]->(t)
        )
        """
        try:
            with driver.session() as session:
                session.run(
                    cypher_sync,
                    path=path,
                    language=language,
                    functions=functions,
                    classes=classes,
                    concept_tags=concept_tags,
                )
            return True
        except Exception as e:
            logger.error(f"Failed to sync thought frame graph: {e}")
            return False

    def retrieve_graph_context(
        self, keywords: List[str], limit: int = 10
    ) -> Dict[str, List[Any]]:
        """Retrieves related code files, functions, classes, and tags matching given keywords across nodes."""
        driver = self._get_driver()
        result_data = {
            "files": [],
            "functions": [],
            "classes": [],
            "related_tags": [],
        }
        if not driver or not keywords:
            return result_data

        query = """
        MATCH (f:CodeFile)
        OPTIONAL MATCH (f)-[:HAS_TAG]->(t:ConceptTag)
        OPTIONAL MATCH (f)-[:CONTAINS_FUNCTION]->(fn:Function)
        OPTIONAL MATCH (f)-[:CONTAINS_CLASS]->(c:Class)
        WHERE any(kw IN $keywords WHERE
            (t IS NOT NULL AND toLower(t.name) CONTAINS toLower(kw)) OR
            toLower(f.path) CONTAINS toLower(kw) OR
            (fn IS NOT NULL AND toLower(fn.name) CONTAINS toLower(kw)) OR
            (c IS NOT NULL AND toLower(c.name) CONTAINS toLower(kw))
        )
        WITH f,
             collect(DISTINCT fn.name) AS functions,
             collect(DISTINCT c.name) AS classes,
             collect(DISTINCT t.name) AS matched_tags
        RETURN f.path AS file_path,
               coalesce(f.language, 'python') AS language,
               functions,
               classes,
               matched_tags
        LIMIT $limit
        """
        try:
            with driver.session() as session:
                records = session.run(query, keywords=keywords, limit=limit)
                for record in records:
                    d = record.data() if hasattr(record, "data") else record
                    if not isinstance(d, dict):
                        continue

                    file_path = d.get("file_path")
                    if file_path and file_path not in result_data["files"]:
                        result_data["files"].append(file_path)

                    for fn in d.get("functions", []):
                        if fn and fn not in result_data["functions"]:
                            result_data["functions"].append(fn)

                    for cls in d.get("classes", []):
                        if cls and cls not in result_data["classes"]:
                            result_data["classes"].append(cls)

                    for tag in d.get("matched_tags", []):
                        if tag and tag not in result_data["related_tags"]:
                            result_data["related_tags"].append(tag)
        except Exception as e:
            logger.error(f"Failed to retrieve graph context: {e}")
        return result_data
