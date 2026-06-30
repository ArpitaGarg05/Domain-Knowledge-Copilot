import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

CORPUS_NAME_MIN_LENGTH = 3
CORPUS_NAME_MAX_LENGTH = 100


def normalize_corpus_name(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Corpus name is required.")
    if len(normalized) < CORPUS_NAME_MIN_LENGTH:
        raise ValueError(
            f"Corpus name must be at least {CORPUS_NAME_MIN_LENGTH} characters.",
        )
    if len(normalized) > CORPUS_NAME_MAX_LENGTH:
        raise ValueError(
            f"Corpus name must be at most {CORPUS_NAME_MAX_LENGTH} characters.",
        )
    if not re.search(r"[A-Za-z]", normalized):
        raise ValueError("Corpus name must contain at least one letter.")
    return normalized


class CorpusCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=CORPUS_NAME_MAX_LENGTH)
    description: str = Field(default="", max_length=2000)

    @field_validator("name")
    @classmethod
    def name_must_be_valid(cls, value: str) -> str:
        return normalize_corpus_name(value)


class CorpusUpdateRequest(BaseModel):
    name: str = ""


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
    message: str = "Corpus permanently deleted."
    deleted_files: int = 0
    deleted_comparisons: int = 0
