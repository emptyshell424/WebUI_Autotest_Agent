from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings

try:
    import chromadb  # type: ignore
except ModuleNotFoundError:
    chromadb = None


@dataclass(slots=True)
class RAGSearchResult:
    context: str
    sources: list[str]
    result_count: int


class RAGService:
    collection_name = "selenium_knowledge"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._fallback_documents: list[dict[str, str]] = []
        self._uses_vector_store = chromadb is not None
        self.client = (
            chromadb.PersistentClient(path=str(settings.vector_store_dir))
            if self._uses_vector_store
            else None
        )

    def rebuild_index(self) -> dict[str, int | str | bool]:
        files = self._knowledge_files()
        documents: list[str] = []
        ids: list[str] = []
        metadatas: list[dict[str, str]] = []
        chunk_count = 0
        fallback_documents: list[dict[str, str]] = []

        for file_path in files:
            chunks = self._split_document(file_path.read_text(encoding="utf-8"))
            for index, chunk in enumerate(chunks):
                documents.append(chunk)
                ids.append(f"{file_path.stem}-{index}")
                metadata = {"source": file_path.name}
                metadatas.append(metadata)
                fallback_documents.append({"document": chunk, "source": file_path.name})
            chunk_count += len(chunks)

        self._fallback_documents = fallback_documents

        if self._uses_vector_store:
            self._reset_collection()
            collection = self._get_collection()
            if documents:
                collection.upsert(documents=documents, ids=ids, metadatas=metadatas)

        return {
            "ready": bool(documents),
            "document_count": len(files),
            "chunk_count": chunk_count,
            "collection_name": self.collection_name,
            "backend": "chromadb" if self._uses_vector_store else "fallback",
        }

    def search(self, query: str, n_results: int = 3) -> RAGSearchResult:
        normalized_query = query.strip()
        if not normalized_query:
            return RAGSearchResult(context="", sources=[], result_count=0)

        if self._uses_vector_store:
            collection = self._get_collection()
            if collection.count() == 0:
                return RAGSearchResult(context="", sources=[], result_count=0)

            results = collection.query(query_texts=[normalized_query], n_results=n_results)
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

        if not self._fallback_documents:
            self.rebuild_index()
        return self._search_fallback(normalized_query, n_results)

    def get_status(self) -> dict[str, int | str | bool]:
        if self._uses_vector_store:
            collection = self._get_collection()
            indexed_chunks = collection.count()
        else:
            if not self._fallback_documents:
                self.rebuild_index()
            indexed_chunks = len(self._fallback_documents)

        return {
            "ready": indexed_chunks > 0,
            "indexed_chunks": indexed_chunks,
            "document_count": len(self._knowledge_files()),
            "source_dir": str(self.settings.knowledge_base_dir),
            "collection_name": self.collection_name,
            "backend": "chromadb" if self._uses_vector_store else "fallback",
        }

    def _search_fallback(self, query: str, n_results: int) -> RAGSearchResult:
        terms = [term for term in query.lower().split() if term]
        ranked = []
        for item in self._fallback_documents:
            haystack = item["document"].lower()
            score = sum(haystack.count(term) for term in terms)
            if score > 0:
                ranked.append((score, item))

        if not ranked:
            ranked = [(0, item) for item in self._fallback_documents[:n_results]]
        else:
            ranked.sort(key=lambda entry: entry[0], reverse=True)

        selected = [item for _, item in ranked[:n_results]]
        return RAGSearchResult(
            context="\n\n".join(item["document"].strip() for item in selected if item["document"].strip()),
            sources=sorted({item["source"] for item in selected}),
            result_count=len(selected),
        )

    def _get_collection(self):
        if not self.client:
            raise RuntimeError("Vector store client is unavailable.")
        return self.client.get_or_create_collection(name=self.collection_name)

    def _reset_collection(self) -> None:
        if not self.client:
            return
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
