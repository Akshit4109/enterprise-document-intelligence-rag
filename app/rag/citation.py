import uuid
from typing import List, Optional
from pydantic import BaseModel, Field

from app.retrieval.base import RetrievedChunk


class CitationSource(BaseModel):
    """
    Structured citation reference metadata for grounded RAG verification.
    """
    source_index: int = Field(description="1-based index matching [N] in the generated answer")
    document_id: uuid.UUID
    document_name: str
    document_version_id: uuid.UUID
    version_number: int
    page_number: Optional[int] = None
    source_filename: str
    chunk_id: uuid.UUID
    similarity_score: float
    snippet: str
    citation_label: str = Field(description="Formatted human-readable citation label")


class CitationBuilder:
    """
    Constructs structured citation objects and citation label strings from retrieved chunks.
    """

    @classmethod
    def build_citations(cls, chunks: List[RetrievedChunk]) -> List[CitationSource]:
        citations: List[CitationSource] = []
        for i, chunk in enumerate(chunks, start=1):
            page_str = f"Page {chunk.page_number}" if chunk.page_number is not None else "Page N/A"
            label = f"[{i}] {chunk.document_name} — v{chunk.version_number} — {page_str}"
            
            snippet = chunk.content[:150] + ("..." if len(chunk.content) > 150 else "")

            citations.append(
                CitationSource(
                    source_index=i,
                    document_id=chunk.document_id,
                    document_name=chunk.document_name,
                    document_version_id=chunk.document_version_id,
                    version_number=chunk.version_number,
                    page_number=chunk.page_number,
                    source_filename=chunk.source_filename,
                    chunk_id=chunk.chunk_id,
                    similarity_score=chunk.similarity_score,
                    snippet=snippet,
                    citation_label=label,
                )
            )
        return citations
