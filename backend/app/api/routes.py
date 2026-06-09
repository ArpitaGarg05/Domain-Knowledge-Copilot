from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.crud import corpus as corpus_crud
from app.crud import document as document_crud
from app.core.config import settings
from app.db.session import get_db
from app.models.corpus import Corpus
from app.schemas.corpus import (
    CorpusCreateRequest,
    CorpusDeleteResponse,
    CorpusResponse,
)
from app.schemas.document import DocumentResponse
from app.schemas.health import HealthResponse
from app.schemas.history import HistoryResponse
from app.services.chunk_service import ChunkService
from app.services.pdf_processor import extract_pdf_text

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


@router.post(
    "/corpora/{corpus_id}/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    corpus_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    corpus = corpus_crud.get_corpus(db, corpus_id)
    if corpus is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Corpus not found.",
        )

    original_filename = Path(file.filename or "").name
    if not original_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must include a filename.",
        )

    if Path(original_filename).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF uploads are supported.",
        )

    upload_dir = Path(settings.upload_dir) / "corpora" / str(corpus_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{uuid4().hex}_{original_filename}"
    destination = upload_dir / stored_filename

    with destination.open("wb") as output_file:
        output_file.write(file.file.read())

    try:
        extracted_pages = extract_pdf_text(destination)
    except Exception as error:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not extract text from the uploaded PDF.",
        ) from error

    chunks = ChunkService().chunk_pages(extracted_pages)

    document = document_crud.create_document(
        db=db,
        corpus_id=corpus_id,
        filename=original_filename,
        source_path=str(destination),
        pages=extracted_pages,
        chunks=chunks,
    )
    return DocumentResponse.model_validate(document)


@router.get("/history", response_model=HistoryResponse)
def get_history() -> HistoryResponse:
    return HistoryResponse(
        items=[
            "Opened Product Docs corpus",
            "Asked a mock question",
            "Viewed corpus settings",
        ]
    )
