import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

NEON_DATABASE_URL = (
    "postgresql://neondb_owner:npg_yYKDd34lEBNJ@"
    "ep-bitter-resonance-ao1a29h4.c-2.ap-southeast-1.aws.neon.tech/"
    "neondb?sslmode=require"
)


def load_env_file() -> None:
    env_paths = [
        Path(__file__).resolve().parents[3] / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    ]

    for env_path in env_paths:
        if not env_path.exists():
            continue

        for line in env_path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue

            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_env_file()


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    return database_url


class Settings(BaseModel):
    database_url: str = normalize_database_url(
        os.getenv(
            "DATABASE_URL",
            NEON_DATABASE_URL,
        ),
    )
    upload_dir: str = "uploads"
    chroma_dir: str = "chroma"
    groq_api_key: Optional[str] = os.getenv("GROQ_API_KEY")
    groq_model: str = "llama-3.3-70b-versatile"
    embedding_backend: str = os.getenv("EMBEDDING_BACKEND", "hash")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    debug_retrieval: bool = os.getenv("DEBUG_RETRIEVAL", "").lower() in {
        "1",
        "true",
        "yes",
    }
    retrieval_log_chars: int = int(os.getenv("RETRIEVAL_LOG_CHARS", "240"))
    jwt_secret_key: str = os.getenv(
        "JWT_SECRET_KEY",
        "development-only-change-me",
    )
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    app_version: str = os.getenv(
        "APP_VERSION",
        os.getenv("RAILWAY_GIT_COMMIT_SHA", "development"),
    )


settings = Settings()
