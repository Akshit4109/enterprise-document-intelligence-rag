import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.embeddings.base import BaseEmbeddingProvider
from app.embeddings.local import SentenceTransformerEmbeddingProvider
from app.main import app
from app.rag.base import BaseRAGEngine
from app.rag.factory import get_rag_engine
from app.rag.langchain_engine import LangChainRAGEngine
from app.services.ingestion import DocumentIngestionService
from app.services.rag import RAGService


@pytest.fixture
def embedding_provider():
    return SentenceTransformerEmbeddingProvider(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        dimension=384,
    )


@pytest.fixture
def client(db_session: Session) -> TestClient:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestRAGEngineFactory:
    def test_factory_returns_native_when_flag_is_false(self, db_session: Session, embedding_provider: BaseEmbeddingProvider):
        original_flag = settings.USE_LANGCHAIN_RAG
        try:
            settings.USE_LANGCHAIN_RAG = False
            engine = get_rag_engine(
                db=db_session,
                embedding_provider=embedding_provider,
            )
            assert isinstance(engine, BaseRAGEngine)
            assert isinstance(engine, RAGService)
        finally:
            settings.USE_LANGCHAIN_RAG = original_flag

    def test_factory_returns_langchain_when_flag_is_true(self, db_session: Session, embedding_provider: BaseEmbeddingProvider):
        original_flag = settings.USE_LANGCHAIN_RAG
        try:
            settings.USE_LANGCHAIN_RAG = True
            engine = get_rag_engine(
                db=db_session,
                embedding_provider=embedding_provider,
            )
            assert isinstance(engine, BaseRAGEngine)
            assert isinstance(engine, LangChainRAGEngine)
            assert engine.db is db_session
        finally:
            settings.USE_LANGCHAIN_RAG = original_flag


class TestAPIEndpointWiringWithEngines:
    @pytest.fixture(autouse=True)
    def setup_sample_document(self, db_session: Session, embedding_provider: BaseEmbeddingProvider):
        self.ingestion = DocumentIngestionService(embedding_provider=embedding_provider)
        self.owner_id = f"usr_phase19_{uuid.uuid4().hex[:6]}"
        self.doc_content = (
            "The Enterprise Document Intelligence Platform utilizes PostgreSQL 16 with the pgvector extension. "
            "It stores 384-dimensional dense embeddings and indexes them using vector cosine distance metrics. "
            "Access control policies strictly isolate documents per user and department."
        )
        self.doc, self.ver, _, self.chunks = self.ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=self.doc_content.encode("utf-8"),
            filename="platform_architecture.txt",
            name="Platform Architecture",
            owner_id=self.owner_id,
            department="Engineering",
            tags=["architecture", "postgresql", "pgvector"],
        )

    def test_query_api_with_native_rag(self, client: TestClient):
        original_flag = settings.USE_LANGCHAIN_RAG
        try:
            settings.USE_LANGCHAIN_RAG = False
            response = client.post(
                "/api/v1/query",
                json={
                    "question": "Which database and extension does the platform use?",
                    "top_k": 3,
                    "filters": {"owner_id": self.owner_id},
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["is_grounded"] is True
            assert len(data["sources"]) >= 1
            assert data["retrieval_metadata"]["top_similarity"] >= 0.25
        finally:
            settings.USE_LANGCHAIN_RAG = original_flag

    def test_query_api_with_langchain_lcel_rag(self, client: TestClient):
        original_flag = settings.USE_LANGCHAIN_RAG
        try:
            settings.USE_LANGCHAIN_RAG = True
            response = client.post(
                "/api/v1/query",
                json={
                    "question": "Which database and extension does the platform use?",
                    "top_k": 3,
                    "filters": {"owner_id": self.owner_id},
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["is_grounded"] is True
            assert len(data["sources"]) >= 1
            assert data["retrieval_metadata"]["engine"] == "langchain_lcel"
            assert data["sources"][0]["source_filename"] == "platform_architecture.txt"
        finally:
            settings.USE_LANGCHAIN_RAG = original_flag

    def test_conversation_api_with_langchain_rag(self, client: TestClient):
        original_flag = settings.USE_LANGCHAIN_RAG
        try:
            settings.USE_LANGCHAIN_RAG = True
            # 1. Create conversation
            conv_res = client.post(
                "/api/v1/conversations",
                json={"user_id": self.owner_id, "title": "LangChain Architecture Session"},
            )
            assert conv_res.status_code == 201
            conv_id = conv_res.json()["id"]

            # 2. Send first message (empty history -> standard LCEL)
            msg_res = client.post(
                f"/api/v1/conversations/{conv_id}/messages",
                json={
                    "content": "Which database and extension does the platform use?",
                    "top_k": 3,
                    "filters": {"owner_id": self.owner_id},
                },
            )
            assert msg_res.status_code == 200
            msg_data = msg_res.json()
            assert msg_data["is_grounded"] is True
            assert len(msg_data["sources"]) >= 1
            assert msg_data["retrieval_metadata"]["engine"] == "langchain_lcel"
            assert msg_data["assistant_message"]["role"] == "assistant"
            assert len(msg_data["sources"]) > 0

            # 3. Send second follow-up message (non-empty history -> conversational LCEL)
            msg2_res = client.post(
                f"/api/v1/conversations/{conv_id}/messages",
                json={
                    "content": "How are embeddings indexed and documents isolated?",
                    "top_k": 3,
                    "filters": {"owner_id": self.owner_id},
                },
            )
            assert msg2_res.status_code == 200
            msg2_data = msg2_res.json()
            assert msg2_data["is_grounded"] is True
            assert len(msg2_data["sources"]) >= 1
            assert msg2_data["retrieval_metadata"]["engine"] == "langchain_lcel_conversational"
            assert msg2_data["assistant_message"]["role"] == "assistant"
        finally:
            settings.USE_LANGCHAIN_RAG = original_flag
