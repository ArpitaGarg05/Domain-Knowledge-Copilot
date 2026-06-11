from pathlib import Path

from alembic import command
from alembic.config import Config


def run_migrations() -> None:
    backend_dir = Path(__file__).resolve().parents[2]
    alembic_ini = backend_dir / "alembic.ini"

    print(f"backend_dir={backend_dir}")
    print(f"alembic_ini={alembic_ini}")
    print("RUNNING ALEMBIC MIGRATIONS")

    config = Config(str(alembic_ini))
    command.upgrade(config, "head")

    print("ALEMBIC MIGRATIONS COMPLETE")