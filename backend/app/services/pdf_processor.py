from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass(frozen=True)
class ExtractedPdfPage:
    page_number: int
    text: str


def extract_pdf_text(pdf_path: str | Path) -> list[ExtractedPdfPage]:
    reader = PdfReader(str(pdf_path))
    extracted_pages: list[ExtractedPdfPage] = []

    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        extracted_pages.append(
            ExtractedPdfPage(
                page_number=index,
                text=text.strip(),
            )
        )

    return extracted_pages
