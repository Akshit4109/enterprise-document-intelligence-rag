import io
import uuid
import pytest
from langchain_community.chat_models.fake import FakeListChatModel
from langchain_core.documents import Document as LCDocument
from sqlalchemy.orm import Session

from app.chunking.langchain import LangChainRecursiveChunker
from app.embeddings.local import SentenceTransformerEmbeddingProvider
from app.embeddings.langchain import LangChainEmbeddingWrapper
from app.parsers.base import ParsedDocument, ParsedPage
from app.rag.langchain_engine import LangChainRAGEngine
from app.retrieval.base import RetrievalFilter
from app.retrieval.langchain import EnterprisePGVectorRetriever
from app.services.ingestion import DocumentIngestionService


@pytest.fixture
def embedding_provider():
    return SentenceTransformerEmbeddingProvider(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        dimension=384,
    )


class TestLangChainChunker:
    def test_langchain_recursive_chunker_basic(self):
        chunker = LangChainRecursiveChunker(chunk_size=100, chunk_overlap=20)
        sample_text = (
            "Paragraph one introduces the enterprise platform architecture and vector database. "
            "Paragraph two explains the LangChain recursive character text splitting strategy and metadata preservation."
        )
        chunks = chunker.chunk_text(sample_text, page_number=1)
        assert len(chunks) >= 2
        for c in chunks:
            assert len(c.content) <= 120
            assert c.page_number == 1
            assert c.metadata["splitter"] == "langchain_recursive"

    def test_langchain_chunker_document_metadata_preservation(self):
        chunker = LangChainRecursiveChunker(chunk_size=150, chunk_overlap=30)
        pages = [
            ParsedPage(page_number=1, text="Page 1: System architecture overview and database design.", char_count=56),
            ParsedPage(page_number=2, text="Page 2: Vector embeddings and LangChain retrieval adapters.", char_count=59),
        ]
        parsed_doc = ParsedDocument(
            filename="arch.txt",
            text="Page 1: System architecture overview and database design.\n\nPage 2: Vector embeddings and LangChain retrieval adapters.",
            total_pages=2,
            pages=pages,
            word_count=18,
            character_count=117,
            metadata={"format": "TXT"},
        )

        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        raw_chunks = chunker.chunk_document(
            parsed_doc=parsed_doc,
            document_id=doc_id,
            version_id=ver_id,
            filename="arch.txt",
        )

        assert len(raw_chunks) == 2
        assert raw_chunks[0].chunk_index == 0
        assert raw_chunks[0].page_number == 1
        assert raw_chunks[0].metadata["document_id"] == str(doc_id)
        assert raw_chunks[0].metadata["source_filename"] == "arch.txt"

        assert raw_chunks[1].chunk_index == 1
        assert raw_chunks[1].page_number == 2
        assert raw_chunks[1].metadata["document_version_id"] == str(ver_id)


class TestLangChainEmbeddingsWrapper:
    def test_langchain_embedding_wrapper(self, embedding_provider):
        lc_embeddings = LangChainEmbeddingWrapper(provider=embedding_provider)
        
        # Test query embedding
        query_vec = lc_embeddings.embed_query("PostgreSQL pgvector search")
        assert len(query_vec) == 384
        assert isinstance(query_vec[0], float)

        # Test document batch embedding
        doc_vecs = lc_embeddings.embed_documents(["First chunk text", "Second chunk text"])
        assert len(doc_vecs) == 2
        assert len(doc_vecs[0]) == 384
        assert len(doc_vecs[1]) == 384


class TestLangChainRetrieverAndMetadata:
    def test_langchain_retriever_metadata_preservation_and_access_control(
        self, db_session: Session, embedding_provider
    ):
        ingestion = DocumentIngestionService(embedding_provider=embedding_provider)

        # 1. Ingest HR Document for User A
        doc_hr, ver_hr, _, _ = ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=b"Human Resources Policy: Full-time employees receive 25 days of annual paid time off and health insurance.",
            filename="hr_policy.txt",
            name="HR Time Off Policy",
            department="HR",
            tags=["hr", "vacation", "benefits"],
            owner_id="user_a",
        )

        # 2. Ingest Finance Document for User B
        doc_fin, ver_fin, _, _ = ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=b"Corporate Finance Budget: $1,000,000 capital expenditure allocated for vector compute clusters.",
            filename="fin_budget.txt",
            name="Finance Budget Plan",
            department="Finance",
            tags=["finance", "capex"],
            owner_id="user_b",
        )

        # 3. Query via EnterprisePGVectorRetriever for User A with department filter
        retriever_a = EnterprisePGVectorRetriever(
            db=db_session,
            embedding_provider=embedding_provider,
            top_k=5,
            filters=RetrievalFilter(department="HR", requesting_user_id="user_a"),
        )

        docs = retriever_a.invoke("annual paid time off and health benefits")
        assert len(docs) > 0
        for d in docs:
            assert isinstance(d, LCDocument)
            assert d.metadata["document_name"] == "HR Time Off Policy"
            assert d.metadata["document_id"] == str(doc_hr.id)
            assert d.metadata["document_version_id"] == str(ver_hr.id)
            assert d.metadata["page_number"] == 1
            assert d.metadata["similarity_score"] > 0.0
            assert "paid time off" in d.page_content.lower() or "health insurance" in d.page_content.lower()

        # 4. Access Isolation: User A should not retrieve User B finance document
        retriever_isolation = EnterprisePGVectorRetriever(
            db=db_session,
            embedding_provider=embedding_provider,
            top_k=5,
            filters=RetrievalFilter(requesting_user_id="user_a"),
        )
        docs_iso = retriever_isolation.invoke("capital expenditure vector compute")
        for d in docs_iso:
            assert d.metadata["document_name"] != "Finance Budget Plan"


class TestLangChainLCELRAGChain:
    def test_lcel_rag_execution_and_citation_generation(
        self, db_session: Session, embedding_provider
    ):
        ingestion = DocumentIngestionService(embedding_provider=embedding_provider)
        ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=b"Enterprise Compliance Guideline: Password rotation must occur every 90 days across all cloud accounts.",
            filename="compliance.txt",
            name="Security Compliance",
            department="Security",
            tags=["compliance", "security"],
            owner_id="admin_sec",
        )

        fake_llm = FakeListChatModel(
            responses=[
                "According to the compliance guidelines [1], passwords must be rotated every 90 days [1]."
            ]
        )

        rag_engine = LangChainRAGEngine(chat_model=fake_llm, min_relevance_threshold=0.20)
        response = rag_engine.answer_question(
            db=db_session,
            query="How often must passwords be rotated?",
            top_k=3,
            embedding_provider=embedding_provider,
            filters=RetrievalFilter(department="Security"),
        )

        assert "passwords must be rotated every 90 days" in response.answer
        assert len(response.sources) > 0
        citation = response.sources[0]
        assert citation.source_index == 1
        assert citation.document_name == "Security Compliance"
        assert citation.version_number == 1
        assert response.retrieval_metadata["engine"] == "langchain_lcel"
        assert response.is_grounded is True

    def test_lcel_rag_anti_hallucination_guard(
        self, db_session: Session, embedding_provider
    ):
        fake_llm = FakeListChatModel(responses=["This should never be reached"])
        rag_engine = LangChainRAGEngine(chat_model=fake_llm, min_relevance_threshold=0.95)

        response = rag_engine.answer_question(
            db=db_session,
            query="Unrelated query about interplanetary space travel",
            top_k=3,
            embedding_provider=embedding_provider,
        )

        assert "cannot find sufficient information" in response.answer
        assert response.retrieval_metadata["fallback_triggered"] is True
        assert len(response.sources) == 0
        assert response.is_grounded is False

    def test_lcel_conversational_rag_with_history(
        self, db_session: Session, embedding_provider
    ):
        ingestion = DocumentIngestionService(embedding_provider=embedding_provider)
        ingestion.process_and_ingest_document(
            db=db_session,
            file_bytes=b"Cloud Architecture: The primary database is PostgreSQL 16 with pgvector extension.",
            filename="cloud_arch.txt",
            name="Cloud Arch Spec",
            department="Engineering",
            owner_id="admin_eng",
        )

        fake_llm = FakeListChatModel(
            responses=[
                "Following up on our earlier discussion, the database engine is PostgreSQL 16 with pgvector [1]."
            ]
        )

        rag_engine = LangChainRAGEngine(chat_model=fake_llm, min_relevance_threshold=0.20)
        history = [
            ("user", "What database do we use?"),
            ("assistant", "We use PostgreSQL."),
        ]

        response = rag_engine.answer_question_conversational(
            db=db_session,
            query="Which version and extension does it use?",
            chat_history=history,
            top_k=3,
            embedding_provider=embedding_provider,
        )

        assert "PostgreSQL 16 with pgvector" in response.answer
        assert response.retrieval_metadata["engine"] == "langchain_lcel_conversational"
        assert len(response.sources) > 0
        assert response.is_grounded is True
