from __future__ import annotations

import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from langchain_core.documents import Document as LCDocument
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.rag.citation import CitationSource
from app.rag.langchain_prompts import CONVERSATIONAL_RAG_PROMPT, GROUNDED_RAG_PROMPT
from app.rag.graph.state import RAGGraphState
from app.retrieval.langchain import EnterprisePGVectorRetriever
from app.schemas.rag import RAGQueryResponse


QUERY_REWRITE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are an AI assistant optimizing queries for enterprise and document search. "
        "Analyze the original question and recent chat history to produce a single, focused, "
        "keyword-rich search query that retrieves the most relevant informational passages. "
        "Preserve all specific names, entities, character names, identifiers, and technical terms. "
        "For short entity questions (e.g. 'who is [Name]' or 'what is [Concept]'), preserve the full entity name and expand with descriptive contextual terms (e.g. character, background, overview, description). "
        "Output ONLY the refined search query string without any explanations or quotation marks.",
    ),
    (
        "human",
        "Chat History:\n{chat_history}\n\nCurrent Question: {question}\n\nOptimized Search Query:",
    ),
])


class RAGGraphNodes:
    """
    Stateful execution nodes for the LangGraph RAG workflow.
    Orchestrates PostgreSQL/pgvector retrieval, relevance grading, query rewriting,
    grounded LLM generation, and citation provenance mapping.
    """

    def __init__(
        self,
        db: Session,
        embedding_provider: Optional[Any] = None,
        chat_model: Optional[BaseChatModel] = None,
        min_relevance_threshold: float = settings.RAG_MIN_RELEVANCE_THRESHOLD,
        max_retries: int = settings.LANGGRAPH_MAX_RETRIES,
    ):
        self.db = db
        self.embedding_provider = embedding_provider
        self.chat_model = chat_model
        self.min_relevance_threshold = min_relevance_threshold
        self.max_retries = max_retries

    def _resolve_llm(self) -> BaseChatModel:
        if self.chat_model is not None:
            return self.chat_model

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
            from langchain_community.chat_models.fake import FakeListChatModel
            return FakeListChatModel(
                responses=[
                    "According to the documentation [1], the platform uses PostgreSQL with pgvector for vector retrieval [2]."
                ]
            )

    @classmethod
    def format_docs_context(cls, docs: List[LCDocument]) -> str:
        """
        Formats retrieved LangChain Document objects into structured XML reference blocks.
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
        Extracts cited source references ([1], [2]) from answer and pairs them with doc metadata.
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

    def retrieve_documents(self, state: RAGGraphState) -> Dict[str, Any]:
        """
        Node 1: Executes vector similarity search against PostgreSQL/pgvector.
        Uses rewritten_question if present, otherwise question.
        """
        query = state.get("rewritten_question") or state.get("question", "")
        top_k = state.get("top_k", settings.RAG_DEFAULT_TOP_K)
        threshold = state.get("similarity_threshold")
        if threshold is None:
            threshold = self.min_relevance_threshold
        filters = state.get("filters")

        attempt = state.get("retrieval_attempt", 1)
        logger.info(f"LangGraph [Node: retrieve_documents] Attempt {attempt} | Query: '{query[:60]}'")

        retriever = EnterprisePGVectorRetriever(
            db=self.db,
            embedding_provider=self.embedding_provider,
            top_k=top_k,
            similarity_threshold=threshold,
            filters=filters,
        )

        docs: List[LCDocument] = retriever.invoke(query)
        return {
            "retrieved_documents": docs,
            "retrieval_attempt": attempt,
        }

    def grade_documents(self, state: RAGGraphState) -> Dict[str, Any]:
        """
        Node 2: Evaluates the relevance and sufficiency of retrieved documents.
        Checks chunk count and cosine similarity threshold.
        """
        docs = state.get("retrieved_documents", [])
        threshold = state.get("similarity_threshold")
        if threshold is None:
            threshold = self.min_relevance_threshold

        max_score = max([d.metadata.get("similarity_score", 0.0) for d in docs], default=0.0)
        is_sufficient = bool(docs and max_score >= threshold)

        logger.info(
            f"LangGraph [Node: grade_documents] Sufficiency: {is_sufficient} | "
            f"Docs: {len(docs)}, Max Score: {max_score:.4f}, Threshold: {threshold}"
        )

        return {
            "retrieval_sufficient": is_sufficient,
        }

    def rewrite_query(self, state: RAGGraphState) -> Dict[str, Any]:
        """
        Node 3: Reformulates user question to expand search terms when retrieval is insufficient.
        Incorporates conversation history and increments retrieval_attempt counter.
        """
        current_query = state.get("question", "")
        original_query = state.get("original_question", current_query)
        history = state.get("chat_history", [])
        current_attempt = state.get("retrieval_attempt", 1)
        next_attempt = current_attempt + 1

        logger.info(f"LangGraph [Node: rewrite_query] Generating rewritten query for attempt {next_attempt}")

        history_str = "\n".join([f"{role}: {content}" for role, content in history]) if history else "None"
        llm = self._resolve_llm()

        try:
            chain = QUERY_REWRITE_PROMPT | llm | StrOutputParser()
            rewritten = chain.invoke({"chat_history": history_str, "question": original_query}).strip()
            # Sanitize output from any quotes or multiline artifact
            rewritten = rewritten.strip('"\'').split("\n")[0]
            if not rewritten:
                rewritten = f"{original_query} enterprise architecture details"
        except Exception as e:
            logger.warning(f"LangGraph query rewriting exception: {e}, falling back to term expansion")
            rewritten = f"{original_query} documentation overview"

        logger.info(f"LangGraph [Node: rewrite_query] Rewritten Query: '{rewritten}'")

        return {
            "rewritten_question": rewritten,
            "retrieval_attempt": next_attempt,
        }

    def generate_answer(self, state: RAGGraphState) -> Dict[str, Any]:
        """
        Node 4: Generates grounded response using retrieved documents or triggers safe fallback.
        """
        is_sufficient = state.get("retrieval_sufficient", False)
        docs = state.get("retrieved_documents", [])
        original_query = state.get("original_question", state.get("question", ""))
        history = state.get("chat_history", [])

        if not is_sufficient or not docs:
            logger.info("LangGraph [Node: generate_answer] Insufficient retrieval -> Generating safe fallback answer")
            return {
                "generated_answer": "I cannot find sufficient information in the available documents to answer this question.",
                "citations": [],
                "is_grounded": False,
            }

        logger.info(f"LangGraph [Node: generate_answer] Generating grounded answer with {len(docs)} documents")
        context_str = self.format_docs_context(docs)
        llm = self._resolve_llm()

        if history:
            messages = []
            for role, content in history:
                if role.lower() in ("user", "human"):
                    messages.append(HumanMessage(content=content))
                else:
                    messages.append(AIMessage(content=content))

            chain = CONVERSATIONAL_RAG_PROMPT | llm | StrOutputParser()
            raw_answer = chain.invoke({
                "context": context_str,
                "question": original_query,
                "chat_history": messages,
            })
        else:
            chain = GROUNDED_RAG_PROMPT | llm | StrOutputParser()
            raw_answer = chain.invoke({
                "context": context_str,
                "question": original_query,
            })

        citations = self.extract_citations(raw_answer, docs)
        return {
            "generated_answer": raw_answer,
            "citations": citations,
            "is_grounded": len(citations) > 0,
        }

    def finalize_response(self, state: RAGGraphState) -> Dict[str, Any]:
        """
        Node 5: Assembles RAGQueryResponse matching the platform's API contract.
        """
        original_query = state.get("original_question", state.get("question", ""))
        answer = state.get("generated_answer", "")
        citations = state.get("citations", [])
        is_grounded = state.get("is_grounded", False)
        docs = state.get("retrieved_documents", [])
        threshold = state.get("similarity_threshold", self.min_relevance_threshold)
        attempt = state.get("retrieval_attempt", 1)
        rewritten = state.get("rewritten_question")
        has_history = bool(state.get("chat_history"))

        max_score = max([d.metadata.get("similarity_score", 0.0) for d in docs], default=0.0)
        is_fallback = not is_grounded or not docs

        engine_name = "langgraph_conversational" if has_history else "langgraph"

        response = RAGQueryResponse(
            question=original_query,
            answer=answer,
            sources=citations,
            is_grounded=is_grounded,
            llm_model=engine_name,
            token_usage={},
            retrieval_metadata={
                "engine": engine_name,
                "retrieved_count": len(docs),
                "max_similarity": max_score,
                "threshold_applied": threshold,
                "retry_attempts": attempt,
                "rewritten_query": rewritten,
                "fallback_triggered": is_fallback,
            },
        )

        logger.info(f"LangGraph [Node: finalize_response] Response assembled for '{original_query[:60]}'")
        return {"final_response": response}
