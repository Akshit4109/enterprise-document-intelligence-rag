import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.chunking.base import BaseChunker, RawChunk
from app.chunking.recursive import RecursiveCharacterChunker
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.exceptions import DocumentNotFoundException
from app.core.logging import logger, log_duration
from app.embeddings.base import BaseEmbeddingProvider
from app.embeddings import get_embedding_provider
from app.models.document import Document, DocumentStatus
from app.models.document_version import DocumentVersion, VersionStatus
from app.models.chunk import Chunk
from app.parsers.base import ParsedDocument
from app.parsers.factory import DocumentParserFactory
from app.services.storage.base import BaseStorageService
from app.services.storage import get_storage_service
from app.services.validator import FileValidator


class DocumentIngestionService:
    """
    Orchestrator for enterprise document ingestion, versioning, metadata management, and embedding.
    Pipeline: Upload -> Validation -> Storage -> Parsing -> Chunking -> Batch Embedding -> PostgreSQL/pgvector
    """

    def __init__(
        self,
        storage_service: Optional[BaseStorageService] = None,
        chunker: Optional[BaseChunker] = None,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
    ):
        self.storage_service = storage_service or get_storage_service()
        self.chunker = chunker or RecursiveCharacterChunker(
            chunk_size=settings.DEFAULT_CHUNK_SIZE,
            chunk_overlap=settings.DEFAULT_CHUNK_OVERLAP,
        )
        self.embedding_provider = embedding_provider or get_embedding_provider()

    def process_and_ingest_document(
        self,
        db: Session,
        file_bytes: bytes,
        filename: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        owner_id: str = "default_user",
        department: Optional[str] = None,
        tags: Optional[List[str]] = None,
        effective_date: Optional[datetime] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
        document_id: Optional[uuid.UUID] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> Tuple[Document, DocumentVersion, ParsedDocument, List[Chunk]]:
        """
        Executes complete ingestion pipeline synchronously with batch embedding generation, metadata tagging, and transaction safety.
        """
        clean_filename = FileValidator.sanitize_filename(filename)

        with log_duration("Document Ingestion Pipeline", {"filename": clean_filename, "owner_id": owner_id, "department": department}):
            # Step 1: File Validation
            with log_duration("File Validation", {"filename": clean_filename}):
                doc_type, checksum = FileValidator.validate(file_bytes, clean_filename)
                display_name = name.strip() if (name and name.strip()) else clean_filename

            # Step 2: Storage Persistence
            subpath = f"{owner_id}/{doc_type}"
            with log_duration("Storage Persistence", {"subpath": subpath}):
                storage_path = self.storage_service.save(
                    file_bytes=file_bytes,
                    filename=clean_filename,
                    subpath=subpath,
                )

            # Step 3: Parsing
            with log_duration("Document Parsing", {"type": doc_type}):
                parser = DocumentParserFactory.get_parser(doc_type)
                parsed_doc = parser.parse(file_bytes=file_bytes, filename=clean_filename)

            # Step 4: Database Persistence (Document & DocumentVersion)
            try:
                if document_id:
                    stmt = select(Document).where(Document.id == document_id)
                    document = db.execute(stmt).scalar_one_or_none()
                    if not document:
                        raise DocumentNotFoundException(
                            message=f"Document with ID '{document_id}' not found.",
                            details={"document_id": str(document_id)}
                        )

                    if department is not None:
                        document.department = department
                    if tags is not None:
                        document.tags = tags
                    if effective_date is not None:
                        document.effective_date = effective_date
                    if extra_metadata is not None:
                        document.extra_metadata = extra_metadata

                    version_stmt = select(func.coalesce(func.max(DocumentVersion.version_number), 0)).where(
                        DocumentVersion.document_id == document_id
                    )
                    max_version = db.execute(version_stmt).scalar()
                    next_version = max_version + 1
                else:
                    document = Document(
                        name=display_name,
                        description=description,
                        document_type=doc_type,
                        owner_id=owner_id,
                        department=department,
                        tags=tags or [],
                        effective_date=effective_date,
                        extra_metadata=extra_metadata or {},
                        status=DocumentStatus.ACTIVE.value,
                    )
                    db.add(document)
                    db.flush()
                    next_version = 1

                version = DocumentVersion(
                    document_id=document.id,
                    version_number=next_version,
                    file_name=clean_filename,
                    storage_path=storage_path,
                    file_size=len(file_bytes),
                    checksum=checksum,
                    created_by=owner_id,
                    status=VersionStatus.PROCESSING.value,
                )
                db.add(version)
                db.flush()

                # Set as active version by default
                document.active_version_id = version.id

                # Step 5: Chunking
                with log_duration("Document Chunking", {"document_id": str(document.id), "version": next_version}):
                    active_chunker = self.chunker
                    if chunk_size is not None or chunk_overlap is not None:
                        sz = chunk_size or settings.DEFAULT_CHUNK_SIZE
                        ov = chunk_overlap if chunk_overlap is not None else settings.DEFAULT_CHUNK_OVERLAP
                        active_chunker = RecursiveCharacterChunker(chunk_size=sz, chunk_overlap=ov)

                    raw_chunks: List[RawChunk] = active_chunker.chunk_document(
                        parsed_doc=parsed_doc,
                        document_id=document.id,
                        version_id=version.id,
                        filename=clean_filename,
                    )

                # Step 6: Batch Embedding Generation
                with log_duration("Embedding Generation", {"chunk_count": len(raw_chunks)}):
                    chunk_texts = [c.content for c in raw_chunks]
                    embeddings: List[List[float]] = []
                    if chunk_texts:
                        embeddings = self.embedding_provider.embed_batch(
                            texts=chunk_texts,
                            batch_size=settings.EMBEDDING_BATCH_SIZE,
                        )

                # Step 7: Persist Chunks and Vectors into PostgreSQL
                with log_duration("pgvector Persistence", {"chunks_to_insert": len(raw_chunks)}):
                    created_chunks: List[Chunk] = []
                    for i, raw_c in enumerate(raw_chunks):
                        vector = embeddings[i] if i < len(embeddings) else None
                        chunk_model = Chunk(
                            document_version_id=version.id,
                            chunk_index=raw_c.chunk_index,
                            content=raw_c.content,
                            page_number=raw_c.page_number,
                            chunk_metadata=raw_c.metadata,
                            embedding=vector,
                            embedding_model=self.embedding_provider.model_name if vector is not None else None,
                        )
                        db.add(chunk_model)
                        created_chunks.append(chunk_model)

                    version.status = VersionStatus.READY.value
                    db.commit()
                    db.refresh(document)
                    db.refresh(version)

                return document, version, parsed_doc, created_chunks

            except Exception:
                db.rollback()
                self.storage_service.delete(storage_path)
                raise

    def prepare_async_ingestion(
        self,
        db: Session,
        file_bytes: bytes,
        filename: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        owner_id: str = "default_user",
        department: Optional[str] = None,
        tags: Optional[List[str]] = None,
        effective_date: Optional[datetime] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
        document_id: Optional[uuid.UUID] = None,
    ) -> Tuple[Document, DocumentVersion, str, str]:
        """
        Validates, saves file to storage, creates initial Document & DocumentVersion in 'processing' status,
        and returns details to trigger a background worker task.
        """
        clean_filename = FileValidator.sanitize_filename(filename)
        doc_type, checksum = FileValidator.validate(file_bytes, clean_filename)
        display_name = name.strip() if (name and name.strip()) else clean_filename

        subpath = f"{owner_id}/{doc_type}"
        storage_path = self.storage_service.save(
            file_bytes=file_bytes,
            filename=clean_filename,
            subpath=subpath,
        )

        try:
            if document_id:
                stmt = select(Document).where(Document.id == document_id)
                document = db.execute(stmt).scalar_one_or_none()
                if not document:
                    raise DocumentNotFoundException(
                        message=f"Document with ID '{document_id}' not found.",
                        details={"document_id": str(document_id)}
                    )
                if department is not None:
                    document.department = department
                if tags is not None:
                    document.tags = tags
                if effective_date is not None:
                    document.effective_date = effective_date
                if extra_metadata is not None:
                    document.extra_metadata = extra_metadata

                version_stmt = select(func.coalesce(func.max(DocumentVersion.version_number), 0)).where(
                    DocumentVersion.document_id == document_id
                )
                max_version = db.execute(version_stmt).scalar()
                next_version = max_version + 1
            else:
                document = Document(
                    name=display_name,
                    description=description,
                    document_type=doc_type,
                    owner_id=owner_id,
                    department=department,
                    tags=tags or [],
                    effective_date=effective_date,
                    extra_metadata=extra_metadata or {},
                    status=DocumentStatus.ACTIVE.value,
                )
                db.add(document)
                db.flush()
                next_version = 1

            version = DocumentVersion(
                document_id=document.id,
                version_number=next_version,
                file_name=clean_filename,
                storage_path=storage_path,
                file_size=len(file_bytes),
                checksum=checksum,
                created_by=owner_id,
                status=VersionStatus.PROCESSING.value,
            )
            db.add(version)
            db.flush()

            document.active_version_id = version.id
            db.commit()
            db.refresh(document)
            db.refresh(version)

            return document, version, storage_path, doc_type

        except Exception:
            db.rollback()
            self.storage_service.delete(storage_path)
            raise

    @classmethod
    def execute_background_ingestion(
        cls,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
        storage_path: str,
        filename: str,
        doc_type: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> None:
        """
        Background worker routine: reads file from storage, parses, chunks, generates embeddings,
        persists into pgvector, and marks version 'ready'.
        """
        logger.info(f"Background ingestion worker started for Document {document_id}, Version {version_id}")
        storage = get_storage_service()
        embedding_provider = get_embedding_provider()
        chunker = RecursiveCharacterChunker(
            chunk_size=chunk_size or settings.DEFAULT_CHUNK_SIZE,
            chunk_overlap=chunk_overlap or settings.DEFAULT_CHUNK_OVERLAP,
        )

        with SessionLocal() as db:
            version = db.get(DocumentVersion, version_id)
            if not version:
                logger.error(f"Version {version_id} not found in background job.")
                return

            try:
                file_bytes = storage.get(storage_path)
                parser = DocumentParserFactory.get_parser(doc_type)
                parsed_doc = parser.parse(file_bytes=file_bytes, filename=filename)

                raw_chunks = chunker.chunk_document(
                    parsed_doc=parsed_doc,
                    document_id=document_id,
                    version_id=version_id,
                    filename=filename,
                )

                chunk_texts = [c.content for c in raw_chunks]
                embeddings: List[List[float]] = []
                if chunk_texts:
                    embeddings = embedding_provider.embed_batch(
                        texts=chunk_texts,
                        batch_size=settings.EMBEDDING_BATCH_SIZE,
                    )

                for i, raw_c in enumerate(raw_chunks):
                    vector = embeddings[i] if i < len(embeddings) else None
                    chunk_model = Chunk(
                        document_version_id=version.id,
                        chunk_index=raw_c.chunk_index,
                        content=raw_c.content,
                        page_number=raw_c.page_number,
                        chunk_metadata=raw_c.metadata,
                        embedding=vector,
                        embedding_model=embedding_provider.model_name if vector is not None else None,
                    )
                    db.add(chunk_model)

                version.status = VersionStatus.READY.value
                db.commit()
                logger.info(f"Background ingestion worker completed successfully for Document {document_id}, Version {version_id} ({len(raw_chunks)} chunks).")

            except Exception as exc:
                db.rollback()
                version.status = VersionStatus.FAILED.value
                db.commit()
                logger.error(f"Background ingestion failed for Document {document_id}, Version {version_id}: {exc}")

    def set_active_version(
        self,
        db: Session,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> Document:
        """
        Sets a specific version as the active version for search and retrieval.
        """
        doc = db.get(Document, document_id)
        if not doc:
            raise DocumentNotFoundException(
                message=f"Document with ID '{document_id}' not found.",
                details={"document_id": str(document_id)}
            )

        ver = db.get(DocumentVersion, version_id)
        if not ver or ver.document_id != document_id:
            raise ValueError(f"Version '{version_id}' does not belong to document '{document_id}'.")

        doc.active_version_id = version_id
        db.commit()
        db.refresh(doc)
        return doc
