from pydantic import BaseModel


class Settings(BaseModel):
    database_url: str = "sqlite:///./domain_knowledge_copilot.db"


settings = Settings()
