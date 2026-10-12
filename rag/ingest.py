"""Build the vector index: parse -> clean -> chunk -> embed -> store.

Usage:
    python -m rag.ingest                     # (re)build index from CORPUS_DIR into INDEX_DIR
    python -m rag.ingest --chunk-size 400 --index-dir index_400   # ablation variant
    python -m rag.ingest --stats             # print corpus statistics only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from .chunking import chunk_corpus
from .config import Settings, get_settings
from .loaders import load_corpus

MANIFEST = "manifest.json"
WORDS_PER_PAGE = 500  # rough printed-page estimate used for corpus statistics


def corpus_fingerprint(corpus_dir: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(corpus_dir.rglob("*")):
        if p.is_file():
            h.update(p.name.encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


def build_index(settings: Settings, verbose: bool = True) -> dict:
    from .embeddings import Embedder
    from .vectorstore import VectorStore

    t0 = time.perf_counter()
    docs = load_corpus(settings.corpus_dir)
    if not docs:
        raise SystemExit(f"No documents found in {settings.corpus_dir}")
    chunks = chunk_corpus(docs, settings.chunk_size, settings.chunk_overlap, settings.min_chunk_words)
    if verbose:
        print(f"Parsed {len(docs)} documents -> {len(chunks)} chunks "
              f"(size={settings.chunk_size} words, overlap={settings.chunk_overlap})")

    embedder = Embedder(settings.embedding_model, settings.model_cache_dir)
    vectors = embedder.embed_passages([c.embed_text for c in chunks])

    store = VectorStore(settings.index_dir, settings.collection)
    store.reset()
    store.add(
        ids=[c.chunk_id for c in chunks],
        embeddings=vectors,
        documents=[c.text for c in chunks],
        metadatas=[c.metadata() for c in chunks],
    )

    manifest = {
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "corpus_fingerprint": corpus_fingerprint(settings.corpus_dir),
        "embedding_model": settings.embedding_model,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "min_chunk_words": settings.min_chunk_words,
        "num_documents": len(docs),
        "num_chunks": len(chunks),
        "documents": [
            {
                "doc_id": d.doc_id,
                "title": d.title,
                "source": d.source,
                "format": d.fmt,
                "words": d.word_count,
                "sections": [{"index": s.index, "heading": s.heading} for s in d.sections],
            }
            for d in docs
        ],
    }
    (settings.index_dir / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if verbose:
        print(f"Indexed {store.count()} chunks into {settings.index_dir} in {time.perf_counter() - t0:.1f}s")
    return manifest


def read_manifest(index_dir: Path) -> dict | None:
    p = index_dir / MANIFEST
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def print_stats(settings: Settings) -> None:
    docs = load_corpus(settings.corpus_dir)
    total = 0
    for d in docs:
        total += d.word_count
        print(f"{d.doc_id:8} {d.fmt:4} {d.word_count:6} words  {len(d.sections):3} sections  {d.title}")
    print(f"{len(docs)} documents, {total} words (~{total / WORDS_PER_PAGE:.0f} pages)")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chunk-size", type=int)
    ap.add_argument("--chunk-overlap", type=int)
    ap.add_argument("--index-dir", type=Path)
    ap.add_argument("--corpus-dir", type=Path)
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args(argv)
    overrides = {
        k: v
        for k, v in {
            "chunk_size": a.chunk_size,
            "chunk_overlap": a.chunk_overlap,
            "index_dir": a.index_dir,
            "corpus_dir": a.corpus_dir,
        }.items()
        if v is not None
    }
    settings = get_settings(**overrides)
    if a.stats:
        print_stats(settings)
        return
    build_index(settings)


if __name__ == "__main__":
    main()
