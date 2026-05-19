"""ChromaDB storage wrapper for retrieval experiments and demos.

The database layer deliberately stays small. It owns collection creation,
document insertion, JSON fixture loading, and id-based lookup. Search,
reconciliation, and evaluation modules should treat it as storage rather than
place retrieval policy here.

Key variables:
    `collection_name`: ChromaDB collection opened by the wrapper.
    `persist_directory`: Optional directory for persistent local storage. When
        omitted, ChromaDB uses an in-memory client.
    `reset`: Whether to delete an existing collection before opening it. This is
        useful for deterministic demos, benchmarks, and tests.
    `batch_size`: Number of documents inserted per ChromaDB add call.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings


class Database:
    """Manage a ChromaDB collection for document storage and retrieval."""

    def __init__(
        self,
        collection_name: str = "noetic_memories",
        persist_directory: str | None = None,
        reset: bool = False,
    ) -> None:
        """Initialize ChromaDB client and collection.

        Args:
            collection_name: Name of the ChromaDB collection.
            persist_directory: Directory to persist data. When omitted, the
                collection is in-memory.
            reset: Whether to delete an existing collection before opening it.

        Returns:
            None.
        """
        if persist_directory:
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(anonymized_telemetry=False),
            )
        else:
            self.client = chromadb.Client(
                settings=Settings(anonymized_telemetry=False),
            )

        if reset:
            try:
                self.client.delete_collection(name=collection_name)
            except Exception:
                # Chroma raises when the collection does not exist; reset should
                # remain idempotent for tests and throwaway benchmark runs.
                pass

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(
        self,
        documents: list[dict[str, Any]],
    ) -> None:
        """Add documents to the collection.

        Args:
            documents: Documents with `id`, `text`, and optional `metadata` keys.

        Returns:
            None.
        """
        if not documents:
            return

        batch_size = 1000
        for start in range(0, len(documents), batch_size):
            batch = documents[start : start + batch_size]
            ids = [doc["id"] for doc in batch]
            texts = [doc["text"] for doc in batch]
            metadatas = [doc.get("metadata", {}) for doc in batch]

            self.collection.add(
                ids=ids,
                documents=texts,
                metadatas=metadatas,
            )

    def load_from_json(self, json_path: str | Path) -> None:
        """Load documents from a JSON file.

        Args:
            json_path: Path to a JSON file containing a `test_corpus` list.

        Returns:
            None.
        """
        with open(json_path) as f:
            data = json.load(f)

        documents = data.get("test_corpus", [])
        self.add_documents(documents)

    def count(self) -> int:
        """Return the number of documents in the collection.

        Args:
            None.

        Returns:
            Number of stored documents.
        """
        return self.collection.count()

    def get_all_ids(self) -> list[str]:
        """Return all document IDs in the collection.

        Args:
            None.

        Returns:
            Stored document identifiers.
        """
        result = self.collection.get()
        return result["ids"]

    def get_by_id(self, doc_id: str) -> dict[str, Any] | None:
        """Retrieve a document by ID.

        Args:
            doc_id: Document identifier to fetch.

        Returns:
            Document with `id`, `text`, and `metadata`, or `None` when the
            identifier is not present.
        """
        result = self.collection.get(ids=[doc_id])

        if not result["ids"]:
            return None

        return {
            "id": result["ids"][0],
            "text": result["documents"][0],
            "metadata": result["metadatas"][0],
        }

    def reset(self) -> None:
        """Delete all documents from the collection.

        Args:
            None.

        Returns:
            None.
        """
        collection_name = self.collection.name
        self.client.delete_collection(name=collection_name)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
