"""Render a simple Markdown policy (headings, paragraphs, '- ' bullets) to PDF.

Used once to produce the PDF member of the corpus (so ingestion is exercised on PDF input):
    python scripts/build_pdf.py corpus_src/HR-008_onboarding-and-offboarding.md \
        data/policies/HR-008_onboarding-and-offboarding.pdf
Requires fpdf2 (requirements-dev.txt).
"""

from __future__ import annotations

import sys
from pathlib import Path

from fpdf import FPDF


class PolicyPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", size=8)
        self.set_text_color(120)
        self.cell(0, 8, f"Page {self.page_no()} of {{nb}}", align="C")


def render(src: Path, dst: Path) -> None:
    pdf = PolicyPDF(format="Letter")
    pdf.set_margins(22, 20, 22)
    pdf.set_auto_page_break(True, margin=18)
    pdf.set_title(src.stem)
    pdf.add_page()
    sizes = {1: 17, 2: 13, 3: 11}
    for raw in src.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip().encode("latin-1", "replace").decode("latin-1")
        if not line.strip():
            pdf.ln(2)
            continue
        level = len(line) - len(line.lstrip("#"))
        if 1 <= level <= 3 and line[level:level + 1] == " ":
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", sizes[level])
            pdf.multi_cell(0, sizes[level] * 0.5, line[level + 1:].strip())
            pdf.ln(1)
        elif line.lstrip().startswith("- "):
            pdf.set_font("Helvetica", size=10)
            pdf.set_x(pdf.l_margin + 4)
            pdf.multi_cell(0, 5, "- " + line.lstrip()[2:])
        else:
            pdf.set_font("Helvetica", size=10)
            pdf.multi_cell(0, 5, line.strip())
    dst.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(dst))
    print(f"wrote {dst} ({pdf.page_no()} pages)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    render(Path(sys.argv[1]), Path(sys.argv[2]))
