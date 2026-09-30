import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.conversation import MessageRole
from app.rag.citation import CitationSource
from app.retrieval.base import RetrievalFilter


class ConversationCreateRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100, description="User or tenant identifier")
    title: Optional[str] = Field(default="New Conversation", max_length=255, description="Optional conversation title")


class MessageCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Message content from user")
    top_k: Optional[int] = Field(default=5, ge=1, le=20, description="Number of context chunks to retrieve")
    similarity_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Minimum relevance threshold")
    filters: Optional[RetrievalFilter] = Field(default=None, description="Optional document/metadata filters")


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    message_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: uuid.UUID
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class ConversationDetailResponse(BaseModel):
    id: uuid.UUID
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ConversationalRAGResponse(BaseModel):
    conversation_id: uuid.UUID
    user_message: MessageResponse
    assistant_message: MessageResponse
    sources: List[CitationSource] = Field(default_factory=list)
    is_grounded: bool = True
    retrieval_metadata: Dict[str, Any] = Field(default_factory=dict)
