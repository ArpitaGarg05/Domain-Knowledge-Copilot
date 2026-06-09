from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.crud import corpus as corpus_crud
from app.db.session import get_db
from app.models.corpus import Corpus
from app.schemas.corpus import (
    CorpusCreateRequest,
    CorpusDeleteResponse,
    CorpusResponse,
)
from app.schemas.health import HealthResponse
from app.schemas.history import HistoryResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


def build_corpus_response(corpus: Corpus) -> CorpusResponse:
    return CorpusResponse(
        id=corpus.id,
        name=corpus.name,
        description=corpus.description,
        document_count=len(corpus.documents),
    )


@router.get("/corpora", response_model=list[CorpusResponse])
def list_corpora(db: Session = Depends(get_db)) -> list[CorpusResponse]:
    corpora = corpus_crud.list_corpora(db)
    return [build_corpus_response(corpus) for corpus in corpora]


@router.post(
    "/corpora",
    response_model=CorpusResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_corpus(
    request: CorpusCreateRequest,
    db: Session = Depends(get_db),
) -> CorpusResponse:
    corpus = corpus_crud.create_corpus(db, request)
    return build_corpus_response(corpus)


@router.delete("/corpora/{corpus_id}", response_model=CorpusDeleteResponse)
def delete_corpus(
    corpus_id: int,
    db: Session = Depends(get_db),
) -> CorpusDeleteResponse:
    deleted = corpus_crud.delete_corpus(db, corpus_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Corpus not found.",
        )

    return CorpusDeleteResponse(id=corpus_id, deleted=True)


@router.get("/history", response_model=HistoryResponse)
def get_history() -> HistoryResponse:
    return HistoryResponse(
        items=[
            "Opened Product Docs corpus",
            "Asked a mock question",
            "Viewed corpus settings",
        ]
    )
