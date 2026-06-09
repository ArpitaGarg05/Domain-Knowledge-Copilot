from pydantic import BaseModel, ConfigDict, Field


class CorpusCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)


class CorpusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    document_count: int


class CorpusDeleteResponse(BaseModel):
    id: int
    deleted: bool
