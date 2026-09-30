import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.parsers.base import ParsedDocument


class RawChunk(BaseModel):
    """
    In-memory representation of a document chunk before database persistence.
    """
    chunk_index: int = Field(description="Sequential 0-indexed position within the document version")
    content: str = Field(description="The textual content of the chunk")
    page_number: Optional[int] = Field(default=None, description="Page number where the chunk originates")
    char_start: int = Field(default=0, description="Starting character offset within the source text")
    char_end: int = Field(default=0, description="Ending character offset within the source text")
    token_count_estimate: int = Field(default=0, description="Approximate token count (~4 chars per token)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary to be saved in JSONB")


class BaseChunker(ABC):
    """
    Abstract interface for document chunking algorithms.
    Supports polymorphic chunking strategies (recursive, semantic, token-based, sliding window).
    """

    def __init__(self, chunk_size: int, chunk_overlap: int):
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got {chunk_size}")
        if chunk_overlap < 0:
            raise ValueError(f"chunk_overlap cannot be negative, got {chunk_overlap}")
        if chunk_overlap >= chunk_size:
            raise ValueError(f"chunk_overlap ({chunk_overlap}) must be strictly less than chunk_size ({chunk_size})")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @abstractmethod
    def chunk_document(
        self,
        parsed_doc: ParsedDocument,
        document_id: Optional[uuid.UUID] = None,
        version_id: Optional[uuid.UUID] = None,
        filename: Optional[str] = None,
    ) -> List[RawChunk]:
        """
        Chunks an entire parsed document preserving per-page metadata and continuous index ordering.
        """
        pass

    @abstractmethod
    def chunk_text(self, text: str, page_number: Optional[int] = None) -> List[RawChunk]:
        """
        Splits a single block of text into structured chunks.
        """
        pass
