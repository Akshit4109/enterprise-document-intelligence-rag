from typing import Dict, Optional
from app.core.config import settings
from app.embeddings.base import BaseEmbeddingProvider
from app.embeddings.mock import MockEmbeddingProvider
from app.embeddings.local import SentenceTransformerEmbeddingProvider


class EmbeddingProviderFactory:
    """
    Factory registry for instantiating and caching Embedding Providers.
    """

    _instances: Dict[str, BaseEmbeddingProvider] = {}

    @classmethod
    def get_provider(
        cls,
        provider_type: Optional[str] = None,
        model_name: Optional[str] = None,
        dimension: Optional[int] = None,
    ) -> BaseEmbeddingProvider:
        p_type = (provider_type or settings.EMBEDDING_PROVIDER).lower()
        m_name = model_name or settings.EMBEDDING_MODEL_NAME
        dim = dimension or settings.EMBEDDING_DIMENSION

        cache_key = f"{p_type}_{m_name}_{dim}"
        if cache_key in cls._instances:
            return cls._instances[cache_key]

        if p_type == "mock":
            provider = MockEmbeddingProvider(dimension=dim, model_name=m_name)
        elif p_type == "local":
            provider = SentenceTransformerEmbeddingProvider(model_name=m_name, dimension=dim)
        else:
            raise ValueError(f"Unsupported embedding provider: '{p_type}'. Options: 'local', 'mock'")

        cls._instances[cache_key] = provider
        return provider


def get_embedding_provider() -> BaseEmbeddingProvider:
    """Dependency helper to get the active embedding provider."""
    return EmbeddingProviderFactory.get_provider()
