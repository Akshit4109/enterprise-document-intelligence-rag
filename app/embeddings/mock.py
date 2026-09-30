import hashlib
import math
from typing import List
from app.embeddings.base import BaseEmbeddingProvider


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """
    Deterministic Mock Embedding Provider for fast offline testing and verification.
    Generates normalized pseudo-embeddings with configurable dimensions.
    """

    def __init__(self, dimension: int = 384, model_name: str = "mock-embedding-v1"):
        self._dimension = dimension
        self._model_name = model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_text(self, text: str) -> List[float]:
        if not text:
            return [0.0] * self._dimension

        # Generate deterministic vector using SHA-256 hash stream
        vector: List[float] = []
        seed = text.encode("utf-8")
        current_hash = hashlib.sha256(seed).digest()

        while len(vector) < self._dimension:
            for byte in current_hash:
                # Map byte (0-255) to float in [-1.0, 1.0]
                vector.append((byte / 127.5) - 1.0)
                if len(vector) == self._dimension:
                    break
            current_hash = hashlib.sha256(current_hash).digest()

        # Normalize to unit length (L2 normalization)
        norm = math.sqrt(sum(x * x for x in vector))
        if norm > 0:
            vector = [x / norm for x in vector]

        return vector

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]
