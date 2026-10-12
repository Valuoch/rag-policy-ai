"""Heading-aware chunking with sliding word windows.

Strategy (deterministic, no randomness):
1. Each heading-delimited section is a natural unit.
2. Consecutive small sections of the same document are merged until they reach
   ``min_words`` (so a 15-word "Purpose" section does not become its own weak chunk).
3. Sections longer than ``size`` words are split into windows of ``size`` words with
   ``overlap`` words of overlap, cut at paragraph/sentence boundaries where possible.
4. Every chunk text is prefixed with "<title> > <section heading>" so the embedding carries
   the document and section context, which helps short chunks such as table rows.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from .loaders import Document, Section


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    source: str
    section: str
    section_index: int
    chunk_index: int
    text: str  # body only (shown as the snippet)

    @property
    def embed_text(self) -> str:
        return f"{self.doc_id} {self.title} > {self.section}\n{self.text}"

    def metadata(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "source": self.source,
            "section": self.section,
            "section_index": self.section_index,
            "chunk_index": self.chunk_index,
        }




def _windows(text: str, size: int, overlap: int) -> list[str]:
    # Keep newlines attached to words so paragraph structure survives the split.
    tokens = re.findall(r"\S+\s*", text)
    if len(tokens) <= size:
        return [text.strip()]
    out: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + size, len(tokens))
        if end < len(tokens):
            # Prefer to end at a sentence/paragraph boundary within the last 30% of the window.
            floor = start + int(size * 0.7)
            for i in range(end, floor, -1):
                if re.search(r"[.!?:]\s*$|\n\s*$", tokens[i - 1]):
                    end = i
                    break
        out.append("".join(tokens[start:end]).strip())
        if end >= len(tokens):
            break
        start = max(end - overlap, start + 1)
    return out


def _merge_small(sections: list[Section], min_words: int, max_words: int) -> list[Section]:
    merged: list[Section] = []
    for s in sections:
        prev = merged[-1] if merged else None
        if (
            prev is not None
            and len(prev.text.split()) < min_words
            and len(prev.text.split()) + len(s.text.split()) <= max_words
        ):
            heading = prev.heading if s.heading == prev.heading else f"{prev.heading}; {s.heading}"
            merged[-1] = Section(heading=heading, text=f"{prev.text}\n\n{s.heading}\n{s.text}", index=prev.index)
        else:
            merged.append(Section(heading=s.heading, text=s.text, index=s.index))
    return merged


def chunk_document(doc: Document, size: int = 220, overlap: int = 40, min_words: int = 40) -> list[Chunk]:
    if overlap >= size:
        raise ValueError("chunk overlap must be smaller than chunk size")
    chunks: list[Chunk] = []
    for sec in _merge_small(doc.sections, min_words, size):
        for piece in _windows(sec.text, size, overlap):
            if not piece:
                continue
            n = len(chunks)
            digest = hashlib.sha1(f"{doc.doc_id}|{n}|{piece}".encode()).hexdigest()[:10]
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.doc_id}#{n:03d}-{digest}",
                    doc_id=doc.doc_id,
                    title=doc.title,
                    source=doc.source,
                    section=sec.heading,
                    section_index=sec.index,
                    chunk_index=n,
                    text=piece,
                )
            )
    return chunks


def chunk_corpus(docs: list[Document], size: int = 220, overlap: int = 40, min_words: int = 40) -> list[Chunk]:
    out: list[Chunk] = []
    for d in docs:
        out.extend(chunk_document(d, size=size, overlap=overlap, min_words=min_words))
    return out
