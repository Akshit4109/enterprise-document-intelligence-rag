from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ParsedPage(BaseModel):
    """
    Represents an individual page or logical section of a document.
    Crucial for preserving page boundaries for PDF documents and exact citations.
    """
    page_number: Optional[int] = Field(default=None, description="1-indexed page number if applicable")
    text: str = Field(description="Cleaned textual content of the page")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Page-level metadata (e.g. dimensions, headers)")


class ParsedDocument(BaseModel):
    """
    Unified representation of a parsed enterprise document across all formats.
    """
    text: str = Field(description="Full aggregated text content")
    pages: List[ParsedPage] = Field(default_factory=list, description="Per-page extracted text items")
    total_pages: int = Field(default=1, description="Total number of pages or sections")
    word_count: int = Field(default=0, description="Total word count")
    character_count: int = Field(default=0, description="Total character count")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document-level metadata (author, title, etc.)")


class BaseDocumentParser(ABC):
    """
    Abstract Document Parser interface.
    Enforces polymorphic document parsing behavior across all supported document types.
    """

    @abstractmethod
    def parse(self, file_bytes: bytes, filename: str) -> ParsedDocument:
        """
        Parses raw document bytes into a unified ParsedDocument object.
        Must raise CorruptedFileException or ParserException on failure.
        """
        pass
