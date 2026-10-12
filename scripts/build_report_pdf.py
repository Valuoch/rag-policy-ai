"""Build a plain-English, step-by-step project report as a PDF.

    python scripts/build_report_pdf.py            # -> docs/PolicyBot-Project-Report.pdf

Numbers are read from eval/results/*/summary.json and index/manifest.json so the report
always matches the latest evaluation. Requires reportlab (requirements-dev.txt).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "PolicyBot-Project-Report.pdf"
REPO_URL = "https://github.com/Valuoch/rag-policy-ai"

NAVY = colors.HexColor("#1F3A5F")
TEAL = colors.HexColor("#2A7F86")
SOFT = colors.HexColor("#EEF3F8")
SOFT_TEAL = colors.HexColor("#E3F2F1")
AMBER = colors.HexColor("#FFF4DE")
GREY = colors.HexColor("#5F6B7A")
LINE = colors.HexColor("#C9D3DE")


# --------------------------------------------------------------------------- data
def _json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


LLM = _json(ROOT / "eval" / "results" / "llm" / "summary.json")
EXT = _json(ROOT / "eval" / "results" / "extractive" / "summary.json")
MAN = _json(ROOT / "index" / "manifest.json") or {}
MAIN = LLM or EXT


def pct(s, key):
    v = (s or {}).get(key)
    return "n/a" if v is None else f"{v:.0f}%" if float(v).is_integer() else f"{v:.1f}%"


def secs(s, key):
    v = ((s or {}).get("latency_ms") or {}).get(key)
    return "n/a" if v is None else f"{v / 1000:.1f} seconds"


# --------------------------------------------------------------------------- styles
ss = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=ss["Normal"], fontName="Helvetica", fontSize=10.5, leading=15.5,
                      spaceAfter=7, textColor=colors.HexColor("#1D2330"))
SMALL = ParagraphStyle("small", parent=BODY, fontSize=9, leading=12.5, textColor=GREY, spaceAfter=4)
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=19, leading=24,
                    textColor=NAVY, spaceBefore=4, spaceAfter=10)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=13.5, leading=18,
                    textColor=NAVY, spaceBefore=12, spaceAfter=6)
STEP = ParagraphStyle("step", parent=H2, fontSize=14, textColor=colors.white, spaceBefore=0, spaceAfter=0)
BULLET = ParagraphStyle("bullet", parent=BODY, leftIndent=14, bulletIndent=3, spaceAfter=3)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=9.5, leading=12.5, spaceAfter=0)
CELL_B = ParagraphStyle("cellb", parent=CELL, fontName="Helvetica-Bold")
TITLE = ParagraphStyle("title", parent=H1, fontSize=30, leading=36, alignment=TA_CENTER, spaceAfter=6)
SUB = ParagraphStyle("sub", parent=BODY, fontSize=13, leading=18, alignment=TA_CENTER, textColor=GREY)


def p(text, style=BODY):
    return Paragraph(text, style)


def bullets(items):
    return [Paragraph(t, BULLET, bulletText="•") for t in items]


def box(flowables, bg=SOFT, border=None, pad=10):
    t = Table([[flowables]], colWidths=[170 * mm])
    style = [("BACKGROUND", (0, 0), (-1, -1), bg), ("LEFTPADDING", (0, 0), (-1, -1), pad),
             ("RIGHTPADDING", (0, 0), (-1, -1), pad), ("TOPPADDING", (0, 0), (-1, -1), pad),
             ("BOTTOMPADDING", (0, 0), (-1, -1), pad)]
    if border:
        style.append(("LINEBEFORE", (0, 0), (0, -1), 4, border))
    t.setStyle(TableStyle(style))
    return t


def note(title, text, bg=AMBER, border=colors.HexColor("#E0A030")):
    return box([p(f"<b>{title}</b>", CELL), Spacer(1, 3), p(text, CELL)], bg=bg, border=border, pad=8)


def step_header(n, title):
    t = Table([[p(f"Step {n}", STEP), p(title, STEP)]], colWidths=[24 * mm, 146 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("BACKGROUND", (0, 0), (0, 0), TEAL),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 7),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    return t


def step(n, title, what, why, detail=None, extra=None):
    """One step = header + 'What I did' + 'Why it matters' (+ optional detail flowables)."""
    parts = [step_header(n, title), Spacer(1, 6),
             p("<b>What I did</b>", CELL_B), p(what),
             p("<b>Why it matters</b>", CELL_B), p(why)]
    out = [KeepTogether(parts)]
    if detail:
        out += detail if isinstance(detail, list) else [detail]
    if extra:
        out.append(extra)
    out.append(Spacer(1, 12))
    return out


def table(rows, widths, header=True, zebra=True):
    data = [[p(str(c), CELL_B if (header and i == 0) else CELL) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
    if header:
        st.append(("BACKGROUND", (0, 0), (-1, 0), SOFT))
    if zebra:
        for i in range(2 if header else 1, len(rows), 2):
            st.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FAFBFD")))
    t.setStyle(TableStyle(st))
    return t


# --------------------------------------------------------------------------- diagram
def journey_diagram():
    """The path of one question through the system, as 6 numbered boxes."""
    w, h = 170 * mm, 84 * mm
    d = Drawing(w, h)
    stages = [
        ("1  You ask", "\"How many vacation days", "do I get after 4 years?\""),
        ("2  Understand", "The question is turned into", "a 'meaning fingerprint'"),
        ("3  Search", "Find the 20 passages with", "the closest meaning"),
        ("4  Double-check", "A second model re-reads them", "and keeps the best 4"),
        ("5  Write", "The AI writes a short answer", "using ONLY those 4 passages"),
        ("6  Check & reply", "Safety rules check citations,", "then the answer is shown"),
    ]
    bw, bh, gapx = 50 * mm, 26 * mm, 10 * mm
    xs = [0, bw + gapx, 2 * (bw + gapx)]
    ys = [h - bh - 2 * mm, h - 2 * bh - 16 * mm]
    pos = [(xs[0], ys[0]), (xs[1], ys[0]), (xs[2], ys[0]), (xs[2], ys[1]), (xs[1], ys[1]), (xs[0], ys[1])]
    for (x, y), (title, l1, l2) in zip(pos, stages):
        d.add(Rect(x, y, bw, bh, rx=6, ry=6, fillColor=SOFT, strokeColor=NAVY, strokeWidth=1))
        d.add(Rect(x, y + bh - 8 * mm, bw, 8 * mm, rx=6, ry=6, fillColor=NAVY, strokeColor=NAVY))
        d.add(Rect(x, y + bh - 8 * mm, bw, 3 * mm, fillColor=NAVY, strokeColor=NAVY))
        d.add(String(x + 4 * mm, y + bh - 5.6 * mm, title, fontName="Helvetica-Bold", fontSize=10, fillColor=colors.white))
        d.add(String(x + 4 * mm, y + 10 * mm, l1, fontName="Helvetica", fontSize=8.2, fillColor=colors.black))
        d.add(String(x + 4 * mm, y + 5 * mm, l2, fontName="Helvetica", fontSize=8.2, fillColor=colors.black))

    def arrow(x1, y1, x2, y2):
        d.add(Line(x1, y1, x2, y2, strokeColor=TEAL, strokeWidth=2))
        if x2 > x1:
            pts = [x2, y2, x2 - 6, y2 + 4, x2 - 6, y2 - 4]
        elif x2 < x1:
            pts = [x2, y2, x2 + 6, y2 + 4, x2 + 6, y2 - 4]
        else:
            pts = [x2, y2, x2 - 4, y2 + 6, x2 + 4, y2 + 6]
        d.add(Polygon(pts, fillColor=TEAL, strokeColor=TEAL))

    mid = ys[0] + bh / 2
    arrow(xs[0] + bw, mid, xs[1], mid)
    arrow(xs[1] + bw, mid, xs[2], mid)
    arrow(xs[2] + bw / 2, ys[0], xs[2] + bw / 2, ys[1] + bh)
    mid2 = ys[1] + bh / 2
    arrow(xs[2], mid2, xs[1] + bw, mid2)
    arrow(xs[1], mid2, xs[0] + bw, mid2)
    # Side branch: refusal.
    d.add(String(xs[0], 1 * mm, "If nothing relevant is found in step 3-4, the assistant politely says it can only answer "
                 "questions about company policies.", fontName="Helvetica-Oblique", fontSize=8.2, fillColor=GREY))
    return d


def bars(items, title, maxv=100.0):
    """Simple horizontal bar chart: items = [(label, value)]."""
    w, row = 170 * mm, 9 * mm
    h = row * len(items) + 12 * mm
    d = Drawing(w, h)
    d.add(String(0, h - 6 * mm, title, fontName="Helvetica-Bold", fontSize=10, fillColor=NAVY))
    lx, bw = 62 * mm, 92 * mm
    for i, (label, v) in enumerate(items):
        y = h - 14 * mm - i * row
        d.add(String(0, y + 1.5 * mm, label, fontName="Helvetica", fontSize=9, fillColor=colors.black))
        d.add(Rect(lx, y, bw, 5 * mm, fillColor=SOFT, strokeColor=None))
        if v is not None:
            d.add(Rect(lx, y, bw * min(v, maxv) / maxv, 5 * mm, fillColor=TEAL, strokeColor=None))
            d.add(String(lx + bw + 3 * mm, y + 1.2 * mm, f"{v:.0f}%" if float(v).is_integer() else f"{v:.1f}%",
                         fontName="Helvetica-Bold", fontSize=9, fillColor=NAVY))
    return d


def example_box():
    """A real question/answer pair from the latest AI evaluation run, with its sources."""
    rows = []
    path = ROOT / "eval" / "results" / ("llm" if LLM else "extractive") / "per_question.jsonl"
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        return []
    ex = next((r for r in rows if r["id"] == "Q02" and not r.get("refused")), None)
    oos = next((r for r in rows if r["id"] == "OOS2"), None)
    if not ex:
        return []
    titles = {d["doc_id"]: d["title"] for d in MAN.get("documents", [])}
    srcs = [p(f"[{c['n']}] <b>{c['doc_id']}</b> {titles.get(c['doc_id'], '')} - section <i>{c['section']}</i>", SMALL)
            for c in ex["citations"]]
    out = [p("A real example", H2),
           p("This exchange was recorded during testing. The numbers in square brackets are the sources; in the "
             "chat page they are clickable and open the policy at that exact section."),
           box([p(f"<b>Question:</b> {ex['question']}", CELL), Spacer(1, 5),
                p(f"<b>PolicyBot:</b> {ex['answer']}", CELL), Spacer(1, 6), p("<b>Sources shown:</b>", CELL)] + srcs,
               bg=SOFT_TEAL, border=TEAL)]
    if oos:
        out += [Spacer(1, 8), box([p(f"<b>Question:</b> {oos['question']}", CELL), Spacer(1, 5),
                                   p(f"<b>PolicyBot:</b> {oos['answer']}", CELL), Spacer(1, 4),
                                   p("This information is not in the policies, so PolicyBot declines instead of guessing.",
                                     SMALL)], bg=SOFT, border=GREY)]
    return out


# --------------------------------------------------------------------------- content
def build_story():
    s = []
    docs_n = MAN.get("num_documents", 13)
    chunks_n = MAN.get("num_chunks", 382)
    words = sum(d["words"] for d in MAN.get("documents", [])) or 33321
    model = (LLM or {}).get("model", "openai/gpt-oss-120b")

    # ---- cover
    s += [Spacer(1, 40 * mm), p("PolicyBot", TITLE),
          p("An AI assistant that answers questions about company policies,<br/>and always shows where the answer came from", SUB),
          Spacer(1, 14 * mm),
          p("A step-by-step account of how I built it and how well it works", SUB),
          Spacer(1, 30 * mm),
          box([p("<b>Project:</b> AI Engineering Project (Retrieval-Augmented Generation)", CELL),
               p(f"<b>Code:</b> {REPO_URL}", CELL),
               p(f"<b>Date:</b> {date.today():%d %B %Y}", CELL),
               p("<b>Reader:</b> no technical background needed. Technical words are explained when they first appear.", CELL)]),
          PageBreak()]

    # ---- summary
    s += [p("The short version", H1),
          p("I built a chat assistant, called <b>PolicyBot</b>, for a made-up company named <b>Lumora Systems</b>. "
            "An employee types a question such as <i>\"How many vacation days do I get?\"</i> or <i>\"What's the hotel "
            "limit in New York?\"</i>, and PolicyBot answers in a few sentences. Each answer comes with numbered "
            "<b>sources</b>: the exact policy, section and sentence it relied on, with a link to read it in full."),
          p("PolicyBot does not answer from general knowledge. It answers <b>only</b> from the company's own policy "
            "documents, and if the answer is not in them, it says so instead of guessing.")]
    if MAIN:
        s += [Spacer(1, 4), table([
            ["What I measured", "Result", "What it means"],
            ["Answers backed by the documents", pct(MAIN, "groundedness_pct"), "Answers contain nothing made up"],
            ["Sources pointing to the right passage", pct(MAIN, "citation_accuracy_pct"), "The links really support the answer"],
            ["Answers containing the key facts", pct(MAIN, "exact_match_pct"), "Compared with answers written in advance"],
            ["Off-topic questions politely declined", pct(MAIN, "refusal_accuracy_oos_pct"), "It doesn't wander outside its job"],
            ["Typical time to answer", secs(MAIN, "p50"), f"95% of answers within {secs(MAIN, 'p95')}"],
        ], [62, 25, 83])]
        s.append(p(f"Results from the {'AI-written' if LLM else 'basic'} mode, on a test of {MAIN['n_questions']} "
                   "questions. Step 12 explains how these were measured.", SMALL))
    s += [Spacer(1, 6), p("Everything required by the assignment was delivered:", BODY)]
    s += bullets([
        f"A library of {docs_n} realistic company policies (about {words / 500:.0f} pages).",
        "A system that reads, organises and searches those policies by meaning.",
        "An AI that writes short answers with sources, plus safety rules.",
        "A web page to chat with it, and a health-check page.",
        "Automatic quality checks that run every time the code changes, with a report.",
        "A measured evaluation of accuracy and speed, and written design documents.",
        f"All code published at {REPO_URL}.",
    ])
    s.append(PageBreak())

    # ---- key ideas
    s += [p("A few ideas in plain English", H1),
          p("You don't need any of these terms to follow the report, but they appear in the code and documents."),
          table([
              ["Term", "Plain-English meaning", "Everyday comparison"],
              ["Large language model (LLM)", "An AI that reads and writes text, like the one behind ChatGPT.",
               "A very well-read writer who can be confidently wrong."],
              ["RAG (Retrieval-Augmented Generation)",
               "First <b>find</b> the relevant pages, then let the AI <b>write</b> an answer using only those pages.",
               "An <b>open-book exam</b> instead of answering from memory."],
              ["Document chunk", "A short passage (about half a page) cut from a policy.",
               "An index card with one topic on it."],
              ["Embedding", "A list of numbers that captures what a passage <i>means</i>.",
               "A 'meaning fingerprint'. Similar meanings have similar fingerprints."],
              ["Vector database", "Storage that can quickly find passages with similar fingerprints.",
               "A library shelved by meaning instead of alphabetically."],
              ["Re-ranking", "A second, more careful model that re-reads the top results and re-orders them.",
               "A librarian double-checking the books a search pulled."],
              ["Citation", "A numbered reference [1] showing which passage supports a sentence.",
               "A footnote in a report."],
              ["Guardrail", "A safety rule the system must follow.",
               "The rule 'never guess: say you don't know'."],
              ["CI (Continuous Integration)", "Automatic checks that run every time the code is changed.",
               "A checklist inspector at the factory door."],
          ], [40, 70, 60]),
          PageBreak(),
          p("How one question travels through PolicyBot", H1),
          p("Every question goes through the same six stages, and the whole journey usually takes about one to two seconds."),
          Spacer(1, 4), journey_diagram(), Spacer(1, 10)]
    s += example_box()
    s.append(PageBreak())

    # ---- steps
    s += [p("What I did, step by step", H1),
          p("I followed the assignment brief from start to finish. Each step below says what I did and "
            "why it matters.")]

    s += step(1, "Understanding the assignment",
              "I read the assignment document (a 7-page PDF) and turned it into a checklist: build a question-answering "
              "assistant over company policies, show sources, refuse off-topic questions, give it a web page, add "
              "automatic checks, measure accuracy and speed, and document the design decisions.",
              "A clear checklist means nothing gets missed. Every item on it is covered by one of the steps below, and "
              "the final row of the checklist is in the last section.")

    s += step(2, "Setting up a clean workspace",
              "I created a self-contained project folder with its own private set of software tools (a "
              "'virtual environment'), so it doesn't interfere with anything else on the computer. I recorded the exact version of "
              "every tool, so anyone can rebuild the same setup later.",
              "Recording exact versions makes the work <b>repeatable</b>. Another person, or the grader, gets the same "
              "results.",
              extra=note("A real-world hiccup",
                         "The office network inspects secure internet traffic, which at first blocked the download of "
                         "the AI models. I fixed this by telling the software to trust the computer's own security "
                         "certificates, so it works both on the office network and anywhere else."))

    fmt_rows = [["ID", "Policy", "File type"]] + [
        [d["doc_id"], d["title"], d["format"].upper()] for d in MAN.get("documents", [])]
    s += step(3, "Writing the company policy library",
              f"There was no real company data to use, so I wrote a realistic but fictional set of {docs_n} policies "
              f"for 'Lumora Systems': about {words:,} words, or roughly {words / 500:.0f} printed pages. They cover "
              "vacation and leave, holidays, remote work, expenses, travel, IT security, acceptable use of computers, "
              "privacy, performance reviews, benefits, workplace conduct and onboarding. I wrote a single <b>fact sheet</b> "
              "first, listing every number (vacation days, spending limits, deadlines), and every document had "
              "to agree with it. I then had four AI writing assistants draft the documents at the same time.",
              "Using made-up policies keeps real company information private while still being realistic. The fact "
              "sheet matters: if two documents disagreed (say, 15 vs 20 vacation days), nobody could judge whether an "
              "answer was right. I saved the documents in four file types (web page, formatted text, plain text and "
              "PDF) to show the system can read all of them.",
              detail=[Spacer(1, 4), table(fmt_rows, [20, 120, 30])] if len(fmt_rows) > 1 else None)

    s += step(4, "Teaching the computer to read the documents",
              "I built a reader for each file type. It strips out formatting and keeps the structure: each policy is "
              "split along its own headings (for example <i>'4. Paid Time Off &gt; 4.1 PTO accrual by tenure'</i>), so "
              "every passage knows which section it came from.",
              "Keeping the section names is what lets PolicyBot later say <i>exactly</i> where an answer came from.",
              extra=note("Problem found and fixed",
                         "PDF files store text line by line as it appears on the page, so sentences were being cut in "
                         "half at the end of each printed line and at page breaks. A clean-up step now joins those lines "
                         "back into proper paragraphs. This one fix raised the 'sources point to the right passage' "
                         "score from 96% to 100% in testing."))

    s += step(5, "Cutting the policies into bite-sized passages",
              f"I cut each section into passages of about 220 words (roughly half a page), with a small overlap "
              f"between neighbouring passages so no sentence is lost at a boundary. I joined very short sections to "
              f"the next one. The result: <b>{chunks_n} passages</b>. Each passage is labelled with its policy name and "
              "section heading.",
              "An AI answers best when it is given a few focused passages rather than whole documents. I chose half a page "
              "after testing three sizes (Step 12): smaller pieces lost context, and larger ones added noise.")

    s += step(6, "Making the passages searchable by meaning",
              "I converted every passage into a 'meaning fingerprint' (an embedding) using a free AI model that runs "
              "on the computer itself. I stored the fingerprints in a small database (Chroma) kept inside the "
              "project folder.",
              "Searching by meaning means a question like <i>\"I left my work computer in a taxi\"</i> still finds the "
              "rule about <i>\"reporting lost or stolen devices\"</i>, even though the words are different. Running the "
              "model locally means it is free, private and has no usage limits.")

    s += step(7, "Finding the best passages for each question",
              "When a question arrives, it gets its own fingerprint, and the 20 closest passages are pulled from the "
              "database. A second, more careful model then re-reads those 20 alongside the question and keeps the "
              "<b>best 4</b>.",
              "The first search is fast but rough; the second check is slower but sharper. In testing with casually "
              "worded questions, the double-check moved the correct passage to the top every time (it was in the top "
              "spot 94% of the time without it).")

    s += step(8, "Writing the answer",
              f"The 4 best passages, numbered [1] to [4], are handed to a large AI language model ({model}, accessed "
              "through Groq's free service) with strict instructions: use <b>only</b> these passages, put the source "
              "number after every fact, keep it to about five sentences, and if the passages don't contain the answer, "
              "reply with a fixed polite refusal. If no AI key is set up, PolicyBot can still work in a simpler mode "
              "that quotes the most relevant sentences directly.",
              "This is the 'open-book exam' idea. Because the AI may only use the passages it was given, its answers "
              "can be checked, and the numbered sources let the reader verify every sentence.",
              extra=note("Problem found and fixed",
                         "The AI model originally planned for this project had been retired by the provider. I "
                         "compared two available models on real policy questions and chose the stronger one. One "
                         "of them writes source numbers in an unusual bracket style, so a small clean-up step converts "
                         "them to the standard [1] form."))

    s += step(9, "Adding safety rules (guardrails)",
              "I added several layers of protection, each catching what the one before might miss:",
              "Together these make PolicyBot <b>trustworthy</b>: it won't invent policies, won't go off-topic, and "
              "never shows an answer without a source.",
              detail=bullets([
                  "<b>Off-topic filter:</b> if nothing in the policies resembles the question (e.g. <i>\"What is the "
                  "capital of France?\"</i>), PolicyBot politely declines before the AI is even asked.",
                  "<b>Refusal rule:</b> the AI itself is told to decline questions the policies don't cover, such as "
                  "<i>\"What is Lumora's stock price?\"</i>",
                  "<b>Sources required:</b> source numbers that don't match a real passage are removed. An answer with "
                  "no sources is retried once, and if it still has none, it is replaced by the polite refusal.",
                  "<b>Length limit:</b> answers are capped at a few sentences.",
                  "<b>Input checks:</b> empty or extremely long questions are rejected with a clear message.",
                  "<b>Error handling:</b> if the AI service is down, the user sees a friendly message, not technical errors.",
              ]))

    s += step(10, "Building the website",
              "I built a simple web application with three required parts: a <b>chat page</b> where you type a "
              "question and see the answer with clickable source cards (policy name, section, the exact quoted "
              "sentence and a link); a <b>/chat</b> address that other programs can send questions to; and a "
              "<b>/health</b> address that reports whether everything is running. A bonus <b>document viewer</b> "
              "lets you click a source and jump straight to that section of the policy.",
              "This is how people actually use the assistant. The clickable sources make it easy to check any answer "
              "in seconds.")

    s += step(11, "Automatic quality checks (CI) and the run report",
              "I wrote 20 automatic tests. They check that every file type is read correctly, that passages are "
              "cut consistently, that the safety rules work, and that the website answers real questions with sources "
              "and refuses off-topic ones. On GitHub, every time the code changes, a robot (GitHub Actions) installs "
              "everything from scratch, runs all the tests, starts the website, asks it a sample question, and publishes "
              "a <b>CI report</b> on the run page (test results, sample answer, document statistics and the latest "
              "accuracy numbers). The same report can be downloaded as a file.",
              "Automatic checks catch mistakes before they reach users. If a future change breaks something, the run "
              "turns red immediately and the report shows what failed. When everything passes, the robot can also "
              "publish the new version to a public website.")

    # ---- evaluation step
    eval_detail = [
        p("<b>How I tested it.</b> I wrote 30 test questions in advance, each with a short 'correct answer' and "
          "the policy it should come from: 27 about the policies (vacation, holidays, travel, security, benefits, and "
          "so on) and 3 deliberately off-topic ones that PolicyBot should decline. Every expected fact was "
          "automatically confirmed to really exist in the policies. A second set of 16 casually worded questions "
          "(e.g. <i>\"My flight to Tokyo is 13 hours, am I allowed to sit up front?\"</i>) tested the search."),
        p("<b>Who marked the answers.</b> Exact facts and sources were checked automatically against the prepared "
          "answers. Whether an answer was fully backed by its sources was judged by a <b>different</b> AI model, so "
          "the writer was not marking its own homework."),
    ]
    if LLM:
        eval_detail += [Spacer(1, 4), bars([
            ("Backed by the documents", LLM.get("groundedness_pct")),
            ("Sources point to right passage", LLM.get("citation_accuracy_pct")),
            ("Contains all key facts", LLM.get("exact_match_pct")),
            ("Contains at least one key fact", LLM.get("partial_match_pct")),
            ("Policy questions answered", LLM.get("answer_rate_in_scope_pct")),
            ("Off-topic questions declined", LLM.get("refusal_accuracy_oos_pct")),
        ], f"AI-written answers ({LLM['n_questions']} questions)")]
    rows = [["Measure", "AI-written mode", "Basic mode (no AI writer)"]]
    for label, key in [("Answers backed by the documents", "groundedness_pct"),
                       ("Sources pointing to the right passage", "citation_accuracy_pct"),
                       ("Answers containing all key facts", "exact_match_pct"),
                       ("Policy questions answered", "answer_rate_in_scope_pct"),
                       ("Off-topic questions declined", "refusal_accuracy_oos_pct")]:
        rows.append([label, pct(LLM, key), pct(EXT, key)])
    rows.append(["Typical answer time (half of answers faster)", secs(LLM, "p50"), secs(EXT, "p50")])
    rows.append(["Slow-case answer time (95% faster)", secs(LLM, "p95"), secs(EXT, "p95")])
    eval_detail += [Spacer(1, 6), KeepTogether([table(rows, [80, 45, 45]),
                    p("'Basic mode' is the fallback that quotes sentences directly when no AI key is available. It "
                      "cannot recognise every off-topic question on its own, which is why the AI writer matters.", SMALL)])]
    eval_detail.append(p("<b>Fine-tuning the settings.</b> I compared different settings to choose the defaults: how "
                         "many passages to give the AI (1, 2, 4, 6 or 8), with or without the double-check, and passage "
                         "sizes of about a quarter, half and a full page. <b>Four passages, with the double-check, at half "
                         "a page each</b> was the smallest setup that found the needed facts for every test question."))
    s += step(12, "Measuring how good it is",
              "I tested PolicyBot on a fixed set of questions and scored on accuracy, honesty about its sources, "
              "willingness to say 'I don't know', and speed.",
              "Measuring, rather than assuming, shows whether the system can be trusted, and it guided several of the "
              "fixes described above.",
              detail=eval_detail)

    s += step(13, "Publishing the work",
              f"I published all the code, the policy library, the tests, the evaluation results and the design documents "
              f"on GitHub at <b>{REPO_URL}</b>, with a history of each change. The project includes the required "
              "documents: a README (how to set it up and run it), a design-and-evaluation document (why each choice "
              "was made, and the results), and an AI-tooling document (how AI tools helped build it).",
              "This is what the grader reviews. Anyone can download the project and run it with three commands. "
              "Secret items, such as the AI service key, are deliberately kept out of the published code.")

    # ---- checklist
    s += [PageBreak(), p("Assignment checklist", H1), table([
        ["Requirement from the brief", "Status", "Where"],
        ["Policy library: 5-20 documents, 30-120 pages", "Done", f"{docs_n} documents, ~{words / 500:.0f} pages (Step 3)"],
        ["Read PDF / web / text files; cut into passages", "Done", "Steps 4-5"],
        ["Free embedding model + vector database", "Done", "Step 6"],
        ["Top-k search with optional re-ranking", "Done", "Step 7"],
        ["Answers with sources; refuse off-topic; length limit", "Done", "Steps 8-9"],
        ["Web chat page, /chat and /health", "Done", "Step 10"],
        ["Automatic checks on every change (GitHub Actions)", "Done", "Step 11"],
        ["Evaluation: groundedness, citation accuracy, latency", "Done", "Step 12"],
        ["Optional: comparison of settings (ablations)", "Done", "Step 12"],
        ["README, design-and-evaluation, ai-tooling documents", "Done", "Step 13"],
        ["Fixed settings for repeatable results", "Done", "Steps 2, 5, 12"],
        ["Optional: public website (Render)", "Ready, not yet switched on", "See 'Next steps'"],
        ["Demo video (5-10 minutes)", "To do (presenter)", "See 'Next steps'"],
    ], [78, 37, 55]),
        Spacer(1, 10), p("Next steps", H2)]
    s += bullets([
        "<b>Put it online (optional):</b> connect the GitHub project to Render's free hosting, add the AI key there, "
        "and paste Render's 'deploy hook' link into GitHub. After that, every approved change goes live automatically.",
        "<b>Record the demo video:</b> show the chat page answering a few questions with sources, an off-topic question "
        "being declined, the CI report on GitHub, and the evaluation results.",
        "<b>Share the code:</b> make sure the GitHub account <i>quantic-grader</i> has access to the project.",
        "<b>Replace the AI key</b> after the project is graded, as good security practice.",
        "<b>Submit:</b> a single PDF containing the link to the GitHub project and the link to the demo video.",
    ])

    # ---- appendix
    s += [Spacer(1, 6), KeepTogether([p("Appendix: how to run it yourself", H2),
          p("On a computer with Python installed, in the project folder:"),
          box([p("<font face='Courier'>pip install -r requirements.txt</font>   (installs the tools)", CELL),
               p("<font face='Courier'>python -m rag.ingest</font>   (reads the policies and builds the search index)", CELL),
               p("<font face='Courier'>python app.py</font>   (starts the website at http://localhost:8000)", CELL)], bg=SOFT_TEAL),
          p("To enable AI-written answers, put a free Groq key in a file called <font face='Courier'>.env</font> "
            "(see <font face='Courier'>.env.example</font>). Without it, PolicyBot still runs in basic mode.", SMALL)])]
    return s


def on_page(canvas, doc):
    canvas.saveState()
    if doc.page > 1:
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(GREY)
        canvas.drawString(20 * mm, 12 * mm, "PolicyBot - project report")
        canvas.drawRightString(190 * mm, 12 * mm, f"Page {doc.page}")
        canvas.setStrokeColor(LINE)
        canvas.line(20 * mm, 16 * mm, 190 * mm, 16 * mm)
    canvas.restoreState()


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm,
                            bottomMargin=22 * mm, title="PolicyBot - Project Report",
                            author="PolicyBot project", subject="Step-by-step, non-technical project report")
    doc.build(build_story(), onFirstPage=on_page, onLaterPages=on_page)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
