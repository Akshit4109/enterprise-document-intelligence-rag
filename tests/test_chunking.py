import uuid
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.chunking.recursive import RecursiveCharacterChunker
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus
from app.models.document_version import DocumentVersion, VersionStatus
from app.parsers.base import ParsedDocument, ParsedPage
from app.services.ingestion import DocumentIngestionService


class TestRecursiveCharacterChunker:
    """Test suite covering algorithmic chunking behaviors, boundaries, and overlap."""

    def test_small_document_single_chunk(self):
        chunker = RecursiveCharacterChunker(chunk_size=500, chunk_overlap=50)
        short_text = "This is a brief enterprise summary."
        chunks = chunker.chunk_text(short_text)

        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
        assert chunks[0].content == short_text
        assert chunks[0].token_count_estimate > 0

    def test_large_document_multiple_chunks(self):
        chunker = RecursiveCharacterChunker(chunk_size=150, chunk_overlap=20)
        long_text = (
            "Section 1: Distributed Systems.\n\n"
            "Distributed systems require fault tolerance, replication, and consensus protocols. "
            "Raft and Paxos are widely implemented consensus algorithms in production backends.\n\n"
            "Section 2: Database Scalability.\n\n"
            "Horizontal partitioning and read replicas reduce query latency and improve throughput under heavy enterprise workloads."
        )

        chunks = chunker.chunk_text(long_text)

        assert len(chunks) > 1
        # Verify continuous ordering
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
            assert len(chunk.content) <= 150
            assert len(chunk.content.strip()) > 0

    def test_overlap_preserves_context(self):
        chunker = RecursiveCharacterChunker(chunk_size=120, chunk_overlap=30)
        text = (
            "Paragraph one introduces modern microservices architecture and cloud-native patterns.\n\n"
            "Paragraph two explains database sharding, caching layers with Redis, and eventual consistency."
        )

        chunks = chunker.chunk_text(text)
        assert len(chunks) >= 2

        # Check overlap between consecutive chunks
        first_chunk = chunks[0].content
        second_chunk = chunks[1].content

        # There should be overlap text present in both chunks
        # Find shared words
        first_words = set(first_chunk.split())
        second_words = set(second_chunk.split())
        shared_words = first_words.intersection(second_words)
        assert len(shared_words) > 0

    def test_empty_and_whitespace_content(self):
        chunker = RecursiveCharacterChunker(chunk_size=500, chunk_overlap=50)

        assert chunker.chunk_text("") == []
        assert chunker.chunk_text("   \n\n\t   ") == []

    def test_different_chunk_sizes(self):
        text = "Alpha Beta Gamma Delta Epsilon. " * 30

        chunker_small = RecursiveCharacterChunker(chunk_size=100, chunk_overlap=10)
        chunks_small = chunker_small.chunk_text(text)

        chunker_large = RecursiveCharacterChunker(chunk_size=600, chunk_overlap=50)
        chunks_large = chunker_large.chunk_text(text)

        assert len(chunks_small) > len(chunks_large)

    def test_chunk_document_with_page_boundaries(self):
        chunker = RecursiveCharacterChunker(chunk_size=200, chunk_overlap=30)

        page1 = ParsedPage(page_number=1, text="Page 1 Content: Introduction to Vector Databases.", metadata={"dpi": 300})
        page2 = ParsedPage(page_number=2, text="Page 2 Content: HNSW and IVFFlat Indexing Strategies.", metadata={"dpi": 300})

        parsed_doc = ParsedDocument(
            text="Page 1 Content: Introduction to Vector Databases.\n\nPage 2 Content: HNSW and IVFFlat Indexing Strategies.",
            pages=[page1, page2],
            total_pages=2,
            word_count=14,
            character_count=98,
            metadata={"format": "PDF", "title": "Vector Guide"}
        )

        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()

        chunks = chunker.chunk_document(
            parsed_doc=parsed_doc,
            document_id=doc_id,
            version_id=ver_id,
            filename="vector_guide.pdf",
        )

        assert len(chunks) >= 2
        # Check page numbers
        assert chunks[0].page_number == 1
        assert chunks[1].page_number == 2

        # Check metadata preservation
        assert chunks[0].metadata["source_filename"] == "vector_guide.pdf"
        assert chunks[0].metadata["document_id"] == str(doc_id)
        assert chunks[0].metadata["document_version_id"] == str(ver_id)
        assert chunks[0].metadata["page_number"] == 1


class TestChunkDatabasePersistence:
    """Integration test suite verifying chunk persistence in PostgreSQL."""

    def test_ingestion_service_persists_chunks_to_database(self, db_session: Session):
        ingestion_service = DocumentIngestionService()
        sample_txt = (
            "Enterprise Document Intelligence Platform Overview.\n\n"
            "This platform processes multi-format documents, splits them into retrieval-friendly chunks, "
            "generates vector embeddings, and performs semantic search.\n\n"
            "Robust database schemas ensure multi-version integrity and transactional safety."
        ).encode("utf-8")

        doc, ver, parsed_doc, created_chunks = ingestion_service.process_and_ingest_document(
            db=db_session,
            file_bytes=sample_txt,
            filename="platform_overview.txt",
            name="Platform Architecture",
            owner_id="usr_eng_lead",
            chunk_size=120,
            chunk_overlap=20,
        )

        assert doc.id is not None
        assert ver.id is not None
        assert len(created_chunks) > 1

        # Query database directly to verify persistence
        stmt = (
            select(Chunk)
            .where(Chunk.document_version_id == ver.id)
            .order_by(Chunk.chunk_index.asc())
        )
        persisted_chunks = db_session.execute(stmt).scalars().all()

        assert len(persisted_chunks) == len(created_chunks)
        for i, chunk in enumerate(persisted_chunks):
            assert chunk.chunk_index == i
            assert chunk.document_version_id == ver.id
            assert len(chunk.content) > 0
            assert chunk.chunk_metadata["source_filename"] == "platform_overview.txt"
            assert chunk.chunk_metadata["document_version_id"] == str(ver.id)

    def test_invalid_chunker_parameters(self):
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            RecursiveCharacterChunker(chunk_size=0, chunk_overlap=0)

        with pytest.raises(ValueError, match="chunk_overlap.*must be strictly less"):
            RecursiveCharacterChunker(chunk_size=100, chunk_overlap=150)
