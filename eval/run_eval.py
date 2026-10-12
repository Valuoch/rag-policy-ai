"""Evaluate the RAG application on eval/questions.jsonl.

Metrics
  Answer quality
    groundedness       % of answered in-scope questions whose answer is fully supported by the
                       retrieved context (LLM-as-judge when an LLM key is set; otherwise a strict
                       lexical check: every sentence's numbers and >=80% of its content words must
                       appear in the retrieved passages).
    citation accuracy  % of answered in-scope questions whose citations (a) all point to a gold
                       document and (b) the cited passages themselves contain every gold key fact.
    exact / partial    % of in-scope questions whose answer contains all / at least one gold key fact.
    refusal accuracy   % of out-of-scope questions correctly refused (and in-scope ones answered).
  System
    latency p50 / p95  wall-clock from POST /chat to JSON response (Flask test client, warm models).
  Retrieval ablations (no LLM calls)
    hit@k, evidence recall@k and MRR for k in {1,2,4,6,8}, with/without re-ranking, and for chunk
    sizes {120, 220, 400} words.

Usage
  python -m eval.run_eval                       # full eval with current settings, writes eval/results/
  python -m eval.run_eval --ablations           # also run retrieval ablations (builds extra indexes)
  python -m eval.run_eval --sample 15           # seeded random subset
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag import guardrails as g  # noqa: E402
from rag.config import ROOT, SEED, get_settings  # noqa: E402
from rag.llm import content_words, split_sentences  # noqa: E402

EVAL_DIR = ROOT / "eval"
RESULTS_DIR = EVAL_DIR / "results"


def load_questions(path: Path = EVAL_DIR / "questions.jsonl") -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def norm(text: str) -> str:
    text = text.lower().replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text)


def facts_found(text: str, groups: list[list[str]]) -> list[bool]:
    t = norm(text)
    return [any(norm(alt) in t for alt in grp) for grp in groups]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    xs = sorted(values)
    idx = (len(xs) - 1) * p / 100
    lo, hi = int(idx), min(int(idx) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (idx - lo)


# --------------------------------------------------------------------------- groundedness
JUDGE_PROMPT = """You are grading a retrieval-augmented answer for groundedness.

CONTEXT (the only allowed evidence):
{context}

ANSWER:
{answer}

Is every factual claim in the ANSWER fully supported by the CONTEXT, with nothing added or contradicted?
Ignore citation markers like [1]. Reply with JSON only: {{"grounded": true|false, "unsupported": "<short note or empty>"}}"""


def lexical_grounded(answer: str, context: str) -> tuple[bool, str]:
    ctx = norm(context)
    ctx_words = content_words(context)
    for sent in split_sentences(g.strip_citations(answer)) or [g.strip_citations(answer)]:
        nums = re.findall(r"\$?\d[\d,.:%/-]*\d|\$?\d+%?", sent)
        missing_nums = [n for n in nums if norm(n).rstrip(".") not in ctx]
        words = content_words(sent)
        coverage = len(words & ctx_words) / (len(words) or 1)
        if missing_nums or coverage < 0.8:
            return False, f"unsupported sentence: {sent[:120]!r} (coverage {coverage:.0%}, numbers {missing_nums})"
    return True, ""


class Judge:
    def __init__(self, settings):
        self.client = None
        if settings.llm_enabled:
            from rag.llm import LLMClient

            self.client = LLMClient(settings)
        self.settings = settings
        self.kind = f"llm-judge ({settings.judge_model})" if self.client else "lexical"

    def grounded(self, answer: str, context: str) -> tuple[bool, str]:
        if self.client is None:
            return lexical_grounded(answer, context)
        out = self.client.complete(
            [{"role": "user", "content": JUDGE_PROMPT.format(context=context, answer=answer)}], max_tokens=200,
            model=self.settings.judge_model, reasoning_effort=self.settings.judge_reasoning_effort,
        )
        m = re.search(r"\{.*\}", out, re.S)
        try:
            data = json.loads(m.group(0)) if m else {}
            return bool(data.get("grounded")), str(data.get("unsupported", ""))
        except json.JSONDecodeError:
            return ("true" in out.lower() and "false" not in out.lower()), out[:200]


# --------------------------------------------------------------------------- end-to-end eval
def run_end_to_end(questions: list[dict], settings, run_name: str, delay: float = 0.0) -> dict:
    import app as webapp

    pipeline = webapp.get_pipeline()
    retr = pipeline.retriever
    client = webapp.app.test_client()
    judge = Judge(settings)
    client.post("/chat", json={"question": "How many PTO days do I get?"})  # warm-up (model load)

    rows = []
    for q in questions:
        time.sleep(delay)  # stay under free-tier tokens/minute limits; not included in latency
        t = time.perf_counter()
        resp = client.post("/chat", json={"question": q["question"]})
        latency = (time.perf_counter() - t) * 1000
        data = resp.get_json()
        passages = retr.retrieve(q["question"])  # same deterministic retrieval the pipeline used
        by_n = {p.n: p for p in passages}
        context = "\n\n".join(f"[{p.n}] {p.text}" for p in passages)
        expect_refusal = bool(q.get("expect_refusal"))
        row = {
            "id": q["id"], "topic": q["topic"], "question": q["question"], "gold_answer": q["gold_answer"],
            "answer": data.get("answer"), "refused": data.get("refused"), "expect_refusal": expect_refusal,
            "citations": [{"n": c["n"], "doc_id": c["doc_id"], "section": c["section"]} for c in data.get("citations", [])],
            "retrieved_docs": [p.doc_id for p in passages], "latency_ms": round(latency, 1), "status": resp.status_code,
        }
        if not expect_refusal and not data.get("refused"):
            found = facts_found(data["answer"], q["must_include"])
            row["exact_match"] = all(found)
            row["partial_match"] = any(found)
            cited = [by_n[c["n"]] for c in data["citations"] if c["n"] in by_n]
            cited_docs_ok = bool(cited) and all(p.doc_id in q["gold_docs"] for p in cited)
            cited_text = " ".join(p.text for p in cited)
            row["citation_correct"] = cited_docs_ok and all(facts_found(cited_text, q["must_include"]))
            row["citation_precision"] = (sum(p.doc_id in q["gold_docs"] for p in cited) / len(cited)) if cited else 0.0
            row["grounded"], row["grounded_note"] = judge.grounded(data["answer"], context)
        rows.append(row)
        print(f"{q['id']:5} {latency:7.0f} ms  refused={row['refused']!s:5}  "
              f"exact={row.get('exact_match', '-')!s:5} cite={row.get('citation_correct', '-')!s:5} "
              f"grounded={row.get('grounded', '-')!s:5}  {(row['answer'] or '')[:70]!r}")

    in_scope = [r for r in rows if not r["expect_refusal"]]
    answered = [r for r in in_scope if not r["refused"]]
    oos = [r for r in rows if r["expect_refusal"]]
    lat = [r["latency_ms"] for r in rows]
    pct = lambda xs: round(100 * sum(xs) / len(xs), 1) if xs else None  # noqa: E731
    summary = {
        "run": run_name,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": pipeline.mode,
        "model": pipeline.model_name,
        "judge": judge.kind,
        "settings": {"reasoning_effort": settings.llm_reasoning_effort if pipeline.llm else None,
                     "top_k": settings.top_k, "rerank": settings.rerank, "chunk_size": settings.chunk_size,
                     "chunk_overlap": settings.chunk_overlap, "embedding_model": settings.embedding_model,
                     "temperature": settings.temperature, "max_answer_tokens": settings.max_answer_tokens},
        "n_questions": len(rows), "n_in_scope": len(in_scope), "n_answered": len(answered), "n_out_of_scope": len(oos),
        "groundedness_pct": pct([r["grounded"] for r in answered]),
        "citation_accuracy_pct": pct([r["citation_correct"] for r in answered]),
        "citation_precision_pct": pct([r["citation_precision"] for r in answered]),
        "exact_match_pct": pct([bool(r.get("exact_match")) for r in in_scope]),
        "partial_match_pct": pct([bool(r.get("partial_match")) for r in in_scope]),
        "answer_rate_in_scope_pct": pct([not r["refused"] for r in in_scope]),
        "refusal_accuracy_oos_pct": pct([bool(r["refused"]) for r in oos]),
        "latency_ms": {"p50": round(percentile(lat, 50), 1), "p95": round(percentile(lat, 95), 1),
                       "mean": round(statistics.mean(lat), 1), "max": round(max(lat), 1), "n": len(lat)},
    }
    out = RESULTS_DIR / run_name
    out.mkdir(parents=True, exist_ok=True)
    with (out / "per_question.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


# --------------------------------------------------------------------------- retrieval ablations
def retrieval_metrics(retriever, questions: list[dict], k: int, rerank: bool) -> dict:
    hits, evid, rr = [], [], []
    for q in questions:
        ps = retriever.retrieve(q["question"], k=k, rerank=rerank)
        docs = [p.doc_id for p in ps]
        hits.append(any(d in q["gold_docs"] for d in docs))
        evid.append(all(facts_found(" ".join(p.text for p in ps), q["must_include"])))
        rank = next((i for i, d in enumerate(docs, 1) if d in q["gold_docs"]), None)
        rr.append(1 / rank if rank else 0.0)
    n = len(questions)
    return {"hit_at_k": round(100 * sum(hits) / n, 1), "evidence_recall": round(100 * sum(evid) / n, 1),
            "mrr": round(sum(rr) / n, 3)}


def gate_scores(retriever, questions: list[dict]) -> list[dict]:
    out = []
    for q in questions:
        ps = retriever.retrieve(q["question"], k=1, rerank=True)
        out.append({"id": q["id"], "oos": bool(q.get("expect_refusal")),
                    "top_rerank": round(ps[0].rerank_score, 2), "top_similarity": round(ps[0].similarity, 3)})
    return out


def run_ablations(questions: list[dict], settings) -> dict:
    from rag.ingest import build_index
    from rag.retriever import Retriever

    sets = {
        "standard": [q for q in questions if not q.get("expect_refusal")],
        "hard_paraphrase": load_questions(EVAL_DIR / "retrieval_hard.jsonl"),
    }
    results: dict = {"k_and_rerank": [], "chunk_size": []}
    base = Retriever(settings)
    for set_name, qs in sets.items():
        for rerank in (False, True):
            for k in (1, 2, 4, 6, 8):
                row = {"set": set_name, "n": len(qs), "k": k, "rerank": rerank, **retrieval_metrics(base, qs, k, rerank)}
                results["k_and_rerank"].append(row)
                print("ablation", row)
    for size, overlap in ((120, 25), (220, 40), (400, 60)):
        s = get_settings(chunk_size=size, chunk_overlap=overlap, index_dir=ROOT / "index_ablation" / f"cs{size}",
                         rerank=True)
        manifest = build_index(s, verbose=False)
        r = Retriever(s)
        for set_name, qs in sets.items():
            for rerank in (False, True):
                row = {"set": set_name, "chunk_size": size, "overlap": overlap, "chunks": manifest["num_chunks"],
                       "k": settings.top_k, "rerank": rerank, **retrieval_metrics(r, qs, settings.top_k, rerank)}
                results["chunk_size"].append(row)
                print("ablation", row)
    results["gate_scores"] = gate_scores(base, questions + sets["hard_paraphrase"])
    (RESULTS_DIR / "ablations.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", type=int, help="evaluate a seeded random subset of N questions")
    ap.add_argument("--ablations", action="store_true", help="also run retrieval ablations")
    ap.add_argument("--ablations-only", action="store_true")
    ap.add_argument("--run-name", help="results sub-folder (default: <mode>)")
    ap.add_argument("--delay", type=float, default=0.0,
                    help="seconds to pause between questions (rate limits); excluded from latency")
    a = ap.parse_args(argv)

    random.seed(SEED)
    settings = get_settings()
    questions = load_questions()
    if a.sample:
        questions = random.sample(questions, min(a.sample, len(questions)))
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if not a.ablations_only:
        run_name = a.run_name or ("llm" if settings.llm_enabled else "extractive")
        summary = run_end_to_end(questions, settings, run_name, a.delay)
        print(json.dumps(summary, indent=2))
    if a.ablations or a.ablations_only:
        run_ablations(load_questions(), settings)


if __name__ == "__main__":
    main()
