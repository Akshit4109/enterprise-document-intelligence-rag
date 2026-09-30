import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.rag.base import BaseRAGEngine
from app.rag.factory import get_rag_engine
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationResponse,
    ConversationalRAGResponse,
    MessageCreateRequest,
    MessageResponse,
)
from app.services.conversation import ConversationService

router = APIRouter(tags=["Conversations"])


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation session",
)
def create_conversation(
    request: ConversationCreateRequest,
    db: Session = Depends(get_db),
) -> ConversationResponse:
    conv = ConversationService.create_conversation(
        db=db,
        user_id=request.user_id,
        title=request.title,
    )
    return ConversationResponse(
        id=conv.id,
        user_id=conv.user_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=0,
    )


@router.get(
    "/conversations",
    response_model=List[ConversationResponse],
    status_code=status.HTTP_200_OK,
    summary="List conversations for a user",
)
def list_conversations(
    user_id: str = Query(..., description="User ID to list conversations for"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> List[ConversationResponse]:
    conversations = ConversationService.list_conversations(
        db=db,
        user_id=user_id,
        skip=skip,
        limit=limit,
    )
    responses = []
    for conv in conversations:
        responses.append(
            ConversationResponse(
                id=conv.id,
                user_id=conv.user_id,
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=len(conv.messages),
            )
        )
    return responses


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get conversation detail and message history",
)
def get_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ConversationDetailResponse:
    conv = ConversationService.get_conversation(db=db, conversation_id=conversation_id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation with ID '{conversation_id}' not found.",
        )
    return ConversationDetailResponse.model_validate(conv)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationalRAGResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a message in a conversation and get grounded RAG response",
)
def send_message(
    conversation_id: uuid.UUID,
    request: MessageCreateRequest,
    db: Session = Depends(get_db),
    rag_engine: BaseRAGEngine = Depends(get_rag_engine),
) -> ConversationalRAGResponse:
    try:
        user_msg, assistant_msg, rag_res = ConversationService.send_message_and_generate_response(
            db=db,
            conversation_id=conversation_id,
            user_content=request.content,
            rag_service=rag_engine,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
            filters=request.filters,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return ConversationalRAGResponse(
        conversation_id=conversation_id,
        user_message=MessageResponse.model_validate(user_msg),
        assistant_message=MessageResponse.model_validate(assistant_msg),
        sources=rag_res.sources,
        is_grounded=rag_res.is_grounded,
        retrieval_metadata=rag_res.retrieval_metadata,
    )
