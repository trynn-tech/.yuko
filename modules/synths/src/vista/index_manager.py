#!/usr/bin/env python3
# modules/synths/src/vista/index_manager.py

import hashlib
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class IndexManager:
    """Manages AST extraction and Neo4j synchronization using blake2b checksums."""
    
    def __init__(self, graph_linker, patcher, redis_client):
        self.graph = graph_linker
        self.patcher = patcher
        self.redis = redis_client

    def _get_file_hash(self, code_bytes: bytes) -> str:
        return hashlib.blake2b(code_bytes).hexdigest()

    def sync_file_if_changed(self, filepath: str) -> bool:
        path = Path(filepath)
        if not path.exists():
            return False

        try:
            code_bytes = path.read_bytes()
            current_hash = self._get_file_hash(code_bytes)
            
            # Check Redis for the last known hash
            redis_key = f"yuko:hash:{filepath}"
            last_hash = self.redis.get(redis_key)
            
            if last_hash and last_hash == current_hash:
                return False # File hasn't changed

            code_str = code_bytes.decode("utf-8")
            facts = self.patcher.extract_ast_facts(filepath, code_str)
            lang = self.patcher._detect_language(filepath)
            
            frame_data = {
                "resolved_path": filepath,
                "language": lang,
                "ast_facts": facts,
                "concept_tags": facts.get("imports", []),
            }
            
            success = self.graph.sync_thought_frame_graph(frame_data)
            if success:
                self.redis.set(redis_key, current_hash)
                logger.info(f"Updated AST graph for {filepath}")
                
            return success
            
        except Exception as e:
            logger.error(f"Failed to sync {filepath}: {e}")
            return False
