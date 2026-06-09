from sqlalchemy.orm import Session

from app.models.document import Document, DocumentChunk, DocumentPage
from app.services.chunk_service import TextChunk
from app.services.pdf_processor import ExtractedPdfPage


def create_document(
    db: Session,
    corpus_id: int,
    filename: str,
    source_path: str,
    pages: list[ExtractedPdfPage],
    chunks: list[TextChunk],
) -> Document:
    extracted_text = "\n".join(page.text for page in pages).strip()
    document = Document(
        corpus_id=corpus_id,
        title=filename,
        filename=filename,
        source_path=source_path,
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
            )
            for chunk in chunks
        ],
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document
