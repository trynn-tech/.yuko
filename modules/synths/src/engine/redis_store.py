#!/usr/bin/env python3
# modules/synths/src/engine/redis_store.py

import json
import struct
from typing import Any, Dict, List, Optional

try:
    import redis
    from redis.commands.search.field import VectorField, TextField, TagField
    from redis.commands.search.indexDefinition import IndexDefinition, IndexType
    from redis.commands.search.query import Query
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

from engine.working_memory import ThoughtFrame


class RedisMemoryStore:
    """
    Redis Vector and Key-Value Memory Store using RediSearch KNN queries.
    Stores ThoughtFrames, indexes 768-dim embeddings, and handles similarity lookups.
    """

    INDEX_NAME = "reasoning_vector_idx"
    VECTOR_DIM = 768  # Standard dimension for CodeBERT / Nomic Embed

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

    def _get_client(self):
        if self._client is None:
            if not HAS_REDIS:
                raise ImportError("redis-py with search support is required.")
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=False,  # Byte mode for raw vector storage
            )
            if not self._index_initialized:
                self._ensure_vector_index()
        return self._client

    def _ensure_vector_index(self):
        """Creates the RediSearch HNSW vector index if it does not already exist."""
        r = self._client
        try:
            r.ft(self.INDEX_NAME).info()
            self._index_initialized = True
        except Exception:
            # Index does not exist, define and create it
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
            try:
                r.ft(self.INDEX_NAME).create_index(
                    fields=schema, definition=definition
                )
                self._index_initialized = True
            except Exception:
                pass

    def save_thought_frame(
        self, frame: ThoughtFrame, vector: Optional[List[float]] = None
    ) -> bool:
        """Stores a ThoughtFrame as a Redis Hash with float32 vector bytes."""
        try:
            r = self._get_client()
            key = f"reasoning:frame:{frame.session_id}"

            payload = {
                b"session_id": frame.session_id.encode("utf-8"),
                b"instruction": frame.instruction.encode("utf-8"),
                b"language": frame.language.encode("utf-8"),
                b"data": frame.to_redis_payload().encode("utf-8"),
            }

            if vector and len(vector) == self.VECTOR_DIM:
                # Pack vector as float32 binary buffer for RediSearch
                payload[b"embedding"] = struct.pack(f"{len(vector)}f", *vector)

            r.hset(key, mapping=payload)
            r.sadd(b"reasoning:sessions", frame.session_id.encode("utf-8"))
            return True
        except Exception:
            return False

    def knn_search(
        self, query_vector: List[float], top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """Executes a K-Nearest Neighbors (KNN) cosine similarity search."""
        if not query_vector or len(query_vector) != self.VECTOR_DIM:
            return []

        try:
            r = self._get_client()
            vector_bytes = struct.pack(f"{len(query_vector)}f", *query_vector)

            # RediSearch KNN Query Syntax
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
                raw_data = getattr(doc, "data", b"{}")
                if isinstance(raw_data, bytes):
                    raw_data = raw_data.decode("utf-8")

                hits.append(
                    {
                        "session_id": getattr(doc, "session_id", ""),
                        "score": float(getattr(doc, "vector_score", 1.0)),
                        "payload": json.loads(raw_data),
                    }
                )
            return hits
        except Exception:
            return []

    def flush_db(self) -> bool:
        """Flushes reasoning keys from Redis."""
        try:
            r = self._get_client()
            keys = r.keys(b"reasoning:*")
            if keys:
                r.delete(*keys)
            return True
        except Exception:
            return False
