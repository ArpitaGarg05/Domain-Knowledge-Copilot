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
    embedding_count: int
    file_size_bytes: int


class DocumentSummaryResponse(DocumentResponse):
    indexing_status: str


class CorpusDocumentListResponse(BaseModel):
    corpus_id: int
    documents: list[DocumentSummaryResponse]
    total_documents: int
    total_pages: int
    total_chunks: int
    total_embeddings: int
    total_storage_bytes: int


class DocumentPageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page_number: int
    text: str


class DocumentChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page_number: int
    chunk_index: int
    text: str
