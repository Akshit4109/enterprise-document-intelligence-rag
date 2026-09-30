import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import CheckConstraint, Computed, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from pgvector.sqlalchemy import Vector

from app.core.config import settings
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.document_version import DocumentVersion


class Chunk(Base, TimestampMixin):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_version_id", "chunk_index", name="uq_version_chunk_index"),
        CheckConstraint("chunk_index >= 0", name="ck_chunk_index_non_negative"),
        CheckConstraint("page_number IS NULL OR page_number >= 1", name="ck_chunk_page_number_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    page_number: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    # JSON metadata for section, tokens, offsets, etc.
    chunk_metadata: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=dict,
        server_default="{}",
    )

    # Vector embedding column (pgvector)
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(settings.EMBEDDING_DIMENSION),
        nullable=True,
    )
    embedding_model: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Full-Text Search TSVECTOR column (PostgreSQL FTS)
    search_vector: Mapped[Optional[Any]] = mapped_column(
        TSVECTOR().with_variant(Text(), "sqlite"),
        Computed("to_tsvector('english', content)", persisted=True),
        nullable=True,
    )

    # Relationships
    document_version: Mapped["DocumentVersion"] = relationship(
        "DocumentVersion",
        back_populates="chunks",
    )

    def __repr__(self) -> str:
        return (
            f"<Chunk(id={self.id}, version_id={self.document_version_id}, "
            f"index={self.chunk_index}, page={self.page_number}, has_embedding={self.embedding is not None})>"
        )
