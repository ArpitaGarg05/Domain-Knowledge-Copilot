from pydantic import BaseModel


class CorpusCreateRequest(BaseModel):
    name: str
    description: str = ""


class CorpusResponse(BaseModel):
    id: str
    name: str
    description: str
    document_count: int
