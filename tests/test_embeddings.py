import pytest
import math
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.embeddings.mock import MockEmbeddingProvider
from app.embeddings.local import SentenceTransformerEmbeddingProvider
from app.embeddings.factory import EmbeddingProviderFactory
from app.models.chunk import Chunk
from app.services.ingestion import DocumentIngestionService
from app.chunking.recursive import RecursiveCharacterChunker


class TestEmbeddingProviders:
    """Test suite covering embedding provider abstractions and vector properties."""

    def test_mock_embedding_provider_single_and_batch(self):
        provider = MockEmbeddingProvider(dimension=384, model_name="test-mock")
        assert provider.dimension == 384
        assert provider.model_name == "test-mock"

        # Single embedding
        vec = provider.embed_text("Test sentence for vector embedding.")
        assert len(vec) == 384
        # Verify L2 normalization (sum of squares is ~1.0)
        norm = math.sqrt(sum(x * x for x in vec))
        assert abs(norm - 1.0) < 1e-5

        # Batch embedding
        texts = ["Text item 1", "Text item 2", "Text item 3"]
        batch_vecs = provider.embed_batch(texts)
        assert len(batch_vecs) == 3
        for v in batch_vecs:
            assert len(v) == 384
            v_norm = math.sqrt(sum(x * x for x in v))
            assert abs(v_norm - 1.0) < 1e-5

    def test_empty_string_embedding(self):
        provider = MockEmbeddingProvider(dimension=384)
        vec = provider.embed_text("")
        assert len(vec) == 384
        assert all(x == 0.0 for x in vec)

    def test_sentence_transformer_provider(self):
        provider = SentenceTransformerEmbeddingProvider(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            dimension=384,
        )
        assert provider.dimension == 384

        texts = ["Artificial intelligence and retrieval augmented generation."]
        vecs = provider.embed_batch(texts)
        assert len(vecs) == 1
        assert len(vecs[0]) == 384
        norm = math.sqrt(sum(x * x for x in vecs[0]))
        assert abs(norm - 1.0) < 1e-4

    def test_embedding_factory(self):
        mock_p = EmbeddingProviderFactory.get_provider("mock", dimension=384)
        assert isinstance(mock_p, MockEmbeddingProvider)
        assert mock_p.dimension == 384

        local_p = EmbeddingProviderFactory.get_provider("local", dimension=384)
        assert isinstance(local_p, SentenceTransformerEmbeddingProvider)

        with pytest.raises(ValueError, match="Unsupported embedding provider"):
            EmbeddingProviderFactory.get_provider("invalid_provider")


class TestVectorDatabasePersistence:
    """Integration test suite verifying PostgreSQL pgvector storage and rollback."""

    def test_ingestion_generates_and_persists_embeddings_in_pgvector(self, db_session: Session):
        provider = MockEmbeddingProvider(dimension=384, model_name="mock-384")
        ingestion_service = DocumentIngestionService(embedding_provider=provider)

        content = (
            "PostgreSQL pgvector extension enables efficient vector similarity indexing.\n\n"
            "Chunks and their corresponding high-dimensional dense embeddings are co-located in the database."
        ).encode("utf-8")

        doc, ver, parsed_doc, chunks = ingestion_service.process_and_ingest_document(
            db=db_session,
            file_bytes=content,
            filename="vector_persistence.txt",
            owner_id="usr_vector_test",
            chunk_size=100,
            chunk_overlap=20,
        )

        assert len(chunks) > 0

        # Query chunks from PostgreSQL
        stmt = select(Chunk).where(Chunk.document_version_id == ver.id)
        db_chunks = db_session.execute(stmt).scalars().all()

        assert len(db_chunks) == len(chunks)
        for chunk in db_chunks:
            assert chunk.embedding is not None
            # pgvector vector can be indexed or converted to list
            assert len(chunk.embedding) == 384
            assert chunk.embedding_model == "mock-384"

    def test_embedding_failure_rolls_back_database_transaction(self, db_session: Session):
        class FailingEmbeddingProvider(MockEmbeddingProvider):
            def embed_batch(self, texts, batch_size=32):
                raise RuntimeError("Embedding service API connection timeout")

        failing_provider = FailingEmbeddingProvider(dimension=384)
        ingestion_service = DocumentIngestionService(embedding_provider=failing_provider)

        with pytest.raises(RuntimeError, match="Embedding service API connection timeout"):
            ingestion_service.process_and_ingest_document(
                db=db_session,
                file_bytes=b"Sample document content for rollback test.",
                filename="fail_test.txt",
            )

        # Verify no orphan chunks or versions exist in the database for this filename
        stmt = select(Chunk).join(Chunk.document_version).where(Chunk.document_version.has(file_name="fail_test.txt"))
        orphan_chunks = db_session.execute(stmt).scalars().all()
        assert len(orphan_chunks) == 0
