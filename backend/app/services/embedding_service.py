import json
from dataclasses import dataclass

from sentence_transformers import SentenceTransformer

from app.services.chunk_service import TextChunk

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


@dataclass(frozen=True)
class EmbeddedChunk:
    chunk_index: int
    model_name: str
    vector: list[float]

    @property
    def vector_dimension(self) -> int:
        return len(self.vector)

    @property
    def vector_json(self) -> str:
        return json.dumps(self.vector)


class EmbeddingService:
    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME) -> None:
        self.model_name = model_name
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_chunks(self, chunks: list[TextChunk]) -> list[EmbeddedChunk]:
        if not chunks:
            return []

        vectors = self.model.encode(
            [chunk.text for chunk in chunks],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        return [
            EmbeddedChunk(
                chunk_index=chunk.chunk_index,
                model_name=self.model_name,
                vector=vector.astype(float).tolist(),
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
