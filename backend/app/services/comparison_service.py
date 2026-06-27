import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app.models.document import Document
from app.services.llm_service import LLMGenerationError, LLMService
from app.services.pdf_processor import extract_pdf_text


class ComparisonValidationError(ValueError):
    pass


@dataclass(frozen=True)
class DocumentComparisonInput:
    id: int
    filename: str
    text: str


@dataclass(frozen=True)
class DocumentSummary:
    document_id: int
    filename: str
    summary: str


@dataclass(frozen=True)
class GeneratedComparison:
    title: str
    overall_summary: str
    comparison_json: dict[str, Any]
    summaries: list[DocumentSummary]


class ComparisonService:
    max_document_chars = 24000

    def __init__(self, llm_service: Optional[LLMService] = None) -> None:
        self.llm_service = llm_service or LLMService()

    def compare_documents(self, documents: list[Document]) -> GeneratedComparison:
        if len(documents) < 2:
            raise ComparisonValidationError(
                "Select at least two documents to compare.",
            )

        inputs = [self._build_input(document) for document in documents]
        empty_documents = [
            document.filename for document in inputs if not document.text.strip()
        ]
        if empty_documents:
            raise ComparisonValidationError(
                "Could not find extractable text for: " + ", ".join(empty_documents),
            )

        summaries = [
            DocumentSummary(
                document_id=document.id,
                filename=document.filename,
                summary=self.llm_service.generate_document_summary(
                    filename=document.filename,
                    text=document.text[: self.max_document_chars],
                ),
            )
            for document in inputs
        ]
        raw_comparison = self.llm_service.generate_document_comparison(summaries)
        comparison_json = self._normalize_comparison_json(
            self._parse_json_response(raw_comparison),
            summaries,
        )
        return GeneratedComparison(
            title=self._build_title(summaries),
            overall_summary=str(comparison_json["overall_summary"]),
            comparison_json=comparison_json,
            summaries=summaries,
        )

    def _build_input(self, document: Document) -> DocumentComparisonInput:
        page_text = "\n\n".join(
            page.text.strip() for page in document.pages if page.text.strip()
        )
        if not page_text and document.source_path:
            source_path = Path(document.source_path)
            if source_path.exists():
                page_text = "\n\n".join(
                    page.text.strip()
                    for page in extract_pdf_text(source_path)
                    if page.text.strip()
                )

        return DocumentComparisonInput(
            id=document.id,
            filename=document.filename,
            text=page_text,
        )

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        stripped = response.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
            stripped = re.sub(r"\s*```$", "", stripped)

        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as error:
            raise LLMGenerationError("The comparison model returned invalid JSON.") from error

        if not isinstance(parsed, dict):
            raise LLMGenerationError("The comparison model returned a non-object JSON value.")
        return parsed

    def _normalize_comparison_json(
        self,
        parsed: dict[str, Any],
        summaries: list[DocumentSummary],
    ) -> dict[str, Any]:
        filenames = [summary.filename for summary in summaries]

        return {
            "overall_summary": self._string_value(parsed, "overall_summary"),
            "common_topics": self._list_value(parsed, "common_topics"),
            "unique_topics": self._document_map_value(
                parsed.get("unique_topics"),
                filenames,
            ),
            "major_differences": self._list_value(parsed, "major_differences"),
            "missing_concepts": self._document_map_value(
                parsed.get("missing_concepts"),
                filenames,
            ),
            "beginner_document": self._string_value(parsed, "beginner_document"),
            "most_comprehensive_document": self._string_value(
                parsed,
                "most_comprehensive_document",
            ),
            "recommendation": self._string_value(parsed, "recommendation"),
            "document_summaries": {
                summary.filename: summary.summary for summary in summaries
            },
        }

    def _string_value(self, parsed: dict[str, Any], key: str) -> str:
        value = parsed.get(key, "")
        return value.strip() if isinstance(value, str) else ""

    def _list_value(self, parsed: dict[str, Any], key: str) -> list[str]:
        value = parsed.get(key, [])
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _document_map_value(
        self,
        value: Any,
        filenames: list[str],
    ) -> dict[str, list[str]]:
        if not isinstance(value, dict):
            return {filename: [] for filename in filenames}
        normalized: dict[str, list[str]] = {}
        for filename in filenames:
            topics = value.get(filename, [])
            if not isinstance(topics, list):
                topics = []
            normalized[filename] = [
                str(topic).strip() for topic in topics if str(topic).strip()
            ]
        for key, topics in value.items():
            if key in normalized:
                continue
            if isinstance(topics, list):
                normalized[str(key)] = [
                    str(topic).strip() for topic in topics if str(topic).strip()
                ]
        return normalized

    def _build_title(self, summaries: list[DocumentSummary]) -> str:
        first_two = " vs ".join(summary.filename for summary in summaries[:2])
        suffix = f" +{len(summaries) - 2}" if len(summaries) > 2 else ""
        return f"{first_two}{suffix}"[:255]
