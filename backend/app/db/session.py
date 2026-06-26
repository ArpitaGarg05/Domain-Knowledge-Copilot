from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine_kwargs = {}

if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {
        "check_same_thread": False
    }

print("DATABASE_URL =", settings.database_url)

engine = create_engine(
    settings.database_url,
    **engine_kwargs,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
