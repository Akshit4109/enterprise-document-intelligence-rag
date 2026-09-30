import io
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.exceptions import EmptyFileException, FileTooLargeException, UnsupportedFileFormatException
from app.embeddings.local import SentenceTransformerEmbeddingProvider
from app.main import app
from app.core.database import get_db
from app.retrieval.base import RetrievalFilter
from app.retrieval.vector import VectorRetriever
from app.services.ingestion import DocumentIngestionService
from app.services.storage.local import LocalStorageService
from app.services.validator import FileValidator


@pytest.fixture
def client(db_session: Session) -> TestClient:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def embedding_provider():
    return SentenceTransformerEmbeddingProvider(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        dimension=384,
    )


class TestEnterpriseMetadataFiltering:
    def test_department_filtered_retrieval(
        self, db_session: Session, embedding_provider
    ):
        ingestion = DocumentIngestionService(embedding_provider=embedding_provider)
        retriever = VectorRetriever(db=db_session, embedding_provider=embedding_provider)

        # 1. Ingest HR Document
        doc_hr, _, _, _ = ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=b"Human Resources Handbook: Employee benefits, health insurance, and 401k matching.",
            filename="hr_handbook.txt",
            name="HR Benefits Handbook",
            department="HR",
            tags=["benefits", "insurance"],
            owner_id="admin_hr",
        )

        # 2. Ingest Finance Document
        doc_fin, _, _, _ = ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=b"Finance Quarterly Report: Corporate budget allocation, capital expenditures, and revenue growth.",
            filename="finance_report.txt",
            name="Q3 Finance Report",
            department="Finance",
            tags=["quarterly", "budget"],
            owner_id="admin_fin",
        )

        # Query HR only
        filter_hr = RetrievalFilter(department="HR")
        res_hr = retriever.retrieve(query="corporate budget allocation and employee health benefits", top_k=5, filters=filter_hr)
        assert len(res_hr.results) > 0
        for match in res_hr.results:
            assert match.document_id == doc_hr.id
            assert "Human Resources" in match.content

        # Query Finance only
        filter_fin = RetrievalFilter(department="Finance")
        res_fin = retriever.retrieve(query="corporate budget allocation and employee health benefits", top_k=5, filters=filter_fin)
        assert len(res_fin.results) > 0
        for match in res_fin.results:
            assert match.document_id == doc_fin.id
            assert "Finance Quarterly" in match.content

    def test_tags_filtered_retrieval(
        self, db_session: Session, embedding_provider
    ):
        ingestion = DocumentIngestionService(embedding_provider=embedding_provider)
        retriever = VectorRetriever(db=db_session, embedding_provider=embedding_provider)

        doc_public, _, _, _ = ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=b"Public Press Release: Company launches AI document intelligence platform.",
            filename="press_release.txt",
            name="Press Release",
            department="Marketing",
            tags=["public", "press"],
        )

        doc_conf, _, _, _ = ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=b"Strictly Confidential: Internal merger acquisition target evaluation and pricing.",
            filename="merger_strategy.txt",
            name="Merger Strategy",
            department="Executive",
            tags=["confidential", "m&a"],
        )

        # Query only confidential documents
        filter_conf = RetrievalFilter(tags=["confidential"])
        res_conf = retriever.retrieve(query="document strategy and pricing evaluation", top_k=5, filters=filter_conf)
        assert len(res_conf.results) == 1
        assert res_conf.results[0].document_id == doc_conf.id
        assert "Strictly Confidential" in res_conf.results[0].content

    def test_effective_date_range_filtering(
        self, db_session: Session, embedding_provider
    ):
        ingestion = DocumentIngestionService(embedding_provider=embedding_provider)
        retriever = VectorRetriever(db=db_session, embedding_provider=embedding_provider)

        past_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
        future_date = datetime(2028, 1, 1, tzinfo=timezone.utc)

        doc_old, _, _, _ = ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=b"Archived 2023 Guidelines: Legacy travel expense reimbursement policy.",
            filename="travel_2023.txt",
            name="2023 Travel Policy",
            effective_date=past_date,
        )

        doc_future, _, _, _ = ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=b"Future 2028 Guidelines: Next generation travel expense policy.",
            filename="travel_2028.txt",
            name="2028 Travel Policy",
            effective_date=future_date,
        )

        # Filter for policies effective in 2027 and beyond
        filter_future = RetrievalFilter(effective_from=datetime(2027, 1, 1, tzinfo=timezone.utc))
        res = retriever.retrieve(query="travel expense reimbursement policy", top_k=5, filters=filter_future)
        assert len(res.results) == 1
        assert res.results[0].document_id == doc_future.id
        assert "Future 2028" in res.results[0].content


class TestAccessControlFoundation:
    def test_user_document_isolation(
        self, db_session: Session, embedding_provider
    ):
        """
        Verifies:
        User A -> Document A
        User B -> Document B
        User A should NOT retrieve Document B.
        """
        ingestion = DocumentIngestionService(embedding_provider=embedding_provider)
        retriever = VectorRetriever(db=db_session, embedding_provider=embedding_provider)

        # User A owns Document A
        doc_a, _, _, _ = ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=b"User A Private Journal: Encrypted secret project roadmap for Apollo.",
            filename="project_apollo.txt",
            name="Project Apollo",
            owner_id="user_a",
        )

        # User B owns Document B
        doc_b, _, _, _ = ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=b"User B Private Journal: Encrypted secret project roadmap for Artemis.",
            filename="project_artemis.txt",
            name="Project Artemis",
            owner_id="user_b",
        )

        # User A searches for project roadmaps
        filter_user_a = RetrievalFilter(requesting_user_id="user_a")
        res_user_a = retriever.retrieve(query="secret project roadmap", top_k=10, filters=filter_user_a)
        assert len(res_user_a.results) > 0
        for match in res_user_a.results:
            assert match.document_id == doc_a.id
            assert "Apollo" in match.content
            assert "Artemis" not in match.content

        # User B searches for project roadmaps
        filter_user_b = RetrievalFilter(requesting_user_id="user_b")
        res_user_b = retriever.retrieve(query="secret project roadmap", top_k=10, filters=filter_user_b)
        assert len(res_user_b.results) > 0
        for match in res_user_b.results:
            assert match.document_id == doc_b.id
            assert "Artemis" in match.content
            assert "Apollo" not in match.content


class TestSecurityHardening:
    def test_safe_filenames_and_path_traversal_sanitization(self):
        # Malicious filename attempting directory traversal and null byte injection
        malicious_filename = "../../../../../etc/passwd\x00_exploit.pdf"
        sanitized = FileValidator.sanitize_filename(malicious_filename)
        assert "../" not in sanitized
        assert ".." not in sanitized
        assert "\x00" not in sanitized
        assert sanitized.endswith(".pdf")

    def test_storage_service_rejects_path_traversal(self, tmp_path):
        storage = LocalStorageService(root_dir=str(tmp_path / "safe_storage"))
        
        # Test direct get with traversal
        with pytest.raises(ValueError, match="Path traversal detected"):
            storage.get(str(tmp_path / "outside_file.txt"))

    def test_file_size_limit_rejection(self):
        # File exceeding MAX_UPLOAD_SIZE_BYTES limit
        oversized_bytes = b"0" * (FileValidator.validate.__globals__["settings"].MAX_UPLOAD_SIZE_BYTES + 1024)
        with pytest.raises(FileTooLargeException):
            FileValidator.validate(oversized_bytes, "large_file.txt")

    def test_empty_file_rejection(self):
        with pytest.raises(EmptyFileException):
            FileValidator.validate(b"", "empty.txt")

    def test_spoofed_pdf_magic_byte_rejection(self):
        # Text file pretending to be PDF
        spoofed_pdf_bytes = b"Hello world, I am just plain text pretending to be a PDF"
        with pytest.raises(UnsupportedFileFormatException, match="missing PDF magic header"):
            FileValidator.validate(spoofed_pdf_bytes, "fake.pdf")


class TestEnterpriseSearchAPI:
    def test_search_api_with_department_and_access_control(self, client: TestClient):
        # Upload doc with department
        file_bytes = io.BytesIO(b"Enterprise HR Policy: Paid parental leave is 16 weeks.")
        upload_res = client.post(
            "/api/v1/documents/upload",
            files={"file": ("parental_leave.txt", file_bytes, "text/plain")},
            data={
                "name": "Parental Leave Policy",
                "department": "HR",
                "tags": "benefits,leave",
                "owner_id": "hr_manager",
            },
        )
        assert upload_res.status_code == 201
        doc_id = upload_res.json()["document"]["id"]

        # Search with matching department
        search_res = client.post(
            "/api/v1/search",
            json={
                "query": "parental leave duration",
                "filters": {
                    "department": "HR",
                    "requesting_user_id": "hr_manager",
                },
            },
        )
        assert search_res.status_code == 200
        data = search_res.json()
        assert len(data["results"]) >= 1
        assert "16 weeks" in data["results"][0]["content"]

        # Search with non-matching department
        search_mismatch = client.post(
            "/api/v1/search",
            json={
                "query": "parental leave duration",
                "filters": {
                    "department": "Legal",
                },
            },
        )
        assert search_mismatch.status_code == 200
        assert len(search_mismatch.json()["results"]) == 0
