import logging
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.crud import chat_message as chat_message_crud
from app.crud import comparison as comparison_crud
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
    UserProfileUpdateRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.schemas.corpus import (
    CorpusCreateRequest,
    CorpusDeleteResponse,
    CorpusResponse,
    CorpusUpdateRequest,
    normalize_corpus_name,
)
from app.schemas.comparison import (
    ComparedDocumentResponse,
    ComparisonAskRequest,
    ComparisonAskResponse,
    ComparisonCreateRequest,
    ComparisonCreateResponse,
    ComparisonDetailResponse,
    ComparisonListItemResponse,
    ComparisonListResponse,
    ComparisonQuestionResponse,
    ReferencedSectionResponse,
)
from app.schemas.document import (
    CorpusDocumentListResponse,
    DocumentResponse,
    DocumentSummaryResponse,
)
from app.schemas.health import HealthResponse
from app.schemas.history import ChatMessageResponse, HistoryResponse
from app.schemas.search import (
    AnswerRequest,
    AnswerResponse,
    RetrievedChunkResponse,
    SearchRequest,
)
from app.services.chunk_service import ChunkService
from app.services.comparison_service import (
    ComparisonService,
    ComparisonValidationError,
)
from app.services.corpus_deletion_service import CorpusDeletionService
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import (
    LLMConfigurationError,
    LLMGenerationError,
    LLMService,
)
from app.services.pdf_processor import extract_pdf_text
from app.services.vector_store_service import VectorStoreService

router = APIRouter()
logger = logging.getLogger(__name__)


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


@router.get("/auth/me", response_model=UserResponse)
def get_authenticated_user(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch("/auth/profile", response_model=UserResponse)
def update_profile(
    request: UserProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    user = user_crud.update_user_profile(db, current_user, request)
    return UserResponse.model_validate(user)


def build_corpus_response(corpus: Corpus) -> CorpusResponse:
    return CorpusResponse(
        id=corpus.id,
        name=corpus.name,
        description=corpus.description,
        document_count=len(corpus.documents),
        total_storage_bytes=sum(
            get_document_file_size_bytes(document)
            for document in corpus.documents
        ),
        updated_at=corpus.updated_at,
    )


def get_document_file_size_bytes(document) -> int:
    persisted_size = getattr(document, "file_size_bytes", 0) or 0
    if persisted_size > 0:
        return persisted_size

    source_path = Path(document.source_path) if document.source_path else None
    if source_path is None:
        return 0
    try:
        return source_path.stat().st_size
    except OSError:
        return 0


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
    existing_corpus = corpus_crud.get_user_corpus_by_name(
        db,
        owner_id=current_user.id,
        name=request.name,
    )
    if existing_corpus is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A corpus with this name already exists.",
        )

    corpus = corpus_crud.create_corpus(db, request, owner_id=current_user.id)
    return build_corpus_response(corpus)


@router.patch("/api/corpora/{corpus_id}", response_model=CorpusResponse)
@router.patch("/corpora/{corpus_id}", response_model=CorpusResponse)
def rename_corpus(
    corpus_id: int,
    request: CorpusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CorpusResponse:
    corpus = corpus_crud.get_corpus(db, corpus_id)
    if corpus is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Corpus not found.",
        )
    if corpus.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to rename this corpus.",
        )

    try:
        new_name = normalize_corpus_name(request.name)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    duplicate = corpus_crud.get_user_corpus_by_name(
        db,
        owner_id=current_user.id,
        name=new_name,
        exclude_corpus_id=corpus_id,
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A corpus with this name already exists.",
        )

    updated = corpus_crud.rename_corpus(db, corpus, new_name)
    return build_corpus_response(updated)


@router.delete("/api/corpora/{corpus_id}", response_model=CorpusDeleteResponse)
@router.delete("/corpora/{corpus_id}", response_model=CorpusDeleteResponse)
def delete_corpus(
    corpus_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CorpusDeleteResponse:
    try:
        result = CorpusDeletionService().delete_user_corpus(
            db,
            corpus_id=corpus_id,
            owner_id=current_user.id,
        )
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Corpus not found.",
        )

    return CorpusDeleteResponse(
        id=corpus_id,
        deleted=True,
        deleted_files=len(result.deleted_file_paths),
        deleted_comparisons=len(result.deleted_comparison_ids),
    )


def build_document_summary(document) -> DocumentSummaryResponse:
    if document.chunk_count == 0:
        indexing_status = "empty"
    elif document.embedding_count == document.chunk_count:
        indexing_status = "indexed"
    else:
        indexing_status = "partial"

    return DocumentSummaryResponse(
        id=document.id,
        corpus_id=document.corpus_id,
        filename=document.filename,
        source_path=document.source_path or "",
        uploaded_at=document.uploaded_at,
        page_count=document.page_count,
        chunk_count=document.chunk_count,
        embedding_count=document.embedding_count,
        file_size_bytes=get_document_file_size_bytes(document),
        indexing_status=indexing_status,
    )


def build_compared_document_response(document) -> ComparedDocumentResponse:
    return ComparedDocumentResponse(
        id=document.id,
        filename=document.filename,
        corpus_id=document.corpus_id,
        corpus_name=document.corpus.name if document.corpus else f"Corpus {document.corpus_id}",
    )


def build_comparison_create_response(comparison) -> ComparisonCreateResponse:
    comparison_json = comparison_crud.parse_comparison_json(comparison.result)
    return ComparisonCreateResponse(
        comparison_id=comparison.id,
        overall_summary=str(comparison_json.get("overall_summary", "")),
        common_topics=list(comparison_json.get("common_topics", [])),
        unique_topics=dict(comparison_json.get("unique_topics", {})),
        major_differences=list(comparison_json.get("major_differences", [])),
        missing_concepts=dict(comparison_json.get("missing_concepts", {})),
        beginner_document=str(comparison_json.get("beginner_document", "")),
        most_comprehensive_document=str(
            comparison_json.get("most_comprehensive_document", ""),
        ),
        recommendation=str(comparison_json.get("recommendation", "")),
        evidence=list(comparison_json.get("evidence", [])),
    )


def build_comparison_list_item(comparison) -> ComparisonListItemResponse:
    comparison_json = comparison_crud.parse_comparison_json(comparison.result)
    documents = [
        build_compared_document_response(link.document)
        for link in comparison.documents
        if link.document is not None
    ]
    return ComparisonListItemResponse(
        id=comparison.id,
        title=comparison.title,
        overall_summary=str(comparison_json.get("overall_summary", "")),
        evidence=list(comparison_json.get("evidence", [])),
        document_count=len(documents),
        documents=documents,
        created_at=comparison.created_at,
    )


def build_comparison_question_response(question) -> ComparisonQuestionResponse:
    referenced_sections = [
        ReferencedSectionResponse(**section)
        for section in comparison_crud.parse_json_list(question.referenced_sections)
        if isinstance(section, dict)
    ]
    supporting_documents = [
        str(document)
        for document in comparison_crud.parse_json_list(question.supporting_documents)
    ]
    return ComparisonQuestionResponse(
        id=question.id,
        question=question.question,
        answer=question.answer,
        supporting_documents=supporting_documents,
        referenced_sections=referenced_sections,
        evidence=build_evidence_from_referenced_sections(
            statement=question.answer,
            sections=[section.model_dump() for section in referenced_sections],
        ),
        confidence=question.confidence,
        created_at=question.created_at,
    )


def build_evidence_from_referenced_sections(
    statement: str,
    sections: list[dict[str, object]],
) -> list[dict[str, object]]:
    citations = []
    for section in sections:
        citations.append(
            {
                "document": str(section.get("filename", "Unknown document")),
                "page": int(section.get("page_number") or 0),
                "chunk": str(section.get("chunk_reference", "unknown")),
                "score": float(section.get("score") or 0),
                "relevant_paragraph": str(section.get("text", "")),
                "document_id": int(section.get("document_id") or 0),
                "chunk_id": int(section.get("chunk_id") or 0),
            }
        )
    return [{"statement": statement, "citations": citations}] if citations else []


def build_comparison_detail_response(comparison) -> ComparisonDetailResponse:
    comparison_json = comparison_crud.parse_comparison_json(comparison.result)
    base = build_comparison_create_response(comparison)
    return ComparisonDetailResponse(
        id=comparison.id,
        title=comparison.title,
        documents=[
            build_compared_document_response(link.document)
            for link in comparison.documents
            if link.document is not None
        ],
        comparison_json=comparison_json,
        questions=[
            build_comparison_question_response(question)
            for question in comparison.questions
        ],
        created_at=comparison.created_at,
        **base.model_dump(),
    )


@router.get(
    "/corpora/{corpus_id}/documents",
    response_model=CorpusDocumentListResponse,
)
def list_corpus_documents(
    corpus_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CorpusDocumentListResponse:
    corpus = corpus_crud.get_user_corpus(db, corpus_id, owner_id=current_user.id)
    if corpus is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Corpus not found.",
        )

    documents = [
        build_document_summary(document)
        for document in document_crud.list_documents(db, corpus_id)
    ]
    return CorpusDocumentListResponse(
        corpus_id=corpus_id,
        documents=documents,
        total_documents=len(documents),
        total_pages=sum(document.page_count for document in documents),
        total_chunks=sum(document.chunk_count for document in documents),
        total_embeddings=sum(document.embedding_count for document in documents),
        total_storage_bytes=sum(document.file_size_bytes for document in documents),
    )


@router.get("/api/corpora/{corpus_id}/documents/{document_id}/preview")
def preview_document_pdf(
    corpus_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    corpus = corpus_crud.get_corpus(db, corpus_id)
    if corpus is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Corpus not found.",
        )
    if corpus.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to preview this document.",
        )

    document = document_crud.get_document(db, document_id)
    if document is None or document.corpus_id != corpus_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    source_path = Path(document.source_path) if document.source_path else None
    if source_path is None or not source_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF file not found.",
        )

    return FileResponse(
        path=source_path,
        media_type="application/pdf",
        filename=document.filename,
        content_disposition_type="inline",
        headers={"Accept-Ranges": "bytes"},
    )


@router.post("/comparisons", response_model=ComparisonCreateResponse)
def create_comparison(
    request: ComparisonCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ComparisonCreateResponse:
    document_ids = list(dict.fromkeys(request.document_ids))
    if len(document_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Select at least two unique documents to compare.",
        )

    documents = document_crud.list_user_documents_by_ids(
        db,
        document_ids=document_ids,
        owner_id=current_user.id,
    )
    if len(documents) != len(document_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more selected documents were not found.",
        )

    try:
        generated = ComparisonService().compare_documents(documents)
    except ComparisonValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
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

    comparison = comparison_crud.create_comparison(
        db,
        user_id=current_user.id,
        title=generated.title,
        document_ids=[document.id for document in documents],
        overall_summary=generated.overall_summary,
        comparison_json=generated.comparison_json,
    )
    return build_comparison_create_response(comparison)


@router.get("/comparisons", response_model=ComparisonListResponse)
def list_comparisons(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ComparisonListResponse:
    comparisons = comparison_crud.list_user_comparisons(
        db,
        user_id=current_user.id,
        limit=limit,
    )
    return ComparisonListResponse(
        comparisons=[build_comparison_list_item(comparison) for comparison in comparisons],
    )


@router.get("/comparisons/{comparison_id}", response_model=ComparisonDetailResponse)
def get_comparison(
    comparison_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ComparisonDetailResponse:
    comparison = comparison_crud.get_user_comparison(
        db,
        comparison_id,
        user_id=current_user.id,
    )
    if comparison is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comparison not found.",
        )
    return build_comparison_detail_response(comparison)


@router.post(
    "/comparisons/{comparison_id}/ask",
    response_model=ComparisonAskResponse,
)
def ask_comparison_question(
    comparison_id: int,
    request: ComparisonAskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ComparisonAskResponse:
    comparison = comparison_crud.get_user_comparison(
        db,
        comparison_id,
        user_id=current_user.id,
    )
    if comparison is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comparison not found.",
        )

    documents = [
        link.document for link in comparison.documents if link.document is not None
    ]
    try:
        generated = ComparisonService().answer_question(
            question=request.question,
            documents=documents,
        )
    except ComparisonValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
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

    saved_question = comparison_crud.create_comparison_question(
        db,
        comparison_id=comparison.id,
        question=request.question,
        answer=generated.answer,
        supporting_documents=generated.supporting_documents,
        referenced_sections=generated.referenced_sections,
        confidence=generated.confidence,
    )
    response = build_comparison_question_response(saved_question)
    return ComparisonAskResponse(
        answer=response.answer,
        supporting_documents=response.supporting_documents,
        referenced_sections=response.referenced_sections,
        evidence=generated.evidence,
        confidence=response.confidence,
        created_at=response.created_at,
    )


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
    file_size_bytes = destination.stat().st_size
    logger.info(
        "Stored uploaded PDF: corpus_id=%s filename=%s stored_path=%s file_size_bytes=%s",
        corpus_id,
        original_filename,
        destination,
        file_size_bytes,
    )

    try:
        extracted_pages = extract_pdf_text(destination)
    except Exception as error:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not extract text from the uploaded PDF.",
        ) from error

    extracted_text_length = sum(len(page.text or "") for page in extracted_pages)
    logger.info(
        "Extracted PDF text: corpus_id=%s filename=%s pages=%s extracted_text_length=%s",
        corpus_id,
        original_filename,
        len(extracted_pages),
        extracted_text_length,
    )

    chunks = ChunkService().chunk_pages(extracted_pages)
    logger.info(
        "Chunked PDF text: corpus_id=%s filename=%s chunks=%s",
        corpus_id,
        original_filename,
        len(chunks),
    )
    embeddings = EmbeddingService().embed_chunks(chunks)
    logger.info(
        "Generated embeddings: corpus_id=%s filename=%s embeddings=%s chunks=%s",
        corpus_id,
        original_filename,
        len(embeddings),
        len(chunks),
    )

    document = document_crud.create_document(
        db=db,
        corpus_id=corpus_id,
        filename=original_filename,
        source_path=str(destination),
        file_size_bytes=file_size_bytes,
        pages=extracted_pages,
        chunks=chunks,
        embeddings=embeddings,
    )
    stored_vectors = VectorStoreService().add_document_chunks(
        corpus_id=corpus_id,
        document=document,
    )
    logger.info(
        "Indexed document vectors: corpus_id=%s document_id=%s chunks=%s embeddings=%s stored_vectors=%s",
        corpus_id,
        document.id,
        document.chunk_count,
        document.embedding_count,
        stored_vectors,
    )
    if document.chunk_count and document.embedding_count != document.chunk_count:
        logger.warning(
            "Document marked partially indexed: corpus_id=%s document_id=%s chunks=%s embeddings=%s",
            corpus_id,
            document.id,
            document.chunk_count,
            document.embedding_count,
        )
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
    logger.info(
        "Search retrieved chunks: corpus_id=%s query=%r requested_limit=%s retrieved=%s",
        request.corpus_id,
        request.question,
        request.limit,
        len(results),
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
        conversation_id=message.conversation_id,
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

    conversation_id = request.conversation_id or uuid4().hex
    try:
        UUID(conversation_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="conversation_id must be a valid UUID.",
        ) from error

    retrieved_chunks = VectorStoreService().retrieve_by_text(
        corpus_id=request.corpus_id,
        query_text=request.question,
        limit=request.limit,
    )
    logger.info(
        "Answer retrieval complete: corpus_id=%s conversation_id=%s query=%r requested_limit=%s retrieved=%s",
        request.corpus_id,
        conversation_id,
        request.question,
        request.limit,
        len(retrieved_chunks),
    )
    sources = [build_retrieved_chunk_response(result) for result in retrieved_chunks]
    logger.info(
        "Passing retrieved context to LLM: corpus_id=%s conversation_id=%s chunks=%s context_chars=%s source_documents=%s",
        request.corpus_id,
        conversation_id,
        len(retrieved_chunks),
        sum(len(chunk.text or "") for chunk in retrieved_chunks),
        sorted({chunk.filename for chunk in retrieved_chunks}),
    )
    recent_messages = chat_message_crud.list_chat_messages(
        db,
        user_id=current_user.id,
        corpus_id=request.corpus_id,
        conversation_id=conversation_id,
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
        conversation_id=conversation_id,
        question=request.question,
        answer=generated.answer,
        citations=sources,
    )

    return AnswerResponse(
        conversation_id=conversation_id,
        answer=generated.answer,
        sources=sources,
        created_at=answer_message.created_at,
    )


@router.get("/history", response_model=HistoryResponse)
def get_history(
    corpus_id: Optional[int] = Query(default=None),
    conversation_id: Optional[str] = Query(default=None),
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
        conversation_id=conversation_id,
        limit=limit,
    )
    return HistoryResponse(
        items=[
            f"{message.role.title()}: {message.content[:80]}"
            for message in messages
        ],
        messages=[build_chat_message_response(message) for message in messages],
    )
