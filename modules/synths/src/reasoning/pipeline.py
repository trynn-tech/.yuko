#!/usr/bin/env python3
# modules/synths/src/reasoning/pipeline.py

from typing import Any, Dict, Optional

from memory import RedisMemoryStore
from memory import ThoughtFrame
from reasoning.embedder import FeatureEmbedder
from reasoning.graph_linker import KnowledgeGraphLinker


class ReasoningOrchestrator:
    """
    Central orchestration engine for the 3-Tier Memory Architecture:
    1. Vectorizes ThoughtFrame code & instruction via BERT FeatureEmbedder.
    2. Persists JSON & vectors in Redis Memory Store (RediSearch).
    3. Maps AST topology relationships into the Neo4j Knowledge Graph.
    """

    def __init__(
        self,
        embedder: Optional[FeatureEmbedder] = None,
        redis_store: Optional[RedisMemoryStore] = None,
        graph_linker: Optional[KnowledgeGraphLinker] = None,
    ):
        self.embedder = embedder or FeatureEmbedder()
        self.redis_store = redis_store or RedisMemoryStore()
        self.graph_linker = graph_linker or KnowledgeGraphLinker()

    def process_and_store(self, frame: ThoughtFrame) -> Dict[str, Any]:
        """Runs the full vectorization, cache persistence, and Neo4j graph sync loop."""
        results = {
            "session_id": frame.session_id,
            "embedded": False,
            "redis_saved": False,
            "graph_synced": False,
        }

        # 1. Vectorize instruction and code snippet via BERT / Embedder
        vector = None
        try:
            target_text = frame.extracted_code or frame.instruction
            if target_text.strip():
                vector = self.embedder.encode(target_text)
                results["embedded"] = len(vector) > 0
        except Exception as e:
            results["embedded"] = False

        # 2. Persist in Redis Working Memory (with RediSearch vector embedding payload)
        try:
            results["redis_saved"] = self.redis_store.save_thought_frame(frame, vector=vector)
        except Exception:
            results["redis_saved"] = False

        # 3. Synchronize Graph Nodes and AST Topology in Neo4j
        try:
            results["graph_synced"] = self.graph_linker.sync_thought_frame_graph(
                frame.model_dump()
            )
        except Exception:
            results["graph_synced"] = False

        return results
