# src/memory/thoughtframe_collection.py
import json
import logging
from typing import Any, Dict, List, Optional
import redis
from redis.commands.search.field import (
    NumericField,
    TagField,
    TextField,
    VectorField,
)
from redis.commands.search.index_definition import IndexDefinition, IndexType
from .schemas import ThoughtFrame, CreationPayload, EditPayload

logger = logging.getLogger(__name__)


class ThoughtFrameFactory:
    """Specialized factory for instantiating typed ThoughtFrame instances."""

    @classmethod
    def create(
        cls,
        session_id: str,
        instruction: str,
        language: str = "python",
        intent_type: str = "patch",
        target_file: str = "src/dummy.py",
        raw_prompt: Optional[str] = None,
        vector: Optional[List[float]] = None,
        ast_facts: Optional[Dict[str, Any]] = None,
    ) -> ThoughtFrame:
        """Generic factory method for standard test and runtime initialization."""
        prompt = raw_prompt or instruction
        payload = CreationPayload(
            created_content=instruction,
            file_bytes=len(instruction.encode("utf-8")),
            total_lines_created=len(instruction.splitlines()) or 1,
        )
        return ThoughtFrame(
            session_id=session_id,
            target_file=target_file,
            raw_prompt=prompt,
            instruction=instruction,
            language=language,
            intent_type=intent_type,
            payload_type="CREATE",
            payload=payload,
            vector=vector or [],
            ast_facts=ast_facts or {},
        )

    @staticmethod
    def create_creation_frame(
        session_id: str,
        target_file: str,
        created_content: str,
        raw_prompt: str,
        ast_facts: Optional[Dict[str, Any]] = None,
    ) -> ThoughtFrame:
        payload = CreationPayload(
            created_content=created_content,
            file_bytes=len(created_content.encode("utf-8")),
            total_lines_created=len(created_content.splitlines()) or 1,
        )
        return ThoughtFrame(
            session_id=session_id,
            target_file=target_file,
            raw_prompt=raw_prompt,
            instruction=raw_prompt,
            payload_type="CREATE",
            payload=payload,
            ast_facts=ast_facts or {},
        )

    @staticmethod
    def create_edit_frame(
        session_id: str,
        target_file: str,
        original_content: str,
        updated_content: str,
        raw_prompt: str,
        ast_facts: Optional[Dict[str, Any]] = None,
    ) -> ThoughtFrame:
        orig_lines = original_content.splitlines()
        upd_lines = updated_content.splitlines()
                
        payload = EditPayload(
            original_content=original_content,
            updated_content=updated_content,
            original_line_count=len(orig_lines),
            updated_line_count=len(upd_lines),
            lines_added=max(0, len(upd_lines) - len(orig_lines)),
            lines_removed=max(0, len(orig_lines) - len(upd_lines)),
        )
        return ThoughtFrame(
            session_id=session_id,
            target_file=target_file,
            raw_prompt=raw_prompt,
            instruction=raw_prompt,
            payload_type="EDIT",
            payload=payload,
            ast_facts=ast_facts or {},
        )


class ThoughtFrameCollection:
    """Data Access Object managing RediSearch HNSW indices and Redis Hash operations."""

    def __init__(self, client: redis.Redis, index_name: str = "idx:thought_frames"):
        self.client = client
        self.index_name = index_name

    def ensure_index(self) -> None:
        """Idempotently builds the RediSearch index schema for vector and metadata search."""
        try:
            self.client.ft(self.index_name).info()
            logger.debug("RediSearch index '%s' already exists.", self.index_name)
        except Exception:
            logger.info("Creating RediSearch index '%s'...", self.index_name)
            schema = (
                TagField("$.session_id", as_name="session_id"),
                TagField("$.payload_type", as_name="payload_type"),
                TextField("$.target_file", as_name="target_file"),
                VectorField(
                    "$.vector",
                    "HNSW",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": 768,
                        "DISTANCE_METRIC": "COSINE",
                        "INITIAL_CAP": 1000,
                    },
                    as_name="vector",
                ),
            )
            definition = IndexDefinition(prefix=["frame:"], index_type=IndexType.HASH)
            try:
                self.client.ft(self.index_name).create_index(schema, definition=definition)
            except Exception as e:
                logger.error("Failed to create RediSearch index: %s", e)

    def add(self, frame: ThoughtFrame, vector: Optional[List[float]] = None) -> bool:
        """Alias for insert to match collection test workflows."""
        return self.insert(frame, vector=vector or getattr(frame, "vector", None))

    def insert(self, frame: ThoughtFrame, vector: Optional[List[float]] = None) -> bool:
       """Persists the frame into a Redis Hash under key `frame:<session_id>`."""
       key = f"frame:{frame.session_id}"
       mapping = {
           "session_id": frame.session_id,
           "target_file": frame.target_file,
           "raw_prompt": frame.raw_prompt,
           "payload_type": frame.payload_type,
           "payload": json.dumps(
               frame.payload.model_dump()
               if hasattr(frame.payload, "model_dump")
               else (frame.payload.dict() if hasattr(frame.payload, "dict") else frame.payload)
           ),
           "ast_facts": json.dumps(frame.ast_facts),
           "timestamp": getattr(frame, "timestamp", 0.0),
       }

       vec = vector or getattr(frame, "vector", None)
       if vec:
           import numpy as np
           # Convert to float32 numpy array and flatten any residual dimensions down to 1D
           np_vec = np.array(vec, dtype=np.float32).flatten()
           mapping["vector"] = np_vec.tobytes()

       self.client.hset(key, mapping=mapping)
       return True

    def get_by_id(self, session_id: str) -> Optional[ThoughtFrame]:
        key = f"frame:{session_id}"
        data = self.client.hgetall(key)
        if not data:
            return None
                
        decoded = {k.decode("utf-8") if isinstance(k, bytes) else k: v.decode("utf-8") if isinstance(v, bytes) else v for k, v in data.items()}
        payload_dict = json.loads(decoded.get("payload", "{}"))
        payload_type = decoded.get("payload_type", "CREATE")
        if payload_type == "EDIT":
            payload = EditPayload(**payload_dict)
        else:
            payload = CreationPayload(**payload_dict)
            
        return ThoughtFrame(
            session_id=decoded["session_id"],
            target_file=decoded["target_file"],
            raw_prompt=decoded.get("raw_prompt", ""),
            payload_type=payload_type,
            payload=payload,
            ast_facts=json.loads(decoded.get("ast_facts", "{}")),
        )

    def search_knn(self, vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """Alias matching search_knn test assertions."""
        return self.vector_search(vector, k=top_k)

    def vector_search(self, vector: List[float], k: int = 5) -> List[Dict[str, Any]]:
        """Executes KNN search against RediSearch index."""
        import numpy as np
        from redis.commands.search.query import Query
        query_vec = np.array(vector, dtype=np.float32).tobytes()
        q = Query(f"*=>[KNN {k} @vector $vec AS score]").sort_by("score").paging(0, k).return_fields("session_id", "target_file", "score").dialect(2)
        res = self.client.ft(self.index_name).search(q, query_params={"vec": query_vec})
                
        results = []
        for doc in res.docs:
            results.append({
                "session_id": getattr(doc, "session_id", ""),
                "target_file": getattr(doc, "target_file", ""),
                "score": float(getattr(doc, "score", 0.0)),
            })
        return results
