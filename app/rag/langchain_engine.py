import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from langchain_core.documents import Document as LCDocument
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import log_duration, logger
from app.rag.base import BaseRAGEngine
from app.rag.citation import CitationSource
from app.rag.langchain_prompts import CONVERSATIONAL_RAG_PROMPT, GROUNDED_RAG_PROMPT
from app.schemas.rag import RAGQueryResponse
from app.retrieval.base import RetrievalFilter
from app.retrieval.langchain import EnterprisePGVectorRetriever


class LangChainRAGEngine(BaseRAGEngine):
    """
    Enterprise RAG orchestration engine using modern LangChain Expression Language (LCEL).
    Combines EnterprisePGVectorRetriever, ChatPromptTemplate, ChatModel, and StrOutputParser,
    while enforcing strict anti-hallucination relevance thresholding and source citation resolution.
    """

    def __init__(
        self,
        db: Optional[Session] = None,
        embedding_provider: Optional[Any] = None,
        chat_model: Optional[BaseChatModel] = None,
        min_relevance_threshold: float = settings.RAG_MIN_RELEVANCE_THRESHOLD,
    ):
        self.db = db
        self.embedding_provider = embedding_provider
        self.min_relevance_threshold = min_relevance_threshold
        self._llm = chat_model

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
        Unified query method conforming to BaseRAGEngine contract.
        Routes to conversational LCEL chain if chat history is present, or standard LCEL chain.
        """
        if self.db is None:
            raise ValueError("Database session must be provided to LangChainRAGEngine for query execution.")

        k = top_k or settings.RAG_DEFAULT_TOP_K

        if chat_history and len(chat_history) > 0:
            history_tuples: List[Tuple[str, str]] = [
                (turn.get("role", "user"), turn.get("content", "")) for turn in chat_history
            ]
            return self.answer_question_conversational(
                db=self.db,
                query=question,
                chat_history=history_tuples,
                top_k=k,
                similarity_threshold=similarity_threshold,
                filters=filters,
                embedding_provider=self.embedding_provider,
            )
        else:
            return self.answer_question(
                db=self.db,
                query=question,
                top_k=k,
                similarity_threshold=similarity_threshold,
                filters=filters,
                embedding_provider=self.embedding_provider,
            )

    def _resolve_llm(self) -> BaseChatModel:
        if self._llm is not None:
            return self._llm

        provider_type = settings.LLM_PROVIDER.lower()
        if provider_type == "openai" and settings.OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=settings.OPENAI_MODEL_NAME,
                temperature=settings.RAG_TEMPERATURE,
                api_key=settings.OPENAI_API_KEY,
            )
        elif provider_type == "gemini" and settings.GEMINI_API_KEY:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL_NAME,
                temperature=settings.RAG_TEMPERATURE,
                google_api_key=settings.GEMINI_API_KEY,
            )
        else:
            # Deterministic mock LLM for testing & offline mode
            from langchain_community.chat_models.fake import FakeListChatModel
            return FakeListChatModel(
                responses=[
                    "According to the documentation [1], the platform uses PostgreSQL with pgvector for vector retrieval [2]."
                ]
            )

    @classmethod
    def format_docs_context(cls, docs: List[LCDocument]) -> str:
        """
        Formats retrieved LangChain Document objects into a structured XML-tagged context block.
        """
        if not docs:
            return "No reference documents available."

        formatted_blocks = []
        for i, doc in enumerate(docs, start=1):
            doc_id = doc.metadata.get("document_id", "N/A")
            name = doc.metadata.get("document_name", "Document")
            version = doc.metadata.get("version_number", 1)
            page = doc.metadata.get("page_number", 1)
            score = doc.metadata.get("similarity_score", 0.0)

            header = f'<doc id="[{i}]" document_id="{doc_id}" name="{name}" version="v{version}" page="{page}" score="{score}">'
            footer = "</doc>"
            formatted_blocks.append(f"{header}\n{doc.page_content}\n{footer}")

        return "\n\n".join(formatted_blocks)

    @classmethod
    def extract_citations(cls, answer: str, docs: List[LCDocument]) -> List[CitationSource]:
        """
        Scans answer for citation markers like [1], [2] and links them to retrieved LangChain Documents.
        """
        marker_pattern = re.compile(r"\[(\d+)\]")
        matches = marker_pattern.findall(answer)
        cited_indices = sorted(list(set(int(m) for m in matches)))

        doc_map = {i: doc for i, doc in enumerate(docs, start=1)}
        citations: List[CitationSource] = []

        for idx in cited_indices:
            if idx in doc_map:
                doc = doc_map[idx]
                meta = doc.metadata
                citations.append(
                    CitationSource(
                        source_index=idx,
                        document_id=uuid.UUID(meta["document_id"]) if meta.get("document_id") else uuid.uuid4(),
                        document_name=meta.get("document_name", "Unknown"),
                        document_version_id=uuid.UUID(meta["document_version_id"]) if meta.get("document_version_id") else uuid.uuid4(),
                        version_number=meta.get("version_number", 1),
                        page_number=meta.get("page_number"),
                        source_filename=meta.get("source_filename", "unknown"),
                        chunk_id=uuid.UUID(meta["chunk_id"]) if meta.get("chunk_id") else uuid.uuid4(),
                        similarity_score=meta.get("similarity_score", 0.0),
                        snippet=doc.page_content[:150] + ("..." if len(doc.page_content) > 150 else ""),
                        citation_label=meta.get("citation_label", f"[{idx}]"),
                    )
                )

        return citations

    def answer_question(
        self,
        db: Session,
        query: str,
        top_k: int = 5,
        similarity_threshold: Optional[float] = None,
        filters: Optional[RetrievalFilter] = None,
        embedding_provider: Optional[Any] = None,
    ) -> RAGQueryResponse:
        """
        Executes end-to-end grounded RAG with LCEL Runnable chain.
        """
        start_time = time.perf_counter()
        thresh = similarity_threshold if similarity_threshold is not None else self.min_relevance_threshold

        with log_duration("LangChain LCEL RAG Pipeline", {"query": query[:60], "top_k": top_k}):
            # Step 1: LangChain Retriever Execution
            retriever = EnterprisePGVectorRetriever(
                db=db,
                embedding_provider=embedding_provider,
                top_k=top_k,
                similarity_threshold=thresh,
                filters=filters,
            )

            retrieved_docs: List[LCDocument] = retriever.invoke(query)

            # Step 2: Anti-Hallucination Guardrail
            max_score = max([d.metadata.get("similarity_score", 0.0) for d in retrieved_docs], default=0.0)
            if not retrieved_docs or max_score < thresh:
                total_duration = round((time.perf_counter() - start_time) * 1000, 2)
                logger.info(f"LangChain RAG: No relevant docs above threshold {thresh} (max={max_score})")
                return RAGQueryResponse(
                    question=query,
                    answer="I cannot find sufficient information in the available documents to answer this question.",
                    sources=[],
                    is_grounded=False,
                    llm_model="langchain_fallback",
                    token_usage={},
                    retrieval_metadata={
                        "engine": "langchain_lcel",
                        "retrieved_count": len(retrieved_docs),
                        "max_similarity": max_score,
                        "threshold_applied": thresh,
                        "latency_ms": total_duration,
                        "fallback_triggered": True,
                    },
                )

            # Step 3: Build Context & Execute LCEL Chain
            context_str = self.format_docs_context(retrieved_docs)
            llm = self._resolve_llm()

            # LCEL Composition: Prompt -> LLM -> StrOutputParser
            chain = GROUNDED_RAG_PROMPT | llm | StrOutputParser()

            raw_answer = chain.invoke(
                {
                    "context": context_str,
                    "question": query,
                }
            )

            # Step 4: Extract Citations & Build Response
            citations = self.extract_citations(raw_answer, retrieved_docs)
            total_duration = round((time.perf_counter() - start_time) * 1000, 2)

            return RAGQueryResponse(
                question=query,
                answer=raw_answer,
                sources=citations,
                is_grounded=len(citations) > 0,
                llm_model="langchain_lcel",
                token_usage={},
                retrieval_metadata={
                    "engine": "langchain_lcel",
                    "retrieved_count": len(retrieved_docs),
                    "max_similarity": max_score,
                    "threshold_applied": thresh,
                    "latency_ms": total_duration,
                    "fallback_triggered": False,
                },
            )

    def answer_question_conversational(
        self,
        db: Session,
        query: str,
        chat_history: List[Tuple[str, str]],
        top_k: int = 5,
        similarity_threshold: Optional[float] = None,
        filters: Optional[RetrievalFilter] = None,
        embedding_provider: Optional[Any] = None,
    ) -> RAGQueryResponse:
        """
        Executes multi-turn conversational RAG using LangChain ChatPromptTemplate with MessagesPlaceholder.
        """
        start_time = time.perf_counter()
        thresh = similarity_threshold if similarity_threshold is not None else self.min_relevance_threshold

        retriever = EnterprisePGVectorRetriever(
            db=db,
            embedding_provider=embedding_provider,
            top_k=top_k,
            similarity_threshold=thresh,
            filters=filters,
        )

        retrieved_docs: List[LCDocument] = retriever.invoke(query)
        max_score = max([d.metadata.get("similarity_score", 0.0) for d in retrieved_docs], default=0.0)

        if not retrieved_docs or max_score < thresh:
            total_duration = round((time.perf_counter() - start_time) * 1000, 2)
            return RAGQueryResponse(
                question=query,
                answer="I cannot find sufficient information in the available documents to answer this question.",
                sources=[],
                is_grounded=False,
                llm_model="langchain_fallback",
                token_usage={},
                retrieval_metadata={
                    "engine": "langchain_lcel_conversational",
                    "retrieved_count": len(retrieved_docs),
                    "max_similarity": max_score,
                    "latency_ms": total_duration,
                    "fallback_triggered": True,
                },
            )

        context_str = self.format_docs_context(retrieved_docs)
        llm = self._resolve_llm()

        # Convert history tuples to LangChain BaseMessage instances
        history_messages: List[BaseMessage] = []
        for role, content in chat_history:
            if role.lower() in ("user", "human"):
                history_messages.append(HumanMessage(content=content))
            else:
                history_messages.append(AIMessage(content=content))

        chain = CONVERSATIONAL_RAG_PROMPT | llm | StrOutputParser()

        raw_answer = chain.invoke(
            {
                "context": context_str,
                "chat_history": history_messages,
                "question": query,
            }
        )

        citations = self.extract_citations(raw_answer, retrieved_docs)
        total_duration = round((time.perf_counter() - start_time) * 1000, 2)

        return RAGQueryResponse(
            question=query,
            answer=raw_answer,
            sources=citations,
            is_grounded=len(citations) > 0,
            llm_model="langchain_lcel_conversational",
            token_usage={},
            retrieval_metadata={
                "engine": "langchain_lcel_conversational",
                "retrieved_count": len(retrieved_docs),
                "max_similarity": max_score,
                "latency_ms": total_duration,
                "fallback_triggered": False,
            },
        )
