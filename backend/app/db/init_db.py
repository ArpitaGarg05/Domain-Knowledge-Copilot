import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.models import chat_message, comparison, corpus, document, user

logger = logging.getLogger(__name__)


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
        logger.info("Fresh database schema created and stamped at Alembic head.")
        return

    logger.info("Running Alembic migrations.")
    try:
        command.upgrade(config, "head")
    except Exception:
        logger.exception("Alembic migration failed.")
        raise
    logger.info("Alembic migrations complete.")
