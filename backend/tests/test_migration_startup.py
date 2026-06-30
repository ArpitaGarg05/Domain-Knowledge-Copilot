from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.db import init_db


class ExistingDatabaseInspector:
    def get_table_names(self) -> list[str]:
        return ["alembic_version", "users", "corpora", "documents"]


def test_startup_runs_future_migrations_when_database_is_at_0010(monkeypatch) -> None:
    upgraded_targets: list[str] = []
    stamped_targets: list[str] = []
    ensured_columns: list[bool] = []

    monkeypatch.setattr(init_db, "inspect", lambda engine: ExistingDatabaseInspector())
    monkeypatch.setattr(
        init_db,
        "engine",
        SimpleNamespace(dialect=SimpleNamespace(name="sqlite")),
    )
    monkeypatch.setattr(
        init_db,
        "get_current_revision",
        lambda: "0010_add_comparison_questions",
    )
    monkeypatch.setattr(
        init_db.command,
        "upgrade",
        lambda config, target: upgraded_targets.append(target),
    )
    monkeypatch.setattr(
        init_db.command,
        "stamp",
        lambda config, target: stamped_targets.append(target),
    )
    monkeypatch.setattr(
        init_db,
        "ensure_document_file_size_column",
        lambda connection=None: ensured_columns.append(True),
    )

    init_db.run_migrations()

    assert upgraded_targets == ["head"]
    assert stamped_targets == []
    assert ensured_columns == [True]


def test_startup_schema_guard_adds_missing_document_file_size_column() -> None:
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE documents ("
                "id INTEGER PRIMARY KEY, "
                "filename VARCHAR(255)"
                ")",
            ),
        )
        connection.execute(
            text("INSERT INTO documents (id, filename) VALUES (1, 'resume.pdf')"),
        )

        init_db.ensure_document_file_size_column(connection)

        columns = {
            column["name"]
            for column in inspect(connection).get_columns("documents")
        }
        stored_size = connection.execute(
            text("SELECT file_size_bytes FROM documents WHERE id = 1"),
        ).scalar_one()

    assert "file_size_bytes" in columns
    assert stored_size == 0


def test_corpus_listing_tolerates_missing_document_file_size_column() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE corpora ("
                "id INTEGER PRIMARY KEY, "
                "name VARCHAR(255), "
                "description TEXT DEFAULT '', "
                "owner_id INTEGER, "
                "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"
                ")",
            ),
        )
        connection.execute(
            text(
                "CREATE TABLE documents ("
                "id INTEGER PRIMARY KEY, "
                "corpus_id INTEGER, "
                "title VARCHAR(255), "
                "filename VARCHAR(255), "
                "source_path VARCHAR(500), "
                "content_preview TEXT DEFAULT '', "
                "page_count INTEGER DEFAULT 0, "
                "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
                "uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP"
                ")",
            ),
        )
        connection.execute(
            text(
                "INSERT INTO corpora (id, name, description, owner_id) "
                "VALUES (1, 'Legacy Corpus', 'Missing new document column', 1)",
            ),
        )
        connection.execute(
            text(
                "INSERT INTO documents (id, corpus_id, title, filename) "
                "VALUES (1, 1, 'resume.pdf', 'resume.pdf')",
            ),
        )

    app = FastAPI()
    app.include_router(routes.router)

    def override_get_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[routes.get_db] = override_get_db
    app.dependency_overrides[routes.get_current_user] = lambda: SimpleNamespace(id=1)

    response = TestClient(app).get("/corpora")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == 1
    assert payload[0]["name"] == "Legacy Corpus"
    assert payload[0]["description"] == "Missing new document column"
    assert payload[0]["document_count"] == 1
    assert payload[0]["total_storage_bytes"] == 0
