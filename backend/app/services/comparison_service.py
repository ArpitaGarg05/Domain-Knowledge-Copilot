import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app.models.document import Document
from app.services.llm_service import LLMGenerationError, LLMService
from app.services.pdf_processor import extract_pdf_text
from app.services.vector_store_service import RetrievalResult, VectorStoreService


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


@dataclass(frozen=True)
class GeneratedComparisonAnswer:
    answer: str
    supporting_documents: list[str]
    referenced_sections: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    confidence: str
    retrieved_chunks: list[RetrievalResult]


class ComparisonService:
    max_document_chars = 24000

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        vector_store_service: Optional[VectorStoreService] = None,
    ) -> None:
        self.llm_service = llm_service or LLMService()
        self.vector_store_service = vector_store_service or VectorStoreService()

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
        comparison_json["evidence"] = self._build_comparison_evidence(
            comparison_json=comparison_json,
            documents=documents,
        )
        return GeneratedComparison(
            title=self._build_title(summaries),
            overall_summary=str(comparison_json["overall_summary"]),
            comparison_json=comparison_json,
            summaries=summaries,
        )

    def answer_question(
        self,
        *,
        question: str,
        documents: list[Document],
        limit_per_document: int = 3,
    ) -> GeneratedComparisonAnswer:
        if len(documents) < 2:
            raise ComparisonValidationError(
                "A comparison needs at least two documents before questions can be answered.",
            )

        documents_by_corpus: dict[int, list[int]] = {}
        for document in documents:
            documents_by_corpus.setdefault(document.corpus_id, []).append(document.id)

        retrieved_chunks = self.vector_store_service.retrieve_by_text_for_documents(
            documents_by_corpus=documents_by_corpus,
            query_text=question,
            limit_per_document=limit_per_document,
        )
        if not retrieved_chunks:
            return GeneratedComparisonAnswer(
                answer=(
                    "I could not find enough retrieved context in the compared "
                    "documents to answer this question."
                ),
                supporting_documents=[],
                referenced_sections=[],
                evidence=[],
                confidence="low",
                retrieved_chunks=[],
            )

        grouped_context = self._group_chunks_for_prompt(documents, retrieved_chunks)
        raw_answer = self.llm_service.generate_comparison_answer(
            question=question,
            grouped_context=grouped_context,
        )
        parsed = self._parse_json_response(raw_answer)
        chunk_lookup = {
            (chunk.filename, chunk.chunk_reference): chunk
            for chunk in retrieved_chunks
        }
        referenced_sections = self._normalize_referenced_sections(
            parsed.get("referenced_sections"),
            chunk_lookup,
            retrieved_chunks,
        )
        answer = self._string_value(parsed, "answer")
        return GeneratedComparisonAnswer(
            answer=answer,
            supporting_documents=self._list_value(parsed, "supporting_documents"),
            referenced_sections=referenced_sections,
            evidence=self._build_answer_evidence(answer, retrieved_chunks),
            confidence=self._normalize_confidence(parsed.get("confidence")),
            retrieved_chunks=retrieved_chunks,
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

    def _group_chunks_for_prompt(
        self,
        documents: list[Document],
        chunks: list[RetrievalResult],
    ) -> dict[str, list[RetrievalResult]]:
        chunks_by_document: dict[int, list[RetrievalResult]] = {}
        for chunk in chunks:
            chunks_by_document.setdefault(chunk.document_id, []).append(chunk)

        labels: dict[int, str] = {}
        for index, document in enumerate(documents):
            suffix = chr(ord("A") + index)
            labels[document.id] = f"Document {suffix}: {document.filename}"

        return {
            labels[document.id]: chunks_by_document.get(document.id, [])
            for document in documents
        }

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

    def _build_comparison_evidence(
        self,
        *,
        comparison_json: dict[str, Any],
        documents: list[Document],
    ) -> list[dict[str, Any]]:
        statements = self._collect_comparison_statements(comparison_json)
        if not statements:
            return []

        documents_by_corpus: dict[int, list[int]] = {}
        for document in documents:
            documents_by_corpus.setdefault(document.corpus_id, []).append(document.id)

        evidence_chunks = self.vector_store_service.retrieve_evidence_for_texts(
            documents_by_corpus=documents_by_corpus,
            texts=statements,
            limit_per_statement=3,
        )
        return [
            {
                "statement": statement,
                "citations": [
                    self._citation_from_chunk(chunk)
                    for chunk in evidence_chunks.get(index, [])
                ],
            }
            for index, statement in enumerate(statements)
        ]

    def _collect_comparison_statements(
        self,
        comparison_json: dict[str, Any],
    ) -> list[str]:
        statements: list[str] = []
        self._append_statement(statements, comparison_json.get("overall_summary"))
        for topic in comparison_json.get("common_topics", []):
            self._append_statement(statements, topic)
        for document_name, topics in comparison_json.get("unique_topics", {}).items():
            for topic in topics:
                self._append_statement(statements, f"{topic} is unique to {document_name}.")
        for difference in comparison_json.get("major_differences", []):
            self._append_statement(statements, difference)
        for document_name, concepts in comparison_json.get("missing_concepts", {}).items():
            for concept in concepts:
                self._append_statement(statements, f"{concept} is missing from {document_name}.")
        beginner = comparison_json.get("beginner_document")
        if beginner:
            self._append_statement(
                statements,
                f"{beginner} is most suitable for beginners.",
            )
        comprehensive = comparison_json.get("most_comprehensive_document")
        if comprehensive:
            self._append_statement(
                statements,
                f"{comprehensive} is the most comprehensive document.",
            )
        self._append_statement(statements, comparison_json.get("recommendation"))
        return statements

    def _append_statement(self, statements: list[str], value: Any) -> None:
        statement = str(value or "").strip()
        if statement and statement not in statements:
            statements.append(statement)

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

    def _normalize_referenced_sections(
        self,
        value: Any,
        chunk_lookup: dict[tuple[str, str], RetrievalResult],
        retrieved_chunks: list[RetrievalResult],
    ) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, dict):
                    continue
                filename = str(item.get("filename", ""))
                chunk_reference = str(item.get("chunk_reference", ""))
                chunk = chunk_lookup.get((filename, chunk_reference))
                if chunk is None:
                    continue
                sections.append(self._section_from_chunk(chunk))

        if sections:
            return sections

        return [self._section_from_chunk(chunk) for chunk in retrieved_chunks[:6]]

    def _section_from_chunk(self, chunk: RetrievalResult) -> dict[str, Any]:
        return {
            "document_id": chunk.document_id,
            "filename": chunk.filename,
            "page_number": chunk.page_number,
            "chunk_reference": chunk.chunk_reference,
            "text": chunk.text,
            "chunk_id": chunk.chunk_id,
            "score": self._score_from_distance(chunk.distance),
        }

    def _build_answer_evidence(
        self,
        answer: str,
        retrieved_chunks: list[RetrievalResult],
    ) -> list[dict[str, Any]]:
        statements = self._split_answer_statements(answer)
        return [
            {
                "statement": statement,
                "citations": [
                    self._citation_from_chunk(chunk)
                    for chunk in self._best_chunks_for_statement(
                        statement,
                        retrieved_chunks,
                    )
                ],
            }
            for statement in statements
        ]

    def _split_answer_statements(self, answer: str) -> list[str]:
        statements: list[str] = []
        for line in answer.splitlines():
            cleaned = line.strip(" -•\t")
            if not cleaned or cleaned.lower() in {
                "summary",
                "final comparison",
            } or cleaned.lower().startswith("document "):
                continue
            if len(cleaned) >= 12:
                statements.append(cleaned)
        return statements[:8]

    def _best_chunks_for_statement(
        self,
        statement: str,
        retrieved_chunks: list[RetrievalResult],
        limit: int = 3,
    ) -> list[RetrievalResult]:
        statement_tokens = set(re.findall(r"\b\w+\b", statement.lower()))
        scored: list[tuple[float, RetrievalResult]] = []
        for chunk in retrieved_chunks:
            chunk_tokens = set(re.findall(r"\b\w+\b", chunk.text.lower()))
            overlap = len(statement_tokens & chunk_tokens)
            similarity = self._score_from_distance(chunk.distance)
            scored.append((overlap + similarity, chunk))
        return [
            chunk
            for _, chunk in sorted(
                scored,
                key=lambda item: item[0],
                reverse=True,
            )[:limit]
        ]

    def _citation_from_chunk(self, chunk: RetrievalResult) -> dict[str, Any]:
        return {
            "document": chunk.filename,
            "page": chunk.page_number,
            "chunk": chunk.chunk_reference,
            "score": self._score_from_distance(chunk.distance),
            "relevant_paragraph": chunk.text,
            "document_id": chunk.document_id,
            "chunk_id": chunk.chunk_id,
        }

    def _score_from_distance(self, distance: Optional[float]) -> float:
        if distance is None:
            return 0.0
        score = 1 / (1 + max(float(distance), 0.0))
        return round(score, 4)

    def _normalize_confidence(self, value: Any) -> str:
        confidence = str(value or "medium").strip().lower()
        return confidence if confidence in {"high", "medium", "low"} else "medium"

    def _build_title(self, summaries: list[DocumentSummary]) -> str:
        first_two = " vs ".join(summary.filename for summary in summaries[:2])
        suffix = f" +{len(summaries) - 2}" if len(summaries) > 2 else ""
        return f"{first_two}{suffix}"[:255]
