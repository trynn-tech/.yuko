#!/usr/bin/env python3
# src/memory/redis_store.py

import json
import logging
import time
from typing import Any, Dict, List, Optional
import redis
from redis.commands.search.field import TextField, VectorField

# Robust import for Redis search index definition across library versions
try:
    from redis.commands.search.index_definition import IndexDefinition, IndexType
except ImportError:
    try:
        from redis.commands.search.indexDefinition import IndexDefinition, IndexType
    except ImportError:
        # Fallback dummy definitions if redis-py search modules are absent or structured differently
        class IndexType:
            HASH = "HASH"
            JSON = "JSON"
        class IndexDefinition:
            def __init__(self, prefix=None, index_type=None):
                self.prefix = prefix
                self.index_type = index_type

from .render import render_thought_frame
from .schemas import CreationPayload, EditPayload, ThoughtFrame

logger = logging.getLogger(__name__)

class RedisMemoryStore:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
    ):
        self.client = redis.Redis(
            host=host, port=port, db=db, password=password, decode_responses=False
        )

    def _get_client(self) -> Optional[redis.Redis]:
        return self.client

    def _ensure_initialized(self) -> None:
        try:
            ft = self.client.ft("idx:thoughtframes")
            ft.info()
        except redis.exceptions.ResponseError:
            # Index missing; issue index schema definition
            ft = self.client.ft("idx:thoughtframes")
            schema = [
                TextField("session_id"),
                TextField("target_file"),
                TextField("intent_type"),
                VectorField(
                    "vector",
                    "FLAT",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": 768,
                        "DISTANCE_METRIC": "COSINE",
                    },
                ),
            ]
            definition = IndexDefinition(
                prefix=["thoughtframe:"], index_type=IndexType.HASH
            )
            try:
                ft.create_index(schema, definition=definition)
            except Exception as e:
                logger.error(f"Failed to create RediSearch index: {e}")
        except Exception as e:
            logger.warning(f"Index check failed: {e}")

    def save_thought_frame(self, frame: ThoughtFrame, vector: Optional[List[float]] = None) -> bool:
        try:
            self._ensure_initialized()
            key = f"thoughtframe:{frame.session_id}"
            payload = frame.to_redis_payload()
            
            # Save as Hash to support RediSearch fields/vectors if vector provided, else standard set/hash
            mapping = {"json_payload": payload}
            if vector and len(vector) == 768:
                import numpy as np
                mapping["vector"] = np.array(vector, dtype=np.float32).tobytes()
            
            saved = bool(self.client.hset(key, mapping=mapping))
            
            # Track in ZSET timeline for temporal traversal
            timeline_key = "thought_frames:timeline"
            timestamp = getattr(frame, "timestamp", time.time())
            self.client.zadd(timeline_key, {frame.session_id: timestamp})
            
            return saved
        except Exception as e:
            logger.error(f"Failed to save ThoughtFrame {frame.session_id}: {e}")
            return False

    def retrieve_thought_frame(self, session_id: str) -> Optional[ThoughtFrame]:
        key = f"thoughtframe:{session_id}"
        data = None
        try:
            data = self.client.hget(key, "json_payload")
        except Exception:
            pass
        if not data:
            try:
                data = self.client.get(key)
            except Exception as e:
                logger.warning(f"Failed byte retrieval for {session_id}: {e}")
                return None
        if not data:
            return None
        try:
            raw_json = json.loads(data.decode("utf-8"))
            return ThoughtFrame(**raw_json)
        except Exception as e:
            logger.error(f"Failed parsing ThoughtFrame payload for {session_id}: {e}")
            return None

    def retrieve_nearest_thought_frame(
        self, target_timestamp: float, offset_step: int = 0
    ) -> Tuple[Optional[ThoughtFrame], int, int]:
        """
        Fuzzy timestamp lookup using linked-list ZSET traversal,
        hydrating the target result.
        """
        client = self._get_client()
        if not client:
            return None, -1, 0
        timeline_key = "thought_frames:timeline"
        try:
            total_count = client.zcard(timeline_key)
            if total_count == 0:
                return None, -1, 0
            
            # Nearest frame with score >= target_timestamp
            items = client.zrangebyscore(
                timeline_key, min=target_timestamp, max="+inf", start=1, num=1
            )
            if items:
                base_session = items[0]
                if isinstance(base_session, bytes):
                    base_session = base_session.decode("utf-8")
                base_index = client.zrank(timeline_key, base_session)
                if base_index is None:
                    base_index = 0
            else:
                base_index = total_count - 1
                
            target_index = (base_index + offset_step) % total_count
            attempts = 0
            while attempts < total_count:
                curr_idx = target_index % total_count
                target_items = client.zrange(timeline_key, curr_idx, curr_idx)
                if not target_items:
                    break
                resolved_session_id = target_items[0]
                if isinstance(resolved_session_id, bytes):
                    resolved_session_id = resolved_session_id.decode("utf-8")
                frame = self.retrieve_thought_frame(resolved_session_id)
                if frame:
                    return frame, curr_idx, total_count
                
                # Evict orphan ZSET reference if target frame expired
                client.zrem(timeline_key, resolved_session_id)
                total_count = client.zcard(timeline_key)
                if total_count == 0:
                    break
            return None, -1, total_count
        except Exception as e:
            logger.error(f"Error in timeline traversal for {target_timestamp}: {e}")
            return None, -1, 0

    def knn_search(
        self,
        vector: Optional[List[float]] = None,
        query_vector: Optional[List[float]] = None,
        k: int = 5,
        top_k: Optional[int] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Performs vector similarity search against RediSearch index."""
        target_vector = vector if vector is not None else (query_vector if query_vector is not None else kwargs.get("vector"))
        limit_k = top_k if top_k is not None else k
        
        if target_vector is None or len(target_vector) != 768:
            logger.warning(f"Invalid or missing vector dimension. Expected 768, got {len(target_vector) if target_vector else 0}.")
            return []
            
        try:
            self._ensure_initialized()
            import numpy as np
            q_vec = np.array(target_vector, dtype=np.float32).tobytes()
            query = f"*=>[KNN {limit_k} @vector $vec AS score]"
            ft = self.client.ft("idx:thoughtframes")
            result = ft.search(query, query_params={"vec": q_vec})
            return [doc.__dict__ for doc in result.docs]
        except Exception as e:
            logger.error(f"KNN search failed: {e}")
            return []


def watch_thought_stream(redis_store: RedisMemoryStore, poll_interval: float = 1.0) -> None:
    """Observer watcher monitoring incoming stream items in real time."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    client = redis_store._get_client()
    if not client:
        logger.error("Unable to attach observer: Redis client connection failed.")
        return

    timeline_key = "thought_frames:timeline"

    # Start tracking from the highest score currently in the timeline
    top_entry = client.zrevrange(timeline_key, 0, 0, withscores=True)
    highest_seen_ts = top_entry[0][1] if top_entry else 0.0

    console.print(
        Panel(
            "[bold cyan]📡 Meta-Cognition — MONITORING THOUGHT STREAM[/bold cyan]",
            border_style="magenta",
            expand=True,
        )
    )

    try:
        while True:
            # Query strictly greater than the highest seen score
            new_entries = client.zrangebyscore(
                timeline_key,
                min=f"({highest_seen_ts}",
                max="+inf",
                withscores=True,
            )

            for session_id, ts in new_entries:
                if isinstance(session_id, bytes):
                    session_id = session_id.decode("utf-8")

                frame = redis_store.retrieve_thought_frame(session_id)
                if frame:
                    console.print(f"\n[bold magenta]⚡ [EVENT] New Frame ({ts}):[/bold magenta]")
                    render_thought_frame(frame, console_out=console)
                else:
                    console.print(
                        f"\n[bold yellow]⚠️ [EVENT] Frame Key Updated (No Payload): {session_id}[/bold yellow]"
                    )

                highest_seen_ts = max(highest_seen_ts, ts)

            time.sleep(poll_interval)
    except KeyboardInterrupt:
        console.print("\n[bold red]Observer detached. Exiting stream watch.[/bold red]")
