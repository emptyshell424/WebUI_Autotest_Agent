from dataclasses import dataclass
from pathlib import Path

import chromadb

from app.core.config import Settings


@dataclass(slots=True)
class RAGSearchResult:
    context: str
    sources: list[str]
    result_count: int


class RAGService:
    collection_name = "selenium_knowledge"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = chromadb.PersistentClient(path=str(settings.vector_store_dir))

    def rebuild_index(self) -> dict[str, int | str | bool]:
        files = self._knowledge_files()
        self._reset_collection()
        collection = self._get_collection()

        documents: list[str] = []
        ids: list[str] = []
        metadatas: list[dict[str, str]] = []
        chunk_count = 0

        for file_path in files:
            chunks = self._split_document(file_path.read_text(encoding="utf-8"))
            for index, chunk in enumerate(chunks):
                documents.append(chunk)
                ids.append(f"{file_path.stem}-{index}")
                metadatas.append({"source": file_path.name})
            chunk_count += len(chunks)

        if documents:
            collection.upsert(documents=documents, ids=ids, metadatas=metadatas)

        return {
            "ready": bool(documents),
            "document_count": len(files),
            "chunk_count": chunk_count,
            "collection_name": self.collection_name,
        }

    def search(self, query: str, n_results: int = 3) -> RAGSearchResult:
        if not query.strip():
            return RAGSearchResult(context="", sources=[], result_count=0)

        collection = self._get_collection()
        if collection.count() == 0:
            return RAGSearchResult(context="", sources=[], result_count=0)

        results = collection.query(query_texts=[query], n_results=n_results)
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        sources = sorted(
            {
                str(metadata.get("source"))
                for metadata in metadatas
                if metadata and metadata.get("source")
            }
        )
        return RAGSearchResult(
            context="\n\n".join(document.strip() for document in documents if document.strip()),
            sources=sources,
            result_count=len(documents),
        )

    def get_status(self) -> dict[str, int | str | bool]:
        collection = self._get_collection()
        return {
            "ready": collection.count() > 0,
            "indexed_chunks": collection.count(),
            "document_count": len(self._knowledge_files()),
            "source_dir": str(self.settings.knowledge_base_dir),
            "collection_name": self.collection_name,
        }

    def _get_collection(self):
        return self.client.get_or_create_collection(name=self.collection_name)

    def _reset_collection(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass

    def _knowledge_files(self) -> list[Path]:
        if not self.settings.knowledge_base_dir.exists():
            return []
        files = sorted(self.settings.knowledge_base_dir.glob("*.md"))
        files.extend(sorted(self.settings.knowledge_base_dir.glob("*.txt")))
        return files

    def _split_document(self, text: str) -> list[str]:
        normalized = text.replace("\r\n", "\n")
        chunks = [chunk.strip() for chunk in normalized.split("\n\n") if chunk.strip()]
        if chunks:
            return chunks
        return [line.strip() for line in normalized.splitlines() if line.strip()]
