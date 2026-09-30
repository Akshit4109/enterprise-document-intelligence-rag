import json
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.exceptions import AppException, DocumentNotFoundException, EmptyFileException
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.chunk import Chunk
from app.schemas.document import (
    AsyncDocumentUploadResponse,
    ChunkResponse,
    DocumentDetailResponse,
    DocumentResponse,
    DocumentUploadResponse,
    DocumentVersionDetailResponse,
    DocumentVersionResponse,
    DocumentVersionStatusResponse,
    ParsedSummaryResponse,
)
from app.services.ingestion import DocumentIngestionService
from app.services.storage import get_storage_service

router = APIRouter(prefix="/documents", tags=["Documents"])


def parse_tags_input(tags_raw: Optional[str]) -> List[str]:
    if not tags_raw or not tags_raw.strip():
        return []
    raw = tags_raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass
    return [t.strip() for t in raw.split(",") if t.strip()]


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload, Parse, and Chunk Document (Synchronous)",
    description="Accepts PDF, DOCX, or TXT documents, validates them, saves storage artifact, parses text, splits content into semantic chunks with configurable size/overlap, and persists entities with enterprise metadata to PostgreSQL.",
)
async def upload_document(
    file: UploadFile = File(..., description="Document file to upload (PDF, DOCX, TXT)"),
    name: Optional[str] = Form(None, description="Optional custom document title"),
    description: Optional[str] = Form(None, description="Optional document description"),
    owner_id: str = Form("default_user", description="Owner/tenant identifier"),
    department: Optional[str] = Form(None, description="Enterprise department (e.g. HR, Finance, Engineering)"),
    tags: Optional[str] = Form(None, description="Comma-separated or JSON list of categorical tags"),
    effective_date: Optional[datetime] = Form(None, description="Optional effective date for document"),
    document_id: Optional[uuid.UUID] = Form(None, description="Optional existing Document UUID to create a new version"),
    chunk_size: Optional[int] = Form(None, description="Optional custom chunk size in characters (e.g. 500)"),
    chunk_overlap: Optional[int] = Form(None, description="Optional custom chunk overlap in characters (e.g. 50)"),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    if not file.filename:
        raise EmptyFileException(message="Uploaded file has no filename.")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise EmptyFileException(message=f"Uploaded file '{file.filename}' is empty (0 bytes).")

    parsed_tags = parse_tags_input(tags)
    ingestion_service = DocumentIngestionService(storage_service=get_storage_service())
    
    document, version, parsed_doc, chunks = ingestion_service.process_and_ingest_document(
        db=db,
        file_bytes=file_bytes,
        filename=file.filename,
        name=name,
        description=description,
        owner_id=owner_id,
        department=department,
        tags=parsed_tags,
        effective_date=effective_date,
        document_id=document_id,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    preview = parsed_doc.text[:300] + ("..." if len(parsed_doc.text) > 300 else "")

    return DocumentUploadResponse(
        message="Document uploaded, parsed, chunked, and embedded successfully",
        document=DocumentResponse.model_validate(document),
        version=DocumentVersionResponse.model_validate(version),
        parsing_summary=ParsedSummaryResponse(
            total_pages=parsed_doc.total_pages,
            word_count=parsed_doc.word_count,
            character_count=parsed_doc.character_count,
            chunk_count=len(chunks),
            embedding_model=ingestion_service.embedding_provider.model_name,
            embedding_dimension=ingestion_service.embedding_provider.dimension,
            metadata=parsed_doc.metadata,
            preview_text=preview,
        ),
    )


@router.post(
    "/upload/async",
    response_model=AsyncDocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload Document Asynchronously (Background Job)",
    description="Validates and accepts a document upload, returning immediately with a polling status URL while parsing, chunking, and vector embedding occur in the background.",
)
async def upload_document_async(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Document file to upload (PDF, DOCX, TXT)"),
    name: Optional[str] = Form(None, description="Optional custom document title"),
    description: Optional[str] = Form(None, description="Optional document description"),
    owner_id: str = Form("default_user", description="Owner/tenant identifier"),
    department: Optional[str] = Form(None, description="Enterprise department"),
    tags: Optional[str] = Form(None, description="Comma-separated or JSON list of tags"),
    effective_date: Optional[datetime] = Form(None, description="Optional effective date"),
    chunk_size: Optional[int] = Form(None, description="Optional custom chunk size"),
    chunk_overlap: Optional[int] = Form(None, description="Optional custom chunk overlap"),
    db: Session = Depends(get_db),
) -> AsyncDocumentUploadResponse:
    if not file.filename:
        raise EmptyFileException(message="Uploaded file has no filename.")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise EmptyFileException(message=f"Uploaded file '{file.filename}' is empty (0 bytes).")

    parsed_tags = parse_tags_input(tags)
    ingestion_service = DocumentIngestionService(storage_service=get_storage_service())

    document, version, storage_path, doc_type = ingestion_service.prepare_async_ingestion(
        db=db,
        file_bytes=file_bytes,
        filename=file.filename,
        name=name,
        description=description,
        owner_id=owner_id,
        department=department,
        tags=parsed_tags,
        effective_date=effective_date,
    )

    background_tasks.add_task(
        DocumentIngestionService.execute_background_ingestion,
        document_id=document.id,
        version_id=version.id,
        storage_path=storage_path,
        filename=version.file_name,
        doc_type=doc_type,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    poll_url = f"/api/v1/documents/{document.id}/versions/{version.id}/status"

    return AsyncDocumentUploadResponse(
        message="Document upload accepted and queued for background processing",
        document_id=document.id,
        version_id=version.id,
        version_number=version.version_number,
        status=version.status,
        poll_url=poll_url,
    )


@router.post(
    "/{document_id}/versions",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload New Document Version",
    description="Uploads a new file revision for an existing document, auto-incrementing the version number.",
)
async def upload_new_version(
    document_id: uuid.UUID,
    file: UploadFile = File(..., description="Document file revision"),
    owner_id: str = Form("default_user", description="Owner/uploader identifier"),
    department: Optional[str] = Form(None, description="Optional updated department"),
    tags: Optional[str] = Form(None, description="Optional updated tags"),
    effective_date: Optional[datetime] = Form(None, description="Optional updated effective date"),
    chunk_size: Optional[int] = Form(None, description="Optional custom chunk size"),
    chunk_overlap: Optional[int] = Form(None, description="Optional custom chunk overlap"),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    if not file.filename:
        raise EmptyFileException(message="Uploaded file has no filename.")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise EmptyFileException(message=f"Uploaded file '{file.filename}' is empty (0 bytes).")

    parsed_tags = parse_tags_input(tags) if tags is not None else None
    ingestion_service = DocumentIngestionService(storage_service=get_storage_service())

    document, version, parsed_doc, chunks = ingestion_service.process_and_ingest_document(
        db=db,
        file_bytes=file_bytes,
        filename=file.filename,
        owner_id=owner_id,
        department=department,
        tags=parsed_tags,
        effective_date=effective_date,
        document_id=document_id,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    preview = parsed_doc.text[:300] + ("..." if len(parsed_doc.text) > 300 else "")

    return DocumentUploadResponse(
        message=f"Document version {version.version_number} uploaded, parsed, chunked, and embedded successfully",
        document=DocumentResponse.model_validate(document),
        version=DocumentVersionResponse.model_validate(version),
        parsing_summary=ParsedSummaryResponse(
            total_pages=parsed_doc.total_pages,
            word_count=parsed_doc.word_count,
            character_count=parsed_doc.character_count,
            chunk_count=len(chunks),
            embedding_model=ingestion_service.embedding_provider.model_name,
            embedding_dimension=ingestion_service.embedding_provider.dimension,
            metadata=parsed_doc.metadata,
            preview_text=preview,
        ),
    )


@router.get(
    "/{document_id}/versions/{version_id}/status",
    response_model=DocumentVersionStatusResponse,
    summary="Get Ingestion Processing Status",
    description="Polls current lifecycle status of an asynchronous document version ingestion job.",
)
def get_version_status(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DocumentVersionStatusResponse:
    doc = db.get(Document, document_id)
    if not doc:
        raise DocumentNotFoundException(
            message=f"Document with ID '{document_id}' not found.",
            details={"document_id": str(document_id)}
        )

    stmt = select(DocumentVersion).where(
        DocumentVersion.id == version_id,
        DocumentVersion.document_id == document_id,
    )
    version = db.execute(stmt).scalar_one_or_none()
    if not version:
        raise DocumentNotFoundException(
            message=f"Version '{version_id}' for Document '{document_id}' not found.",
            details={"document_id": str(document_id), "version_id": str(version_id)}
        )

    return DocumentVersionStatusResponse(
        document_id=doc.id,
        version_id=version.id,
        version_number=version.version_number,
        file_name=version.file_name,
        status=version.status,
        chunk_count=len(version.chunks),
        is_active=(doc.active_version_id == version.id),
        created_at=version.created_at,
    )


@router.get(
    "/{document_id}/versions",
    response_model=List[DocumentVersionDetailResponse],
    summary="List Document Versions",
    description="Lists all historical and current versions of a document.",
)
def list_document_versions(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> List[DocumentVersionDetailResponse]:
    doc = db.get(Document, document_id)
    if not doc:
        raise DocumentNotFoundException(
            message=f"Document with ID '{document_id}' not found.",
            details={"document_id": str(document_id)}
        )

    stmt = (
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
    )
    versions = db.scalars(stmt).all()

    results = []
    for v in versions:
        is_active = (doc.active_version_id == v.id)
        v_dict = {
            "id": v.id,
            "document_id": v.document_id,
            "version_number": v.version_number,
            "file_name": v.file_name,
            "storage_path": v.storage_path,
            "file_size": v.file_size,
            "checksum": v.checksum,
            "created_by": v.created_by,
            "status": v.status,
            "created_at": v.created_at,
            "chunk_count": len(v.chunks),
            "is_active": is_active,
        }
        results.append(DocumentVersionDetailResponse.model_validate(v_dict))
    return results


@router.get(
    "/{document_id}/versions/{version_id}",
    response_model=DocumentVersionDetailResponse,
    summary="Get Document Version Detail",
    description="Fetches metadata and chunk summary for a specific document version.",
)
def get_document_version(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DocumentVersionDetailResponse:
    doc = db.get(Document, document_id)
    if not doc:
        raise DocumentNotFoundException(
            message=f"Document with ID '{document_id}' not found.",
            details={"document_id": str(document_id)}
        )

    stmt = select(DocumentVersion).where(
        DocumentVersion.id == version_id,
        DocumentVersion.document_id == document_id,
    )
    version = db.execute(stmt).scalar_one_or_none()
    if not version:
        raise DocumentNotFoundException(
            message=f"Version '{version_id}' for Document '{document_id}' not found.",
            details={"document_id": str(document_id), "version_id": str(version_id)}
        )

    return DocumentVersionDetailResponse(
        id=version.id,
        document_id=version.document_id,
        version_number=version.version_number,
        file_name=version.file_name,
        storage_path=version.storage_path,
        file_size=version.file_size,
        checksum=version.checksum,
        created_by=version.created_by,
        status=version.status,
        created_at=version.created_at,
        chunk_count=len(version.chunks),
        is_active=(doc.active_version_id == version.id),
    )


@router.put(
    "/{document_id}/versions/{version_id}/activate",
    response_model=DocumentResponse,
    summary="Set Active Document Version",
    description="Selects and activates a specific historical version as the primary version for semantic search.",
)
def activate_document_version(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DocumentResponse:
    ingestion_service = DocumentIngestionService(storage_service=get_storage_service())
    updated_doc = ingestion_service.set_active_version(
        db=db,
        document_id=document_id,
        version_id=version_id,
    )
    return DocumentResponse.model_validate(updated_doc)


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Get Document by ID",
    description="Fetches document details along with its full version history.",
)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DocumentDetailResponse:
    stmt = select(Document).where(Document.id == document_id)
    document = db.execute(stmt).scalar_one_or_none()
    if not document:
        raise DocumentNotFoundException(
            message=f"Document with ID '{document_id}' not found.",
            details={"document_id": str(document_id)}
        )
    return DocumentDetailResponse.model_validate(document)


@router.get(
    "/{document_id}/versions/{version_id}/chunks",
    response_model=List[ChunkResponse],
    summary="Get Chunks for Document Version",
    description="Retrieves all ordered chunks generated for a specific document version.",
)
def get_version_chunks(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> List[ChunkResponse]:
    stmt = select(DocumentVersion).where(
        DocumentVersion.id == version_id,
        DocumentVersion.document_id == document_id,
    )
    version = db.execute(stmt).scalar_one_or_none()
    if not version:
        raise DocumentNotFoundException(
            message=f"Version '{version_id}' for Document '{document_id}' not found.",
            details={"document_id": str(document_id), "version_id": str(version_id)}
        )

    chunk_stmt = (
        select(Chunk)
        .where(Chunk.document_version_id == version_id)
        .order_by(Chunk.chunk_index.asc())
        .offset(skip)
        .limit(limit)
    )
    chunks = db.execute(chunk_stmt).scalars().all()
    results = []
    for c in chunks:
        chunk_dict = {
            "id": c.id,
            "document_version_id": c.document_version_id,
            "chunk_index": c.chunk_index,
            "content": c.content,
            "page_number": c.page_number,
            "metadata": c.chunk_metadata,
            "embedding_model": c.embedding_model,
            "has_embedding": c.embedding is not None,
            "created_at": c.created_at,
        }
        results.append(ChunkResponse.model_validate(chunk_dict))
    return results


@router.get(
    "",
    response_model=List[DocumentResponse],
    summary="List Documents",
    description="Lists documents with pagination and metadata filtering support.",
)
def list_documents(
    skip: int = 0,
    limit: int = 50,
    owner_id: Optional[str] = None,
    department: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[DocumentResponse]:
    stmt = select(Document).offset(skip).limit(limit).order_by(Document.created_at.desc())
    if owner_id:
        stmt = stmt.where(Document.owner_id == owner_id)
    if department:
        stmt = stmt.where(func.lower(Document.department) == department.strip().lower())
    documents = db.execute(stmt).scalars().all()
    return [DocumentResponse.model_validate(d) for d in documents]


@router.get(
    "/{document_id}/versions/{version_id}/file",
    summary="Download/View Document File",
    description="Serves the raw document file artifact from storage for inline browser viewing or download.",
)
def get_document_file(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    stmt = select(DocumentVersion).where(
        DocumentVersion.id == version_id,
        DocumentVersion.document_id == document_id,
    )
    version = db.execute(stmt).scalar_one_or_none()
    if not version:
        raise DocumentNotFoundException(
            message=f"Version '{version_id}' for Document '{document_id}' not found.",
            details={"document_id": str(document_id), "version_id": str(version_id)}
        )

    storage = get_storage_service()
    if not storage.exists(version.storage_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File artifact not found on storage server for version '{version_id}'.",
        )

    content_type = "application/octet-stream"
    ext = version.file_name.split(".")[-1].lower() if "." in version.file_name else ""
    if ext == "pdf":
        content_type = "application/pdf"
    elif ext == "txt":
        content_type = "text/plain; charset=utf-8"
    elif ext == "docx":
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    return FileResponse(
        path=version.storage_path,
        filename=version.file_name,
        media_type=content_type,
    )
