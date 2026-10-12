"""End-to-end RAG pipeline: validate -> retrieve (+rerank) -> gate -> generate -> enforce citations."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

from . import guardrails as g
from .config import Settings, get_settings
from .llm import LLMClient, build_messages, content_words, extractive_answer, split_sentences
from .retriever import Passage, Retriever

log = logging.getLogger(__name__)


@dataclass
class Answer:
    question: str
    answer: str
    refused: bool
    citations: list[dict]
    retrieved: list[dict]
    mode: str  # "llm" | "extractive"
    model: str
    latency_ms: float
    timings: dict

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "answer": self.answer,
            "refused": self.refused,
            "citations": self.citations,
            "retrieved": self.retrieved,
            "mode": self.mode,
            "model": self.model,
            "latency_ms": round(self.latency_ms, 1),
            "timings_ms": {k: round(v, 1) for k, v in self.timings.items()},
        }


def best_snippet(passage_text: str, answer: str, max_chars: int = 320) -> str:
    """The sentence(s) in the passage that overlap most with the answer, so the UI shows evidence."""
    sents = split_sentences(passage_text) or [passage_text]
    target = content_words(g.strip_citations(answer))
    scored = [(len(target & content_words(s)), -i, i) for i, s in enumerate(sents)]
    _, _, i = max(scored)
    snippet = sents[i]
    if len(snippet) < max_chars * 0.6 and i + 1 < len(sents):
        snippet = f"{snippet} {sents[i + 1]}"
    snippet = re.sub(r"\s+", " ", snippet).strip()
    return snippet if len(snippet) <= max_chars else snippet[: max_chars - 3].rsplit(" ", 1)[0] + "..."


class RAGPipeline:
    def __init__(self, settings: Settings | None = None, retriever: Retriever | None = None):
        self.s = settings or get_settings()
        self.retriever = retriever or Retriever(self.s)
        self.llm = LLMClient(self.s) if self.s.llm_enabled else None

    @property
    def mode(self) -> str:
        return "llm" if self.llm else "extractive"

    @property
    def model_name(self) -> str:
        return self.s.llm_model if self.llm else "extractive (no LLM key configured)"

    def _citations(self, answer: str, passages: list[Passage]) -> list[dict]:
        by_n = {p.n: p for p in passages}
        out = []
        for n in g.cited_numbers(answer):
            p = by_n.get(n)
            if p is None:
                continue
            out.append(
                {
                    "n": n,
                    "doc_id": p.doc_id,
                    "title": p.title,
                    "section": p.section,
                    "chunk_id": p.chunk_id,
                    "source": p.source,
                    "url": f"/docs/{p.doc_id}#sec-{p.section_index}",
                    "snippet": best_snippet(p.text, answer),
                    "score": round(p.score, 4),
                }
            )
        return out

    def answer(self, question: str, k: int | None = None) -> Answer:
        t0 = time.perf_counter()
        timings: dict[str, float] = {}
        q = g.clean_question(question, self.s.max_question_chars)

        t = time.perf_counter()
        passages = self.retriever.retrieve(q, k=k)
        timings["retrieval"] = (time.perf_counter() - t) * 1000
        retrieved = [
            {"n": p.n, "doc_id": p.doc_id, "section": p.section, "similarity": round(p.similarity, 4),
             "rerank_score": None if p.rerank_score is None else round(p.rerank_score, 4)}
            for p in passages
        ]

        def done(text: str, refused: bool, cites: list[dict]) -> Answer:
            return Answer(q, text, refused, cites, retrieved, self.mode, self.model_name,
                          (time.perf_counter() - t0) * 1000, timings)

        # Guardrail 1: refuse off-corpus questions without spending an LLM call.
        if not self.retriever.in_scope(passages):
            return done(g.REFUSAL, True, [])

        t = time.perf_counter()
        if self.llm:
            text = self.llm.answer(q, passages)
            valid = {p.n for p in passages}
            # Guardrail 2: every non-refusal answer must cite a retrieved source; retry once if not.
            if not g.is_refusal(text) and not (set(g.cited_numbers(text)) & valid):
                log.info("answer had no valid citations; retrying with a reminder")
                msgs = build_messages(q, passages)
                msgs += [{"role": "assistant", "content": text},
                         {"role": "user", "content": "Rewrite the answer, citing the supporting source number "
                                                     "in square brackets after each sentence, e.g. [1]."}]
                text = self.llm.complete(msgs)
        else:
            text = extractive_answer(q, passages, self.retriever.reranker)
        timings["generation"] = (time.perf_counter() - t) * 1000

        if g.is_refusal(text):
            return done(g.REFUSAL, True, [])

        text = g.drop_invalid_citations(text, {p.n for p in passages})
        text = g.limit_length(text, self.s.max_answer_chars)  # Guardrail 3: output length cap
        cites = self._citations(text, passages)
        if not cites:
            # Still uncited after the retry: do not present unsupported text as policy.
            return done(g.REFUSAL, True, [])
        return done(text, False, cites)
