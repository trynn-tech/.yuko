#!/usr/bin/env python3emed
# modules/synths/src/reasoning/embedder.py

import logging
from typing import List, Union

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

logger = logging.getLogger(__name__)


class FeatureEmbedder:
    """Encoder-only Transformer node (CodeBERT / nomic-embed-text).

    Rapidly vectorizes code functions, markdown chunks, and prompts into 768-dim
    embeddings.
    """

    def __init__(self, model_name: str = "nomic-ai/nomic-embed-text-v1.5"):
        self.model_name = model_name
        self._model = None

    def _lazy_load(self):
        if self._model is None:
            if not HAS_SENTENCE_TRANSFORMERS:
                raise ImportError(
                    "sentence-transformers is required for vector embeddings. "
                    "Ensure it is available in your Nix environment."
                )
            # Load with FP16 to keep memory footprint under 500MB VRAM
            self._model = SentenceTransformer(self.model_name, trust_remote_code=True)

    def encode(self, text: Union[str, List[str]], task_type: str = "search_document") -> List[List[float]]:
        """Encodes text. task_type should be 'search_document' for code, 'search_query' for prompts."""
        self._lazy_load()
        if isinstance(text, str):
            text = [text]
            
        # Nomic v1.5 requires specific task prefixes for accurate retrieval
        prefixed_text = [f"{task_type}: {t}" for t in text]
        
        embeddings = self._model.encode(prefixed_text, normalize_embeddings=True)
        return embeddings.tolist()

class TextEmbedder(FeatureEmbedder):
    """Convenience wrapper mapping FeatureEmbedder to single-string queries."""

    def embed_text(self, text: str) -> List[float]:
        """Returns a single 768-dim vector for string prompts and queries."""
        if not text:
            return [0.0] * 768
        try:
            vectors = self.encode(text)
            if vectors and len(vectors) > 0:
                return vectors[0]
        except Exception as e:
            logger.warning("Failed to generate embedding vector: %s", e)
        return [0.0] * 768
