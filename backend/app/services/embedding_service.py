import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from app.core.config import settings
from app.services.chunk_service import TextChunk

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL_NAME = settings.embedding_model
HASH_EMBEDDING_DIMENSION = 384


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
    def __init__(
        self,
        model_name: str = EMBEDDING_MODEL_NAME,
        backend: str = settings.embedding_backend,
    ) -> None:
        self.model_name = model_name
        self.backend = backend
        self._model: Optional["SentenceTransformer"] = None

    @property
    def model(self) -> "SentenceTransformer":
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            try:
                self._model = SentenceTransformer(
                    self.model_name,
                    local_files_only=True,
                )
            except Exception:
                self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_chunks(self, chunks: list[TextChunk]) -> list[EmbeddedChunk]:
        if not chunks:
            return []

        if self.backend == "sentence-transformers":
            return self._embed_with_sentence_transformers(chunks)

        return [
            EmbeddedChunk(
                chunk_index=chunk.chunk_index,
                model_name="hash-embedding-384",
                vector=self._hash_embedding(chunk.text),
            )
            for chunk in chunks
        ]

    def _embed_with_sentence_transformers(
        self,
        chunks: list[TextChunk],
    ) -> list[EmbeddedChunk]:
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

    def _hash_embedding(self, text: str) -> list[float]:
        vector = [0.0] * HASH_EMBEDDING_DIMENSION
        tokens = re.findall(r"\b\w+\b", text.lower())

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % HASH_EMBEDDING_DIMENSION
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            return vector

        return [value / magnitude for value in vector]
