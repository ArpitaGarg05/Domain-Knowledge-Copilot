import logging
from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, inspect, text

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.models import chat_message, comparison, corpus, document, user

logger = logging.getLogger(__name__)


DOCUMENT_FILE_SIZE_COLUMN = "file_size_bytes"


def run_migrations() -> None:
    backend_dir = Path(__file__).resolve().parents[2]
    alembic_ini = backend_dir / "alembic.ini"

    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    is_fresh_database = "alembic_version" not in existing_tables

    if is_fresh_database:
        logger.info("Creating schema for a fresh database.")
        Base.metadata.create_all(bind=engine)
        command.stamp(config, "head")
        ensure_document_file_size_column()
        logger.info("Fresh database schema created and stamped at Alembic head.")
        return

    logger.info("Running Alembic migrations.")
    if engine.dialect.name == "postgresql":
        with engine.connect() as connection:
            connection.execute(text("SELECT pg_advisory_lock(73421491)"))
            connection.commit()
            try:
                command.upgrade(config, "head")
                ensure_document_file_size_column(connection)
                connection.commit()
            except Exception:
                connection.rollback()
                logger.exception("Alembic migration failed.")
                raise
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(73421491)"))
                connection.commit()
        logger.info("Alembic migrations complete.")
        return

    try:
        command.upgrade(config, "head")
        ensure_document_file_size_column()
    except Exception:
        logger.exception("Alembic migration failed.")
        raise
    logger.info("Alembic migrations complete.")


def get_current_revision() -> Optional[str]:
    try:
        with engine.connect() as connection:
            return connection.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1"),
            ).scalar_one_or_none()
    except Exception:
        logger.exception("Could not read current Alembic revision.")
        return None


def ensure_document_file_size_column(connection: Optional[Connection] = None) -> None:
    """Keep production bootable if Alembic was stamped ahead of physical schema."""

    if connection is None:
        with engine.begin() as managed_connection:
            ensure_document_file_size_column(managed_connection)
        return

    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    if "documents" not in existing_tables:
        return

    document_columns = {
        column["name"]
        for column in inspector.get_columns("documents")
    }
    if DOCUMENT_FILE_SIZE_COLUMN in document_columns:
        return

    logger.warning(
        "documents.%s is missing after migrations; adding compatibility column.",
        DOCUMENT_FILE_SIZE_COLUMN,
    )
    connection.execute(
        text(
            "ALTER TABLE documents "
            "ADD COLUMN file_size_bytes INTEGER NOT NULL DEFAULT 0",
        ),
    )
