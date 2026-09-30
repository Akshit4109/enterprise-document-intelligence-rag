from typing import List, Optional
from langchain_core.embeddings import Embeddings

from app.embeddings.base import BaseEmbeddingProvider
from app.embeddings import get_embedding_provider


class LangChainEmbeddingWrapper(Embeddings):
    """
    Adapter that wraps the enterprise platform's BaseEmbeddingProvider into LangChain's Embeddings interface.
    Allows LangChain components to generate embeddings via SentenceTransformers, OpenAI, or Mock providers.
    """

    def __init__(self, provider: Optional[BaseEmbeddingProvider] = None):
        self.provider = provider or get_embedding_provider()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed search docs using the underlying provider's batch embedding implementation.
        """
        if not texts:
            return []
        return self.provider.embed_batch(texts)

    def embed_query(self, text: str) -> List[float]:
        """
        Embed query text using the underlying provider.
        """
        return self.provider.embed_text(text)
