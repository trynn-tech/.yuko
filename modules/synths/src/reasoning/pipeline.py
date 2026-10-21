#!/usr/bin/env python3
# modules/synths/src/reasoning/pipeline.py

from typing import Any, Dict, Optional
from memory import RedisMemoryStore, ThoughtFrame
from reasoning.embedder import FeatureEmbedder
from reasoning.graph_linker import KnowledgeGraphLinker


class ReasoningOrchestrator:
    """Central orchestration engine for the 3-Tier Memory Architecture:

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
            "session_id": getattr(frame, "session_id", "N/A"),
            "embedded": False,
            "redis_saved": False,
            "graph_synced": False,
        }

        # 0. Convert frame to dictionary safely
        if hasattr(frame, "model_dump"):
            frame_dict = frame.model_dump()
        elif hasattr(frame, "to_dict"):
            frame_dict = frame.to_dict()
        elif isinstance(frame, dict):
            frame_dict = frame
        else:
            frame_dict = getattr(frame, "__dict__", {})

        # Normalize target file & code payload for downstream vectorization and graph linking
        payload = frame_dict.get("payload", {})
        target_file = (
            frame_dict.get("resolved_path")
            or frame_dict.get("target_file")
            or payload.get("target_file")
            or "src/main.py"
        )
        extracted_code = (
            frame_dict.get("extracted_code")
            or payload.get("updated_content")
            or payload.get("created_content")
            or frame_dict.get("raw_response", "")
        )

        frame_dict["resolved_path"] = target_file
        frame_dict["target_file"] = target_file
        frame_dict["extracted_code"] = extracted_code

        # 1. Vectorize instruction and code snippet via BERT / Embedder
        vector = None
        try:
            instruction = frame_dict.get("instruction") or frame_dict.get(
                "raw_prompt", ""
            )
            target_text = extracted_code or instruction
            if target_text.strip():
                vector = self.embedder.encode(target_text)
                results["embedded"] = bool(
                    vector is not None and len(vector) > 0
                )
        except Exception:
            results["embedded"] = False

        # 2. Persist in Redis Working Memory (with RediSearch vector embedding payload)
        try:
            results["redis_saved"] = self.redis_store.save_thought_frame(
                frame, vector=vector
            )
        except Exception:
            results["redis_saved"] = False

        # 3. Synchronize Graph Nodes and AST Topology in Neo4j
        try:
            results["graph_synced"] = self.graph_linker.sync_thought_frame_graph(
                frame_dict
            )
        except Exception:
            results["graph_synced"] = False

        return results
