import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RetrievalFilter(BaseModel):
    """
    Metadata filter criteria applied during semantic retrieval.
    Supports enterprise metadata (department, tags, date ranges) and access control.
    """
    document_id: Optional[uuid.UUID] = Field(default=None, description="Filter to a specific logical document")
    document_version_id: Optional[uuid.UUID] = Field(default=None, description="Filter to a specific document revision")
    document_type: Optional[str] = Field(default=None, description="Filter by format (pdf, docx, txt)")
    owner_id: Optional[str] = Field(default=None, description="Filter by document owner identifier")
    department: Optional[str] = Field(default=None, description="Filter by enterprise department (e.g. HR, Finance, Legal)")
    tags: Optional[List[str]] = Field(default=None, description="Filter documents containing all specified tags")
    created_from: Optional[datetime] = Field(default=None, description="Filter documents created at or after this timestamp")
    created_to: Optional[datetime] = Field(default=None, description="Filter documents created at or before this timestamp")
    effective_from: Optional[datetime] = Field(default=None, description="Filter documents effective on or after this timestamp")
    effective_to: Optional[datetime] = Field(default=None, description="Filter documents effective on or before this timestamp")
    version_number: Optional[int] = Field(default=None, description="Filter to a specific version number")
    requesting_user_id: Optional[str] = Field(default=None, description="Access control: restricting search results to documents accessible by this user")
    active_only: bool = Field(default=True, description="When true, restricts search to active/latest version of documents")
    include_all_versions: bool = Field(default=False, description="When true, searches across all historical versions")


class RetrievedChunk(BaseModel):
    """
    Structured search result representing a ranked chunk with source citation metadata.
    """
    chunk_id: uuid.UUID
    chunk_index: int
    content: str
    similarity_score: float = Field(description="Normalized similarity/relevance score in range [0.0, 1.0]")
    page_number: Optional[int] = Field(default=None, description="Source page number for citation")
    document_id: uuid.UUID
    document_name: str
    document_version_id: uuid.UUID
    version_number: int
    source_filename: str
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom chunk and page metadata")

    # Multi-stage / Hybrid scoring telemetry (Phase 22)
    dense_score: Optional[float] = Field(default=None, description="Dense vector cosine similarity score")
    keyword_score: Optional[float] = Field(default=None, description="PostgreSQL Full-Text Search ts_rank score")
    fusion_score: Optional[float] = Field(default=None, description="RRF (Reciprocal Rank Fusion) score")
    reranker_score: Optional[float] = Field(default=None, description="Cross-encoder relevance score")
    retrieval_mode: Optional[str] = Field(default="dense", description="Mode used: dense, keyword, hybrid, or hybrid_reranked")


class RetrievalResult(BaseModel):
    """
    Aggregated response returned by retriever.
    """
    query: str
    results: List[RetrievedChunk] = Field(default_factory=list)
    total_results: int = 0
    execution_time_ms: float = 0.0
    retrieval_mode: str = Field(default="dense", description="Retrieval mode: dense, keyword, hybrid, or hybrid_reranked")


class BaseRetriever(ABC):
    """
    Abstract interface for semantic, keyword, hybrid, and reranked retrieval systems.
    """

    @abstractmethod
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        similarity_threshold: Optional[float] = None,
        filters: Optional[RetrievalFilter] = None,
    ) -> RetrievalResult:
        """
        Retrieves and ranks the most relevant chunks for a given query.
        """
        pass
