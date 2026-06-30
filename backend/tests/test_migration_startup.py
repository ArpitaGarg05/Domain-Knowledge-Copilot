from types import SimpleNamespace

from sqlalchemy import create_engine, inspect, text

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
