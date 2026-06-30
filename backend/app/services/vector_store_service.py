import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Union

from app.core.config import settings
from app.models.document import Document
from app.services.chunk_service import TextChunk
from app.services.embedding_service import EmbeddingService

if TYPE_CHECKING:
    from chromadb.api import ClientAPI
    from chromadb.api.models.Collection import Collection

logger = logging.getLogger(__name__)


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
        import chromadb

        self.client: "ClientAPI" = chromadb.PersistentClient(path=persist_directory)

    def collection_name(self, corpus_id: int) -> str:
        return f"corpus_{corpus_id}"

    def get_or_create_collection(self, corpus_id: int) -> "Collection":
        return self.client.get_or_create_collection(
            name=self.collection_name(corpus_id),
            metadata={"corpus_id": corpus_id},
        )

    def delete_collection(self, corpus_id: int) -> None:
        collection_name = self.collection_name(corpus_id)
        existing_names = [collection.name for collection in self.client.list_collections()]
        if collection_name in existing_names:
            self.client.delete_collection(name=collection_name)

    def add_document_chunks(self, corpus_id: int, document: Document) -> int:
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

        if not ids:
            logger.warning(
                "No chunk embeddings to store: corpus_id=%s document_id=%s filename=%s chunks=%s",
                corpus_id,
                document.id,
                document.filename,
                len(document.chunks),
            )
            return 0

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info(
            "Stored chunk embeddings in vector database: corpus_id=%s collection=%s document_id=%s vectors=%s",
            corpus_id,
            self.collection_name(corpus_id),
            document.id,
            len(ids),
        )
        return len(ids)

    def retrieve_by_embedding(
        self,
        corpus_id: int,
        query_embedding: list[float],
        limit: int = 5,
        document_ids: Optional[list[int]] = None,
    ) -> list[RetrievalResult]:
        collection = self.get_or_create_collection(corpus_id)
        where_filter = None
        if document_ids:
            unique_ids = list(dict.fromkeys(document_ids))
            where_filter = (
                {"document_id": unique_ids[0]}
                if len(unique_ids) == 1
                else {"document_id": {"$in": unique_ids}}
            )
        query_kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": limit,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter is not None:
            query_kwargs["where"] = where_filter
        result = collection.query(**query_kwargs)
        results = self._format_results(result)
        self._log_retrieval_results(
            corpus_id=corpus_id,
            query_text=None,
            results=results,
            limit=limit,
            document_ids=document_ids,
        )
        return results

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

        results = self.retrieve_by_embedding(
            corpus_id=corpus_id,
            query_embedding=query_embedding[0].vector,
            limit=limit,
        )
        self._log_retrieval_results(
            corpus_id=corpus_id,
            query_text=query_text,
            results=results,
            limit=limit,
        )
        return results

    def retrieve_by_text_for_documents(
        self,
        documents_by_corpus: dict[int, list[int]],
        query_text: str,
        limit_per_document: int = 3,
    ) -> list[RetrievalResult]:
        query_embedding = EmbeddingService().embed_chunks(
            [TextChunk(page_number=0, chunk_index=0, text=query_text)]
        )
        if not query_embedding:
            return []

        retrieved: list[RetrievalResult] = []
        for corpus_id, document_ids in documents_by_corpus.items():
            unique_document_ids = list(dict.fromkeys(document_ids))
            corpus_results = self.retrieve_by_embedding(
                corpus_id=corpus_id,
                query_embedding=query_embedding[0].vector,
                limit=max(limit_per_document * len(unique_document_ids), limit_per_document),
                document_ids=unique_document_ids,
            )
            grouped: dict[int, list[RetrievalResult]] = {
                document_id: [] for document_id in unique_document_ids
            }
            for result in corpus_results:
                if result.document_id in grouped:
                    grouped[result.document_id].append(result)

            for document_id in unique_document_ids:
                retrieved.extend(grouped[document_id][:limit_per_document])

        return retrieved

    def _log_retrieval_results(
        self,
        *,
        corpus_id: int,
        query_text: Optional[str],
        results: list[RetrievalResult],
        limit: int,
        document_ids: Optional[list[int]] = None,
    ) -> None:
        logger.info(
            "Retrieved chunks from vector database: corpus_id=%s document_ids=%s query=%r limit=%s retrieved=%s",
            corpus_id,
            document_ids,
            query_text,
            limit,
            len(results),
        )
        if not settings.debug_retrieval:
            return

        max_chars = max(settings.retrieval_log_chars, 0)
        for result in results:
            preview = result.text[:max_chars].replace("\n", " ")
            logger.debug(
                "Retrieved chunk content: corpus_id=%s document_id=%s filename=%s page=%s chunk_id=%s distance=%s text=%r",
                result.corpus_id,
                result.document_id,
                result.filename,
                result.page_number,
                result.chunk_id,
                result.distance,
                preview,
            )

    def retrieve_evidence_for_texts(
        self,
        documents_by_corpus: dict[int, list[int]],
        texts: list[str],
        limit_per_statement: int = 3,
    ) -> dict[int, list[RetrievalResult]]:
        chunks = [
            TextChunk(page_number=0, chunk_index=index, text=text)
            for index, text in enumerate(texts)
            if text.strip()
        ]
        embeddings = EmbeddingService().embed_chunks(chunks)
        if not embeddings:
            return {}

        evidence: dict[int, list[RetrievalResult]] = {
            embedding.chunk_index: [] for embedding in embeddings
        }
        query_embeddings = [embedding.vector for embedding in embeddings]
        embedding_indexes = [embedding.chunk_index for embedding in embeddings]

        for corpus_id, document_ids in documents_by_corpus.items():
            unique_document_ids = list(dict.fromkeys(document_ids))
            collection = self.get_or_create_collection(corpus_id)
            where_filter = (
                {"document_id": unique_document_ids[0]}
                if len(unique_document_ids) == 1
                else {"document_id": {"$in": unique_document_ids}}
            )
            result = collection.query(
                query_embeddings=query_embeddings,
                n_results=max(limit_per_statement, limit_per_statement * len(unique_document_ids)),
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
            for position, statement_index in enumerate(embedding_indexes):
                evidence[statement_index].extend(
                    self._format_result_group(result, position)[:limit_per_statement]
                )

        for statement_index, results in evidence.items():
            evidence[statement_index] = sorted(
                results,
                key=lambda item: item.distance if item.distance is not None else 1_000_000,
            )[:limit_per_statement]

        return evidence

    def _format_results(self, result: dict) -> list[RetrievalResult]:
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        formatted_results: list[RetrievalResult] = []
        for text, metadata, distance in zip(documents, metadatas, distances):
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

    def _format_result_group(self, result: dict, position: int) -> list[RetrievalResult]:
        documents = result.get("documents", [])
        metadatas = result.get("metadatas", [])
        distances = result.get("distances", [])
        if position >= len(documents):
            return []
        return self._format_result_rows(
            documents[position],
            metadatas[position],
            distances[position],
        )

    def _format_result_rows(
        self,
        documents: list[str],
        metadatas: list[dict],
        distances: list[Optional[float]],
    ) -> list[RetrievalResult]:
        formatted_results: list[RetrievalResult] = []
        for text, metadata, distance in zip(documents, metadatas, distances):
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
