"""Thin wrapper around a persistent, local Chroma collection (cosine space)."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")


def _client(index_dir: Path):
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    index_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(index_dir), settings=ChromaSettings(anonymized_telemetry=False))


class VectorStore:
    def __init__(self, index_dir: Path, collection: str):
        self.index_dir = index_dir
        self.name = collection
        self.client = _client(index_dir)
        self.col = self.client.get_or_create_collection(name=collection, metadata={"hnsw:space": "cosine"})

    def reset(self) -> None:
        try:
            self.client.delete_collection(self.name)
        except Exception:
            pass
        self.col = self.client.get_or_create_collection(name=self.name, metadata={"hnsw:space": "cosine"})

    def add(self, ids, embeddings, documents, metadatas, batch: int = 256) -> None:
        for i in range(0, len(ids), batch):
            self.col.add(
                ids=ids[i : i + batch],
                embeddings=embeddings[i : i + batch],
                documents=documents[i : i + batch],
                metadatas=metadatas[i : i + batch],
            )

    def count(self) -> int:
        return self.col.count()

    def query(self, embedding: list[float], n: int) -> list[dict]:
        n = max(1, min(n, self.count() or 1))
        res = self.col.query(query_embeddings=[embedding], n_results=n, include=["documents", "metadatas", "distances"])
        hits = []
        for cid, doc, meta, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]):
            hits.append({"id": cid, "text": doc, "meta": meta, "similarity": 1.0 - float(dist)})
        return hits

    def get_doc_chunks(self, doc_id: str) -> list[dict]:
        res = self.col.get(where={"doc_id": doc_id}, include=["documents", "metadatas"])
        rows = [{"id": i, "text": d, "meta": m} for i, d, m in zip(res["ids"], res["documents"], res["metadatas"])]
        return sorted(rows, key=lambda r: r["meta"]["chunk_index"])
