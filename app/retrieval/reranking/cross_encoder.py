import math
from typing import List, Optional
from app.core.config import settings
from app.core.logging import logger
from app.retrieval.base import RetrievedChunk
from app.retrieval.reranking.base import BaseReranker


class CrossEncoderReranker(BaseReranker):
    """
    Neural Cross-Encoder reranker using SentenceTransformers CrossEncoder models.
    Jointly evaluates (query, candidate) tokens through full self-attention to distinguish
    subtle semantic relevance and answer-bearing evidence from incidental keyword overlaps.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
    ):
        self.model_name = model_name or settings.RERANKER_MODEL_NAME
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                logger.info(f"Loading CrossEncoder reranker model: '{self.model_name}'")
                self._model = CrossEncoder(self.model_name)
            except Exception as e:
                logger.warning(f"Failed to load CrossEncoder '{self.model_name}': {e}. Falling back to heuristic reranking.")
                self._model = "fallback"
        return self._model

    def rerank(
        self,
        query: str,
        candidates: List[RetrievedChunk],
        top_k: int = 5,
    ) -> List[RetrievedChunk]:
        if not candidates or not query.strip():
            return candidates[:top_k]

        model = self._get_model()

        if model != "fallback":
            try:
                pairs = [[query.strip(), c.content.strip()] for c in candidates]
                raw_scores = model.predict(pairs)

                # Cross-encoder output can be a list/array of floats
                scores: List[float] = []
                for s in raw_scores:
                    val = float(s)
                    # Convert logit to probability via sigmoid if outside [0, 1]
                    if val < 0.0 or val > 1.0:
                        prob = 1.0 / (1.0 + math.exp(-val))
                    else:
                        prob = val
                    scores.append(round(prob, 4))
            except Exception as e:
                logger.warning(f"CrossEncoder inference error: {e}. Falling back to existing scores.")
                scores = [c.similarity_score for c in candidates]
        else:
            # Fallback heuristic: score based on entity term coverage and content density
            q_terms = set(query.lower().split())
            scores = []
            for c in candidates:
                c_text = c.content.lower()
                matches = sum(1 for t in q_terms if t in c_text)
                term_ratio = matches / max(1, len(q_terms))
                base = c.similarity_score or c.fusion_score or 0.5
                score = round(0.5 * base + 0.5 * term_ratio, 4)
                scores.append(score)

        # Pair chunks with scores
        scored_candidates = []
        for chunk, score in zip(candidates, scores):
            # Create a copy with updated reranker score
            updated = chunk.model_copy(
                update={
                    "reranker_score": score,
                    "similarity_score": score,  # update primary ranking score
                    "retrieval_mode": "hybrid_reranked" if "hybrid" in (chunk.retrieval_mode or "") else "reranked",
                }
            )
            scored_candidates.append(updated)

        # Sort descending by reranker_score
        scored_candidates.sort(key=lambda x: (x.reranker_score or 0.0), reverse=True)
        return scored_candidates[:top_k]


class MockReranker(BaseReranker):
    """
    Deterministic mock reranker for unit testing and fast regression runs.
    """

    def rerank(
        self,
        query: str,
        candidates: List[RetrievedChunk],
        top_k: int = 5,
    ) -> List[RetrievedChunk]:
        if not candidates:
            return []

        q_lower = query.lower()
        # Prioritize chunks that contain key terms or entity answers
        scored = []
        for c in candidates:
            c_lower = c.content.lower()
            score = 0.5
            if any(term in c_lower for term in q_lower.split() if len(term) > 2):
                score += 0.3
            if "is" in q_lower and ("born" in c_lower or "protagonist" in c_lower or "wizard" in c_lower or "character" in c_lower):
                score += 0.15
            
            score = round(min(1.0, score), 4)
            updated = c.model_copy(
                update={
                    "reranker_score": score,
                    "similarity_score": score,
                    "retrieval_mode": "hybrid_reranked",
                }
            )
            scored.append(updated)

        scored.sort(key=lambda x: (x.reranker_score or 0.0), reverse=True)
        return scored[:top_k]
