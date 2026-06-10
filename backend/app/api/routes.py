from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.crud import chat_message as chat_message_crud
from app.crud import corpus as corpus_crud
from app.crud import document as document_crud
from app.crud import user as user_crud
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.chat_message import ChatMessage
from app.models.corpus import Corpus
from app.models.user import User
from app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.schemas.corpus import (
    CorpusCreateRequest,
    CorpusDeleteResponse,
    CorpusResponse,
)
from app.schemas.document import DocumentResponse
from app.schemas.health import HealthResponse
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


def build_token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(subject=str(user.id)),
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    request: UserRegisterRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    existing_user = user_crud.get_user_by_email(db, request.email)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    user = user_crud.create_user(db, request)
    return build_token_response(user)


@router.post("/auth/login", response_model=TokenResponse)
def login_user(
    request: UserLoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = user_crud.get_user_by_email(db, request.email)
    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return build_token_response(user)


def build_corpus_response(corpus: Corpus) -> CorpusResponse:
    return CorpusResponse(
        id=corpus.id,
        name=corpus.name,
        description=corpus.description,
        document_count=len(corpus.documents),
    )


@router.get("/corpora", response_model=list[CorpusResponse])
def list_corpora(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CorpusResponse]:
    corpora = corpus_crud.list_corpora(db, owner_id=current_user.id)
    return [build_corpus_response(corpus) for corpus in corpora]


@router.post(
    "/corpora",
    response_model=CorpusResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_corpus(
    request: CorpusCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CorpusResponse:
    corpus = corpus_crud.create_corpus(db, request, owner_id=current_user.id)
    VectorStoreService().get_or_create_collection(corpus.id)
    return build_corpus_response(corpus)


@router.delete("/corpora/{corpus_id}", response_model=CorpusDeleteResponse)
def delete_corpus(
    corpus_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CorpusDeleteResponse:
    deleted = corpus_crud.delete_corpus(db, corpus_id, owner_id=current_user.id)
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
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    corpus = corpus_crud.get_user_corpus(db, corpus_id, owner_id=current_user.id)
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
    current_user: User = Depends(get_current_user),
) -> list[RetrievedChunkResponse]:
    corpus = corpus_crud.get_user_corpus(
        db,
        request.corpus_id,
        owner_id=current_user.id,
    )
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
    current_user: User = Depends(get_current_user),
) -> AnswerResponse:
    corpus = corpus_crud.get_user_corpus(
        db,
        request.corpus_id,
        owner_id=current_user.id,
    )
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
        user_id=current_user.id,
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
        user_id=current_user.id,
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
    current_user: User = Depends(get_current_user),
) -> HistoryResponse:
    if corpus_id is not None:
        corpus = corpus_crud.get_user_corpus(db, corpus_id, owner_id=current_user.id)
        if corpus is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Corpus not found.",
            )

    messages = chat_message_crud.list_chat_messages(
        db,
        user_id=current_user.id,
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
