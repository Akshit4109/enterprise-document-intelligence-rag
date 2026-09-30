import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.embeddings.local import SentenceTransformerEmbeddingProvider
from app.main import app
from app.core.database import get_db
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.retrieval.base import RetrievalFilter
from app.retrieval.vector import VectorRetriever
from app.services.ingestion import DocumentIngestionService


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


class TestDocumentVersioning:
    def test_version_creation_and_auto_numbering(
        self, db_session: Session, embedding_provider
    ):
        ingestion = DocumentIngestionService(embedding_provider=embedding_provider)

        # Version 1
        v1_text = "Employee Handbook v1: 15 days of annual leave.".encode("utf-8")
        doc, v1, _, chunks_v1 = ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=v1_text,
            filename="handbook_v1.txt",
            name="Employee Handbook",
            owner_id="usr_admin",
        )
        assert v1.version_number == 1
        assert doc.active_version_id == v1.id

        # Version 2
        v2_text = "Employee Handbook v2: 20 days of annual leave.".encode("utf-8")
        doc, v2, _, chunks_v2 = ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=v2_text,
            filename="handbook_v2.txt",
            document_id=doc.id,
            owner_id="usr_admin",
        )
        assert v2.version_number == 2
        assert doc.active_version_id == v2.id

        # Version 3
        v3_text = "Employee Handbook v3: 25 days of annual leave.".encode("utf-8")
        doc, v3, _, chunks_v3 = ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=v3_text,
            filename="handbook_v3.txt",
            document_id=doc.id,
            owner_id="usr_admin",
        )
        assert v3.version_number == 3
        assert doc.active_version_id == v3.id

        # Verify all 3 versions exist and have independent chunks
        assert len(doc.versions) == 3
        assert len(chunks_v1) > 0
        assert len(chunks_v2) > 0
        assert len(chunks_v3) > 0
        assert chunks_v1[0].document_version_id == v1.id
        assert chunks_v2[0].document_version_id == v2.id
        assert chunks_v3[0].document_version_id == v3.id

    def test_active_version_switching(
        self, db_session: Session, embedding_provider
    ):
        ingestion = DocumentIngestionService(embedding_provider=embedding_provider)

        doc, v1, _, _ = ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=b"Version 1 content",
            filename="doc_v1.txt",
            name="Policy Document",
        )
        doc, v2, _, _ = ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=b"Version 2 content",
            filename="doc_v2.txt",
            document_id=doc.id,
        )

        assert doc.active_version_id == v2.id

        # Switch active version back to v1
        updated_doc = ingestion.set_active_version(
            db=db_session,
            document_id=doc.id,
            version_id=v1.id,
        )
        assert updated_doc.active_version_id == v1.id

    def test_retrieval_defaults_to_active_version(
        self, db_session: Session, embedding_provider
    ):
        ingestion = DocumentIngestionService(embedding_provider=embedding_provider)
        retriever = VectorRetriever(db=db_session, embedding_provider=embedding_provider)

        # Ingest v1 with old vacation policy
        doc, v1, _, _ = ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=b"Company Policy: Annual vacation allowance is exactly 10 days.",
            filename="policy_v1.txt",
            name="Vacation Policy",
        )

        # Ingest v2 with updated vacation policy (becomes active)
        doc, v2, _, _ = ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=b"Company Policy: Annual vacation allowance is exactly 30 days.",
            filename="policy_v2.txt",
            document_id=doc.id,
        )

        # Query without version filter (should match v2 only for Vacation Policy)
        filter_doc = RetrievalFilter(document_id=doc.id)
        result_default = retriever.retrieve(query="annual vacation allowance days", top_k=5, filters=filter_doc)
        assert len(result_default.results) > 0
        top_match = result_default.results[0]
        assert "30 days" in top_match.content
        assert top_match.version_number == 2

        # Verify old 10 days version does NOT appear in active results
        for match in result_default.results:
            assert match.version_number == 2

    def test_historical_version_preservation_and_targeted_retrieval(
        self, db_session: Session, embedding_provider
    ):
        ingestion = DocumentIngestionService(embedding_provider=embedding_provider)
        retriever = VectorRetriever(db=db_session, embedding_provider=embedding_provider)

        # Ingest v1 and v2
        doc, v1, _, _ = ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=b"Historical clause: Overtime pay multiplier is 1.5x.",
            filename="compensation_v1.txt",
            name="Compensation Policy",
        )
        doc, v2, _, _ = ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=b"Modern clause: Overtime pay multiplier is 2.0x.",
            filename="compensation_v2.txt",
            document_id=doc.id,
        )

        # Explicitly query historical v1
        filter_v1 = RetrievalFilter(document_id=doc.id, version_number=1)
        result_v1 = retriever.retrieve(query="Overtime pay multiplier", top_k=1, filters=filter_v1)
        assert len(result_v1.results) == 1
        assert "1.5x" in result_v1.results[0].content
        assert result_v1.results[0].version_number == 1


class TestVersioningAPI:
    def test_versioning_api_endpoints(self, client: TestClient):
        # 1. Upload initial document (v1)
        file1 = ("handbook.txt", io.BytesIO(b"Employee Handbook initial text"), "text/plain")
        res1 = client.post(
            "/api/v1/documents/upload",
            files={"file": file1},
            data={"name": "Company Handbook", "owner_id": "usr_hr"},
        )
        assert res1.status_code == 201
        doc_id = res1.json()["document"]["id"]
        v1_id = res1.json()["version"]["id"]

        # 2. Upload revision (v2) via POST /documents/{id}/versions
        file2 = ("handbook_revised.txt", io.BytesIO(b"Employee Handbook revised revision 2 text"), "text/plain")
        res2 = client.post(
            f"/api/v1/documents/{doc_id}/versions",
            files={"file": file2},
        )
        assert res2.status_code == 201
        v2_id = res2.json()["version"]["id"]
        assert res2.json()["version"]["version_number"] == 2

        # 3. List versions via GET /documents/{id}/versions
        list_res = client.get(f"/api/v1/documents/{doc_id}/versions")
        assert list_res.status_code == 200
        versions_list = list_res.json()
        assert len(versions_list) == 2
        assert versions_list[0]["version_number"] == 2  # Ordered descending
        assert versions_list[0]["is_active"] is True

        # 4. Get specific version detail via GET /documents/{id}/versions/{version_id}
        get_v1_res = client.get(f"/api/v1/documents/{doc_id}/versions/{v1_id}")
        assert get_v1_res.status_code == 200
        assert get_v1_res.json()["version_number"] == 1

        # 5. Activate v1 via PUT /documents/{id}/versions/{version_id}/activate
        activate_res = client.put(f"/api/v1/documents/{doc_id}/versions/{v1_id}/activate")
        assert activate_res.status_code == 200
        assert activate_res.json()["active_version_id"] == v1_id
