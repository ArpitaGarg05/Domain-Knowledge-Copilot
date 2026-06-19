import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat_message import ChatMessage
from app.schemas.search import RetrievedChunkResponse


def list_chat_messages(
    db: Session,
    user_id: int,
    corpus_id: Optional[int] = None,
    conversation_id: Optional[str] = None,
    limit: int = 5,
) -> list[ChatMessage]:
    statement = (
        select(ChatMessage)
        .where(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
    )
    if corpus_id is not None:
        statement = statement.where(ChatMessage.corpus_id == corpus_id)
    if conversation_id is not None:
        statement = statement.where(ChatMessage.conversation_id == conversation_id)

    messages = list(db.scalars(statement.limit(limit)))
    return list(reversed(messages))


def create_chat_turn(
    db: Session,
    corpus_id: int,
    user_id: int,
    conversation_id: str,
    question: str,
    answer: str,
    citations: list[RetrievedChunkResponse],
) -> tuple[ChatMessage, ChatMessage]:
    question_message = ChatMessage(
        corpus_id=corpus_id,
        user_id=user_id,
        conversation_id=conversation_id,
        role="user",
        content=question,
        citations="[]",
    )
    answer_message = ChatMessage(
        corpus_id=corpus_id,
        user_id=user_id,
        conversation_id=conversation_id,
        role="assistant",
        content=answer,
        citations=json.dumps([citation.model_dump() for citation in citations]),
    )

    db.add_all([question_message, answer_message])
    db.commit()
    db.refresh(question_message)
    db.refresh(answer_message)
    return question_message, answer_message


def parse_citations(message: ChatMessage) -> list[dict[str, object]]:
    try:
        parsed = json.loads(message.citations or "[]")
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    return [citation for citation in parsed if isinstance(citation, dict)]
