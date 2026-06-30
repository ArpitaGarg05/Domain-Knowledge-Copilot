from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from typing import Optional

from app.models.corpus import Corpus

from app.models.document import ChunkEmbedding, Document, DocumentChunk, DocumentPage
from app.services.chunk_service import TextChunk
from app.services.embedding_service import EmbeddedChunk
from app.services.pdf_processor import ExtractedPdfPage


def list_documents(db: Session, corpus_id: int) -> list[Document]:
    statement = (
        select(Document)
        .where(Document.corpus_id == corpus_id)
        .order_by(Document.uploaded_at.desc(), Document.id.desc())
    )
    return list(db.scalars(statement))


def get_document(db: Session, document_id: int) -> Optional[Document]:
    return db.get(Document, document_id)


def list_user_documents_by_ids(
    db: Session,
    *,
    document_ids: list[int],
    owner_id: int,
) -> list[Document]:
    unique_ids = list(dict.fromkeys(document_ids))
    statement = (
        select(Document)
        .join(Corpus)
        .where(Document.id.in_(unique_ids), Corpus.owner_id == owner_id)
        .options(
            selectinload(Document.corpus),
            selectinload(Document.pages),
        )
    )
    documents = list(db.scalars(statement))
    documents_by_id = {document.id: document for document in documents}
    return [
        documents_by_id[document_id]
        for document_id in unique_ids
        if document_id in documents_by_id
    ]


def create_document(
    db: Session,
    corpus_id: int,
    filename: str,
    source_path: str,
    file_size_bytes: int,
    pages: list[ExtractedPdfPage],
    chunks: list[TextChunk],
    embeddings: list[EmbeddedChunk],
) -> Document:
    extracted_text = "\n".join(page.text for page in pages).strip()
    embeddings_by_index = {
        embedding.chunk_index: embedding for embedding in embeddings
    }
    document = Document(
        corpus_id=corpus_id,
        title=filename,
        filename=filename,
        source_path=source_path,
        file_size_bytes=file_size_bytes,
        content_preview=extracted_text[:500],
        page_count=len(pages),
        pages=[
            DocumentPage(page_number=page.page_number, text=page.text)
            for page in pages
        ],
        chunks=[
            DocumentChunk(
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                embedding=(
                    ChunkEmbedding(
                        model_name=embeddings_by_index[chunk.chunk_index].model_name,
                        vector_dimension=embeddings_by_index[
                            chunk.chunk_index
                        ].vector_dimension,
                        vector=embeddings_by_index[chunk.chunk_index].vector_json,
                    )
                    if chunk.chunk_index in embeddings_by_index
                    else None
                ),
            )
            for chunk in chunks
        ],
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document
