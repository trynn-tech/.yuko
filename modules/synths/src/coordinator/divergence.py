#!/usr/bin/env python3
# src/coordinator/divergence.py

import logging
import os
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)


class DivergenceHandler:
    """Provides context-enrichment passes to assist anchor patching without destructive file overwrites."""

    def __init__(self, redis_store=None, embedder=None):
        self.redis_store = redis_store
        self.embedder = embedder
        self.searxng_base = os.getenv("SYNTH_SEARXNG_BASE", "http://localhost:8888")
        self.api_base = os.getenv("SYNTH_API_BASE", "http://localhost:8081/v1")

    # -------------------------------------------------------------------
    # Strategy 1: SearXNG Web & Documentation Search
    # -------------------------------------------------------------------
    def enrich_via_searxng(self, query: str, limit: int = 3) -> str:
        """Queries local SearXNG engine for package specs, syntax, or error solutions."""
        logger.info("Executing Divergence Pass 1: SearXNG discovery for '%s'", query)
        try:
            response = httpx.get(
                f"{self.searxng_base}/search",
                params={"q": query, "format": "json"},
                timeout=5.0,
            )
            if response.status_code == 200:
                results = response.json().get("results", [])[:limit]
                snippets = [
                    f"- {r.get('title')}: {r.get('content')}" for r in results
                ]
                return "\n".join(snippets) if snippets else "No web results found."
        except Exception as e:
            logger.warning("SearXNG lookup failed: %s", e)
        return "SearXNG search unavailable."

    # -------------------------------------------------------------------
    # Strategy 2: Upstream / Corporate Model Strategy Query
    # -------------------------------------------------------------------
    def enrich_via_upstream_api(
        self, file_content: str, instruction: str, failed_anchors: List[str]
    ) -> str:
        """Queries an upstream LLM API for structural orientation or a better anchor strategy."""
        logger.info("Executing Divergence Pass 2: Upstream LLM strategy query")
        prompt = (
            f"Analyze this edit task where anchor matching failed.\n"
            f"INSTRUCTION: {instruction}\n"
            f"FAILED ANCHOR ATTEMPTS:\n{failed_anchors}\n\n"
            f"Suggest 1-2 precise lines from the original file that make the safest SEARCH block, "
            f"or explain how to rephrase the edit strategy."
        )
        try:
            response = httpx.post(
                f"{self.api_base}/chat/completions",
                json={
                    "model": os.getenv("SYNTH_MODEL_NAME", "architect"),
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                },
                timeout=15.0,
            )
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning("Upstream LLM query failed: %s", e)
        return "Upstream LLM orientation unavailable."

    # -------------------------------------------------------------------
    # Strategy 3: Redis Working Memory KNN Self-Query
    # -------------------------------------------------------------------
    def enrich_via_redis_memory(self, instruction: str) -> str:
        """Searches past ThoughtFrames in Redis vector store for similar edit patterns."""
        logger.info("Executing Divergence Pass 3: Redis Working Memory KNN search")
        if not self.redis_store or not self.embedder:
            return "Redis vector memory unavailable."

        try:
            vector = self.embedder.embed_text(instruction)
            hits = self.redis_store.knn_search(vector, top_k=2)
            if not hits:
                return "No similar historical ThoughtFrames found."

            insights = []
            for hit in hits:
                payload = hit.get("payload", {})
                insights.append(
                    f"- Session {hit['session_id']} (score: {hit['score']:.3f}): "
                    f"Instruction: '{payload.get('instruction')}' | "
                    f"Summary: {payload.get('semantic_summary')}"
                )
            return "\n".join(insights)
        except Exception as e:
            logger.warning("Redis memory query failed: %s", e)
            return "Redis memory query error."
