from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ComparisonCreateRequest(BaseModel):
    document_ids: list[int] = Field(min_length=2, max_length=12)


class ComparedDocumentResponse(BaseModel):
    id: int
    filename: str
    corpus_id: int
    corpus_name: str


class ComparisonStructuredResponse(BaseModel):
    common_topics: list[str] = Field(default_factory=list)
    unique_topics: dict[str, list[str]] = Field(default_factory=dict)
    major_differences: list[str] = Field(default_factory=list)
    missing_concepts: dict[str, list[str]] = Field(default_factory=dict)
    beginner_document: str = ""
    most_comprehensive_document: str = ""
    recommendation: str = ""


class ComparisonCreateResponse(ComparisonStructuredResponse):
    comparison_id: int
    overall_summary: str


class ComparisonListItemResponse(BaseModel):
    id: int
    title: str
    overall_summary: str
    document_count: int
    documents: list[ComparedDocumentResponse]
    created_at: datetime


class ComparisonListResponse(BaseModel):
    comparisons: list[ComparisonListItemResponse]


class ComparisonDetailResponse(ComparisonCreateResponse):
    id: int
    title: str
    documents: list[ComparedDocumentResponse]
    comparison_json: dict[str, Any]
    created_at: datetime
