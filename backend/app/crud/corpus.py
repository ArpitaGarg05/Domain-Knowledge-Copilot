from typing import Optional

from sqlalchemy import func, inspect, literal, select
from sqlalchemy.orm import Session

from app.models.corpus import Corpus
from app.models.document import Document
from app.schemas.corpus import CorpusCreateRequest


def get_corpus_metrics(
    db: Session,
    corpus_ids: list[int],
) -> dict[int, tuple[int, int]]:
    if not corpus_ids:
        return {}

    unique_ids = list(dict.fromkeys(corpus_ids))
    inspector = inspect(db.get_bind())
    if Document.__tablename__ not in set(inspector.get_table_names()):
        return {corpus_id: (0, 0) for corpus_id in unique_ids}

    document_columns = {
        column["name"]
        for column in inspector.get_columns(Document.__tablename__)
    }
    has_file_size_column = "file_size_bytes" in document_columns

    storage_expression = (
        func.coalesce(func.sum(Document.file_size_bytes), 0)
        if has_file_size_column
        else literal(0)
    )
    statement = (
        select(
            Document.corpus_id,
            func.count(Document.id),
            storage_expression,
        )
        .where(Document.corpus_id.in_(unique_ids))
        .group_by(Document.corpus_id)
    )

    metrics = {
        corpus_id: (0, 0)
        for corpus_id in unique_ids
    }
    for corpus_id, document_count, total_storage_bytes in db.execute(statement):
        metrics[int(corpus_id)] = (
            int(document_count or 0),
            int(total_storage_bytes or 0),
        )

    return metrics


def get_corpus(db: Session, corpus_id: int) -> Optional[Corpus]:
    return db.get(Corpus, corpus_id)


def get_user_corpus(db: Session, corpus_id: int, owner_id: int) -> Optional[Corpus]:
    statement = select(Corpus).where(
        Corpus.id == corpus_id,
        Corpus.owner_id == owner_id,
    )
    return db.scalar(statement)


def get_user_corpus_by_name(
    db: Session,
    *,
    owner_id: int,
    name: str,
    exclude_corpus_id: Optional[int] = None,
) -> Optional[Corpus]:
    statement = select(Corpus).where(
        Corpus.owner_id == owner_id,
        func.lower(Corpus.name) == name.lower(),
    )
    if exclude_corpus_id is not None:
        statement = statement.where(Corpus.id != exclude_corpus_id)
    return db.scalar(statement)


def list_corpora(
    db: Session,
    owner_id: int,
    skip: int = 0,
    limit: int = 100,
) -> list[Corpus]:
    statement = (
        select(Corpus)
        .where(Corpus.owner_id == owner_id)
        .order_by(Corpus.id)
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(statement))


def create_corpus(db: Session, request: CorpusCreateRequest, owner_id: int) -> Corpus:
    corpus = Corpus(
        name=request.name,
        description=request.description,
        owner_id=owner_id,
    )
    db.add(corpus)
    db.commit()
    db.refresh(corpus)
    return corpus


def rename_corpus(db: Session, corpus: Corpus, name: str) -> Corpus:
    corpus.name = name
    db.add(corpus)
    db.commit()
    db.refresh(corpus)
    return corpus


def delete_corpus(db: Session, corpus_id: int, owner_id: int) -> bool:
    corpus = get_user_corpus(db, corpus_id, owner_id)
    if corpus is None:
        return False

    db.delete(corpus)
    db.commit()
    return True
