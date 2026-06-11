import os
from typing import Optional

from pydantic import BaseModel


class Settings(BaseModel):
    database_url: str = "sqlite:///./domain_knowledge_copilot.db"
    upload_dir: str = "uploads"
    chroma_dir: str = "chroma"
    groq_api_key: Optional[str] = os.getenv("GROQ_API_KEY")
    groq_model: str = "llama-3.3-70b-versatile"
    embedding_backend: str = os.getenv("EMBEDDING_BACKEND", "hash")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    jwt_secret_key: str = os.getenv(
        "JWT_SECRET_KEY",
        "development-only-change-me",
    )
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24


settings = Settings()
