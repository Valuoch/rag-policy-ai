"""Local, free embedding + re-ranking models (ONNX via fastembed; no API key, no torch)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np

from .config import use_system_trust_store


@lru_cache(maxsize=4)
def _embedder(model_name: str, cache_dir: str):
    use_system_trust_store()
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=model_name, cache_dir=cache_dir)


@lru_cache(maxsize=4)
def _reranker(model_name: str, cache_dir: str):
    use_system_trust_store()
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(model_name=model_name, cache_dir=cache_dir)


class Embedder:
    def __init__(self, model_name: str, cache_dir: Path):
        self.model_name = model_name
        self._model = _embedder(model_name, str(cache_dir))

    def embed_passages(self, texts: list[str], batch_size: int = 64) -> list[list[float]]:
        vecs = self._model.passage_embed(texts, batch_size=batch_size)
        return [np.asarray(v, dtype=np.float32).tolist() for v in vecs]

    def embed_query(self, text: str) -> list[float]:
        # bge models use an instruction prefix for queries; query_embed applies it.
        return np.asarray(next(iter(self._model.query_embed(text))), dtype=np.float32).tolist()


class Reranker:
    def __init__(self, model_name: str, cache_dir: Path):
        self.model_name = model_name
        self._model = _reranker(model_name, str(cache_dir))

    def scores(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        return [float(s) for s in self._model.rerank(query, passages)]
