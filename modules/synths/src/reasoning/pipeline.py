#!/usr/bin/env python3
# modules/synths/src/reasoning/pipeline.py

from typing import Any, Dict, Optional
from engine.redis_store import RedisMemoryStore
from engine.working_memory import ThoughtFrame
from reasoning.embedder import FeatureEmbedder
from reasoning.graph_linker import KnowledgeGraphLinker


class ReasoningOrchestrator:
    """
    Central orchestration engine for the 3-Tier Memory Architecture:
    1. Vectorizes ThoughtFrame code & instruction via BERT FeatureEmbedder.
    2. Persists JSON & vectors in Redis Memory Store.
    3. Maps relationships into Neo4j Knowledge Graph.
    """

    def __init__(self):
        self.embedder = FeatureEmbedder()
        self.redis_store = RedisMemoryStore()
        self.graph_linker = KnowledgeGraphLinker()

    def process_and_store(self, frame: ThoughtFrame) -> Dict[str, Any]:
        """Runs the full vectorization, cache persistence, and graph sync loop."""
        results = {
            "session_id": frame.session_id,
            "embedded": False,
            "redis_saved": False,
            "graph_synced": False,
        }

        # 1. Vectorize instruction and code snippet via BERT / Embedder
        try:
            vector = self.embedder.encode(frame.extracted_code or frame.instruction)
            results["embedded"] = len(vector) > 0
        except Exception:
            results["embedded"] = False

        # 2. Persist in Redis Working Memory
        results["redis_saved"] = self.redis_store.save_thought_frame(frame)

        # 3. Synchronize Graph Nodes in Neo4j
        results["graph_synced"] = self.graph_linker.sync_thought_frame_graph(
            frame.model_dump()
        )

        return results
