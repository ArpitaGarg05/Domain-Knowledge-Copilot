from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.crud import chat_message as chat_message_crud
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
from app.models.chat_message import ChatMessage
from app.schemas.history import ChatMessageResponse, HistoryResponse
from app.schemas.search import (
    AnswerRequest,
    AnswerResponse,
    RetrievedChunkResponse,
    SearchRequest,
)
from app.services.chunk_service import ChunkService
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import (
    LLMConfigurationError,
    LLMGenerationError,
    LLMService,
)
from app.services.pdf_processor import extract_pdf_text
from app.services.vector_store_service import VectorStoreService

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
    VectorStoreService().get_or_create_collection(corpus.id)
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

    VectorStoreService().delete_collection(corpus_id)
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
    embeddings = EmbeddingService().embed_chunks(chunks)

    document = document_crud.create_document(
        db=db,
        corpus_id=corpus_id,
        filename=original_filename,
        source_path=str(destination),
        pages=extracted_pages,
        chunks=chunks,
        embeddings=embeddings,
    )
    VectorStoreService().add_document_chunks(corpus_id=corpus_id, document=document)
    return DocumentResponse.model_validate(document)


@router.post("/search", response_model=list[RetrievedChunkResponse])
def search_corpus(
    request: SearchRequest,
    db: Session = Depends(get_db),
) -> list[RetrievedChunkResponse]:
    corpus = corpus_crud.get_corpus(db, request.corpus_id)
    if corpus is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Corpus not found.",
        )

    results = VectorStoreService().retrieve_by_text(
        corpus_id=request.corpus_id,
        query_text=request.question,
        limit=request.limit,
    )
    return [
        build_retrieved_chunk_response(result)
        for result in results
    ]


def build_retrieved_chunk_response(result) -> RetrievedChunkResponse:
    return RetrievedChunkResponse(
        chunk_id=result.chunk_id,
        document_id=result.document_id,
        corpus_id=result.corpus_id,
        filename=result.filename,
        page_number=result.page_number,
        chunk_index=result.chunk_index,
        chunk_reference=result.chunk_reference,
        text=result.text,
        distance=result.distance,
    )


def build_chat_message_response(message: ChatMessage) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=message.id,
        corpus_id=message.corpus_id,
        role=message.role,
        content=message.content,
        citations=[
            RetrievedChunkResponse(**citation)
            for citation in chat_message_crud.parse_citations(message)
        ],
        created_at=message.created_at,
    )


@router.post("/answer", response_model=AnswerResponse)
def answer_question(
    request: AnswerRequest,
    db: Session = Depends(get_db),
) -> AnswerResponse:
    corpus = corpus_crud.get_corpus(db, request.corpus_id)
    if corpus is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Corpus not found.",
        )

    retrieved_chunks = VectorStoreService().retrieve_by_text(
        corpus_id=request.corpus_id,
        query_text=request.question,
        limit=request.limit,
    )
    sources = [build_retrieved_chunk_response(result) for result in retrieved_chunks]
    recent_messages = chat_message_crud.list_chat_messages(
        db,
        corpus_id=request.corpus_id,
        limit=5,
    )

    try:
        generated = LLMService().generate_answer(
            question=request.question,
            chunks=retrieved_chunks,
            history=recent_messages,
        )
    except LLMConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except LLMGenerationError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error

    _, answer_message = chat_message_crud.create_chat_turn(
        db=db,
        corpus_id=request.corpus_id,
        question=request.question,
        answer=generated.answer,
        citations=sources,
    )

    return AnswerResponse(
        answer=generated.answer,
        sources=sources,
        created_at=answer_message.created_at,
    )


@router.get("/history", response_model=HistoryResponse)
def get_history(
    corpus_id: Optional[int] = Query(default=None),
    limit: int = Query(default=5, ge=1, le=50),
    db: Session = Depends(get_db),
) -> HistoryResponse:
    messages = chat_message_crud.list_chat_messages(
        db,
        corpus_id=corpus_id,
        limit=limit,
    )
    return HistoryResponse(
        items=[
            f"{message.role.title()}: {message.content[:80]}"
            for message in messages
        ],
        messages=[build_chat_message_response(message) for message in messages],
    )
