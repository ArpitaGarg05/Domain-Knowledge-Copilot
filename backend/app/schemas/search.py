from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    corpus_id: int
    question: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)


class RetrievedChunkResponse(BaseModel):
    chunk_id: int
    document_id: int
    corpus_id: int
    page_number: int
    chunk_index: int
    text: str
    distance: float | None


class AnswerRequest(SearchRequest):
    pass


class AnswerResponse(BaseModel):
    answer: str
    sources: list[RetrievedChunkResponse]
