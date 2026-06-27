import json
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.comparison import (
    Comparison,
    ComparisonDocument,
    ComparisonQuestion,
    ComparisonResult,
)


def create_comparison(
    db: Session,
    *,
    user_id: int,
    title: str,
    document_ids: list[int],
    overall_summary: str,
    comparison_json: dict[str, Any],
) -> Comparison:
    comparison = Comparison(
        user_id=user_id,
        title=title,
        documents=[
            ComparisonDocument(document_id=document_id)
            for document_id in document_ids
        ],
        result=ComparisonResult(
            overall_summary=overall_summary,
            comparison_json=json.dumps(comparison_json),
        ),
    )
    db.add(comparison)
    db.commit()
    db.refresh(comparison)
    return get_user_comparison(db, comparison.id, user_id=user_id) or comparison


def list_user_comparisons(
    db: Session,
    *,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
) -> list[Comparison]:
    statement = (
        select(Comparison)
        .where(Comparison.user_id == user_id)
        .options(
            selectinload(Comparison.documents).selectinload(
                ComparisonDocument.document,
            ),
            selectinload(Comparison.result),
            selectinload(Comparison.questions),
        )
        .order_by(Comparison.created_at.desc(), Comparison.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(statement))


def get_user_comparison(
    db: Session,
    comparison_id: int,
    *,
    user_id: int,
) -> Optional[Comparison]:
    statement = (
        select(Comparison)
        .where(Comparison.id == comparison_id, Comparison.user_id == user_id)
        .options(
            selectinload(Comparison.documents).selectinload(
                ComparisonDocument.document,
            ),
            selectinload(Comparison.result),
            selectinload(Comparison.questions),
        )
    )
    return db.scalar(statement)


def parse_comparison_json(result: Optional[ComparisonResult]) -> dict[str, Any]:
    if result is None:
        return {}
    try:
        parsed = json.loads(result.comparison_json or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def create_comparison_question(
    db: Session,
    *,
    comparison_id: int,
    question: str,
    answer: str,
    supporting_documents: list[str],
    referenced_sections: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    confidence: str,
) -> ComparisonQuestion:
    comparison_question = ComparisonQuestion(
        comparison_id=comparison_id,
        question=question,
        answer=answer,
        supporting_documents=json.dumps(supporting_documents),
        referenced_sections=json.dumps(referenced_sections),
        evidence=json.dumps(evidence),
        confidence=confidence,
    )
    db.add(comparison_question)
    db.commit()
    db.refresh(comparison_question)
    return comparison_question


def parse_json_list(value: str) -> list[Any]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []
