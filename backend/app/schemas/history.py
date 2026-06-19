from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.search import RetrievedChunkResponse


class ChatMessageResponse(BaseModel):
    id: int
    corpus_id: int
    conversation_id: Optional[str] = None
    role: str
    content: str
    citations: list[RetrievedChunkResponse]
    created_at: datetime


class HistoryResponse(BaseModel):
    items: list[str]
    messages: list[ChatMessageResponse] = Field(default_factory=list)
