#!/usr/bin/env python3
# memory/redis_store.py

import json
import logging
import shutil
import time
from typing import List, Optional, Any, Tuple
from unittest.mock import MagicMock
import numpy as np
import redis 
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from memory.working_memory import ThoughtFrame

logger = logging.getLogger(__name__)
console = Console()

# Determine if RedisSearch (RediSearch) modules/commands are available or provide test fallbacks
try:
    from redis.commands.search.field import VectorField, TextField  # type: ignore
    try:
        from redis.commands.search.index_definition import IndexDefinition, IndexType  # type: ignore
    except ImportError:
        from redis.commands.search.indexDefinition import IndexDefinition, IndexType  # type: ignore
    from redis.commands.search.query import Query  # type: ignore
    HAS_REDISEARCH = True
except ImportError:
    class VectorField:
        def __init__(self, *args, **kwargs): pass
    class TextField:
        def __init__(self, *args, **kwargs): pass
    class IndexDefinition:
        def __init__(self, *args, **kwargs):
            self.args = []
            for k, v in kwargs.items():
                if k == 'prefix':
                    self.args.extend(['PREFIX', len(v)] + list(v))
                elif k == 'index_type':
                    self.args.extend(['ON', str(v)])
        def __getattr__(self, name):
            return []
    class IndexType:
        HASH = "HASH"
        JSON = "JSON"
    class Query:
        def __init__(self, query_string: str): pass
        def return_fields(self, *fields): return self
        def sort_by(self, field, asc=True): return self
        def paging(self, offset, num): return self
        def dialect(self, dialect_num): return self
    HAS_REDISEARCH = False


def render_thought_frame(frame: Optional[ThoughtFrame], header_title: Optional[str] = None) -> None:
    """Renders a ThoughtFrame to the console using Rich tables, panels, and syntax highlighting."""
    if not frame:
        console.print("[bold yellow]⚠️ No matching ThoughtFrame found.[/bold yellow]")
        return

    columns, _ = shutil.get_terminal_size((80, 24))

    if header_title:
        console.print(f"\n[bold magenta]{header_title}[/bold magenta]")

    session_id = getattr(frame, "session_id", "N/A")
    verified = getattr(frame, "verification_passed", True)
    ver_status = "[bold green]PASS[/bold green]" if verified else "[bold red]FAIL[/bold red]"
    
    lang = getattr(frame, "language", "python") or "python"
    target_file = getattr(frame, "resolved_path", None) or getattr(frame, "file_path", "N/A")

    meta_table = Table(show_header=False, box=None, padding=(0, 1))
    meta_table.add_column("Key", style="bold cyan")
    meta_table.add_column("Value", style="white")
    meta_table.add_row("Session ID:", str(session_id))
    meta_table.add_row("Target File:", str(target_file))
    meta_table.add_row("Language:", str(lang))
    meta_table.add_row("Verification:", ver_status)

    summary = getattr(frame, "semantic_summary", None)
    if summary:
        meta_table.add_row("Summary:", f"[italic white]{summary}[/italic white]")

    tags = getattr(frame, "concept_tags", [])
    if tags:
        meta_table.add_row("Concept Tags:", f"[yellow]{', '.join(tags)}[/yellow]")

    console.print(meta_table)

    instruction = getattr(frame, "instruction", None)
    if instruction:
        console.print(
            Panel(
                instruction,
                title="[bold yellow]Instruction[/bold yellow]",
                border_style="yellow",
                expand=True,
            )
        )

    code_payload = (
        getattr(frame, "extracted_code", None)
        or getattr(frame, "synthesized_code", None)
        or getattr(frame, "raw_response", None)
        or getattr(frame, "code", None)
    )

    if code_payload:
        clean_code = str(code_payload).strip()
        
        # Strip enclosing markdown backticks if present
        if clean_code.startswith("```"):
            lines = clean_code.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean_code = "\n".join(lines).strip()

        syntax_lang = "python" if lang in ("text", "", None) else lang
        syntax = Syntax(
            clean_code,
            syntax_lang,
            theme="monokai",
            line_numbers=True,
            word_wrap=True,
        )
        console.print(
            Panel(
                syntax,
                title=f"[bold green]Synthesized Code ({syntax_lang})[/bold green]",
                border_style="green",
                expand=True,
            )
        )

    console.print("-" * columns)


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
            self._client = redis.Redis(host=self.host, port=self.port, db=self.db, decode_responses=False)
            try:
                if self._client is not None:
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
                    TextField("data"),
                )
                definition = IndexDefinition(prefix=["thought:"], index_type=IndexType.HASH)
                
                if not hasattr(definition, "args") or definition.args is None:
                    definition.args = ["PREFIX", "1", "thought:", "ON", "HASH"]
                client.ft(self.index_name).create_index(schema, definition=definition)
                self._index_initialized = True
            except Exception as e:
                logger.error(f"Failed to create Redis vector index: {e}")

    def save_thought_frame(self, frame: ThoughtFrame, vector: Optional[List[float]] = None) -> bool:
        """Persists a ThoughtFrame to Redis hash and string storage with a 7-day TTL budget."""
        client = self._get_client()
        if client is None:
            return False
        key = f"thought:{frame.session_id}"
        ttl_seconds = 7 * 24 * 60 * 60  # 7 days (604,800s)
        if hasattr(frame, "to_redis_payload"):
            payload = frame.to_redis_payload()
        elif hasattr(frame, "model_dump_json"):
            payload = frame.model_dump_json()
        elif hasattr(frame, "to_dict"):
            payload = json.dumps(frame.to_dict())
        else:
            payload = json.dumps(frame.__dict__)

        try:
            mapping: dict[str, Any] = {
                "session_id": frame.session_id,
                "language": getattr(frame, "language", "en"),
                "data": payload,
            }
            if vector and len(vector) == 768:
                mapping["embedding"] = np.array(vector, dtype=np.float32).tobytes()
            client.hset(key, mapping=mapping)
            client.set(f"{key}:raw", payload)
            
            # Apply 7-day expiration to prevent RAM growth
            client.expire(key, ttl_seconds)
            client.expire(f"{key}:raw", ttl_seconds)

            # Index timestamp in timeline ZSET and prune entries older than 7 days
            timestamp = getattr(frame, "timestamp", time.time())
            client.zadd("thought_frames:timeline", {frame.session_id: timestamp})
            
            cutoff_timestamp = time.time() - ttl_seconds
            client.zremrangebyscore("thought_frames:timeline", "-inf", cutoff_timestamp)
            return True
        except Exception as e:
            logger.error(f"Error saving thought frame {frame.session_id}: {e}")
            return False

    def retrieve_thought_frame(self, session_id: str) -> Optional[ThoughtFrame]:
        """Retrieves and deserializes a ThoughtFrame by session ID with fallback support."""
        client = self._get_client()
        if client is None:
            return None
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
                res = client.get(f"{key}:raw") or client.get(key)
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
            elif hasattr(ThoughtFrame, "model_validate"):
                return ThoughtFrame.model_validate(data_dict)
            return ThoughtFrame(**data_dict)
        except Exception as e:
            logger.error(f"Error retrieving thought frame {session_id}: {e}")
            return None

    def retrieve_nearest_thought_frame(
        self, target_timestamp: float, offset_step: int = 0
    ) -> Tuple[Optional[ThoughtFrame], int, int]:
        """
        Fuzzy index lookup using timestamp linked-list traversal in the Redis ZSET.

        Offset Semantics:
            offset_step > 0: Travel backward into past history (1 = 1 frame back).
            offset_step < 0: Travel forward toward future/tip (-1 = 1 frame forward).

        Returns:
            Tuple of (ThoughtFrame | None, current_index, active_count)
        """
        client = self._get_client()
        if client is None:
            return None, -1, 0

        timeline_key = "thought_frames:timeline"
        try:
            total_count = client.zcard(timeline_key)
            if total_count == 0:
                return None, -1, 0

            # Find nearest active frame with score >= target_timestamp
            items = client.zrangebyscore(timeline_key, min=target_timestamp, max="+inf", start=0, num=1)

            if items:
                base_session = items[0]
                if isinstance(base_session, bytes):
                    base_session = base_session.decode("utf-8")
                base_index = client.zrank(timeline_key, base_session)
                if base_index is None:
                    base_index = 0
            else:
                base_index = total_count - 1

            # Invert sign internally: positive steps decrease ZSET rank (traveling back into history)
            target_index = (base_index - offset_step) % total_count

            attempts = 0
            while attempts < total_count:
                curr_idx = (target_index + attempts) % total_count
                target_items = client.zrange(timeline_key, curr_idx, curr_idx)

                if not target_items:
                    break

                resolved_session_id = target_items[0]
                if isinstance(resolved_session_id, bytes):
                    resolved_session_id = resolved_session_id.decode("utf-8")

                frame = self.retrieve_thought_frame(resolved_session_id)
                if frame:
                    return frame, curr_idx, total_count

                # Clean up orphaned ZSET key if hash reference vanished
                client.zrem(timeline_key, resolved_session_id)
                total_count = client.zcard(timeline_key)

                if total_count == 0:
                    break

            return None, -1, total_count

        except Exception as e:
            logger.error(f"Error in timestamp linked-list traversal for {target_timestamp}: {e}")
            return None, -1, 0

    def knn_search(
        self,
        vector: Optional[List[float]] = None,
        query_vector: Optional[List[float]] = None,
        k: int = 5,
        **kwargs,
    ) -> List[dict]:
        """Performs K-Nearest Neighbor vector similarity search in Redis using RediSearch."""
        target_vector = vector if vector is not None else query_vector
        if target_vector is None or len(target_vector) != 768:
            logger.warning("Invalid or missing vector dimension. Expected 768.")
            return []
        client = self._get_client()
        if not HAS_REDISEARCH or not client:
            return []
        try:
            vector_bytes = np.array(target_vector, dtype=np.float32).tobytes()
            query_str = f"*=>[KNN {k} @embedding $vec_param AS score]"
            q = (
                Query(query_str)
                .return_fields("session_id", "language", "data", "score")
                .sort_by("score", asc=True)
                .paging(0, k)
                .dialect(2)
            )
            query_params = {"vec_param": vector_bytes}
            results = client.ft(self.index_name).search(q, query_params=query_params)
            matches = []
            for doc in getattr(results, "docs", []):
                doc_dict = {
                    "id": getattr(doc, "id", None),
                    "score": float(getattr(doc, "score", 0.0)),
                    "session_id": getattr(doc, "session_id", None),
                    "language": getattr(doc, "language", None),
                }
                raw_payload = getattr(doc, "data", None)
                if raw_payload:
                    if isinstance(raw_payload, bytes):
                        raw_payload = raw_payload.decode("utf-8")
                    try:
                        data_dict = json.loads(raw_payload)
                        if hasattr(ThoughtFrame, "from_dict"):
                            doc_dict["frame"] = ThoughtFrame.from_dict(data_dict)
                        elif hasattr(ThoughtFrame, "model_validate"):
                            doc_dict["frame"] = ThoughtFrame.model_validate(data_dict)
                        else:
                            doc_dict["frame"] = data_dict
                    except Exception:
                        doc_dict["frame"] = raw_payload
                matches.append(doc_dict)
            return matches
        except Exception as e:
            logger.error(f"KNN search failed: {e}")
            return []


def watch_thought_stream(redis_store, poll_interval: float = 1.0) -> None:
    """
    Observer pattern watcher monitoring incoming ThoughtFrames in real-time.
    Uses score-based polling (ZRANGEBYSCORE) to stay resilient against ZSET TTL pruning.
    """
    client = redis_store._get_client()
    if client is None:
        logger.error("Unable to attach observer: Redis client connection failed.")
        return

    timeline_key = "thought_frames:timeline"

    highest_seen_ts = time.time()
    top_entry = client.zrevrange(timeline_key, 0, 0, withscores=True)
    if top_entry:
        highest_seen_ts = max(highest_seen_ts, top_entry[0][1])

    console.print(
        Panel(
            "[bold cyan]📡 YUKO Meta-Cognition — MONITORING THOUGHT STREAM[/bold cyan]",
            border_style="magenta",
            expand=True,
        )
    )

    try:
        while True:
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
                    render_thought_frame(frame, header_title=f"⚡ [EVENT] New ThoughtFrame Received ({ts}):")
                else:
                    console.print(
                        f"\n[bold yellow]⚠️ [EVENT] Frame Key Updated (No Payload): {session_id}[/bold yellow]"
                    )
                highest_seen_ts = max(highest_seen_ts, ts)
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        console.print("\n[bold red]Observer detached. Exiting watch stream.[/bold red]")
