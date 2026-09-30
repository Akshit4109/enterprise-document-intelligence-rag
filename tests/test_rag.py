import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.embeddings.mock import MockEmbeddingProvider
from app.embeddings.local import SentenceTransformerEmbeddingProvider
from app.llm.mock import MockLLMProvider
from app.main import app
from app.core.database import get_db
from app.rag.citation import CitationBuilder
from app.rag.prompt import GroundedPromptBuilder
from app.retrieval.vector import VectorRetriever
from app.services.ingestion import DocumentIngestionService
from app.services.rag import RAGService


@pytest.fixture
def client(db_session: Session) -> TestClient:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def populated_rag_knowledge_base(db_session: Session):
    """
    Populates database with document chunks using SentenceTransformerEmbeddingProvider for semantic RAG tests.
    """
    provider = SentenceTransformerEmbeddingProvider(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        dimension=384,
    )
    ingestion_service = DocumentIngestionService(embedding_provider=provider)

    doc_text = (
        "Enterprise Security Protocol.\n\n"
        "All engineers must rotate API credentials every 90 days.\n\n"
        "Single Sign-On (SSO) with Multi-Factor Authentication is mandatory across all internal tools."
    ).encode("utf-8")

    doc, ver, _, chunks = ingestion_service.process_and_ingest_document(
        db=db_session,
        file_bytes=doc_text,
        filename="security_protocol.txt",
        name="Enterprise Security Protocol",
        owner_id="usr_sec_lead",
        chunk_size=100,
        chunk_overlap=20,
    )

    return {
        "provider": provider,
        "document": doc,
        "version": ver,
        "chunks": chunks,
    }


class TestRAGQuestionAnswering:
    def test_successful_question_answering_with_citations(
        self, db_session: Session, populated_rag_knowledge_base: dict
    ):
        embedding_provider = populated_rag_knowledge_base["provider"]
        retriever = VectorRetriever(db=db_session, embedding_provider=embedding_provider)
        llm = MockLLMProvider()

        rag_service = RAGService(retriever=retriever, llm_provider=llm)
        result = rag_service.query(question="How often must engineers rotate API credentials?")

        assert result.is_grounded is True
        assert len(result.sources) > 0
        assert result.llm_model == "mock-llm-v1"
        assert "[1]" in result.answer
        assert result.sources[0].document_name == "Enterprise Security Protocol"
        assert result.sources[0].version_number == 1

    def test_citation_generation_structure(
        self, db_session: Session, populated_rag_knowledge_base: dict
    ):
        embedding_provider = populated_rag_knowledge_base["provider"]
        retriever = VectorRetriever(db=db_session, embedding_provider=embedding_provider)
        
        # Test CitationBuilder directly
        retrieval_res = retriever.retrieve("rotate API credentials", top_k=2)
        citations = CitationBuilder.build_citations(retrieval_res.results)

        assert len(citations) == len(retrieval_res.results)
        for i, cit in enumerate(citations, start=1):
            assert cit.source_index == i
            assert cit.citation_label.startswith(f"[{i}]")
            assert "Enterprise Security Protocol" in cit.citation_label
            assert cit.snippet != ""

    def test_no_relevant_documents_hallucination_guard(
        self, db_session: Session
    ):
        # Empty DB (no documents ingested)
        embedding_provider = MockEmbeddingProvider(dimension=384)
        retriever = VectorRetriever(db=db_session, embedding_provider=embedding_provider)
        llm = MockLLMProvider()

        rag_service = RAGService(retriever=retriever, llm_provider=llm)
        result = rag_service.query(question="What is the employee health insurance plan?")

        # Guard must prevent LLM invocation and return controlled refusal
        assert result.is_grounded is False
        assert len(result.sources) == 0
        assert result.answer == RAGService.INSUFFICIENT_CONTEXT_MESSAGE

    def test_weak_retrieval_below_threshold(
        self, db_session: Session, populated_rag_knowledge_base: dict
    ):
        embedding_provider = populated_rag_knowledge_base["provider"]
        retriever = VectorRetriever(db=db_session, embedding_provider=embedding_provider)
        llm = MockLLMProvider()

        rag_service = RAGService(retriever=retriever, llm_provider=llm)
        # Require an impossible threshold (0.999)
        result = rag_service.query(
            question="Unrelated query topic about deep space astrophysics",
            similarity_threshold=0.999,
        )

        assert result.is_grounded is False
        assert len(result.sources) == 0
        assert result.answer == RAGService.INSUFFICIENT_CONTEXT_MESSAGE

    def test_llm_failure_handling(
        self, db_session: Session, populated_rag_knowledge_base: dict
    ):
        embedding_provider = populated_rag_knowledge_base["provider"]
        retriever = VectorRetriever(db=db_session, embedding_provider=embedding_provider)
        
        failing_llm = MockLLMProvider()
        failing_llm.simulate_failure = True

        rag_service = RAGService(retriever=retriever, llm_provider=failing_llm)

        with pytest.raises(RuntimeError, match="Simulated LLM API rate limit"):
            rag_service.query(question="How often must engineers rotate API credentials?")

    def test_malformed_llm_response_handling(
        self, db_session: Session, populated_rag_knowledge_base: dict
    ):
        embedding_provider = populated_rag_knowledge_base["provider"]
        retriever = VectorRetriever(db=db_session, embedding_provider=embedding_provider)
        
        empty_llm = MockLLMProvider()
        empty_llm.custom_response = ""

        rag_service = RAGService(retriever=retriever, llm_provider=empty_llm)
        result = rag_service.query(question="How often must engineers rotate API credentials?")

        assert result.is_grounded is True
        assert result.answer == ""
        assert len(result.sources) > 0


class TestRAGQueryAPI:
    def test_query_api_endpoint_success(
        self, client: TestClient, populated_rag_knowledge_base: dict
    ):
        payload = {
            "question": "What is the mandatory authentication protocol for internal tools?",
            "top_k": 3,
        }

        response = client.post("/api/v1/query", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["question"] == payload["question"]
        assert data["is_grounded"] is True
        assert len(data["sources"]) > 0
        assert data["sources"][0]["document_name"] == "Enterprise Security Protocol"
        assert "[1]" in data["sources"][0]["citation_label"]
        assert data["retrieval_metadata"]["chunks_retrieved"] > 0
