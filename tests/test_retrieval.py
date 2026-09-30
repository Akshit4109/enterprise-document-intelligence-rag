import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.embeddings.mock import MockEmbeddingProvider
from app.embeddings.local import SentenceTransformerEmbeddingProvider
from app.main import app
from app.core.database import get_db
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus, DocumentType
from app.models.document_version import DocumentVersion, VersionStatus
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
def populated_knowledge_base(db_session: Session):
    """
    Populates database with realistic multi-topic document chunks and embeddings.
    Uses SentenceTransformerEmbeddingProvider for realistic semantic cosine distances.
    """
    provider = SentenceTransformerEmbeddingProvider(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        dimension=384,
    )
    ingestion_service = DocumentIngestionService(embedding_provider=provider)

    # Document 1: HR Policies
    hr_doc_text = (
        "Company Leave and Maternity Policy.\n\n"
        "All full-time employees are eligible for 16 weeks of fully paid maternity and parental leave.\n\n"
        "Annual vacation allowance is 25 business days per calendar year."
    ).encode("utf-8")

    doc_hr, ver_hr, _, chunks_hr = ingestion_service.process_and_ingest_document(
        db=db_session,
        file_bytes=hr_doc_text,
        filename="hr_handbook.txt",
        name="Employee HR Handbook",
        owner_id="usr_hr_lead",
        chunk_size=120,
        chunk_overlap=20,
    )

    # Document 2: Distributed Systems Engineering
    tech_doc_text = (
        "Distributed Database Architecture and Replication.\n\n"
        "PostgreSQL with pgvector provides efficient vector similarity indexing using HNSW graphs.\n\n"
        "Consensus protocols like Raft ensure fault-tolerant state machine replication across server nodes."
    ).encode("utf-8")

    doc_tech, ver_tech, _, chunks_tech = ingestion_service.process_and_ingest_document(
        db=db_session,
        file_bytes=tech_doc_text,
        filename="db_architecture.txt",
        name="Database Architecture Guide",
        owner_id="usr_eng_lead",
        chunk_size=120,
        chunk_overlap=20,
    )

    return {
        "provider": provider,
        "hr_doc": doc_hr,
        "hr_ver": ver_hr,
        "tech_doc": doc_tech,
        "tech_ver": ver_tech,
    }


class TestSemanticRetrievalEngine:
    def test_relevant_chunks_rank_higher(self, db_session: Session, populated_knowledge_base: dict):
        provider = populated_knowledge_base["provider"]
        retriever = VectorRetriever(db=db_session, embedding_provider=provider)

        query = "How many weeks of paid maternity leave do employees get?"
        result = retriever.retrieve(query=query, top_k=5)

        assert result.total_results > 0
        top_match = result.results[0]
        # Most relevant chunk should be the HR maternity chunk
        assert "maternity and parental leave" in top_match.content
        assert top_match.document_name == "Employee HR Handbook"
        assert top_match.similarity_score > 0.4
        assert result.execution_time_ms >= 0.0

    def test_top_k_selection(self, db_session: Session, populated_knowledge_base: dict):
        provider = populated_knowledge_base["provider"]
        retriever = VectorRetriever(db=db_session, embedding_provider=provider)

        # Retrieve top 1
        result_top1 = retriever.retrieve(query="database replication and consensus", top_k=1)
        assert len(result_top1.results) == 1
        assert "Database Architecture and Replication" in result_top1.results[0].content or "Consensus protocols" in result_top1.results[0].content

        # Retrieve top 3
        result_top3 = retriever.retrieve(query="database replication and consensus", top_k=3)
        assert len(result_top3.results) >= 2

    def test_similarity_threshold_filtering(self, db_session: Session, populated_knowledge_base: dict):
        provider = populated_knowledge_base["provider"]
        retriever = VectorRetriever(db=db_session, embedding_provider=provider)

        # Unrelated query with high threshold should yield 0 results
        result_strict = retriever.retrieve(
            query="Deep sea exploration and submarine propulsion mechanics",
            top_k=5,
            similarity_threshold=0.85,
        )
        assert len(result_strict.results) == 0

    def test_metadata_preservation(self, db_session: Session, populated_knowledge_base: dict):
        provider = populated_knowledge_base["provider"]
        retriever = VectorRetriever(db=db_session, embedding_provider=provider)

        result = retriever.retrieve(query="maternity leave", top_k=1)
        assert len(result.results) == 1

        match = result.results[0]
        assert match.chunk_id is not None
        assert match.document_id == populated_knowledge_base["hr_doc"].id
        assert match.document_version_id == populated_knowledge_base["hr_ver"].id
        assert match.source_filename == "hr_handbook.txt"
        assert match.version_number == 1
        assert match.chunk_index is not None
        assert match.similarity_score > 0.0

    def test_metadata_filtering(self, db_session: Session, populated_knowledge_base: dict):
        provider = populated_knowledge_base["provider"]
        retriever = VectorRetriever(db=db_session, embedding_provider=provider)

        # Query matches tech document topic, but filter to only HR document
        filter_hr = RetrievalFilter(document_id=populated_knowledge_base["hr_doc"].id)
        result = retriever.retrieve(
            query="database architecture and replication",
            top_k=5,
            filters=filter_hr,
        )

        for chunk in result.results:
            assert chunk.document_id == populated_knowledge_base["hr_doc"].id

    def test_nonexistent_filter_returns_empty_results(self, db_session: Session, populated_knowledge_base: dict):
        provider = populated_knowledge_base["provider"]
        retriever = VectorRetriever(db=db_session, embedding_provider=provider)

        fake_id = uuid.uuid4()
        result = retriever.retrieve(
            query="maternity leave policy",
            top_k=5,
            filters=RetrievalFilter(document_id=fake_id),
        )
        assert result.total_results == 0
        assert len(result.results) == 0


class TestSearchAPI:
    def test_search_api_endpoint(self, client: TestClient, populated_knowledge_base: dict):
        payload = {
            "query": "What is the paid parental leave policy?",
            "top_k": 3,
            "similarity_threshold": 0.2,
        }

        response = client.post("/api/v1/search", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["query"] == payload["query"]
        assert data["total_results"] > 0
        assert len(data["results"]) <= 3
        top_content = data["results"][0]["content"]
        assert "Leave and Maternity Policy" in top_content or "maternity and parental leave" in top_content
        assert data["results"][0]["document_name"] == "Employee HR Handbook"
        assert data["results"][0]["similarity_score"] > 0.0
        assert data["execution_time_ms"] >= 0.0
