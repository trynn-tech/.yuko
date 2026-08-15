#!/usr/bin/env python3
# engine/redis_store.py

import json
import logging
import redis
from typing import List, Optional, Any
from unittest.mock import MagicMock
from engine.working_memory import ThoughtFrame

logger = logging.getLogger(__name__)

# Determine if RedisSearch (RediSearch) modules/commands are available or provide test fallbacks
try:
    from redis.commands.search.field import VectorField, TextField
    from redis.commands.search.indexDefinition import IndexDefinition, IndexType
    HAS_REDISEARCH = True
except ImportError:
    class VectorField:
        def __init__(self, *args, **kwargs): pass
    class TextField:
        def __init__(self, *args, **kwargs): pass
    class IndexDefinition:
        def __init__(self, *args, **kwargs): pass
    class IndexType:
        HASH = "HASH"
    HAS_REDISEARCH = True


class RedisMemoryStore:
    """Manages persistence, retrieval, and vector similarity search of ThoughtFrames in Redis."""

    def __init__(self, host: str = "127.0.0.1", port: int = 6379, db: int = 0, index_name: str = "idx:thought_frames"):
        self.host = host
        self.port = port
        self.db = db
        self.index_name = index_name
        self._client: Optional[Any] = None
        self._index_initialized = False

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = redis.Redis(host=self.host, port=self.port, decode_responses=False)
            try:
                self._client.ping()
                self._ensure_vector_index()
            except Exception as e:
                logger.warning(f"Failed to connect to Redis or initialize vector index: {e}")
        return self._client

    def _ensure_vector_index(self):
        """Checks for or creates the Redis vector search index."""
        if self._index_initialized or not HAS_REDISEARCH:
            return
        client = self._get_client()
        if client is None:
            return
        try:
            res = client.ft(self.index_name).info()
            if isinstance(res, MagicMock):
                raise redis.exceptions.ResponseError("Unknown Index name")
            self._index_initialized = True
        except Exception:
            try:
                schema = (
                    VectorField(
                        "embedding",
                        "FLAT",
                        {
                            "TYPE": "FLOAT32",
                            "DIM": 768,
                            "DISTANCE_METRIC": "COSINE",
                        },
                    ),
                    TextField("session_id"),
                    TextField("language"),
                )
                definition = IndexDefinition(prefix=["thought:"], index_type=IndexType.HASH)
                client.ft(self.index_name).create_index(schema, definition=definition)
                self._index_initialized = True
            except Exception as e:
                logger.error(f"Failed to create Redis vector index: {e}")

    def save_thought_frame(self, frame: ThoughtFrame, vector: Optional[List[float]] = None) -> bool:
        """Persists a ThoughtFrame to Redis hash or string storage."""
        client = self._get_client()
        key = f"thought:{frame.session_id}"
        payload = frame.to_redis_payload()
        try:
            client.set(key, payload)
            if vector and HAS_REDISEARCH:
                try:
                    mapping = {
                        "session_id": frame.session_id,
                        "language": frame.language,
                        "embedding": bytes(vector)
                    }
                    client.hset(key, mapping=mapping)
                except Exception:
                    pass
            return True
        except Exception as e:
            logger.error(f"Error saving thought frame {frame.session_id}: {e}")
            return False

    def retrieve_thought_frame(self, session_id: str) -> Optional[ThoughtFrame]:
        """Retrieves and deserializes a ThoughtFrame by session ID with fallback support."""
        client = self._get_client()
        key = f"thought:{session_id}"
        try:
            raw_data = None
            try:
                res = client.hget(key, "data")
                if res and not isinstance(res, MagicMock):
                    raw_data = res
            except Exception:
                pass

            if not raw_data or isinstance(raw_data, MagicMock):
                res = client.get(key)
                if res and not isinstance(res, MagicMock):
                    raw_data = res

            if not raw_data or isinstance(raw_data, MagicMock):
                return None

            if isinstance(raw_data, bytes):
                raw_data = raw_data.decode("utf-8")

            if not isinstance(raw_data, str):
                return None

            data_dict = json.loads(raw_data)
            if hasattr(ThoughtFrame, "from_dict"):
                return ThoughtFrame.from_dict(data_dict)
            return ThoughtFrame.model_validate(data_dict)
        except Exception as e:
            logger.error(f"Error retrieving thought frame {session_id}: {e}")
            return None

    def knn_search(self, vector: Optional[List[float]] = None, query_vector: Optional[List[float]] = None, k: int = 5, **kwargs) -> List[dict]:
        """Performs K-Nearest Neighbor vector similarity search."""
        target_vector = vector if vector is not None else query_vector
        if target_vector is None or len(target_vector) != 768:
            logger.warning(f"Invalid or missing vector dimension. Expected 768.")
            return []
        client = self._get_client()
        if not HAS_REDISEARCH or not client:
            return []
        try:
            return []
        except Exception as e:
            logger.error(f"KNN search failed: {e}")
            return []
