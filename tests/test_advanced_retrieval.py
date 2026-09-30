import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.embeddings.mock import MockEmbeddingProvider
from app.llm.mock import MockLLMProvider
from app.main import app
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.chunk import Chunk
from app.retrieval.base import RetrievalFilter, RetrievedChunk
from app.retrieval.vector import VectorRetriever
from app.retrieval.keyword import KeywordRetriever
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.reranking.cross_encoder import CrossEncoderReranker, MockReranker
from app.retrieval.factory import get_retriever
from app.retrieval.langchain import EnterprisePGVectorRetriever
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
def sample_retrieval_docs(db_session: Session):
    """
    Creates a set of test documents and chunks to verify dense, keyword, hybrid, and reranked retrieval.
    """
    owner = f"user_{uuid.uuid4().hex[:6]}"
    doc1 = Document(
        name="Security Policy & Cryptographic Protocols",
        document_type="pdf",
        owner_id=owner,
        department="Security",
        tags=["security", "compliance", "cryptography"],
    )
    db_session.add(doc1)
    db_session.flush()

    v1 = DocumentVersion(
        document_id=doc1.id,
        version_number=1,
        file_name="security_policy.pdf",
        file_size=1024,
        storage_path="/tmp/sec.pdf",
        checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    db_session.add(v1)
    db_session.flush()

    doc1.active_version_id = v1.id
    db_session.flush()

    embedder = MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)

    chunk_texts = [
        "Cryptographic keys must be rotated every 90 days according to enterprise NIST guidelines.",
        "PostgreSQL database version 16 with pgvector extension stores high-dimensional vector embeddings.",
        "Role-based access control and multi-tenant isolation policies are strictly enforced.",
    ]

    for idx, text in enumerate(chunk_texts):
        vector = embedder.embed_text(text)
        chunk = Chunk(
            document_version_id=v1.id,
            chunk_index=idx,
            content=text,
            page_number=idx + 1,
            embedding=vector,
            embedding_model="mock-embedding-v1",
        )
        db_session.add(chunk)

    db_session.commit()
    return doc1, v1


def test_dense_retrieval_baseline(db_session: Session, sample_retrieval_docs):
    doc, ver = sample_retrieval_docs
    retriever = VectorRetriever(db=db_session, embedding_provider=MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION))

    result = retriever.retrieve(query="cryptographic key rotation", top_k=2)
    assert result.total_results > 0
    assert result.retrieval_mode == "dense"
    assert "Cryptographic keys" in result.results[0].content
    assert result.results[0].dense_score is not None


def test_keyword_retrieval_postgres_fts(db_session: Session, sample_retrieval_docs):
    doc, ver = sample_retrieval_docs
    retriever = KeywordRetriever(db=db_session)

    result = retriever.retrieve(query="NIST guidelines", top_k=2)
    assert result.total_results > 0
    assert result.retrieval_mode == "keyword"
    assert "NIST" in result.results[0].content


def test_hybrid_retrieval_rrf_fusion(db_session: Session, sample_retrieval_docs):
    doc, ver = sample_retrieval_docs
    retriever = HybridRetriever(
        db=db_session,
        embedding_provider=MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION),
        reranker=None,
        reranker_enabled=False,
    )

    result = retriever.retrieve(query="pgvector extension", top_k=2)
    assert result.total_results > 0
    assert result.retrieval_mode == "hybrid"
    assert result.results[0].fusion_score is not None
    assert "pgvector" in result.results[0].content


def test_hybrid_retrieval_with_reranker(db_session: Session, sample_retrieval_docs):
    doc, ver = sample_retrieval_docs
    mock_reranker = MockReranker()
    retriever = HybridRetriever(
        db=db_session,
        embedding_provider=MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION),
        reranker=mock_reranker,
        reranker_enabled=True,
    )

    result = retriever.retrieve(query="NIST cryptographic rotation", top_k=2)
    assert result.total_results > 0
    assert result.retrieval_mode == "hybrid_reranked"
    assert result.results[0].reranker_score is not None


def test_retrieval_metadata_filters_applied(db_session: Session, sample_retrieval_docs):
    doc, ver = sample_retrieval_docs
    retriever = HybridRetriever(
        db=db_session,
        embedding_provider=MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION),
    )

    # Search with matching department filter
    matching_filter = RetrievalFilter(department="Security")
    res_match = retriever.retrieve(query="keys", filters=matching_filter)
    assert res_match.total_results > 0

    # Search with non-matching department filter
    non_matching_filter = RetrievalFilter(department="Finance")
    res_no_match = retriever.retrieve(query="keys", filters=non_matching_filter)
    assert res_no_match.total_results == 0


def test_retriever_factory_modes(db_session: Session):
    r_dense = get_retriever(db=db_session, mode="dense")
    assert isinstance(r_dense, VectorRetriever)

    r_keyword = get_retriever(db=db_session, mode="keyword")
    assert isinstance(r_keyword, KeywordRetriever)

    r_hybrid = get_retriever(db=db_session, mode="hybrid")
    assert isinstance(r_hybrid, HybridRetriever)


def test_enterprise_langchain_retriever_integration(db_session: Session, sample_retrieval_docs):
    doc, ver = sample_retrieval_docs
    lc_retriever = EnterprisePGVectorRetriever(
        db=db_session,
        embedding_provider=MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION),
        top_k=2,
    )

    docs = lc_retriever.invoke("pgvector")
    assert len(docs) > 0
    assert docs[0].metadata["citation_label"] == "[1]"
    assert "similarity_score" in docs[0].metadata


def test_search_api_endpoint_modes(client, db_session: Session, sample_retrieval_docs):
    doc, ver = sample_retrieval_docs

    # Mode: dense
    res_dense = client.post("/api/v1/search", json={"query": "cryptographic", "top_k": 3, "mode": "dense"})
    assert res_dense.status_code == 200
    assert res_dense.json()["retrieval_mode"] == "dense"

    # Mode: keyword
    res_kw = client.post("/api/v1/search", json={"query": "NIST guidelines", "top_k": 3, "mode": "keyword"})
    assert res_kw.status_code == 200
    assert res_kw.json()["retrieval_mode"] == "keyword"

    # Mode: hybrid
    res_hyb = client.post("/api/v1/search", json={"query": "pgvector", "top_k": 3, "mode": "hybrid"})
    assert res_hyb.status_code == 200
    assert res_hyb.json()["retrieval_mode"] in ("hybrid", "hybrid_reranked")


def test_rag_with_hybrid_retriever_flow(db_session: Session, sample_retrieval_docs):
    hybrid_retriever = HybridRetriever(
        db=db_session,
        embedding_provider=MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION),
    )
    llm = MockLLMProvider()

    rag_service = RAGService(
        retriever=hybrid_retriever,
        llm_provider=llm,
    )

    res = rag_service.query(
        question="How often must cryptographic keys be rotated?",
        top_k=2,
        similarity_threshold=0.1,
    )
    assert res.is_grounded is True
    assert len(res.sources) > 0
    assert "[1]" in res.answer or len(res.sources) > 0
