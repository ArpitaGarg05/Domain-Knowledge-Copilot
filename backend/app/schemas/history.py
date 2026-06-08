from pydantic import BaseModel


class HistoryResponse(BaseModel):
    items: list[str]
