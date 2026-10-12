"""Top-k dense retrieval with optional cross-encoder re-ranking."""

from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from .embeddings import Embedder, Reranker
from .vectorstore import VectorStore


@dataclass
class Passage:
    n: int  # 1-based rank shown to the LLM as [n]
    chunk_id: str
    doc_id: str
    title: str
    source: str
    section: str
    section_index: int
    text: str
    similarity: float
    rerank_score: float | None = None

    @property
    def score(self) -> float:
        return self.rerank_score if self.rerank_score is not None else self.similarity

    def label(self) -> str:
        return f"{self.doc_id} | {self.title} | {self.section}"


class Retriever:
    def __init__(self, settings: Settings, store: VectorStore | None = None):
        self.s = settings
        self.store = store or VectorStore(settings.index_dir, settings.collection)
        self.embedder = Embedder(settings.embedding_model, settings.model_cache_dir)
        self.reranker = Reranker(settings.rerank_model, settings.model_cache_dir) if settings.rerank else None

    def retrieve(self, question: str, k: int | None = None, rerank: bool | None = None) -> list[Passage]:
        k = k or self.s.top_k
        use_rerank = self.reranker is not None if rerank is None else (rerank and self.reranker is not None)
        n = max(self.s.fetch_k, k) if use_rerank else k
        hits = self.store.query(self.embedder.embed_query(question), n)
        if use_rerank and hits:
            scores = self.reranker.scores(question, [f"{h['meta']['title']} > {h['meta']['section']}\n{h['text']}" for h in hits])
            for h, sc in zip(hits, scores):
                h["rerank"] = sc
            # Stable sort with similarity as tie-breaker keeps results deterministic.
            hits.sort(key=lambda h: (h["rerank"], h["similarity"]), reverse=True)
        out = []
        for i, h in enumerate(hits[:k], start=1):
            m = h["meta"]
            out.append(
                Passage(
                    n=i,
                    chunk_id=h["id"],
                    doc_id=m["doc_id"],
                    title=m["title"],
                    source=m["source"],
                    section=m["section"],
                    section_index=int(m["section_index"]),
                    text=h["text"],
                    similarity=h["similarity"],
                    rerank_score=h.get("rerank"),
                )
            )
        return out

    def in_scope(self, passages: list[Passage]) -> bool:
        """Retrieval-confidence gate used to refuse off-corpus questions before generation."""
        if not passages:
            return False
        # Refuse only when BOTH signals are low. The cross-encoder alone under-scores colloquial
        # in-scope questions ("I left my work computer in a taxi..."), while off-topic questions
        # score low on both. Near-domain questions that pass are handled by the LLM's refusal rule.
        best_sim = max(p.similarity for p in passages)
        best_rerank = max((p.rerank_score for p in passages if p.rerank_score is not None), default=None)
        if best_rerank is not None and best_rerank >= self.s.min_rerank_score:
            return True
        return best_sim >= self.s.min_similarity
