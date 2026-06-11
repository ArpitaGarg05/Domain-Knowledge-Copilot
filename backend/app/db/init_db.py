from pathlib import Path

from alembic import command
from alembic.config import Config


def run_migrations() -> None:
    backend_dir = Path(__file__).resolve().parents[2]
    alembic_ini = backend_dir / "alembic.ini"

    config = Config(str(alembic_ini))
    command.upgrade(config, "head")
