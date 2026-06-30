from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.corpus import Corpus
from app.schemas.corpus import CorpusCreateRequest


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
