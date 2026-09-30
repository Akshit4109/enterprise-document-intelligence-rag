from typing import List, Optional
from app.embeddings.base import BaseEmbeddingProvider


class SentenceTransformerEmbeddingProvider(BaseEmbeddingProvider):
    """
    Local embedding provider utilizing the SentenceTransformers library (PyTorch/HuggingFace).
    Generates embeddings locally on CPU/MPS/GPU with batch processing and L2 normalization.
    """
    _cached_models = {}

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        dimension: int = 384,
    ):
        self._model_name = model_name
        self._dimension = dimension

    def _load_model(self):
        if self._model_name not in self._cached_models:
            from sentence_transformers import SentenceTransformer
            self._cached_models[self._model_name] = SentenceTransformer(self._model_name)

        model = self._cached_models[self._model_name]
        # Verify dimension
        if hasattr(model, "get_embedding_dimension"):
            actual_dim = model.get_embedding_dimension()
        else:
            actual_dim = getattr(model, "get_sentence_embedding_dimension", lambda: None)()
        if actual_dim:
            self._dimension = actual_dim
        return model

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_text(self, text: str) -> List[float]:
        if not text:
            return [0.0] * self._dimension

        model = self._load_model()
        vector = model.encode(text, normalize_embeddings=True)
        return vector.tolist()

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        if not texts:
            return []

        model = self._load_model()
        vectors = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return vectors.tolist()
