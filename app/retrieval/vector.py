import time
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, func

from app.embeddings.base import BaseEmbeddingProvider
from app.embeddings import get_embedding_provider
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.retrieval.base import BaseRetriever, RetrievalFilter, RetrievalResult, RetrievedChunk


class VectorRetriever(BaseRetriever):
    """
    Vector similarity retriever utilizing PostgreSQL with pgvector.
    Applies vector cosine distance, relational metadata filters (department, tags, date ranges),
    access control isolation, and version policies.
    """

    def __init__(
        self,
        db: Session,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
    ):
        self.db = db
        self.embedding_provider = embedding_provider or get_embedding_provider()

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        similarity_threshold: Optional[float] = None,
        filters: Optional[RetrievalFilter] = None,
    ) -> RetrievalResult:
        start_time = time.perf_counter()

        if not query or not query.strip():
            return RetrievalResult(
                query=query,
                results=[],
                total_results=0,
                execution_time_ms=0.0,
            )

        # 1. Compute query vector
        query_vector = self.embedding_provider.embed_text(query.strip())

        # 2. Build pgvector query with joins
        cosine_distance_expr = Chunk.embedding.cosine_distance(query_vector)
        similarity_expr = (1.0 - cosine_distance_expr).label("similarity_score")

        stmt = (
            select(Chunk, DocumentVersion, Document, similarity_expr)
            .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
            .join(Document, DocumentVersion.document_id == Document.id)
            .where(Chunk.embedding.is_not(None))
        )

        # 3. Apply version policy
        is_explicit_version = filters and (filters.document_version_id or filters.version_number is not None or filters.include_all_versions)
        if not is_explicit_version:
            stmt = stmt.where(
                or_(
                    Document.active_version_id == DocumentVersion.id,
                    Document.active_version_id.is_(None)
                )
            )

        # 4. Apply metadata & access control filters
        if filters:
            # Access Control: User / Owner isolation
            effective_user_id = filters.requesting_user_id or filters.owner_id
            if effective_user_id:
                stmt = stmt.where(Document.owner_id == effective_user_id)

            # Department filter (e.g. "HR", "Finance", "Legal")
            if filters.department:
                stmt = stmt.where(func.lower(Document.department) == filters.department.strip().lower())

            # Document format/type filter
            if filters.document_type:
                stmt = stmt.where(Document.document_type == filters.document_type.lower())

            # Specific document ID filter
            if filters.document_id:
                stmt = stmt.where(Document.id == filters.document_id)

            # Specific version ID filter
            if filters.document_version_id:
                stmt = stmt.where(DocumentVersion.id == filters.document_version_id)

            # Specific version number filter
            if filters.version_number is not None:
                stmt = stmt.where(DocumentVersion.version_number == filters.version_number)

            # Tags filter (JSONB array contains)
            if filters.tags:
                stmt = stmt.where(Document.tags.contains(filters.tags))

            # Created date range filters
            if filters.created_from:
                stmt = stmt.where(Document.created_at >= filters.created_from)
            if filters.created_to:
                stmt = stmt.where(Document.created_at <= filters.created_to)

            # Effective date range filters
            if filters.effective_from:
                stmt = stmt.where(Document.effective_date >= filters.effective_from)
            if filters.effective_to:
                stmt = stmt.where(Document.effective_date <= filters.effective_to)

        # 5. Apply similarity threshold
        if similarity_threshold is not None:
            max_allowed_distance = 1.0 - similarity_threshold
            stmt = stmt.where(cosine_distance_expr <= max_allowed_distance)

        # 6. Order by distance ascending and apply top_k limit
        stmt = stmt.order_by(cosine_distance_expr.asc()).limit(top_k)

        # 7. Execute query
        rows = self.db.execute(stmt).all()

        results: List[RetrievedChunk] = []
        for chunk, version, doc, sim_score in rows:
            clean_score = max(0.0, min(1.0, float(sim_score)))

            results.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    similarity_score=round(clean_score, 4),
                    dense_score=round(clean_score, 4),
                    page_number=chunk.page_number,
                    document_id=doc.id,
                    document_name=doc.name,
                    document_version_id=version.id,
                    version_number=version.version_number,
                    source_filename=version.file_name,
                    metadata=chunk.chunk_metadata,
                    retrieval_mode="dense",
                )
            )

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return RetrievalResult(
            query=query,
            results=results,
            total_results=len(results),
            execution_time_ms=elapsed_ms,
            retrieval_mode="dense",
        )
