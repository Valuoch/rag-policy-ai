"""Input/output guardrails: question validation, refusal, citation enforcement, length limits."""

from __future__ import annotations

import re

REFUSAL = (
    "I can only answer questions about our company policies and procedures, and I couldn't "
    "find information about that in the policy documents."
)

_CITE_RE = re.compile(r"\[(\d{1,2}(?:\s*,\s*\d{1,2})*)\]")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class InvalidQuestion(ValueError):
    pass


def clean_question(q: object, max_chars: int) -> str:
    if not isinstance(q, str):
        raise InvalidQuestion("'question' must be a string")
    q = _CONTROL_RE.sub("", q).strip()
    if not q:
        raise InvalidQuestion("'question' must not be empty")
    if len(q) > max_chars:
        raise InvalidQuestion(f"'question' must be at most {max_chars} characters")
    return q


def is_refusal(answer: str) -> bool:
    a = answer.strip().lower()
    return a.startswith("i can only answer") or "couldn't find information about that in the policy" in a


def cited_numbers(answer: str) -> list[int]:
    """Return citation numbers in order of first appearance, e.g. '... [2][1, 3]' -> [2, 1, 3]."""
    seen: list[int] = []
    for m in _CITE_RE.finditer(answer):
        for part in m.group(1).split(","):
            n = int(part)
            if n not in seen:
                seen.append(n)
    return seen


def drop_invalid_citations(answer: str, valid: set[int]) -> str:
    def repl(m: re.Match) -> str:
        keep = [p.strip() for p in m.group(1).split(",") if int(p) in valid]
        return f"[{', '.join(keep)}]" if keep else ""

    return re.sub(r"\s+([.,;:])", r"\1", _CITE_RE.sub(repl, answer)).strip()


def strip_citations(answer: str) -> str:
    return re.sub(r"\s{2,}", " ", _CITE_RE.sub("", answer)).strip()


def limit_length(answer: str, max_chars: int) -> str:
    """Hard cap on answer length, cut at the last sentence boundary that fits."""
    if len(answer) <= max_chars:
        return answer
    cut = answer[:max_chars]
    m = list(re.finditer(r"[.!?](?:\s*\[[\d, ]+\])*(?=\s|$)", cut))
    if m and m[-1].end() > max_chars * 0.3:
        return cut[: m[-1].end()].strip()
    return cut.rsplit(" ", 1)[0].rstrip(",;:") + " ..."
