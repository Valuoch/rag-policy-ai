"""Build the CI run report (Markdown) shown on the GitHub Actions run page.

Inputs (all optional; missing ones are reported as such):
  reports/junit.xml        pytest results
  reports/health.json      GET /health from the smoke-tested server
  reports/chat.json        POST /chat sample answer
  reports/refusal.json     POST /chat out-of-scope sample
  index/manifest.json      corpus + index statistics
  eval/results/*/summary.json   latest committed evaluation results

Output: reports/ci-report.md, also appended to $GITHUB_STEP_SUMMARY when set.
"""

from __future__ import annotations

import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def tests_section() -> tuple[list[str], bool]:
    path = REPORTS / "junit.xml"
    if not path.exists():
        return ["## Tests", "", "_No pytest report found._", ""], False
    root = ET.parse(path).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    total, failures, errors, skipped = (int(suite.get(k, 0)) for k in ("tests", "failures", "errors", "skipped"))
    passed = total - failures - errors - skipped
    ok = failures == 0 and errors == 0
    lines = ["## Tests", "", f"{'✅' if ok else '❌'} **{passed}/{total} passed** "
             f"({failures} failed, {errors} errors, {skipped} skipped) in {float(suite.get('time', 0)):.1f}s", "",
             "<details><summary>Test cases</summary>", "", "| Test | Result | Time |", "|---|---|---|"]
    for case in suite.iter("testcase"):
        name = f"{case.get('classname', '').split('.')[-1]}::{case.get('name')}"
        status = "❌ fail" if case.find("failure") is not None or case.find("error") is not None else (
            "⏭ skip" if case.find("skipped") is not None else "✅ pass")
        lines.append(f"| `{name}` | {status} | {float(case.get('time', 0)):.2f}s |")
    lines += ["", "</details>", ""]
    return lines, ok


def corpus_section() -> list[str]:
    m = _json(ROOT / "index" / "manifest.json")
    if not m:
        return ["## Corpus & index", "", "_Index manifest not found._", ""]
    words = sum(d["words"] for d in m["documents"])
    fmts: dict[str, int] = {}
    for d in m["documents"]:
        fmts[d["format"]] = fmts.get(d["format"], 0) + 1
    lines = ["## Corpus & index", "",
             f"**{m['num_documents']} documents** ({', '.join(f'{v} {k}' for k, v in sorted(fmts.items()))}), "
             f"{words:,} words (~{words / 500:.0f} pages) → **{m['num_chunks']} chunks** "
             f"(chunk {m['chunk_size']} words, overlap {m['chunk_overlap']}), embeddings `{m['embedding_model']}`.", "",
             "<details><summary>Documents</summary>", "", "| ID | Title | Format | Words | Sections |", "|---|---|---|---|---|"]
    for d in m["documents"]:
        lines.append(f"| {d['doc_id']} | {d['title']} | {d['format']} | {d['words']:,} | {len(d['sections'])} |")
    lines += ["", "</details>", ""]
    return lines


def smoke_section() -> tuple[list[str], bool]:
    health, chat, refusal = (_json(REPORTS / f) for f in ("health.json", "chat.json", "refusal.json"))
    ok = bool(health and health.get("status") == "ok" and chat and chat.get("citations") and not chat.get("refused")
              and refusal and refusal.get("refused"))
    lines = ["## Server smoke test (gunicorn)", ""]
    if health:
        lines.append(f"- `GET /health` → status **{health.get('status')}**, index_ready={health.get('index_ready')}, "
                     f"{health.get('documents')} docs / {health.get('chunks')} chunks, mode `{health.get('llm_mode')}`")
    else:
        lines.append("- `GET /health` → ❌ no response")
    if chat:
        lines += [f"- `POST /chat` → {'✅' if chat.get('citations') and not chat.get('refused') else '❌'} "
                  f"{len(chat.get('citations', []))} citation(s), {chat.get('latency_ms')} ms", "",
                  f"> **Q:** {chat.get('question')}", ">", f"> **A:** {chat.get('answer')}", ">"]
        for c in chat.get("citations", []):
            lines.append(f"> [{c['n']}] **{c['doc_id']}** {c['title']} § {c['section']}: _{c['snippet']}_")
        lines.append("")
    else:
        lines.append("- `POST /chat` → ❌ no response")
    if refusal:
        lines.append(f"- Out-of-scope guardrail (`{refusal.get('question')}`) → "
                     f"{'✅ refused' if refusal.get('refused') else '❌ answered'}")
    lines.append("")
    return lines, ok


def eval_section() -> list[str]:
    rows = []
    for p in sorted((ROOT / "eval" / "results").glob("*/summary.json")):
        s = _json(p)
        if s:
            rows.append(s)
    if not rows:
        return ["## Evaluation (latest committed results)", "", "_No evaluation results committed._", ""]
    fmt = lambda v: "-" if v is None else f"{v}%"  # noqa: E731
    n = rows[0]
    lines = ["## Evaluation (latest committed results)", "",
             "**What this is:** PolicyBot's scores on a fixed test of "
             f"{n['n_questions']} questions with answers prepared in advance: {n['n_in_scope']} real policy questions "
             f"(e.g. *How many PTO days after 4 years?*) and {n['n_out_of_scope']} deliberately off-topic ones "
             "(e.g. *What is Lumora's stock price?*) that it should politely decline. The exam is run with "
             "`python -m eval.run_eval` and the results are committed to `eval/results/`. CI only displays them, "
             "because running the exam calls the AI service.", "",
             "| Run | Model | Groundedness | Citation acc. | Exact / partial | OOS refused | Latency p50 / p95 |",
             "|---|---|---|---|---|---|---|"]
    for s in rows:
        lat = s.get("latency_ms", {})
        lines.append(f"| {s['run']} ({s['timestamp'][:10]}) | `{s['model']}` | {fmt(s.get('groundedness_pct'))} "
                     f"| {fmt(s.get('citation_accuracy_pct'))} | {fmt(s.get('exact_match_pct'))} / "
                     f"{fmt(s.get('partial_match_pct'))} | {fmt(s.get('refusal_accuracy_oos_pct'))} "
                     f"| {lat.get('p50')} / {lat.get('p95')} ms |")
    lines += ["", "**The two modes**", "",
              "- **llm**: an AI model writes a short answer using only the 4 best-matching policy passages, and "
              "cites them as [1], [2]...",
              "- **extractive**: the backup mode used when no AI key is set. Nothing is written; the most relevant "
              "sentences are copied straight from the policies. It is grounded by construction but less complete, and "
              "it can't always recognise off-topic questions.", "",
              "<details><summary><b>What each column means</b></summary>", "",
              "| Column | Meaning |", "|---|---|",
              "| **Run** | Which mode was tested, and on what date. |",
              "| **Model** | What produced the answers. |",
              "| **Groundedness** | % of answers fully supported by the retrieved policy text, with nothing made up "
              "(judged by a *different* AI model in llm mode, or by a strict word/number check in extractive mode). |",
              "| **Citation acc.** | % of answers whose numbered sources all come from the right policy **and** contain "
              "the facts stated, so the link really proves the answer. |",
              "| **Exact / partial** | % of answers containing **all** / **at least one** of the key facts from the "
              "prepared answer. |",
              "| **OOS refused** | % of the out-of-scope (off-topic) questions correctly declined instead of answered. |",
              "| **Latency p50 / p95** | Time from question to answer. Half of answers were faster than p50, and 95% "
              "were faster than p95. |", "", "</details>", ""]
    lines += _misses(rows)
    return lines


def _misses(rows: list[dict]) -> list[str]:
    """Per run: the questions that did not get full marks, and why (read from per_question.jsonl)."""
    out = ["**Where points were lost**", ""]
    for s in rows:
        path = ROOT / "eval" / "results" / s["run"] / "per_question.jsonl"
        try:
            qs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except OSError:
            continue
        issues = []
        for q in qs:
            if q.get("expect_refusal"):
                if not q.get("refused"):
                    issues.append(f"{q['id']} *{q['question']}*: off-topic but answered instead of declined")
                continue
            if q.get("refused"):
                issues.append(f"{q['id']} *{q['question']}*: declined although the policies answer it")
                continue
            why = []
            if not q.get("exact_match"):
                why.append("missed a key fact" if q.get("partial_match") else "missed the key facts")
            if not q.get("citation_correct"):
                why.append("a source did not contain the fact")
            if not q.get("grounded"):
                note = (q.get("grounded_note") or "").strip()
                why.append("judged not fully supported" + (f" ({note[:160]})" if note else ""))
            if why:
                issues.append(f"{q['id']} *{q['question']}*: {'; '.join(why)}")
        out.append(f"- **{s['run']}**: " + ("full marks on every question." if not issues else
                                            f"{len(issues)} question(s) below full marks:"))
        out += [f"  - {i}" for i in issues]
    out.append("")
    return out


def main() -> int:
    test_lines, tests_ok = tests_section()
    smoke_lines, smoke_ok = smoke_section()
    verdict = "✅ **Build passed**" if tests_ok and smoke_ok else "❌ **Build failed**"
    sha = os.getenv("GITHUB_SHA", "")[:7]
    header = ["# PolicyBot CI report", "",
              f"{verdict} · commit `{sha or 'local'}` · Python {sys.version.split()[0]}", ""]
    if (ROOT / "PolicyBot-Project-Report.pdf").exists():
        repo, server = os.getenv("GITHUB_REPOSITORY"), os.getenv("GITHUB_SERVER_URL", "https://github.com")
        link = (f"{server}/{repo}/blob/{os.getenv('GITHUB_SHA')}/PolicyBot-Project-Report.pdf" if repo
                else "PolicyBot-Project-Report.pdf")
        header += [f"📄 **[Plain-English project report (PDF)]({link})**: a step-by-step account of the project for "
                   "non-technical readers (also included in the `ci-report` artifact below).", ""]
    md = "\n".join(header + test_lines + smoke_lines + corpus_section() + eval_section())
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "ci-report.md").write_text(md, encoding="utf-8")
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(md + "\n")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
