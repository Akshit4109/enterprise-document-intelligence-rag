from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, TypedDict
from langchain_core.documents import Document as LCDocument

from app.rag.citation import CitationSource
from app.retrieval.base import RetrievalFilter

if TYPE_CHECKING:
    from app.schemas.rag import RAGQueryResponse


class RAGGraphState(TypedDict, total=False):
    """
    Explicit state schema for the LangGraph stateful RAG workflow.
    Communicates workflow context across retrieval, grading, rewriting, generation, and response finalization.
    """
    # Query definitions
    question: str
    original_question: str
    rewritten_question: Optional[str]
    chat_history: List[Tuple[str, str]]

    # Retrieval parameters & filters
    top_k: int
    similarity_threshold: Optional[float]
    filters: Optional[RetrievalFilter]

    # Retrieval results & evaluation
    retrieved_documents: List[LCDocument]
    retrieval_attempt: int
    max_retries: int
    retrieval_sufficient: bool

    # Generation & citations
    generated_answer: Optional[str]
    citations: List[CitationSource]
    is_grounded: bool

    # Telemetry and final API contract payload
    retrieval_metadata: Dict[str, Any]
    final_response: Optional[Any]
