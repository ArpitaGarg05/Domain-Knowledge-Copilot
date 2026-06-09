from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    corpus_id: int
    filename: str
    source_path: str
    uploaded_at: datetime
    page_count: int
    chunk_count: int


class DocumentPageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page_number: int
    text: str


class DocumentChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page_number: int
    chunk_index: int
    text: str
