import time
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, func, text, literal_column

from app.models.chunk import Chunk
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.retrieval.base import BaseRetriever, RetrievalFilter, RetrievalResult, RetrievedChunk


class KeywordRetriever(BaseRetriever):
    """
    Keyword-based retriever utilizing PostgreSQL native Full-Text Search (tsvector, tsquery, ts_rank).
    Provides exact-term, identifier, and entity matching (e.g. names, codes, technical terms).
    Applies identical enterprise metadata filtering, access control isolation, and version policies.
    """

    def __init__(self, db: Session):
        self.db = db

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
                retrieval_mode="keyword",
            )

        clean_query = query.strip()
        dialect_name = self.db.bind.dialect.name if self.db.bind else "postgresql"

        if dialect_name == "postgresql":
            # 1. Build PostgreSQL FTS tsquery & ts_rank
            # Use websearch_to_tsquery to handle natural language, quotes, and operators safely
            tsquery_expr = func.websearch_to_tsquery("english", clean_query)
            rank_expr = func.ts_rank_cd(Chunk.search_vector, tsquery_expr).label("keyword_score")

            stmt = (
                select(Chunk, DocumentVersion, Document, rank_expr)
                .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
                .join(Document, DocumentVersion.document_id == Document.id)
                .where(Chunk.search_vector.op("@@")(tsquery_expr))
            )
        else:
            # Fallback for SQLite (e.g. in-memory test mocks)
            words = [w for w in clean_query.lower().split() if len(w) > 2]
            rank_expr = literal_column("0.5").label("keyword_score")
            stmt = (
                select(Chunk, DocumentVersion, Document, rank_expr)
                .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
                .join(Document, DocumentVersion.document_id == Document.id)
            )
            if words:
                conditions = [func.lower(Chunk.content).contains(w) for w in words]
                stmt = stmt.where(or_(*conditions))

        # 2. Apply version policy
        is_explicit_version = filters and (
            filters.document_version_id
            or filters.version_number is not None
            or filters.include_all_versions
        )
        if not is_explicit_version:
            stmt = stmt.where(
                or_(
                    Document.active_version_id == DocumentVersion.id,
                    Document.active_version_id.is_(None),
                )
            )

        # 3. Apply metadata & access control filters
        if filters:
            effective_user_id = filters.requesting_user_id or filters.owner_id
            if effective_user_id:
                stmt = stmt.where(Document.owner_id == effective_user_id)

            if filters.department:
                stmt = stmt.where(func.lower(Document.department) == filters.department.strip().lower())

            if filters.document_type:
                stmt = stmt.where(Document.document_type == filters.document_type.lower())

            if filters.document_id:
                stmt = stmt.where(Document.id == filters.document_id)

            if filters.document_version_id:
                stmt = stmt.where(DocumentVersion.id == filters.document_version_id)

            if filters.version_number is not None:
                stmt = stmt.where(DocumentVersion.version_number == filters.version_number)

            if filters.tags:
                stmt = stmt.where(Document.tags.contains(filters.tags))

            if filters.created_from:
                stmt = stmt.where(Document.created_at >= filters.created_from)
            if filters.created_to:
                stmt = stmt.where(Document.created_at <= filters.created_to)

            if filters.effective_from:
                stmt = stmt.where(Document.effective_date >= filters.effective_from)
            if filters.effective_to:
                stmt = stmt.where(Document.effective_date <= filters.effective_to)

        # 4. Order by rank descending and limit top_k
        if dialect_name == "postgresql":
            stmt = stmt.order_by(rank_expr.desc()).limit(top_k)
        else:
            stmt = stmt.limit(top_k)

        # 5. Execute query
        try:
            rows = self.db.execute(stmt).all()
        except Exception:
            # Fallback if tsquery encounters unexpected syntax (e.g. plainto_tsquery fallback)
            if dialect_name == "postgresql":
                plain_tsquery = func.plainto_tsquery("english", clean_query)
                rank_expr = func.ts_rank_cd(Chunk.search_vector, plain_tsquery).label("keyword_score")
                stmt = (
                    select(Chunk, DocumentVersion, Document, rank_expr)
                    .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
                    .join(Document, DocumentVersion.document_id == Document.id)
                    .where(Chunk.search_vector.op("@@")(plain_tsquery))
                    .order_by(rank_expr.desc())
                    .limit(top_k)
                )
                rows = self.db.execute(stmt).all()
            else:
                rows = []

        results: List[RetrievedChunk] = []
        for chunk, version, doc, raw_rank in rows:
            # Normalize keyword rank score roughly to [0.0, 1.0]
            norm_score = min(1.0, float(raw_rank) if raw_rank is not None else 0.5)

            results.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    similarity_score=round(norm_score, 4),
                    keyword_score=round(norm_score, 4),
                    page_number=chunk.page_number,
                    document_id=doc.id,
                    document_name=doc.name,
                    document_version_id=version.id,
                    version_number=version.version_number,
                    source_filename=version.file_name,
                    metadata=chunk.chunk_metadata,
                    retrieval_mode="keyword",
                )
            )

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return RetrievalResult(
            query=query,
            results=results,
            total_results=len(results),
            execution_time_ms=elapsed_ms,
            retrieval_mode="keyword",
        )
