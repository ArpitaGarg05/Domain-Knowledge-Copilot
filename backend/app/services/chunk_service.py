from dataclasses import dataclass

from app.services.pdf_processor import ExtractedPdfPage

DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 100
MIN_CHUNK_SIZE = 500
MAX_CHUNK_SIZE = 1000


@dataclass(frozen=True)
class TextChunk:
    page_number: int
    chunk_index: int
    text: str


class ChunkService:
    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> None:
        if chunk_size < MIN_CHUNK_SIZE or chunk_size > MAX_CHUNK_SIZE:
            raise ValueError("chunk_size must be between 500 and 1000 characters.")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be non-negative and smaller than chunk_size.")

        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_pages(self, pages: list[ExtractedPdfPage]) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        chunk_index = 0

        for page in pages:
            page_text = page.text.strip()
            if not page_text:
                continue

            for chunk_text in self._chunk_text(page_text):
                chunks.append(
                    TextChunk(
                        page_number=page.page_number,
                        chunk_index=chunk_index,
                        text=chunk_text,
                    )
                )
                chunk_index += 1

        return chunks

    def _chunk_text(self, text: str) -> list[str]:
        chunks: list[str] = []
        start = 0
        step = self.chunk_size - self.overlap

        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end == len(text):
                break

            start += step

        return chunks
