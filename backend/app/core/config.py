import os

from pydantic import BaseModel


class Settings(BaseModel):
    database_url: str = "sqlite:///./domain_knowledge_copilot.db"
    upload_dir: str = "uploads"
    chroma_dir: str = "chroma"
    groq_api_key: str | None = os.getenv("GROQ_API_KEY")
    groq_model: str = "llama-3.3-70b-versatile"


settings = Settings()
