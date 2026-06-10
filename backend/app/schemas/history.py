from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.search import RetrievedChunkResponse


class ChatMessageResponse(BaseModel):
    id: int
    corpus_id: int
    role: str
    content: str
    citations: list[RetrievedChunkResponse]
    created_at: datetime


class HistoryResponse(BaseModel):
    items: list[str]
    messages: list[ChatMessageResponse] = Field(default_factory=list)
