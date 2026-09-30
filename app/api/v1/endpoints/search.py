from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.embeddings import get_embedding_provider
from app.retrieval.factory import get_retriever
from app.schemas.search import SearchRequest, SearchResponse

router = APIRouter(tags=["Retrieval"])


@router.post(
    "/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic, Keyword, or Hybrid Vector Search",
    description="Executes dense semantic retrieval (pgvector), sparse keyword retrieval (PostgreSQL FTS), or hybrid rank fusion (RRF) with optional cross-encoder reranking.",
)
def search_documents(
    request: SearchRequest,
    db: Session = Depends(get_db),
) -> SearchResponse:
    retriever = get_retriever(
        db=db,
        embedding_provider=get_embedding_provider(),
        mode=request.mode,
    )

    result = retriever.retrieve(
        query=request.query,
        top_k=request.top_k,
        similarity_threshold=request.similarity_threshold,
        filters=request.filters,
    )

    return SearchResponse(
        query=result.query,
        total_results=result.total_results,
        execution_time_ms=result.execution_time_ms,
        retrieval_mode=result.retrieval_mode,
        results=result.results,
    )
