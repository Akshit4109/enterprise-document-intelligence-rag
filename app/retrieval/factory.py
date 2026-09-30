from typing import Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.embeddings.base import BaseEmbeddingProvider
from app.retrieval.base import BaseRetriever
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.keyword import KeywordRetriever
from app.retrieval.reranking.base import BaseReranker
from app.retrieval.vector import VectorRetriever


def get_retriever(
    db: Session,
    embedding_provider: Optional[BaseEmbeddingProvider] = None,
    reranker: Optional[BaseReranker] = None,
    use_hybrid: Optional[bool] = None,
    reranker_enabled: Optional[bool] = None,
    mode: Optional[str] = None,
) -> BaseRetriever:
    """
    Factory function resolving the appropriate retriever based on runtime settings or explicit override.
    Supports "dense", "keyword", "hybrid", "hybrid_reranked", or "auto".
    """
    if mode == "keyword":
        return KeywordRetriever(db=db)
    elif mode == "dense":
        return VectorRetriever(db=db, embedding_provider=embedding_provider)
    elif mode in ("hybrid", "hybrid_reranked"):
        enable_rerank = (mode == "hybrid_reranked") if reranker_enabled is None else reranker_enabled
        return HybridRetriever(
            db=db,
            embedding_provider=embedding_provider,
            reranker=reranker,
            reranker_enabled=enable_rerank,
        )

    # Automatic / configuration-based selection
    should_use_hybrid = settings.USE_HYBRID_RETRIEVAL if use_hybrid is None else use_hybrid
    should_rerank = settings.RERANKER_ENABLED if reranker_enabled is None else reranker_enabled

    if should_use_hybrid or should_rerank:
        return HybridRetriever(
            db=db,
            embedding_provider=embedding_provider,
            reranker=reranker,
            reranker_enabled=should_rerank,
        )

    return VectorRetriever(db=db, embedding_provider=embedding_provider)
