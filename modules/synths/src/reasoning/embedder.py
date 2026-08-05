#!/usr/bin/env python3
# modules/synths/src/reasoning/embedder.py

from typing import List, Union
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


class FeatureEmbedder:
    """
    Encoder-only Transformer node (CodeBERT / nomic-embed-text).
    Rapidly vectorizes code functions, markdown chunks, and prompts into 768-dim embeddings.
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

    def encode(self, text: Union[str, List[str]]) -> List[List[float]]:
        """Encodes text or list of code blocks into normalized dense float vectors."""
        self._lazy_load()
        if isinstance(text, str):
            text = [text]

        # Generate vectors
        embeddings = self._model.encode(text, normalize_embeddings=True)
        return embeddings.tolist()
