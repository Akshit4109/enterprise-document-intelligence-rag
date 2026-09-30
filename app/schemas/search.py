import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.retrieval.base import RetrievalFilter, RetrievedChunk


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language search query")
    top_k: int = Field(default=5, ge=1, le=100, description="Maximum number of relevant chunks to return")
    similarity_threshold: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity score (0.0 to 1.0) to filter low-confidence results",
    )
    filters: Optional[RetrievalFilter] = Field(
        default=None,
        description="Optional metadata filters (document_id, document_type, owner_id, version_number)",
    )
    mode: Optional[str] = Field(
        default=None,
        description="Retrieval mode: 'dense' (pgvector), 'keyword' (FTS), 'hybrid' (dense+FTS RRF), 'hybrid_reranked' (RRF+CrossEncoder), or None/'auto' (uses config default)",
    )


class SearchResponse(BaseModel):
    query: str
    total_results: int
    execution_time_ms: float
    retrieval_mode: str = Field(default="dense", description="Retrieval mode used")
    results: List[RetrievedChunk]
