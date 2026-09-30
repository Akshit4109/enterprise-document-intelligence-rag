from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from app.retrieval.base import RetrievalFilter

if TYPE_CHECKING:
    from app.schemas.rag import RAGQueryResponse


class BaseRAGEngine(ABC):
    """
    Abstract Base Class defining the unified contract for RAG Engines
    (both native Python RAGService and LangChain LCEL LangChainRAGEngine).
    """

    @abstractmethod
    def query(
        self,
        question: str,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        filters: Optional[RetrievalFilter] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        temperature: Optional[float] = None,
    ) -> RAGQueryResponse:
        """
        Executes end-to-end question answering or conversational multi-turn RAG.
        Returns a standardized RAGQueryResponse with answer, citations, and provenance metadata.
        """
        pass
