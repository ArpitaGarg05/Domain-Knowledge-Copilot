import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.comparison import Comparison, ComparisonDocument
from app.models.corpus import Corpus
from app.models.document import Document
from app.services.vector_store_service import VectorStoreService


@dataclass(frozen=True)
class CorpusDeletionResult:
    corpus_id: int
    deleted: bool
    deleted_file_paths: list[str] = field(default_factory=list)
    deleted_comparison_ids: list[int] = field(default_factory=list)


class CorpusDeletionService:
    def __init__(
        self,
        vector_store_service: Optional[VectorStoreService] = None,
        upload_root: str = settings.upload_dir,
    ) -> None:
        self.vector_store_service = vector_store_service or VectorStoreService()
        self.upload_root = Path(upload_root)

    def delete_user_corpus(
        self,
        db: Session,
        *,
        corpus_id: int,
        owner_id: int,
    ) -> Optional[CorpusDeletionResult]:
        corpus = self._get_owned_corpus(db, corpus_id=corpus_id, owner_id=owner_id)
        if corpus is None:
            return None

        file_paths = self._document_file_paths(corpus.documents)
        comparison_ids = self._comparison_ids_for_documents(
            db,
            user_id=owner_id,
            document_ids=[document.id for document in corpus.documents],
        )
        comparisons = self._comparisons_by_id(db, comparison_ids)

        for comparison in comparisons:
            db.delete(comparison)
        db.delete(corpus)
        db.commit()

        self.vector_store_service.delete_collection(corpus_id)
        self._delete_files(file_paths)
        self._delete_corpus_upload_directory(corpus_id)

        return CorpusDeletionResult(
            corpus_id=corpus_id,
            deleted=True,
            deleted_file_paths=[str(path) for path in file_paths],
            deleted_comparison_ids=comparison_ids,
        )

    def _get_owned_corpus(
        self,
        db: Session,
        *,
        corpus_id: int,
        owner_id: int,
    ) -> Optional[Corpus]:
        statement = (
            select(Corpus)
            .where(Corpus.id == corpus_id, Corpus.owner_id == owner_id)
            .options(
                selectinload(Corpus.documents).selectinload(Document.pages),
                selectinload(Corpus.documents).selectinload(Document.chunks),
                selectinload(Corpus.chat_messages),
            )
        )
        return db.scalar(statement)

    def _document_file_paths(self, documents: list[Document]) -> list[Path]:
        paths: list[Path] = []
        for document in documents:
            if document.source_path:
                paths.append(Path(document.source_path))
        return paths

    def _comparison_ids_for_documents(
        self,
        db: Session,
        *,
        user_id: int,
        document_ids: list[int],
    ) -> list[int]:
        if not document_ids:
            return []
        statement = (
            select(Comparison.id)
            .join(ComparisonDocument)
            .where(
                Comparison.user_id == user_id,
                ComparisonDocument.document_id.in_(document_ids),
            )
            .distinct()
        )
        return list(db.scalars(statement))

    def _comparisons_by_id(
        self,
        db: Session,
        comparison_ids: list[int],
    ) -> list[Comparison]:
        if not comparison_ids:
            return []
        statement = (
            select(Comparison)
            .where(Comparison.id.in_(comparison_ids))
            .options(
                selectinload(Comparison.documents),
                selectinload(Comparison.result),
                selectinload(Comparison.questions),
            )
        )
        return list(db.scalars(statement))

    def _delete_files(self, file_paths: list[Path]) -> None:
        for file_path in file_paths:
            try:
                if file_path.is_file():
                    file_path.unlink()
            except OSError as error:
                raise RuntimeError(
                    f"Could not delete uploaded file: {file_path}",
                ) from error

    def _delete_corpus_upload_directory(self, corpus_id: int) -> None:
        corpus_upload_dir = self.upload_root / "corpora" / str(corpus_id)
        try:
            if corpus_upload_dir.exists():
                shutil.rmtree(corpus_upload_dir)
        except OSError as error:
            raise RuntimeError(
                f"Could not delete corpus upload directory: {corpus_upload_dir}",
            ) from error
