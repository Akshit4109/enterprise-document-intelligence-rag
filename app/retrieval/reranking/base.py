from abc import ABC, abstractmethod
from typing import List
from app.retrieval.base import RetrievedChunk


class BaseReranker(ABC):
    """
    Abstract interface for cross-encoder and neural rerankers.
    Evaluates (query, candidate_chunk) pairs to produce deep relevance scores.
    """

    @abstractmethod
    def rerank(
        self,
        query: str,
        candidates: List[RetrievedChunk],
        top_k: int = 5,
    ) -> List[RetrievedChunk]:
        """
        Reranks candidate chunks and returns the top_k most relevant chunks.
        """
        pass
