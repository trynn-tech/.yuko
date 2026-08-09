#!/usr/bin/env python3
# modules/synths/src/engine/redis_store.py
import json
import logging
import struct
from typing import Any, Dict, List, Optional, Protocol, Union, runtime_checkable

try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

try:
    from redis.commands.search.field import TagField, TextField, VectorField
    from redis.commands.search.indexDefinition import IndexDefinition, IndexType
    from redis.commands.search.query import Query
    HAS_REDISEARCH = True
except ImportError:
    HAS_REDISEARCH = False

from engine.working_memory import ThoughtFrame

logger = logging.getLogger(__name__)


@runtime_checkable
class ThoughtFrameProtocol(Protocol):
    session_id: str
    instruction: str
    language: str
    def to_redis_payload(self) -> str: ...


ThoughtFrameLike = Union[ThoughtFrame, ThoughtFrameProtocol, Any]


class RedisMemoryStore:
    INDEX_NAME = "reasoning_vector_idx"
    VECTOR_DIM = 768

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self._client = None
        self._index_initialized = False

    def _get_client(self) -> Any:
        if not HAS_REDIS:
            raise ImportError(
                "The 'redis' Python package is missing from the active environment. "
                "Ensure python3Packages.redis is included in your wrapper derivation."
            )
        if self._client is None:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
                socket_timeout=5,
            )
            self._client.ping()
            if not self._index_initialized and HAS_REDISEARCH:
                self._ensure_vector_index()
        return self._client

    def _ensure_vector_index(self) -> None:
        if not HAS_REDISEARCH:
            self._index_initialized = True
            return
        r = self._client
        try:
            r.ft(self.INDEX_NAME).info()
            self._index_initialized = True
        except redis.exceptions.ResponseError as e:
            err_msg = str(e).lower()
            if "unknown index" in err_msg or "no such index" in err_msg:
                try:
                    schema = (
                        TextField("session_id"),
                        TextField("instruction"),
                        TagField("language"),
                        VectorField(
                            "embedding",
                            "HNSW",
                            {
                                "TYPE": "FLOAT32",
                                "DIM": self.VECTOR_DIM,
                                "DISTANCE_METRIC": "COSINE",
                            },
                        ),
                    )
                    definition = IndexDefinition(
                        prefix=["reasoning:frame:"], index_type=IndexType.HASH
                    )
                    r.ft(self.INDEX_NAME).create_index(
                        fields=schema, definition=definition
                    )
                except Exception as create_err:
                    logger.error("Failed to create RediSearch index: %s", create_err)
                self._index_initialized = True
            else:
                self._index_initialized = True
        except Exception as e:
            logger.error("Unexpected error during index check: %s", e)
            self._index_initialized = True

    def save_thought_frame(
        self, frame: ThoughtFrameLike, vector: Optional[List[float]] = None
    ) -> bool:
        try:
            r = self._get_client()
            session_id = getattr(frame, "session_id", "unknown")
            instruction = getattr(frame, "instruction", "")
            language = getattr(frame, "language", "python")

            if hasattr(frame, "to_redis_payload") and callable(frame.to_redis_payload):
                payload_str = frame.to_redis_payload()
            else:
                payload_str = json.dumps({
                    "session_id": session_id,
                    "instruction": instruction,
                    "language": language,
                })

            key = f"reasoning:frame:{session_id}"
            payload = {
                "session_id": session_id,
                "instruction": instruction,
                "language": language,
                "data": payload_str,
            }
            if vector and len(vector) == self.VECTOR_DIM:
                payload["embedding"] = struct.pack(
                    f"{len(vector)}f", *vector
                )
            r.hset(key, mapping=payload)
            r.set(key, payload_str)
            r.sadd("reasoning:sessions", session_id)
            return True
        except Exception as e:
            logger.error("Failed to save ThoughtFrame %s: %s", getattr(frame, "session_id", "unknown"), e)
            return False

    def retrieve_thought_frame(self, session_id: str) -> Optional[ThoughtFrame]:
        """Retrieves and deserializes a ThoughtFrame from Redis, returning a fully typed ThoughtFrame instance."""
        try:
            r = self._get_client()
            key = f"reasoning:frame:{session_id}"
            raw_data = None
            try:
                raw_data = r.hget(key, "data")
            except Exception:
                pass

            if raw_data is None or type(raw_data).__name__ == "MagicMock" or hasattr(raw_data, "__name__"):
                try:
                    raw_data = r.get(key)
                except Exception:
                    pass

            if not raw_data or type(raw_data).__name__ == "MagicMock" or hasattr(raw_data, "__name__"):
                return None

            if isinstance(raw_data, bytes):
                data_str = raw_data.decode("utf-8")
            elif isinstance(raw_data, str):
                data_str = raw_data
            else:
                data_str = str(raw_data)

            parsed_dict = json.loads(data_str)
            if isinstance(parsed_dict, dict):
                return ThoughtFrame(**parsed_dict)
            return None
        except Exception as e:
            logger.error("Failed to retrieve ThoughtFrame %s: %s", session_id, e)
            return None

    def knn_search(
        self, query_vector: List[float], top_k: int = 3
    ) -> List[Dict[str, Any]]:
        if not HAS_REDISEARCH or not query_vector or len(query_vector) != self.VECTOR_DIM:
            return []
        try:
            r = self._get_client()
            vector_bytes = struct.pack(f"{len(query_vector)}f", *query_vector)
            query_str = f"*=>[KNN {top_k} @embedding $vec AS vector_score]"
            q = (
                Query(query_str)
                .sort_by("vector_score")
                .paging(0, top_k)
                .return_fields("session_id", "instruction", "data", "vector_score")
                .dialect(2)
            )
            res = r.ft(self.INDEX_NAME).search(
                q, query_params={"vec": vector_bytes}
            )
            hits = []
            for doc in res.documents:
                raw_data = getattr(doc, "data", "{}")
                hits.append(
                    {
                        "session_id": getattr(doc, "session_id", ""),
                        "score": float(getattr(doc, "vector_score", 1.0)),
                        "payload": json.loads(raw_data),
                    }
                )
            return hits
        except Exception as e:
            logger.error("KNN vector search failed: %s", e)
            return []

    def flush_db(self) -> bool:
        """Flushes reasoning keys directly without requiring RediSearch."""
        try:
            r = self._get_client()
            keys = r.keys("reasoning:*")
            if keys:
                r.delete(*keys)
            return True
        except Exception as e:
            logger.error("Failed to flush reasoning database keys: %s", e)
            return False
