import uuid
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus, DocumentType
from app.models.document_version import DocumentVersion, VersionStatus
from app.models.chunk import Chunk


class TestDocumentSchema:
    """Test suite covering Document entity creation, updates, and defaults."""

    def test_create_document_success(self, db_session: Session):
        doc = Document(
            name="Q3 Financial Report",
            description="Quarterly financial statements and analysis",
            document_type=DocumentType.PDF.value,
            owner_id="usr_finance_01",
            status=DocumentStatus.ACTIVE.value,
        )
        db_session.add(doc)
        db_session.flush()

        assert doc.id is not None
        assert isinstance(doc.id, uuid.UUID)
        assert doc.name == "Q3 Financial Report"
        assert doc.document_type == "pdf"
        assert doc.owner_id == "usr_finance_01"
        assert doc.status == "active"
        assert doc.created_at is not None
        assert doc.updated_at is not None

    def test_document_non_nullable_fields(self, db_session: Session):
        # Missing required name and document_type
        doc = Document(
            owner_id="usr_finance_01",
        )
        db_session.add(doc)
        with pytest.raises(IntegrityError):
            db_session.flush()


class TestDocumentVersionSchema:
    """Test suite covering DocumentVersion entity, constraints, and relationships."""

    def test_create_version_for_document(self, db_session: Session):
        doc = Document(
            name="Employee Handbook",
            description="HR guidelines and policies",
            document_type=DocumentType.PDF.value,
            owner_id="usr_hr_01",
        )
        db_session.add(doc)
        db_session.flush()

        version_1 = DocumentVersion(
            document_id=doc.id,
            version_number=1,
            file_name="handbook_v1.pdf",
            storage_path="s3://enterprise-docs/handbook_v1.pdf",
            file_size=2048576,
            checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            created_by="usr_hr_01",
            status=VersionStatus.READY.value,
        )
        db_session.add(version_1)
        db_session.flush()

        assert version_1.id is not None
        assert version_1.document_id == doc.id
        assert version_1.version_number == 1
        assert version_1.file_size == 2048576
        assert len(doc.versions) == 1
        assert doc.versions[0].id == version_1.id

    def test_multiple_versions_per_document(self, db_session: Session):
        doc = Document(
            name="API Documentation",
            document_type=DocumentType.MARKDOWN.value,
            owner_id="usr_eng_01",
        )
        db_session.add(doc)
        db_session.flush()

        v1 = DocumentVersion(
            document_id=doc.id,
            version_number=1,
            file_name="api_v1.md",
            storage_path="s3://docs/api_v1.md",
            file_size=1024,
            checksum="hash1",
        )
        v2 = DocumentVersion(
            document_id=doc.id,
            version_number=2,
            file_name="api_v2.md",
            storage_path="s3://docs/api_v2.md",
            file_size=1280,
            checksum="hash2",
        )
        db_session.add_all([v1, v2])
        db_session.flush()

        # Check version ordering (descending)
        db_session.refresh(doc)
        assert len(doc.versions) == 2
        assert [v.version_number for v in doc.versions] == [2, 1]

    def test_unique_version_number_per_document_constraint(self, db_session: Session):
        doc = Document(
            name="Architecture Spec",
            document_type=DocumentType.DOCX.value,
            owner_id="usr_eng_01",
        )
        db_session.add(doc)
        db_session.flush()

        v1 = DocumentVersion(
            document_id=doc.id,
            version_number=1,
            file_name="arch_v1.docx",
            storage_path="s3://docs/arch_v1.docx",
            file_size=50000,
            checksum="hash1",
        )
        db_session.add(v1)
        db_session.flush()

        # Attempt to insert a duplicate version 1 for the same document
        v1_duplicate = DocumentVersion(
            document_id=doc.id,
            version_number=1,
            file_name="arch_v1_dup.docx",
            storage_path="s3://docs/arch_v1_dup.docx",
            file_size=50000,
            checksum="hash_dup",
        )
        db_session.add(v1_duplicate)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_version_number_check_constraint(self, db_session: Session):
        doc = Document(
            name="Policy",
            document_type=DocumentType.PDF.value,
            owner_id="usr_01",
        )
        db_session.add(doc)
        db_session.flush()

        invalid_version = DocumentVersion(
            document_id=doc.id,
            version_number=0,  # version_number must be >= 1
            file_name="policy.pdf",
            storage_path="s3://docs/policy.pdf",
            file_size=100,
            checksum="hash0",
        )
        db_session.add(invalid_version)
        with pytest.raises(IntegrityError):
            db_session.flush()


class TestChunkSchema:
    """Test suite covering Chunk entity, constraints, metadata storage, and cascades."""

    def test_create_chunks_for_version(self, db_session: Session):
        doc = Document(
            name="Security Whitepaper",
            document_type=DocumentType.PDF.value,
            owner_id="usr_sec_01",
        )
        db_session.add(doc)
        db_session.flush()

        version = DocumentVersion(
            document_id=doc.id,
            version_number=1,
            file_name="security_whitepaper.pdf",
            storage_path="s3://docs/security_whitepaper.pdf",
            file_size=1048576,
            checksum="hash_sec",
        )
        db_session.add(version)
        db_session.flush()

        chunk_0 = Chunk(
            document_version_id=version.id,
            chunk_index=0,
            content="Chapter 1: Zero Trust Architecture Overview.",
            page_number=1,
            chunk_metadata={"section": "Introduction", "token_count": 8, "char_count": 44},
        )
        chunk_1 = Chunk(
            document_version_id=version.id,
            chunk_index=1,
            content="Chapter 2: Mutual TLS and Identity Verification.",
            page_number=2,
            chunk_metadata={"section": "Implementation", "token_count": 9, "char_count": 48},
        )
        db_session.add_all([chunk_0, chunk_1])
        db_session.flush()

        assert chunk_0.id is not None
        assert chunk_1.id is not None
        assert chunk_0.chunk_metadata["section"] == "Introduction"
        assert chunk_1.chunk_metadata["token_count"] == 9

        db_session.refresh(version)
        assert len(version.chunks) == 2
        assert [c.chunk_index for c in version.chunks] == [0, 1]

    def test_unique_chunk_index_per_version(self, db_session: Session):
        doc = Document(
            name="Network Manual",
            document_type=DocumentType.TXT.value,
            owner_id="usr_net_01",
        )
        db_session.add(doc)
        db_session.flush()

        version = DocumentVersion(
            document_id=doc.id,
            version_number=1,
            file_name="manual.txt",
            storage_path="s3://docs/manual.txt",
            file_size=500,
            checksum="hash_net",
        )
        db_session.add(version)
        db_session.flush()

        chunk_a = Chunk(
            document_version_id=version.id,
            chunk_index=0,
            content="First paragraph.",
        )
        db_session.add(chunk_a)
        db_session.flush()

        # Duplicate index 0 for the same version
        chunk_b = Chunk(
            document_version_id=version.id,
            chunk_index=0,
            content="Duplicate chunk index.",
        )
        db_session.add(chunk_b)
        with pytest.raises(IntegrityError):
            db_session.flush()


class TestCascadeDeletions:
    """Test suite verifying enterprise cascading deletion behavior across tiers."""

    def test_cascade_delete_document_removes_versions_and_chunks(self, db_session: Session):
        doc = Document(
            name="Temporary Audit Log",
            document_type=DocumentType.TXT.value,
            owner_id="usr_audit_01",
        )
        db_session.add(doc)
        db_session.flush()

        version = DocumentVersion(
            document_id=doc.id,
            version_number=1,
            file_name="audit.txt",
            storage_path="s3://docs/audit.txt",
            file_size=1024,
            checksum="hash_audit",
        )
        db_session.add(version)
        db_session.flush()

        chunk = Chunk(
            document_version_id=version.id,
            chunk_index=0,
            content="Audit entries line 1-100.",
        )
        db_session.add(chunk)
        db_session.flush()

        doc_id = doc.id
        version_id = version.id
        chunk_id = chunk.id

        # Delete parent document
        db_session.delete(doc)
        db_session.flush()

        # Verify child version and chunk are cascaded away
        assert db_session.get(Document, doc_id) is None
        assert db_session.get(DocumentVersion, version_id) is None
        assert db_session.get(Chunk, chunk_id) is None

    def test_delete_version_only_removes_own_chunks(self, db_session: Session):
        doc = Document(
            name="Product Roadmap",
            document_type=DocumentType.PDF.value,
            owner_id="usr_pm_01",
        )
        db_session.add(doc)
        db_session.flush()

        v1 = DocumentVersion(
            document_id=doc.id,
            version_number=1,
            file_name="roadmap_v1.pdf",
            storage_path="s3://docs/roadmap_v1.pdf",
            file_size=1000,
            checksum="hash_v1",
        )
        v2 = DocumentVersion(
            document_id=doc.id,
            version_number=2,
            file_name="roadmap_v2.pdf",
            storage_path="s3://docs/roadmap_v2.pdf",
            file_size=2000,
            checksum="hash_v2",
        )
        db_session.add_all([v1, v2])
        db_session.flush()

        c1 = Chunk(document_version_id=v1.id, chunk_index=0, content="v1 content")
        c2 = Chunk(document_version_id=v2.id, chunk_index=0, content="v2 content")
        db_session.add_all([c1, c2])
        db_session.flush()

        c1_id = c1.id
        c2_id = c2.id
        v1_id = v1.id

        # Delete only version 1
        db_session.delete(v1)
        db_session.flush()

        # Document and version 2 and chunk 2 should remain
        assert db_session.get(Document, doc.id) is not None
        assert db_session.get(DocumentVersion, v1_id) is None
        assert db_session.get(Chunk, c1_id) is None
        assert db_session.get(DocumentVersion, v2.id) is not None
        assert db_session.get(Chunk, c2_id) is not None
