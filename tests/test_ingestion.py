from pathlib import Path

from rag.chunking import chunk_document
from rag.config import get_settings
from rag.loaders import Document, Section, load_corpus, load_document


def test_corpus_loads_all_formats():
    docs = load_corpus(get_settings().corpus_dir)
    assert 5 <= len(docs) <= 20
    assert {d.fmt for d in docs} == {"md", "html", "txt", "pdf"}
    assert len({d.doc_id for d in docs}) == len(docs)
    for d in docs:
        assert d.title and d.title != d.doc_id
        assert d.word_count > 1000
        assert len(d.sections) > 5


def test_markdown_sections_and_cleaning(tmp_path: Path):
    p = tmp_path / "XX-001_test.md"
    p.write_text(
        "# XX-001 Test Policy\n\nIntro **bold** and [a link](http://x).\n\n"
        "## 1. Purpose\nWhy.\n\n## 2. Rules\n### 2.1 Limits\n| Item | Cap |\n|---|---|\n| Hotel | $250 |\n",
        encoding="utf-8",
    )
    d = load_document(p)
    assert d.doc_id == "XX-001" and d.title == "Test Policy"
    headings = [s.heading for s in d.sections]
    assert headings == ["XX-001 Test Policy", "1. Purpose", "2. Rules > 2.1 Limits"]
    assert "Intro bold and a link." in d.sections[0].text
    assert "Hotel | $250" in d.sections[2].text


def test_html_and_text_headings(tmp_path: Path):
    h = tmp_path / "XX-002_page.html"
    h.write_text("<html><head><title>T</title><style>p{}</style></head><body><h1>XX-002 Page</h1>"
                 "<h2>1. Scope</h2><p>All staff.</p><ul><li>One</li></ul>"
                 "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table></body></html>")
    d = load_document(h)
    assert d.title == "Page"
    assert d.sections[-1].heading == "1. Scope"
    assert "- One" in d.sections[-1].text and "1 | 2" in d.sections[-1].text

    t = tmp_path / "XX-003_doc.txt"
    t.write_text("Title: Some Policy\n\n1. PURPOSE\n\nText here.\n10 business days after leaving\n\n4.2 AIR TRAVEL\n\nFly.\n")
    d = load_document(t)
    assert d.title == "Some Policy"
    assert [s.heading for s in d.sections][-2:] == ["1. Purpose", "1. Purpose > 4.2 Air Travel"]
    assert "10 business days after leaving" in d.sections[-2].text


def test_chunking_is_deterministic_with_overlap():
    words = " ".join(f"w{i}." for i in range(500))
    doc = Document("XX-009", "T", "x.md", "md", [Section("1. Big", words, 0)])
    a = chunk_document(doc, size=100, overlap=20)
    b = chunk_document(doc, size=100, overlap=20)
    assert [c.chunk_id for c in a] == [c.chunk_id for c in b]
    assert all(len(c.text.split()) <= 100 for c in a)
    assert len(a) >= 6
    assert a[0].text.split()[-20:] == a[1].text.split()[:20]  # overlap carried over
    assert a[0].embed_text.startswith("XX-009 T > 1. Big")


def test_small_sections_are_merged():
    secs = [Section("1. Purpose", "Short purpose.", 0), Section("2. Scope", "word " * 60, 1)]
    chunks = chunk_document(Document("XX-010", "T", "x.md", "md", secs), size=220, overlap=40, min_words=40)
    assert len(chunks) == 1 and "Short purpose." in chunks[0].text
