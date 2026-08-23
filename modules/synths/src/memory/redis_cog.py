# engine/redis_cog.py

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RedisCognitionStore:
    """Manages machine cognition logs directly within Redis using Streams and Hashes."""

    def __init__(self, redis_client):
        self.redis = redis_client

    def write_log(self, session_id: str, step_id: int, target_file: str, payload: Dict[str, Any]) -> None:
        """Appends a cognition packet to a Redis Stream and updates current state hash."""
        if not self.redis:
            logger.warning("Redis store not available. Cognition log skipped.")
            return

        timestamp = datetime.utcnow().isoformat()
        stream_key = f"cognition:stream:{session_id}"
        state_key = f"cognition:state:{session_id}:{step_id}"

        packet_data = {
            "session_id": session_id,
            "step_id": str(step_id),
            "target_file": target_file,
            "timestamp": timestamp,
            "payload": json.dumps(payload),
        }

        try:
            # 1. Append to append-only stream (exact .cog equivalent)
            self.redis.xadd(stream_key, packet_data)
            
            # 2. Maintain latest state hash for rapid recovery/inspection
            self.redis.hset(state_key, mapping=packet_data)
            # Optional: Set a TTL on completed/halted states (e.g., 7 days)
            self.redis.expire(state_key, 604800)
            self.redis.expire(stream_key, 604800)

            logger.debug("Redis cognition log recorded for session %s step %d", session_id, step_id)
        except Exception as e:
            logger.error("Failed to write Redis cognition log: %s", e)

    def read_state(self, session_id: str, step_id: int) -> Optional[Dict[str, Any]]:
        """Re-hydrates the latest cognition state for a specific step."""
        if not self.redis:
            return None

        state_key = f"cognition:state:{session_id}:{step_id}"
        try:
            data = self.redis.hgetall(state_key)
            if not data:
                return None
            
            # Decode byte responses if using standard redis-py
            decoded = {k.decode("utf-8") if isinstance(k, bytes) else k: 
                       v.decode("utf-8") if isinstance(v, bytes) else v 
                       for k, v in data.items()}
            decoded["payload"] = json.loads(decoded["payload"])
            return decoded
        except Exception as e:
            logger.error("Failed to read Redis cognition state: %s", e)
            return None

    def purge_log(self, session_id: str, step_id: int) -> None:
        """Cleans up Redis state upon successful step completion."""
        if not self.redis:
            return

        state_key = f"cognition:state:{session_id}:{step_id}"
        try:
            self.redis.delete(state_key)
            logger.debug("Purged Redis cognition state for session %s step %d", session_id, step_id)
        except Exception as e:
            logger.error("Failed to purge Redis cognition state: %s", e)
