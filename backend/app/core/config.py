from pydantic import BaseModel


class Settings(BaseModel):
    database_url: str = "sqlite:///./domain_knowledge_copilot.db"
    upload_dir: str = "uploads"
    chroma_dir: str = "chroma"


settings = Settings()
