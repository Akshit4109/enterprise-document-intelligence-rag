import uuid
from typing import Dict, List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.conversation import Conversation, Message, MessageRole
from app.rag.base import BaseRAGEngine
from app.retrieval.base import RetrievalFilter
from app.schemas.rag import RAGQueryResponse
from app.services.rag import RAGService, RAGQueryResult


class ConversationService:
    """
    Manages persistent multi-turn conversations and integrates with BaseRAGEngine.
    """

    MAX_HISTORY_TURNS = 5  # Sliding window: 5 turns (up to 10 messages)

    @classmethod
    def create_conversation(
        cls,
        db: Session,
        user_id: str,
        title: Optional[str] = None,
    ) -> Conversation:
        conversation = Conversation(
            user_id=user_id,
            title=title or "New Conversation",
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation

    @classmethod
    def get_conversation(
        cls,
        db: Session,
        conversation_id: uuid.UUID,
    ) -> Optional[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.id == conversation_id)
        )
        return db.scalars(stmt).first()

    @classmethod
    def list_conversations(
        cls,
        db: Session,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    @classmethod
    def get_recent_history(
        cls,
        db: Session,
        conversation_id: uuid.UUID,
        max_turns: int = MAX_HISTORY_TURNS,
    ) -> List[Dict[str, str]]:
        """
        Extracts recent conversation turns in chronological order for sliding-window context injection.
        """
        # Fetch the most recent 2*max_turns messages
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(max_turns * 2)
        )
        recent_messages = list(db.scalars(stmt).all())
        # Reverse to restore chronological order (oldest -> newest)
        recent_messages.reverse()

        history = []
        for msg in recent_messages:
            history.append({
                "role": msg.role.value if hasattr(msg.role, "value") else str(msg.role),
                "content": msg.content,
            })
        return history

    @classmethod
    def send_message_and_generate_response(
        cls,
        db: Session,
        conversation_id: uuid.UUID,
        user_content: str,
        rag_service: BaseRAGEngine,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        filters: Optional[RetrievalFilter] = None,
    ) -> Tuple[Message, Message, RAGQueryResponse]:
        """
        1. Validates conversation exists.
        2. Retrieves recent history window.
        3. Executes conversational RAG query.
        4. Persists user message and assistant message atomically.
        5. Updates conversation title and timestamp.
        """
        conversation = cls.get_conversation(db, conversation_id)
        if not conversation:
            raise ValueError(f"Conversation with ID {conversation_id} not found.")

        # 1. Fetch recent history
        history = cls.get_recent_history(db, conversation_id)

        # 2. Execute RAG query with multi-turn context
        rag_result = rag_service.query(
            question=user_content,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            filters=filters,
            chat_history=history,
        )

        # 3. Persist User Message
        user_msg = Message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=user_content,
            message_metadata={},
        )
        db.add(user_msg)

        # 4. Persist Assistant Message with Citations & Provenance
        sources_meta = [src.model_dump(mode="json") for src in rag_result.sources]
        assistant_meta = {
            "sources": sources_meta,
            "is_grounded": rag_result.is_grounded,
            "llm_model": rag_result.llm_model,
            "token_usage": rag_result.token_usage,
            "retrieval_metadata": rag_result.retrieval_metadata,
        }

        assistant_msg = Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=rag_result.answer,
            message_metadata=assistant_meta,
        )
        db.add(assistant_msg)

        # Auto-update conversation title if default
        if conversation.title == "New Conversation" and user_content:
            conversation.title = user_content[:40] + ("..." if len(user_content) > 40 else "")

        db.commit()
        db.refresh(user_msg)
        db.refresh(assistant_msg)
        db.refresh(conversation)

        return user_msg, assistant_msg, rag_result
