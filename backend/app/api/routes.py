from fastapi import APIRouter

from app.schemas.corpus import CorpusCreateRequest, CorpusResponse
from app.schemas.health import HealthResponse
from app.schemas.history import HistoryResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/corpora", response_model=list[CorpusResponse])
def list_corpora() -> list[CorpusResponse]:
    return [
        CorpusResponse(
            id="product-docs",
            name="Product Docs",
            description="Mock corpus for product documentation.",
            document_count=42,
        ),
        CorpusResponse(
            id="research-notes",
            name="Research Notes",
            description="Mock corpus for research notes.",
            document_count=18,
        ),
    ]


@router.post("/corpora", response_model=CorpusResponse)
def create_corpus(request: CorpusCreateRequest) -> CorpusResponse:
    return CorpusResponse(
        id="new-corpus",
        name=request.name,
        description=request.description,
        document_count=0,
    )


@router.get("/history", response_model=HistoryResponse)
def get_history() -> HistoryResponse:
    return HistoryResponse(
        items=[
            "Opened Product Docs corpus",
            "Asked a mock question",
            "Viewed corpus settings",
        ]
    )
