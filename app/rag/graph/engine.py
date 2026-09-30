from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import log_duration, logger
from app.rag.base import BaseRAGEngine
from app.rag.graph.nodes import RAGGraphNodes
from app.rag.graph.state import RAGGraphState
from app.rag.graph.workflow import create_rag_graph
from app.retrieval.base import RetrievalFilter
from app.schemas.rag import RAGQueryResponse


class LangGraphRAGEngine(BaseRAGEngine):
    """
    Enterprise RAG orchestration engine powered by a stateful, cyclic LangGraph workflow.
    Features automated document relevance grading, query reformulation on weak retrieval,
    bounded retry loops, grounded generation, and verified citation provenance.
    """

    def __init__(
        self,
        db: Optional[Session] = None,
        embedding_provider: Optional[Any] = None,
        chat_model: Optional[BaseChatModel] = None,
        min_relevance_threshold: float = settings.RAG_MIN_RELEVANCE_THRESHOLD,
        max_retries: int = settings.LANGGRAPH_MAX_RETRIES,
        use_checkpointing: bool = True,
    ):
        self.db = db
        self.embedding_provider = embedding_provider
        self.chat_model = chat_model
        self.min_relevance_threshold = min_relevance_threshold
        self.max_retries = max_retries
        self.checkpointer = MemorySaver() if use_checkpointing else None

    def query(
        self,
        question: str,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        filters: Optional[RetrievalFilter] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        temperature: Optional[float] = None,
    ) -> RAGQueryResponse:
        """
        Executes end-to-end question answering via the compiled LangGraph workflow.
        """
        if self.db is None:
            raise ValueError("Database session must be provided to LangGraphRAGEngine for query execution.")

        start_time = time.perf_counter()
        k = top_k or settings.RAG_DEFAULT_TOP_K
        thresh = similarity_threshold if similarity_threshold is not None else self.min_relevance_threshold

        history_tuples: List[Tuple[str, str]] = []
        if chat_history:
            history_tuples = [
                (turn.get("role", "user"), turn.get("content", "")) for turn in chat_history
            ]

        with log_duration("LangGraph Stateful RAG Workflow", {"question": question[:60], "top_k": k}):
            # 1. Initialize Nodes and Graph
            nodes = RAGGraphNodes(
                db=self.db,
                embedding_provider=self.embedding_provider,
                chat_model=self.chat_model,
                min_relevance_threshold=thresh,
                max_retries=self.max_retries,
            )
            graph = create_rag_graph(nodes=nodes, checkpointer=self.checkpointer)

            # 2. Build Initial Graph State
            initial_state: RAGGraphState = {
                "question": question,
                "original_question": question,
                "rewritten_question": None,
                "chat_history": history_tuples,
                "top_k": k,
                "similarity_threshold": thresh,
                "filters": filters,
                "retrieved_documents": [],
                "retrieval_attempt": 1,
                "max_retries": self.max_retries,
                "retrieval_sufficient": False,
                "generated_answer": None,
                "citations": [],
                "is_grounded": False,
                "retrieval_metadata": {},
                "final_response": None,
            }

            # 3. Invoke StateGraph
            config = {"configurable": {"thread_id": str(uuid.uuid4())}}
            final_state = graph.invoke(initial_state, config=config)

            # 4. Extract and Return Result
            final_response: Optional[RAGQueryResponse] = final_state.get("final_response")
            if final_response is None:
                raise RuntimeError("LangGraph workflow completed without generating a final response.")

            total_duration = round((time.perf_counter() - start_time) * 1000, 2)
            if final_response.retrieval_metadata:
                final_response.retrieval_metadata["latency_ms"] = total_duration

            return final_response
