import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.document_version import DocumentVersion


class DocumentStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class DocumentType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MARKDOWN = "md"
    OTHER = "other"


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    department: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        doc="Enterprise department/domain (e.g. HR, Finance, Legal, Engineering)",
    )
    tags: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        server_default="[]",
        doc="Categorical enterprise tags and classification labels",
    )
    effective_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Date when document or policy takes effect",
    )
    extra_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default="{}",
        doc="Arbitrary structured enterprise metadata",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=DocumentStatus.ACTIVE.value,
        nullable=False,
        index=True,
    )
    active_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="SET NULL", use_alter=True, name="fk_documents_active_version_id"),
        nullable=True,
        index=True,
        doc="Explicitly pinned active version for search and retrieval",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    versions: Mapped[List["DocumentVersion"]] = relationship(
        "DocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        foreign_keys="DocumentVersion.document_id",
        order_by="DocumentVersion.version_number.desc()",
        lazy="selectin",
    )

    active_version: Mapped[Optional["DocumentVersion"]] = relationship(
        "DocumentVersion",
        foreign_keys=[active_version_id],
        post_update=True,
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, name='{self.name}', department='{self.department}', type='{self.document_type}', status='{self.status}', active_version_id={self.active_version_id})>"
