import json
from dataclasses import dataclass
from typing import Optional, Union

import chromadb
from chromadb.api.models.Collection import Collection

from app.core.config import settings
from app.models.document import Document
from app.services.chunk_service import TextChunk
from app.services.embedding_service import EmbeddingService


@dataclass(frozen=True)
class RetrievalResult:
    chunk_id: int
    document_id: int
    corpus_id: int
    filename: str
    page_number: int
    chunk_index: int
    chunk_reference: str
    text: str
    distance: Optional[float]


class VectorStoreService:
    def __init__(self, persist_directory: str = settings.chroma_dir) -> None:
        self.client = chromadb.PersistentClient(path=persist_directory)

    def collection_name(self, corpus_id: int) -> str:
        return f"corpus_{corpus_id}"

    def get_or_create_collection(self, corpus_id: int) -> Collection:
        return self.client.get_or_create_collection(
            name=self.collection_name(corpus_id),
            metadata={"corpus_id": corpus_id},
        )

    def delete_collection(self, corpus_id: int) -> None:
        collection_name = self.collection_name(corpus_id)
        existing_names = [collection.name for collection in self.client.list_collections()]
        if collection_name in existing_names:
            self.client.delete_collection(name=collection_name)

    def add_document_chunks(self, corpus_id: int, document: Document) -> None:
        collection = self.get_or_create_collection(corpus_id)

        ids: list[str] = []
        embeddings: list[list[float]] = []
        documents: list[str] = []
        metadatas: list[dict[str, Union[int, str]]] = []

        for chunk in document.chunks:
            if chunk.embedding is None:
                continue

            ids.append(self.chunk_vector_id(chunk.id))
            embeddings.append(json.loads(chunk.embedding.vector))
            documents.append(chunk.text)
            metadatas.append(
                {
                    "chunk_id": chunk.id,
                    "document_id": document.id,
                    "corpus_id": corpus_id,
                    "filename": document.filename,
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                    "chunk_reference": self.chunk_vector_id(chunk.id),
                    "model_name": chunk.embedding.model_name,
                    "vector_dimension": chunk.embedding.vector_dimension,
                }
            )

        if ids:
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )

    def retrieve_by_embedding(
        self,
        corpus_id: int,
        query_embedding: list[float],
        limit: int = 5,
    ) -> list[RetrievalResult]:
        collection = self.get_or_create_collection(corpus_id)
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            include=["documents", "metadatas", "distances"],
        )
        return self._format_results(result)

    def retrieve_by_text(
        self,
        corpus_id: int,
        query_text: str,
        limit: int = 5,
    ) -> list[RetrievalResult]:
        query_embedding = EmbeddingService().embed_chunks(
            [TextChunk(page_number=0, chunk_index=0, text=query_text)]
        )
        if not query_embedding:
            return []

        return self.retrieve_by_embedding(
            corpus_id=corpus_id,
            query_embedding=query_embedding[0].vector,
            limit=limit,
        )

    def _format_results(self, result: dict) -> list[RetrievalResult]:
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        formatted_results: list[RetrievalResult] = []
        for text, metadata, distance in zip(documents, metadatas, distances, strict=True):
            formatted_results.append(
                RetrievalResult(
                    chunk_id=int(metadata["chunk_id"]),
                    document_id=int(metadata["document_id"]),
                    corpus_id=int(metadata["corpus_id"]),
                    filename=str(metadata.get("filename", "Unknown file")),
                    page_number=int(metadata["page_number"]),
                    chunk_index=int(metadata["chunk_index"]),
                    chunk_reference=str(
                        metadata.get(
                            "chunk_reference",
                            self.chunk_vector_id(int(metadata["chunk_id"])),
                        )
                    ),
                    text=text,
                    distance=distance,
                )
            )

        return formatted_results

    def chunk_vector_id(self, chunk_id: int) -> str:
        return f"chunk_{chunk_id}"
