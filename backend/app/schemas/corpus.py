import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CorpusCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)

    @field_validator("name")
    @classmethod
    def name_must_include_letter(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value):
            raise ValueError("Corpus name must contain at least one letter.")
        return value


class CorpusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    document_count: int
    total_storage_bytes: int = 0
    updated_at: Optional[datetime] = None


class CorpusDeleteResponse(BaseModel):
    id: int
    deleted: bool
