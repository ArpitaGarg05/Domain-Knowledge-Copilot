from types import SimpleNamespace

from app.db import init_db


class ExistingDatabaseInspector:
    def get_table_names(self) -> list[str]:
        return ["alembic_version", "users", "corpora", "documents"]


def test_startup_runs_future_migrations_when_database_is_at_0010(monkeypatch) -> None:
    upgraded_targets: list[str] = []
    stamped_targets: list[str] = []

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

    init_db.run_migrations()

    assert upgraded_targets == ["head"]
    assert stamped_targets == []
