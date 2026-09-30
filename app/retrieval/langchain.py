import uuid
from typing import Any, Dict, List, Optional
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document as LCDocument
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, Field
from sqlalchemy.orm import Session

from app.embeddings.base import BaseEmbeddingProvider
from app.retrieval.base import RetrievalFilter
from app.retrieval.factory import get_retriever


class EnterprisePGVectorRetriever(BaseRetriever):
    """
    LangChain-compatible Retriever wrapping the platform's PostgreSQL + pgvector and Hybrid retrieval engines.
    Preserves all enterprise filtering features (access control, department, tags, active versioning).
    Returns native langchain_core.documents.Document objects enriched with complete citation and multi-stage scoring metadata.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    db: Any = Field(description="SQLAlchemy Session")
    embedding_provider: Optional[Any] = Field(default=None, description="Platform BaseEmbeddingProvider")
    top_k: int = Field(default=5, description="Number of chunks to retrieve")
    similarity_threshold: Optional[float] = Field(default=None, description="Minimum similarity/relevance threshold")
    filters: Optional[RetrievalFilter] = Field(default=None, description="Enterprise metadata & access filters")
    mode: Optional[str] = Field(default=None, description="Retrieval mode: dense, keyword, hybrid, hybrid_reranked, or None (uses config)")

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: Optional[CallbackManagerForRetrieverRun] = None,
    ) -> List[LCDocument]:
        """
        Executes retrieval query and maps RetrievedChunk objects to LangChain Documents.
        """
        retriever = get_retriever(
            db=self.db,
            embedding_provider=self.embedding_provider,
            mode=self.mode,
        )

        search_res = retriever.retrieve(
            query=query,
            top_k=self.top_k,
            similarity_threshold=self.similarity_threshold,
            filters=self.filters,
        )

        lc_documents: List[LCDocument] = []
        for rank, chunk in enumerate(search_res.results, start=1):
            metadata: Dict[str, Any] = {
                "chunk_id": str(chunk.chunk_id),
                "chunk_index": chunk.chunk_index,
                "document_id": str(chunk.document_id),
                "document_name": chunk.document_name,
                "document_version_id": str(chunk.document_version_id),
                "version_number": chunk.version_number,
                "page_number": chunk.page_number,
                "source_filename": chunk.source_filename,
                "similarity_score": chunk.similarity_score,
                "dense_score": chunk.dense_score,
                "keyword_score": chunk.keyword_score,
                "fusion_score": chunk.fusion_score,
                "reranker_score": chunk.reranker_score,
                "retrieval_mode": chunk.retrieval_mode,
                "citation_label": f"[{rank}]",
                "extra_metadata": chunk.metadata,
            }

            lc_doc = LCDocument(
                page_content=chunk.content,
                metadata=metadata,
            )
            lc_documents.append(lc_doc)

        return lc_documents
