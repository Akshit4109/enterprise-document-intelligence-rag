from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import logger
from app.embeddings import get_embedding_provider
from app.embeddings.base import BaseEmbeddingProvider
from app.llm import get_llm_provider
from app.llm.base import BaseLLMProvider
from app.rag.base import BaseRAGEngine
from app.rag.graph.engine import LangGraphRAGEngine
from app.rag.langchain_engine import LangChainRAGEngine
from app.retrieval.vector import VectorRetriever
from app.services.rag import RAGService


def get_rag_engine(
    db: Session = Depends(get_db),
    embedding_provider: BaseEmbeddingProvider = Depends(get_embedding_provider),
    llm_provider: BaseLLMProvider = Depends(get_llm_provider),
) -> BaseRAGEngine:
    """
    FastAPI dependency and factory for dynamically selecting and constructing the RAG engine.
    Controlled by USE_LANGGRAPH_RAG and USE_LANGCHAIN_RAG configuration settings.
    """
    if settings.USE_LANGGRAPH_RAG:
        logger.info("RAG engine selected: langgraph")
        return LangGraphRAGEngine(
            db=db,
            embedding_provider=embedding_provider,
            min_relevance_threshold=settings.RAG_MIN_RELEVANCE_THRESHOLD,
            max_retries=settings.LANGGRAPH_MAX_RETRIES,
        )
    elif settings.USE_LANGCHAIN_RAG:
        logger.info("RAG engine selected: langchain")
        return LangChainRAGEngine(
            db=db,
            embedding_provider=embedding_provider,
            min_relevance_threshold=settings.RAG_MIN_RELEVANCE_THRESHOLD,
        )
    else:
        logger.info("RAG engine selected: native")
        retriever = VectorRetriever(
            db=db,
            embedding_provider=embedding_provider,
        )
        return RAGService(
            retriever=retriever,
            llm_provider=llm_provider,
        )
