from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.corpus import Corpus
from app.schemas.corpus import CorpusCreateRequest


def get_corpus(db: Session, corpus_id: int) -> Corpus | None:
    return db.get(Corpus, corpus_id)


def list_corpora(db: Session, skip: int = 0, limit: int = 100) -> list[Corpus]:
    statement = select(Corpus).offset(skip).limit(limit)
    return list(db.scalars(statement))


def create_corpus(db: Session, request: CorpusCreateRequest) -> Corpus:
    corpus = Corpus(name=request.name, description=request.description)
    db.add(corpus)
    db.commit()
    db.refresh(corpus)
    return corpus


def delete_corpus(db: Session, corpus_id: int) -> bool:
    corpus = get_corpus(db, corpus_id)
    if corpus is None:
        return False

    db.delete(corpus)
    db.commit()
    return True
