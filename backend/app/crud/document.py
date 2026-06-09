from sqlalchemy.orm import Session

from app.models.document import Document


def create_document(
    db: Session,
    corpus_id: int,
    filename: str,
    source_path: str,
) -> Document:
    document = Document(
        corpus_id=corpus_id,
        title=filename,
        filename=filename,
        source_path=source_path,
        content_preview="",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document
