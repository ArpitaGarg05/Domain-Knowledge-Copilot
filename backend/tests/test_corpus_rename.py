from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.db.base import Base
from app.models.corpus import Corpus
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


def seed_corpora(session_local: sessionmaker) -> None:
    with session_local() as db:
        owner = User(
            id=1,
            email="owner@example.com",
            display_name="Owner",
            password_hash="hash",
        )
        other = User(
            id=2,
            email="other@example.com",
            display_name="Other",
            password_hash="hash",
        )
        db.add_all(
            [
                owner,
                other,
                Corpus(
                    id=1,
                    name="Research Notes",
                    description="Primary corpus",
                    owner_id=1,
                ),
                Corpus(
                    id=2,
                    name="AI Notes",
                    description="Duplicate candidate",
                    owner_id=1,
                ),
                Corpus(
                    id=3,
                    name="Other User Corpus",
                    description="Forbidden corpus",
                    owner_id=2,
                ),
            ]
        )
        db.commit()


def test_rename_corpus_successfully_updates_name_only() -> None:
    client, session_local = build_test_client()
    seed_corpora(session_local)

    response = client.patch("/api/corpora/1", json={"name": "ML Research"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 1
    assert payload["name"] == "ML Research"
    assert payload["description"] == "Primary corpus"
    with session_local() as db:
        corpus = db.get(Corpus, 1)
        assert corpus.name == "ML Research"
        assert corpus.description == "Primary corpus"


def test_rename_corpus_to_same_name_is_allowed() -> None:
    client, session_local = build_test_client()
    seed_corpora(session_local)

    response = client.patch("/api/corpora/1", json={"name": "Research Notes"})

    assert response.status_code == 200
    assert response.json()["name"] == "Research Notes"


def test_rename_corpus_rejects_duplicate_name_for_same_user() -> None:
    client, session_local = build_test_client()
    seed_corpora(session_local)

    response = client.patch("/api/corpora/1", json={"name": "ai notes"})

    assert response.status_code == 409
    assert response.json()["detail"] == "A corpus with this name already exists."


def test_rename_corpus_rejects_invalid_names() -> None:
    client, session_local = build_test_client()
    seed_corpora(session_local)

    invalid_names = [
        "",
        "   ",
        "12345",
        "ab",
        "x" * 101,
        "---",
    ]

    for name in invalid_names:
        response = client.patch("/api/corpora/1", json={"name": name})
        assert response.status_code == 400


def test_rename_corpus_rejects_other_users_corpus() -> None:
    client, session_local = build_test_client()
    seed_corpora(session_local)

    response = client.patch("/api/corpora/3", json={"name": "New Name"})

    assert response.status_code == 403


def test_rename_corpus_requires_authentication() -> None:
    client, session_local = build_test_client()
    seed_corpora(session_local)

    def unauthenticated_user():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication token.",
        )

    client.app.dependency_overrides[routes.get_current_user] = unauthenticated_user

    response = client.patch("/api/corpora/1", json={"name": "New Name"})

    assert response.status_code == 401


def test_rename_corpus_returns_404_for_missing_id() -> None:
    client, session_local = build_test_client()
    seed_corpora(session_local)

    response = client.patch("/api/corpora/999", json={"name": "New Name"})

    assert response.status_code == 404
