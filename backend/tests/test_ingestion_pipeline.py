from io import BytesIO
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.db.base import Base
from app.models.corpus import Corpus
from app.models.user import User
from app.services.vector_store_service import VectorStoreService


RESUME_TEXT = (
    "Ayushman is a backend engineer. "
    "Ayushman's skills include Python, Django, PostgreSQL, FastAPI, "
    "React, AI systems, and SaaS product development. "
    "Ayushman has built document search and knowledge copilot applications."
)


def build_test_client(
    tmp_path: Path,
    monkeypatch,
) -> tuple[TestClient, sessionmaker]:
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

    vector_dir = tmp_path / "chroma"
    monkeypatch.setattr(routes.settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(
        routes,
        "VectorStoreService",
        lambda: VectorStoreService(persist_directory=str(vector_dir)),
    )

    app.dependency_overrides[routes.get_db] = override_get_db
    app.dependency_overrides[routes.get_current_user] = override_get_current_user
    return TestClient(app), testing_session_local


def create_pdf_bytes(text: str) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    content = DecodedStreamObject()
    escaped_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content.set_data(f"BT /F1 12 Tf 72 720 Td ({escaped_text}) Tj ET".encode("utf-8"))
    page[NameObject("/Contents")] = content

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def seed_user_and_corpus(session_local: sessionmaker) -> None:
    with session_local() as db:
        db.add_all(
            [
                User(
                    id=1,
                    email="owner@example.com",
                    display_name="Owner",
                    password_hash="hash",
                ),
                Corpus(
                    id=1,
                    name="Resume Corpus",
                    description="Uploaded resumes",
                    owner_id=1,
                ),
            ]
        )
        db.commit()


def upload_resume_pdf(client: TestClient, pdf_bytes: bytes):
    return client.post(
        "/corpora/1/upload",
        files={
            "file": (
                "ayushman_resume.pdf",
                pdf_bytes,
                "application/pdf",
            )
        },
    )


def test_upload_persists_file_size_and_storage_totals(tmp_path: Path, monkeypatch) -> None:
    client, session_local = build_test_client(tmp_path, monkeypatch)
    seed_user_and_corpus(session_local)
    pdf_bytes = create_pdf_bytes(RESUME_TEXT)

    upload_response = upload_resume_pdf(client, pdf_bytes)

    assert upload_response.status_code == 201
    assert upload_response.json()["file_size_bytes"] == len(pdf_bytes)

    corpora_response = client.get("/corpora")
    assert corpora_response.status_code == 200
    assert corpora_response.json()[0]["total_storage_bytes"] == len(pdf_bytes)

    documents_response = client.get("/corpora/1/documents")
    assert documents_response.status_code == 200
    payload = documents_response.json()
    assert payload["total_storage_bytes"] == len(pdf_bytes)
    assert payload["documents"][0]["file_size_bytes"] == len(pdf_bytes)


def test_uploaded_resume_is_indexed_and_searchable(tmp_path: Path, monkeypatch) -> None:
    client, session_local = build_test_client(tmp_path, monkeypatch)
    seed_user_and_corpus(session_local)
    upload_response = upload_resume_pdf(client, create_pdf_bytes(RESUME_TEXT))

    assert upload_response.status_code == 201
    uploaded_document = upload_response.json()
    assert uploaded_document["chunk_count"] > 0
    assert uploaded_document["embedding_count"] == uploaded_document["chunk_count"]

    questions = [
        "Who is Ayushman?",
        "What are Ayushman's skills?",
        "Summarize Ayushman's resume",
    ]
    for question in questions:
        response = client.post(
            "/search",
            json={"corpus_id": 1, "question": question, "limit": 5},
        )
        assert response.status_code == 200
        results = response.json()
        assert results
        assert any("Ayushman" in result["text"] for result in results)
        assert any(result["filename"] == "ayushman_resume.pdf" for result in results)
