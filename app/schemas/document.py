import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DocumentBase(BaseModel):
    name: str = Field(..., max_length=255, description="Document display name")
    description: Optional[str] = Field(default=None, description="Optional document description")
    document_type: str = Field(..., description="Detected format (pdf, docx, txt)")
    owner_id: str = Field(..., description="Enterprise owner/user identifier")
    department: Optional[str] = Field(default=None, description="Enterprise department (e.g. HR, Finance, Engineering)")
    tags: List[str] = Field(default_factory=list, description="Categorical classification tags")
    effective_date: Optional[datetime] = Field(default=None, description="Date when policy/document becomes effective")
    extra_metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary custom metadata")
    status: str = Field(default="active", description="Lifecycle status")
    active_version_id: Optional[uuid.UUID] = Field(default=None, description="Currently active version for RAG")


class DocumentResponse(DocumentBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentVersionResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    file_name: str
    storage_path: str
    file_size: int
    checksum: str
    created_by: Optional[str] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentVersionDetailResponse(DocumentVersionResponse):
    chunk_count: int = 0
    is_active: bool = False


class DocumentVersionStatusResponse(BaseModel):
    document_id: uuid.UUID
    version_id: uuid.UUID
    version_number: int
    file_name: str
    status: str
    chunk_count: int = 0
    is_active: bool = False
    created_at: datetime


class ChunkResponse(BaseModel):
    id: uuid.UUID
    document_version_id: uuid.UUID
    chunk_index: int
    content: str
    page_number: Optional[int] = None
    chunk_metadata: Dict[str, Any] = Field(default_factory=dict, serialization_alias="metadata")
    embedding_model: Optional[str] = None
    has_embedding: bool = Field(default=False, description="True if vector embedding is persisted")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(DocumentResponse):
    versions: List[DocumentVersionResponse] = []


class ParsedSummaryResponse(BaseModel):
    total_pages: int
    word_count: int
    character_count: int
    chunk_count: int = 0
    embedding_model: Optional[str] = None
    embedding_dimension: Optional[int] = None
    metadata: Dict[str, Any] = {}
    preview_text: str = Field(description="First 300 characters of extracted text")


class DocumentUploadResponse(BaseModel):
    message: str = "Document uploaded, parsed, chunked, and embedded successfully"
    document: DocumentResponse
    version: DocumentVersionResponse
    parsing_summary: ParsedSummaryResponse


class AsyncDocumentUploadResponse(BaseModel):
    message: str = "Document upload accepted and queued for background processing"
    document_id: uuid.UUID
    version_id: uuid.UUID
    version_number: int
    status: str = "processing"
    poll_url: str
