from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.db.base import Base
from app.models.chat_message import ChatMessage
from app.models.comparison import (
    Comparison,
    ComparisonDocument,
    ComparisonQuestion,
    ComparisonResult,
)
from app.models.corpus import Corpus
from app.models.document import ChunkEmbedding, Document, DocumentChunk, DocumentPage
from app.models.user import User
from app.services.corpus_deletion_service import CorpusDeletionService


class FakeVectorStore:
    def __init__(self) -> None:
        self.deleted_collections: list[int] = []

    def delete_collection(self, corpus_id: int) -> None:
        self.deleted_collections.append(corpus_id)


def build_test_client(tmp_path: Path) -> tuple[TestClient, sessionmaker, FakeVectorStore]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    fake_vector_store = FakeVectorStore()
    upload_root = tmp_path / "uploads"

    app = FastAPI()
    app.include_router(routes.router)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    def override_get_current_user():
        db = testing_session_local()
        try:
            return db.get(User, 1)
        finally:
            db.close()

    def deletion_service_factory():
        return CorpusDeletionService(
            vector_store_service=fake_vector_store,
            upload_root=str(upload_root),
        )

    app.dependency_overrides[routes.get_db] = override_get_db
    app.dependency_overrides[routes.get_current_user] = override_get_current_user
    routes.CorpusDeletionService = deletion_service_factory
    return TestClient(app), testing_session_local, fake_vector_store


def seed_corpus_with_dependents(
    session_local: sessionmaker,
    tmp_path: Path,
) -> Path:
    upload_dir = tmp_path / "uploads" / "corpora" / "1"
    upload_dir.mkdir(parents=True)
    uploaded_file = upload_dir / "document.pdf"
    uploaded_file.write_bytes(b"%PDF-1.4 test")

    with Session(session_local.kw["bind"]) as db:
        user = User(
            id=1,
            email="owner@example.com",
            display_name="Owner",
            password_hash="hash",
        )
        other_user = User(
            id=2,
            email="other@example.com",
            display_name="Other",
            password_hash="hash",
        )
        corpus = Corpus(
            id=1,
            name="Research Notes",
            description="Owned corpus",
            owner_id=1,
        )
        document = Document(
            id=1,
            corpus=corpus,
            title="document.pdf",
            filename="document.pdf",
            source_path=str(uploaded_file),
            content_preview="Preview",
            page_count=1,
        )
        page = DocumentPage(document=document, page_number=1, text="Page text")
        chunk = DocumentChunk(
            document=document,
            page_number=1,
            chunk_index=0,
            text="Chunk text",
        )
        embedding = ChunkEmbedding(
            chunk=chunk,
            model_name="hash",
            vector_dimension=3,
            vector="[0.1, 0.2, 0.3]",
        )
        chat_message = ChatMessage(
            corpus=corpus,
            user=user,
            conversation_id="conversation-1",
            role="assistant",
            content="Answer",
            citations="[]",
        )
        comparison = Comparison(
            id=1,
            user=user,
            title="document.pdf comparison",
            documents=[ComparisonDocument(document=document)],
            result=ComparisonResult(
                overall_summary="Summary",
                comparison_json='{"overall_summary": "Summary"}',
            ),
            questions=[
                ComparisonQuestion(
                    question="Question",
                    answer="Answer",
                    supporting_documents="[]",
                    referenced_sections="[]",
                    confidence="medium",
                )
            ],
        )
        db.add_all(
            [
                user,
                other_user,
                corpus,
                document,
                page,
                chunk,
                embedding,
                chat_message,
                comparison,
            ]
        )
        db.commit()
    return uploaded_file


def test_delete_corpus_removes_database_files_and_vectors(tmp_path: Path) -> None:
    client, session_local, fake_vector_store = build_test_client(tmp_path)
    uploaded_file = seed_corpus_with_dependents(session_local, tmp_path)

    response = client.delete("/api/corpora/1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["deleted"] is True
    assert payload["deleted_files"] == 1
    assert payload["deleted_comparisons"] == 1
    assert uploaded_file.exists() is False
    assert (tmp_path / "uploads" / "corpora" / "1").exists() is False
    assert fake_vector_store.deleted_collections == [1]

    with session_local() as db:
        assert db.get(Corpus, 1) is None
        assert db.get(Document, 1) is None
        assert db.query(DocumentPage).count() == 0
        assert db.query(DocumentChunk).count() == 0
        assert db.query(ChunkEmbedding).count() == 0
        assert db.query(ChatMessage).count() == 0
        assert db.query(Comparison).count() == 0
        assert db.query(ComparisonResult).count() == 0
        assert db.query(ComparisonQuestion).count() == 0


def test_delete_corpus_rejects_unauthorized_user(tmp_path: Path) -> None:
    client, session_local, fake_vector_store = build_test_client(tmp_path)
    uploaded_file = seed_corpus_with_dependents(session_local, tmp_path)

    def override_other_user():
        with session_local() as db:
            return db.get(User, 2)

    client.app.dependency_overrides[routes.get_current_user] = override_other_user

    response = client.delete("/api/corpora/1")

    assert response.status_code == 404
    assert uploaded_file.exists() is True
    assert fake_vector_store.deleted_collections == []
    with session_local() as db:
        assert db.get(Corpus, 1) is not None
        assert db.get(Document, 1) is not None


def test_delete_corpus_returns_404_for_missing_id(tmp_path: Path) -> None:
    client, session_local, fake_vector_store = build_test_client(tmp_path)
    seed_corpus_with_dependents(session_local, tmp_path)

    response = client.delete("/api/corpora/999")

    assert response.status_code == 404
    assert fake_vector_store.deleted_collections == []


def test_delete_corpus_legacy_route_still_works(tmp_path: Path) -> None:
    client, session_local, fake_vector_store = build_test_client(tmp_path)
    uploaded_file = seed_corpus_with_dependents(session_local, tmp_path)

    response = client.delete("/corpora/1")

    assert response.status_code == 200
    assert uploaded_file.exists() is False
    assert fake_vector_store.deleted_collections == [1]
