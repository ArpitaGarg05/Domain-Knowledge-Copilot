import json
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.comparison import Comparison, ComparisonDocument, ComparisonResult


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
