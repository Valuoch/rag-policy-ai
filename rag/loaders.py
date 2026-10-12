"""Parse and clean policy documents (Markdown, HTML, TXT, PDF) into heading-delimited sections.

Every loader returns a :class:`Document` whose ``sections`` keep the heading path, so the
chunker can split along the document's own structure and citations can name the section.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

SUPPORTED_EXTENSIONS = {".md", ".markdown", ".html", ".htm", ".txt", ".pdf"}

_DOC_ID_RE = re.compile(r"^([A-Z]{2,5}-\d{3})")
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
# Plain-text / PDF headings: "4. PURPOSE", "4.2 Air Travel", "8.2 30/60/90-day check-ins" (short, no
# final period). The dot after the first number is required so wrapped lines such as
# "10 business days after ..." are not mistaken for headings.
_TEXT_HEADING_RE = re.compile(r"^(\d+\.(?:\d+\.?)*)\s+([A-Za-z0-9][^\n]{1,90})$")


@dataclass
class Section:
    heading: str  # e.g. "4. Requesting PTO > 4.1 Notice periods"
    text: str
    index: int = 0


@dataclass
class Document:
    doc_id: str
    title: str
    source: str  # file name relative to the corpus dir
    fmt: str
    sections: list[Section] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(s.text for s in self.sections)

    @property
    def word_count(self) -> int:
        return sum(len(s.text.split()) for s in self.sections)


# --------------------------------------------------------------------------- cleaning
def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace(" ", " ").replace("​", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_md_inline(line: str) -> str:
    line = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", line)  # images
    line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)  # links
    line = re.sub(r"(\*\*|__)(.+?)\1", r"\2", line)  # bold
    line = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"\1", line)  # italics
    line = re.sub(r"`([^`]+)`", r"\1", line)
    return line


def _md_table_row(line: str) -> str | None:
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|")):
        return None
    cells = [c.strip() for c in s.strip("|").split("|")]
    if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
        return ""  # separator row
    return " | ".join(cells)


class _SectionBuilder:
    """Accumulates text under a heading stack; emits a Section whenever a heading changes."""

    def __init__(self) -> None:
        self.stack: list[tuple[int, str]] = []
        self.buf: list[str] = []
        self.sections: list[Section] = []

    def heading(self, level: int, title: str) -> None:
        self.flush()
        while self.stack and self.stack[-1][0] >= level:
            self.stack.pop()
        self.stack.append((level, title.strip()))

    def add(self, line: str) -> None:
        self.buf.append(line)

    def flush(self) -> None:
        text = clean_text("\n".join(self.buf))
        self.buf = []
        if not text:
            return
        # The level-1 heading is the document title, so it is left out of the path.
        path = " > ".join(t for lvl, t in self.stack if lvl > 1) or (self.stack[0][1] if self.stack else "Overview")
        self.sections.append(Section(heading=path, text=text, index=len(self.sections)))

    def done(self) -> list[Section]:
        self.flush()
        return self.sections


# --------------------------------------------------------------------------- loaders
def _load_markdown(raw: str) -> tuple[str | None, list[Section]]:
    b = _SectionBuilder()
    title = None
    in_code = False
    for line in raw.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        m = _MD_HEADING_RE.match(line) if not in_code else None
        if m:
            level, text = len(m.group(1)), _strip_md_inline(m.group(2))
            if level == 1 and title is None:
                title = text
            b.heading(level, text)
            continue
        row = _md_table_row(line)
        if row is not None:
            if row:
                b.add(row)
            continue
        if re.fullmatch(r"\s*(-{3,}|\*{3,}|_{3,})\s*", line):
            continue
        line = re.sub(r"^\s*>\s?", "", line)
        b.add(_strip_md_inline(line))
    return title, b.done()


def _load_html(raw: str) -> tuple[str | None, list[Section]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else None
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()
    root = soup.body or soup
    b = _SectionBuilder()
    block_tags = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "tr", "dt", "dd", "pre", "blockquote", "caption"]
    for el in root.find_all(block_tags):
        # Skip blocks nested in another block we already emit (e.g. <p> inside <li>).
        if el.name != "tr" and el.find_parent(["li", "tr", "blockquote", "dd"]):
            continue
        name = el.name
        if name.startswith("h") and len(name) == 2:
            text = el.get_text(" ", strip=True)
            b.heading(int(name[1]), text)
        elif name == "tr":
            cells = [c.get_text(" ", strip=True) for c in el.find_all(["th", "td"])]
            if any(cells):
                b.add(" | ".join(cells))
        elif name == "li":
            b.add("- " + el.get_text(" ", strip=True))
        else:
            b.add(el.get_text(" ", strip=True))
    return title, b.done()


def _load_plaintext(raw: str) -> tuple[str | None, list[Section]]:
    """TXT and extracted PDF text. Headings are numbered lines ('4.2 AIR TRAVEL') or markdown-style '#'."""
    b = _SectionBuilder()
    title = None
    m = re.search(r"^\s*Title:\s*(.+)$", raw, re.MULTILINE)
    if m:
        title = m.group(1).strip()
    for line in raw.splitlines():
        s = line.strip()
        md = _MD_HEADING_RE.match(s)
        if md:
            level = len(md.group(1))
            title = title or (md.group(2) if level == 1 else None)
            b.heading(level, md.group(2))
            continue
        tm = _TEXT_HEADING_RE.match(s)
        if tm and not s.endswith((".", ",", ";", ":")) and len(s.split()) <= 12:
            depth = len([p for p in tm.group(1).split(".") if p]) + 1  # "4." -> level 2, "4.2" -> level 3
            b.heading(depth, s.title() if s.isupper() else s)
            continue
        b.add(s)
    if title is None:
        first = next((ln.strip() for ln in raw.splitlines() if ln.strip()), "")
        title = first[:120] or None
    return title, b.done()


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [(p.extract_text() or "") for p in reader.pages]
    text = "\n".join(pages)
    # Drop running page footers such as "Page 3 of 9" and de-hyphenate wrapped words.
    text = re.sub(r"(?m)^\s*Page \d+ of \d+\s*$", "", text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    return _reflow(text)


def _reflow(text: str) -> str:
    """Join visually wrapped PDF lines back into paragraphs (headings and bullets start new blocks)."""
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            out.append("")
            continue
        new_block = s.startswith(("- ", "•")) or _TEXT_HEADING_RE.match(s) or _MD_HEADING_RE.match(s)
        if len(out) >= 2 and out[-1] == "" and s[0].islower():
            out.pop()  # blank line from a page break in the middle of a sentence
        prev = out[-1] if out else ""
        if prev and not new_block and not _TEXT_HEADING_RE.match(prev) and not prev.endswith((".", ":", "?", "!")):
            out[-1] = f"{prev} {s}"
        else:
            out.append(s)
    return "\n".join(out)


def load_document(path: Path, corpus_dir: Path | None = None) -> Document:
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {path.name}")
    if ext == ".pdf":
        raw, fmt = _read_pdf(path), "pdf"
        title, sections = _load_plaintext(raw)
    else:
        raw = path.read_text(encoding="utf-8", errors="replace")
        if ext in (".md", ".markdown"):
            fmt = "md"
            title, sections = _load_markdown(raw)
        elif ext in (".html", ".htm"):
            fmt = "html"
            title, sections = _load_html(raw)
        else:
            fmt = "txt"
            title, sections = _load_plaintext(raw)

    m = _DOC_ID_RE.match(path.stem)
    doc_id = m.group(1) if m else path.stem
    if title:
        # Titles are often written as "HR-002 Paid Time Off..." or "HR-002: ..." - keep just the name.
        title = re.sub(rf"^{re.escape(doc_id)}\s*[:\-–—|]?\s*", "", title).strip() or title
    source = str(path.relative_to(corpus_dir)) if corpus_dir else path.name
    return Document(doc_id=doc_id, title=title or doc_id, source=source.replace("\\", "/"), fmt=fmt, sections=sections)


def load_corpus(corpus_dir: Path) -> list[Document]:
    files = sorted(p for p in corpus_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS)
    docs = [load_document(p, corpus_dir) for p in files]
    seen: dict[str, str] = {}
    for d in docs:
        if d.doc_id in seen:
            raise ValueError(f"Duplicate doc id {d.doc_id}: {seen[d.doc_id]} and {d.source}")
        seen[d.doc_id] = d.source
    return docs
