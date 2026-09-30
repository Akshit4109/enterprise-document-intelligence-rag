from fastapi import APIRouter, Depends, status

from app.rag.base import BaseRAGEngine
from app.rag.factory import get_rag_engine
from app.schemas.rag import RAGQueryRequest, RAGQueryResponse

router = APIRouter(tags=["RAG Question Answering"])


@router.post(
    "/query",
    response_model=RAGQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="RAG Question Answering with Citations",
    description="Retrieves the most relevant document chunks via vector similarity, applies strict hallucination checks, synthesizes a grounded answer using the selected RAG engine, and returns structured source citations.",
)
def rag_query(
    request: RAGQueryRequest,
    rag_engine: BaseRAGEngine = Depends(get_rag_engine),
) -> RAGQueryResponse:
    result = rag_engine.query(
        question=request.question,
        top_k=request.top_k,
        similarity_threshold=request.similarity_threshold,
        filters=request.filters,
        temperature=request.temperature,
    )

    return RAGQueryResponse(
        question=result.question,
        answer=result.answer,
        sources=result.sources,
        is_grounded=result.is_grounded,
        llm_model=result.llm_model,
        token_usage=result.token_usage,
        retrieval_metadata=result.retrieval_metadata,
    )

