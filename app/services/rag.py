from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.config import settings
from app.llm.base import BaseLLMProvider, LLMResponse
from app.llm import get_llm_provider
from app.rag.base import BaseRAGEngine
from app.rag.citation import CitationBuilder, CitationSource
from app.rag.prompt import GroundedPromptBuilder
from app.retrieval.base import BaseRetriever, RetrievalFilter, RetrievalResult
from app.schemas.rag import RAGQueryResponse

# Type alias for backwards compatibility
RAGQueryResult = RAGQueryResponse


class RAGService(BaseRAGEngine):
    """
    Pure Python RAG Orchestration Service.
    Coordinates: Question -> Vector Retrieval -> Context Check -> Prompt Construction -> LLM Inference -> Grounded Citations.
    """

    INSUFFICIENT_CONTEXT_MESSAGE = "Based on the provided documents, I could not find sufficient information to answer this question."

    def __init__(
        self,
        retriever: BaseRetriever,
        llm_provider: Optional[BaseLLMProvider] = None,
        prompt_builder: Optional[GroundedPromptBuilder] = None,
    ):
        self.retriever = retriever
        self.llm_provider = llm_provider or get_llm_provider()
        self.prompt_builder = prompt_builder or GroundedPromptBuilder()

    def query(
        self,
        question: str,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        filters: Optional[RetrievalFilter] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.0,
    ) -> RAGQueryResult:
        k = top_k or settings.RAG_DEFAULT_TOP_K
        min_threshold = similarity_threshold if similarity_threshold is not None else settings.RAG_MIN_RELEVANCE_THRESHOLD

        # 1. Contextualize query for retrieval if previous turns exist
        retrieval_query = question.strip()
        if chat_history and len(retrieval_query.split()) < 6:
            # For short/elliptical follow-ups ("How many weeks?", "Who is eligible?"), prepend previous user context
            last_user_turns = [turn["content"] for turn in chat_history if turn.get("role") == "user"]
            if last_user_turns:
                retrieval_query = f"{last_user_turns[-1]} {retrieval_query}"

        # 2. Vector Retrieval
        retrieval_result: RetrievalResult = self.retriever.retrieve(
            query=retrieval_query,
            top_k=k,
            similarity_threshold=min_threshold,
            filters=filters,
        )

        retrieval_meta = {
            "chunks_retrieved": retrieval_result.total_results,
            "retrieval_time_ms": retrieval_result.execution_time_ms,
            "top_similarity": retrieval_result.results[0].similarity_score if retrieval_result.results else 0.0,
        }

        # 3. Hallucination Control: Check for weak or empty context
        if not retrieval_result.results or retrieval_meta["top_similarity"] < min_threshold:
            return RAGQueryResult(
                question=question,
                answer=self.INSUFFICIENT_CONTEXT_MESSAGE,
                sources=[],
                is_grounded=False,
                llm_model=None,
                token_usage={},
                retrieval_metadata=retrieval_meta,
            )

        # 4. Build Citations
        citations = CitationBuilder.build_citations(retrieval_result.results)

        # 5. Construct Grounded Prompt with Conversation History
        user_prompt, system_prompt = self.prompt_builder.build_prompt(
            question=question,
            retrieved_chunks=retrieval_result.results,
            citations=citations,
            chat_history=chat_history,
        )

        # 6. LLM Inference
        llm_response: LLMResponse = self.llm_provider.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
        )

        return RAGQueryResult(
            question=question,
            answer=llm_response.content.strip(),
            sources=citations,
            is_grounded=True,
            llm_model=llm_response.model,
            token_usage=llm_response.token_usage,
            retrieval_metadata=retrieval_meta,
        )
