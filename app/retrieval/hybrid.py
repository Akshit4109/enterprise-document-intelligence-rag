import time
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.embeddings.base import BaseEmbeddingProvider
from app.retrieval.base import BaseRetriever, RetrievalFilter, RetrievalResult, RetrievedChunk
from app.retrieval.keyword import KeywordRetriever
from app.retrieval.reranking.base import BaseReranker
from app.retrieval.reranking.cross_encoder import CrossEncoderReranker
from app.retrieval.vector import VectorRetriever


class HybridRetriever(BaseRetriever):
    """
    Advanced Hybrid Retriever combining dense semantic vector retrieval (PostgreSQL pgvector)
    and sparse keyword retrieval (PostgreSQL TSVECTOR Full-Text Search) with Reciprocal Rank Fusion (RRF)
    and optional second-stage Cross-Encoder neural reranking.
    """

    def __init__(
        self,
        db: Session,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
        reranker: Optional[BaseReranker] = None,
        candidate_k: int = settings.RERANKER_CANDIDATE_K,
        rrf_k: int = settings.HYBRID_FUSION_RRF_K,
        dense_weight: float = settings.HYBRID_DENSE_WEIGHT,
        keyword_weight: float = settings.HYBRID_KEYWORD_WEIGHT,
        reranker_enabled: bool = settings.RERANKER_ENABLED,
    ):
        self.db = db
        self.vector_retriever = VectorRetriever(db=db, embedding_provider=embedding_provider)
        self.keyword_retriever = KeywordRetriever(db=db)
        self.candidate_k = candidate_k
        self.rrf_k = rrf_k
        self.dense_weight = dense_weight
        self.keyword_weight = keyword_weight
        self.reranker_enabled = reranker_enabled

        if reranker is not None:
            self.reranker = reranker
        elif self.reranker_enabled:
            self.reranker = CrossEncoderReranker()
        else:
            self.reranker = None

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
                retrieval_mode="hybrid",
            )

        # 1. Retrieve Candidate Pools from both branches
        # Use candidate_k (e.g. 20) to ensure rich candidate pool for fusion & reranking
        pool_limit = max(top_k * 2, self.candidate_k)

        dense_res = self.vector_retriever.retrieve(
            query=query,
            top_k=pool_limit,
            similarity_threshold=None,
            filters=filters,
        )

        keyword_res = self.keyword_retriever.retrieve(
            query=query,
            top_k=pool_limit,
            filters=filters,
        )

        # 2. Reciprocal Rank Fusion (RRF)
        # RRF(d) = (w_dense / (k + rank_dense)) + (w_keyword / (k + rank_keyword))
        fused_chunks_map: Dict[str, RetrievedChunk] = {}
        rrf_scores: Dict[str, float] = {}

        # Process dense rankings (1-indexed)
        for rank, chunk in enumerate(dense_res.results, start=1):
            cid = str(chunk.chunk_id)
            score = self.dense_weight / (self.rrf_k + rank)
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + score
            fused_chunks_map[cid] = chunk

        # Process keyword rankings (1-indexed)
        for rank, chunk in enumerate(keyword_res.results, start=1):
            cid = str(chunk.chunk_id)
            score = self.keyword_weight / (self.rrf_k + rank)
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + score

            if cid in fused_chunks_map:
                # Merge keyword score into existing dense chunk
                fused_chunks_map[cid] = fused_chunks_map[cid].model_copy(
                    update={"keyword_score": chunk.keyword_score}
                )
            else:
                fused_chunks_map[cid] = chunk

        # Normalize RRF scores and construct fused candidate list
        max_possible_rrf = (self.dense_weight / (self.rrf_k + 1)) + (self.keyword_weight / (self.rrf_k + 1))
        fused_candidates: List[RetrievedChunk] = []

        for cid, chunk in fused_chunks_map.items():
            raw_rrf = rrf_scores[cid]
            # Normalize to [0.0, 1.0]
            norm_fusion = min(1.0, raw_rrf / max_possible_rrf) if max_possible_rrf > 0 else raw_rrf
            updated_chunk = chunk.model_copy(
                update={
                    "fusion_score": round(norm_fusion, 4),
                    "similarity_score": round(norm_fusion, 4),
                    "retrieval_mode": "hybrid",
                }
            )
            fused_candidates.append(updated_chunk)

        # Sort descending by fusion score
        fused_candidates.sort(key=lambda x: (x.fusion_score or 0.0), reverse=True)

        # 3. Second-Stage Reranking (if enabled)
        active_mode = "hybrid"
        if self.reranker is not None:
            # Rerank top candidates (up to pool_limit) down to final top_k
            candidate_subset = fused_candidates[:pool_limit]
            final_results = self.reranker.rerank(
                query=query,
                candidates=candidate_subset,
                top_k=top_k,
            )
            active_mode = "hybrid_reranked"
        else:
            final_results = fused_candidates[:top_k]

        # 4. Optional final relevance threshold filter
        if similarity_threshold is not None:
            final_results = [c for c in final_results if (c.similarity_score or 0.0) >= similarity_threshold]

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return RetrievalResult(
            query=query,
            results=final_results,
            total_results=len(final_results),
            execution_time_ms=elapsed_ms,
            retrieval_mode=active_mode,
        )
