from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.rag.citation import CitationSource
from app.retrieval.base import RetrievalFilter


class RAGQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Natural language question to answer from knowledge base")
    top_k: Optional[int] = Field(default=5, ge=1, le=20, description="Number of context chunks to retrieve")
    similarity_threshold: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum relevance score required for retrieval",
    )
    filters: Optional[RetrievalFilter] = Field(default=None, description="Optional metadata filters")
    temperature: float = Field(default=0.0, ge=0.0, le=1.0, description="LLM sampling temperature")


class RAGQueryResponse(BaseModel):
    question: str
    answer: str
    sources: List[CitationSource] = Field(default_factory=list, description="Ordered source citations matching answer markers")
    is_grounded: bool = Field(description="True if answered from retrieved context; False if context was insufficient")
    llm_model: Optional[str] = None
    token_usage: Dict[str, int] = Field(default_factory=dict)
    retrieval_metadata: Dict[str, Any] = Field(default_factory=dict)
