from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.db.base import Base
from app.models.corpus import Corpus
from app.models.document import Document
from app.models.user import User


def build_test_client() -> tuple[TestClient, sessionmaker]:
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

    app = FastAPI()
    app.include_router(routes.router)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    def override_get_current_user():
        with testing_session_local() as db:
            return db.get(User, 1)

    app.dependency_overrides[routes.get_db] = override_get_db
    app.dependency_overrides[routes.get_current_user] = override_get_current_user
    return TestClient(app), testing_session_local


def seed_preview_data(
    session_local: sessionmaker,
    tmp_path: Path,
    *,
    content: bytes = b"%PDF-1.4\npreview\n%%EOF",
) -> Path:
    pdf_path = tmp_path / "uploaded.pdf"
    pdf_path.write_bytes(content)
    with session_local() as db:
        db.add_all(
            [
                User(
                    id=1,
                    email="owner@example.com",
                    display_name="Owner",
                    password_hash="hash",
                ),
                User(
                    id=2,
                    email="other@example.com",
                    display_name="Other",
                    password_hash="hash",
                ),
                Corpus(
                    id=1,
                    name="Preview Corpus",
                    description="Owned",
                    owner_id=1,
                ),
                Corpus(
                    id=2,
                    name="Other Corpus",
                    description="Forbidden",
                    owner_id=2,
                ),
                Document(
                    id=1,
                    corpus_id=1,
                    title="uploaded.pdf",
                    filename="uploaded.pdf",
                    source_path=str(pdf_path),
                    content_preview="preview",
                    page_count=3,
                ),
                Document(
                    id=2,
                    corpus_id=2,
                    title="other.pdf",
                    filename="other.pdf",
                    source_path=str(pdf_path),
                    content_preview="preview",
                    page_count=1,
                ),
                Document(
                    id=3,
                    corpus_id=1,
                    title="missing.pdf",
                    filename="missing.pdf",
                    source_path=str(tmp_path / "missing.pdf"),
                    content_preview="missing",
                    page_count=1,
                ),
            ]
        )
        db.commit()
    return pdf_path


def test_preview_document_streams_pdf_for_owner(tmp_path: Path) -> None:
    client, session_local = build_test_client()
    pdf_path = seed_preview_data(session_local, tmp_path)

    response = client.get("/api/corpora/1/documents/1/preview")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["accept-ranges"] == "bytes"
    assert "inline" in response.headers["content-disposition"]
    assert response.content == pdf_path.read_bytes()


def test_preview_document_supports_large_pdf_range_when_available(tmp_path: Path) -> None:
    client, session_local = build_test_client()
    content = b"%PDF-1.4\n" + (b"0" * 250_000) + b"\n%%EOF"
    seed_preview_data(session_local, tmp_path, content=content)

    response = client.get(
        "/api/corpora/1/documents/1/preview",
        headers={"Range": "bytes=0-99"},
    )

    assert response.status_code in {200, 206}
    if response.status_code == 206:
        assert response.content == content[:100]
        assert response.headers["content-range"].startswith("bytes 0-99/")
    else:
        assert response.content == content


def test_preview_document_rejects_other_users_corpus(tmp_path: Path) -> None:
    client, session_local = build_test_client()
    seed_preview_data(session_local, tmp_path)

    response = client.get("/api/corpora/2/documents/2/preview")

    assert response.status_code == 403


def test_preview_document_requires_authentication(tmp_path: Path) -> None:
    client, session_local = build_test_client()
    seed_preview_data(session_local, tmp_path)

    def unauthenticated_user():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication token.",
        )

    client.app.dependency_overrides[routes.get_current_user] = unauthenticated_user

    response = client.get("/api/corpora/1/documents/1/preview")

    assert response.status_code == 401


def test_preview_document_returns_404_for_missing_document(tmp_path: Path) -> None:
    client, session_local = build_test_client()
    seed_preview_data(session_local, tmp_path)

    response = client.get("/api/corpora/1/documents/999/preview")

    assert response.status_code == 404


def test_preview_document_returns_404_for_missing_pdf_file(tmp_path: Path) -> None:
    client, session_local = build_test_client()
    seed_preview_data(session_local, tmp_path)

    response = client.get("/api/corpora/1/documents/3/preview")

    assert response.status_code == 404
