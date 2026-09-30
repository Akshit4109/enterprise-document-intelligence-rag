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
from app.rag.graph.engine import LangGraphRAGEngine
from app.rag.graph.nodes import RAGGraphNodes
from app.rag.graph.workflow import create_rag_graph, should_generate_or_rewrite
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


class TestLangGraphConstruction:
    def test_graph_compilation_and_topology(self, db_session: Session, embedding_provider: BaseEmbeddingProvider):
        """Test 1: Verify that the LangGraph StateGraph builds, links all nodes, and compiles."""
        nodes = RAGGraphNodes(db=db_session, embedding_provider=embedding_provider)
        graph = create_rag_graph(nodes=nodes)
        assert graph is not None

        # Check conditional routing function logic
        state_sufficient = {"retrieval_sufficient": True, "retrieval_attempt": 1, "max_retries": 2}
        assert should_generate_or_rewrite(state_sufficient) == "generate_answer"

        state_insufficient_can_retry = {"retrieval_sufficient": False, "retrieval_attempt": 1, "max_retries": 2}
        assert should_generate_or_rewrite(state_insufficient_can_retry) == "rewrite_query"

        state_insufficient_exhausted = {"retrieval_sufficient": False, "retrieval_attempt": 2, "max_retries": 2}
        assert should_generate_or_rewrite(state_insufficient_exhausted) == "generate_answer"


class TestLangGraphRAGExecution:
    @pytest.fixture(autouse=True)
    def setup_sample_knowledge_base(self, db_session: Session, embedding_provider: BaseEmbeddingProvider):
        self.ingestion = DocumentIngestionService(embedding_provider=embedding_provider)
        self.owner_id = f"usr_graph_{uuid.uuid4().hex[:6]}"
        self.doc_content = (
            "Enterprise Security and Compliance Guidelines:\n"
            "1. PostgreSQL 16 with pgvector extension stores high-dimensional vector embeddings.\n"
            "2. Access control policies strictly isolate documents per user and department.\n"
            "3. Multi-Factor Authentication (MFA) is strictly required for all administrative access.\n"
            "4. Cryptographic encryption keys must be rotated every 90 days."
        )
        self.doc, self.ver, _, self.chunks = self.ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=self.doc_content.encode("utf-8"),
            filename="compliance_guidelines.txt",
            name="Compliance Guidelines",
            owner_id=self.owner_id,
            department="Security",
            tags=["compliance", "security", "postgresql", "pgvector"],
        )

    def test_successful_retrieval_path(self, db_session: Session, embedding_provider: BaseEmbeddingProvider):
        """Test 2: Question with relevant documents traverses retrieve -> grade -> generate -> finalize."""
        engine = LangGraphRAGEngine(
            db=db_session,
            embedding_provider=embedding_provider,
            min_relevance_threshold=0.25,
            max_retries=2,
        )

        response = engine.query(
            question="What is the policy for cryptographic encryption key rotation?",
            top_k=3,
            filters={"owner_id": self.owner_id},
        )

        assert response.is_grounded is True
        assert len(response.sources) >= 1
        assert response.retrieval_metadata["engine"] == "langgraph"
        assert response.retrieval_metadata["retry_attempts"] == 1
        assert response.retrieval_metadata["fallback_triggered"] is False
        assert response.sources[0].source_filename == "compliance_guidelines.txt"

    def test_insufficient_retrieval_and_rewrite_loop_fallback(self, db_session: Session, embedding_provider: BaseEmbeddingProvider):
        """Test 3 & 4: Unrelated query triggers retrieve -> grade -> rewrite -> retrieve -> fallback."""
        engine = LangGraphRAGEngine(
            db=db_session,
            embedding_provider=embedding_provider,
            min_relevance_threshold=0.85,  # High threshold to force insufficient context
            max_retries=2,
        )

        response = engine.query(
            question="What is the warp drive subspace frequency?",
            top_k=3,
            filters={"owner_id": self.owner_id},
        )

        assert response.is_grounded is False
        assert len(response.sources) == 0
        assert "I cannot find sufficient information" in response.answer
        assert response.retrieval_metadata["fallback_triggered"] is True
        assert response.retrieval_metadata["retry_attempts"] == 2  # Proves query rewrite loop executed to limit
        assert response.retrieval_metadata["rewritten_query"] is not None

    def test_retry_limit_strict_termination(self, db_session: Session, embedding_provider: BaseEmbeddingProvider):
        """Test 4 & 5: Retry limit strictly prevents infinite loops."""
        engine = LangGraphRAGEngine(
            db=db_session,
            embedding_provider=embedding_provider,
            min_relevance_threshold=0.99,  # Impossible threshold
            max_retries=3,
        )

        response = engine.query(
            question="Non-existent content query",
            top_k=2,
            filters={"owner_id": self.owner_id},
        )

        assert response.retrieval_metadata["retry_attempts"] == 3
        assert response.is_grounded is False

    def test_citation_metadata_preservation(self, db_session: Session, embedding_provider: BaseEmbeddingProvider):
        """Test 6: Verify full metadata provenance survives graph state transitions."""
        engine = LangGraphRAGEngine(
            db=db_session,
            embedding_provider=embedding_provider,
            min_relevance_threshold=0.25,
        )

        response = engine.query(
            question="Which database and extension is used for vector embeddings?",
            top_k=2,
            filters={"owner_id": self.owner_id},
        )

        assert len(response.sources) > 0
        cit = response.sources[0]
        assert cit.document_name == "Compliance Guidelines"
        assert cit.source_filename == "compliance_guidelines.txt"
        assert cit.version_number == 1
        assert cit.similarity_score > 0.25
        assert cit.chunk_id is not None
        assert cit.document_id is not None

    def test_conversational_chat_history_in_graph(self, db_session: Session, embedding_provider: BaseEmbeddingProvider):
        """Test 7: Chat history flows into graph state and triggers conversational pipeline."""
        engine = LangGraphRAGEngine(
            db=db_session,
            embedding_provider=embedding_provider,
            min_relevance_threshold=0.25,
        )

        chat_history = [
            {"role": "user", "content": "Hello, I want to ask about compliance."},
            {"role": "assistant", "content": "Sure! I am here to help with compliance guidelines."},
        ]

        response = engine.query(
            question="How frequently must encryption keys be rotated?",
            top_k=3,
            chat_history=chat_history,
            filters={"owner_id": self.owner_id},
        )

        assert response.is_grounded is True
        assert response.retrieval_metadata["engine"] == "langgraph_conversational"
        assert len(response.sources) >= 1


class TestLangGraphFactoryAndAPIRouting:
    @pytest.fixture(autouse=True)
    def setup_sample_document(self, db_session: Session, embedding_provider: BaseEmbeddingProvider):
        self.ingestion = DocumentIngestionService(embedding_provider=embedding_provider)
        self.owner_id = f"usr_api_{uuid.uuid4().hex[:6]}"
        self.doc, self.ver, _, self.chunks = self.ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=b"PostgreSQL 16 with pgvector powers the enterprise semantic search.",
            filename="arch.txt",
            name="Arch",
            owner_id=self.owner_id,
            department="Engineering",
        )

    def test_factory_precedence(self, db_session: Session, embedding_provider: BaseEmbeddingProvider):
        """Test 8 & 9: Factory precedence for LangGraph vs LangChain vs Native."""
        orig_lg = settings.USE_LANGGRAPH_RAG
        orig_lc = settings.USE_LANGCHAIN_RAG
        try:
            # 1. LangGraph active
            settings.USE_LANGGRAPH_RAG = True
            settings.USE_LANGCHAIN_RAG = False
            engine1 = get_rag_engine(db=db_session, embedding_provider=embedding_provider)
            assert isinstance(engine1, LangGraphRAGEngine)

            # 2. LangGraph inactive, LangChain active
            settings.USE_LANGGRAPH_RAG = False
            settings.USE_LANGCHAIN_RAG = True
            engine2 = get_rag_engine(db=db_session, embedding_provider=embedding_provider)
            assert isinstance(engine2, LangChainRAGEngine)

            # 3. Both inactive -> Native RAGService
            settings.USE_LANGGRAPH_RAG = False
            settings.USE_LANGCHAIN_RAG = False
            engine3 = get_rag_engine(db=db_session, embedding_provider=embedding_provider)
            assert isinstance(engine3, RAGService)
        finally:
            settings.USE_LANGGRAPH_RAG = orig_lg
            settings.USE_LANGCHAIN_RAG = orig_lc

    def test_query_api_with_langgraph_engine(self, client: TestClient):
        """Test 8: POST /api/v1/query via LangGraph RAG Engine."""
        orig_lg = settings.USE_LANGGRAPH_RAG
        try:
            settings.USE_LANGGRAPH_RAG = True
            response = client.post(
                "/api/v1/query",
                json={
                    "question": "Which database powers semantic search?",
                    "top_k": 3,
                    "filters": {"owner_id": self.owner_id},
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["is_grounded"] is True
            assert data["retrieval_metadata"]["engine"] == "langgraph"
            assert len(data["sources"]) >= 1
        finally:
            settings.USE_LANGGRAPH_RAG = orig_lg

    def test_conversation_api_with_langgraph_engine(self, client: TestClient):
        """Test 8: POST /api/v1/conversations/{id}/messages via LangGraph RAG Engine."""
        orig_lg = settings.USE_LANGGRAPH_RAG
        try:
            settings.USE_LANGGRAPH_RAG = True
            # Create conversation
            conv_res = client.post(
                "/api/v1/conversations",
                json={"user_id": self.owner_id, "title": "LangGraph Session"},
            )
            assert conv_res.status_code == 201
            conv_id = conv_res.json()["id"]

            # Message 1
            msg1_res = client.post(
                f"/api/v1/conversations/{conv_id}/messages",
                json={
                    "content": "Which database powers semantic search?",
                    "top_k": 3,
                    "filters": {"owner_id": self.owner_id},
                },
            )
            assert msg1_res.status_code == 200
            msg1_data = msg1_res.json()
            assert msg1_data["is_grounded"] is True
            assert msg1_data["retrieval_metadata"]["engine"] == "langgraph"

            # Message 2 (follow-up with history)
            msg2_res = client.post(
                f"/api/v1/conversations/{conv_id}/messages",
                json={
                    "content": "What extension is used?",
                    "top_k": 3,
                    "filters": {"owner_id": self.owner_id},
                },
            )
            assert msg2_res.status_code == 200
            msg2_data = msg2_res.json()
            assert msg2_data["is_grounded"] is True
            assert msg2_data["retrieval_metadata"]["engine"] == "langgraph_conversational"
        finally:
            settings.USE_LANGGRAPH_RAG = orig_lg
