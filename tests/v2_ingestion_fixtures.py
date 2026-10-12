"""Realistic NESA-style PDF fixtures, generated at test time (no binaries are committed).

The content is SYNTHETIC (written for these tests, not copied from NESA papers); the LAYOUT
imitates real papers: question numbers in the left margin as separate text objects, marks in
the right margin, (a)/(i) parts, 'Question N (continued)' page breaks, footers, Office-Use
barcodes, one-line and 2x2 multiple-choice options, graph options drawn as vector graphics, a
graph inside a part, ruled answer-booklet lines, an English stimulus booklet, Legal Sections
III/IV with EITHER/OR option questions, and marking guidelines with running headers, an MCQ
answer key, criteria tables and a mapping grid."""
from __future__ import annotations

from pathlib import Path

import fitz

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
]
FONT = next((f for f in _FONT_CANDIDATES if Path(f).exists()), None)
_ASCII = {"²": "^2", "³": "^3", "ˣ": "^x", "ⁿ": "^n", "₀": "_0", "¹": "^1", "ₙ": "_n", "∫": "int ", "π": "pi", "≤": "<=", "′": "'", "₂": "_2", "₄": "_4"}


def _t(text: str) -> str:
    if FONT:
        return text
    for k, v in _ASCII.items():
        text = text.replace(k, v)
    return text


def _width(text: str, size: float) -> float:
    if FONT:
        return fitz.Font(fontfile=FONT).text_length(_t(text), fontsize=size)
    return fitz.get_text_length(_t(text), fontname="helv", fontsize=size)


def _font(page):
    if FONT:
        page.insert_font(fontname="dv", fontfile=FONT)
        return "dv"
    return "helv"


class P:
    def __init__(self, doc, footer=None, office=False, ruled=0):
        self.page = doc.new_page(width=595, height=842)
        self.fn = _font(self.page)
        self.y = 60
        self.footer, self.office, self.ruled = footer, office, ruled

    def t(self, text, x=60, size=10.5, dy=15):
        self.page.insert_text((x, self.y), _t(text), fontsize=size, fontname=self.fn)
        self.y += dy

    def at(self, x, y, text, size=10.5):
        self.page.insert_text((x, y), _t(text), fontsize=size, fontname=self.fn)

    def mark(self, n):
        """Marks in the right-hand margin, on the baseline of the last written line."""
        self.at(545, self.y - 15, str(n), size=11)

    def gap(self, n=10):
        self.y += n

    def graph(self, x0=120, y0=None, w=260, h=160):
        y0 = y0 or self.y
        pg = self.page
        pg.draw_line((x0, y0 + h / 2), (x0 + w, y0 + h / 2))
        pg.draw_line((x0 + 30, y0), (x0 + 30, y0 + h))
        pts = [(x0 + 30 + (-1.5 + 4.0 * i / 59) * 50, y0 + h / 2 - ((-1.5 + 4.0 * i / 59) ** 3 - 3 * (-1.5 + 4.0 * i / 59) + 1) * 18) for i in range(60)]
        for a, b in zip(pts, pts[1:]):
            if y0 <= a[1] <= y0 + h and y0 <= b[1] <= y0 + h:
                pg.draw_line(a, b)
        for k, lab in enumerate(["1", "2", "3"]):  # axis tick labels must never be read as marks
            self.at(x0 + 30 + 50 * (k + 1) - 3, y0 + h / 2 + 14, lab, size=8)
        self.at(x0 + 18, y0 + h / 2 - 33, "2", size=8)
        self.at(x0 + w + 4, y0 + h / 2 + 3, "x", size=9)
        self.at(x0 + 34, y0 + 8, "y", size=9)
        self.at(x0 + 130, y0 + 20, "y = f(x)", size=9)
        self.y = y0 + h + 20

    def finish(self):
        for i in range(self.ruled):
            yy = 560 + i * 12
            self.page.draw_line((60, yy), (535, yy), color=(0.6, 0.6, 0.6), width=0.4)
        if self.office:
            self.at(150, 800, "Office Use Only – Do NOT write anything, or make any marks below this line.", size=8)
            self.at(250, 815, "5419310196", size=8)
        if self.footer:
            self.at(285, 832, self.footer, size=9)


def _wrap(p: P, text: str, x: int, width: int = 80):
    words, line = text.split(), ""
    for w in words:
        if len(line) + len(w) > width:
            p.t(line.strip(), x=x)
            line = ""
        line += w + " "
    if line.strip():
        p.t(line.strip(), x=x)


# --------------------------------------------------------------------------- Maths ---
MATHS_KEY = {1: "B", 2: "B", 3: "A", 4: "D", 5: "A", 6: "B", 7: "A", 8: "B", 9: "D", 10: "B"}


def maths_paper(path: Path, ruled: int = 0, year: int = 2025) -> Path:
    doc = fitz.open()
    p = P(doc)
    p.t("NSW Education Standards Authority", size=9)
    p.gap(20)
    p.t(f"{year} HIGHER SCHOOL CERTIFICATE EXAMINATION", size=12)
    p.gap(10)
    p.t("Mathematics Advanced", size=20, dy=30)
    p.t("General", size=11, dy=13)
    p.t("Instructions", size=11)
    for ln in ["• Reading time – 10 minutes", "• Working time – 3 hours", "• Write using black pen", "• Calculators approved by NESA may be used",
               "• For questions in Section II, show relevant mathematical reasoning", "  and/or calculations"]:
        p.t(ln, x=160)
    p.gap(8)
    p.t("Total marks:", size=11, dy=0)
    p.t("100", x=120, size=11)
    p.t("Section I – 10 marks (pages 2–5)", x=160)
    p.t("• Attempt Questions 1–10", x=170)
    p.t("• Allow about 15 minutes for this section", x=170)
    p.t("Section II – 90 marks (pages 6–10)", x=160)
    p.t("• Attempt Questions 11–14", x=170)
    p.t("• Allow about 2 hours and 45 minutes for this section", x=170)
    p.at(500, 820, "1151", size=10)
    p.finish()

    p = P(doc, footer="– 2 –")
    p.t("Section I", size=13, dy=18)
    p.t("10 marks")
    p.t("Attempt Questions 1–10")
    p.t("Allow about 15 minutes for this section")
    p.gap(4)
    p.t("Use the multiple-choice answer sheet for Questions 1–10.")
    p.gap(14)
    p.at(60, p.y, "1", size=11)
    p.t("What is the derivative of y = 3x² + 5x?", x=80)
    p.gap(4)
    for o in ["A. 3x + 5", "B. 6x + 5", "C. 6x² + 5", "D. x³ + 5x²/2"]:
        p.t(o, x=80)
    p.gap(14)
    p.at(60, p.y, "2", size=11)
    p.t("A random variable X has E(X) = 4 and Var(X) = 9. What is the standard deviation of X?", x=80)
    p.gap(4)
    yy = p.y
    for i, o in enumerate(["A. 2", "B. 3", "C. 9", "D. 81"]):  # options on ONE line
        p.at(80 + 115 * i, yy, o)
    p.y += 15
    p.gap(14)
    p.at(60, p.y, "3", size=11)
    p.t("Which of the following is the 10th term of the arithmetic sequence 7, 11, 15, ...?", x=80)
    p.gap(4)
    yy = p.y
    p.at(80, yy, "A. 43")
    p.at(300, yy, "B. 47")  # 2 x 2 grid
    p.at(80, yy + 15, "C. 51")
    p.at(300, yy + 15, "D. 55")
    p.y += 30
    p.gap(14)
    p.at(60, p.y, "4", size=11)
    p.t("The probability that it rains on a given day is 0.3.", x=80)
    p.t("A day is chosen at random. What is the probability that it does not rain?", x=80)  # starts with the article 'A'
    p.gap(4)
    for o in ["A. 0.03", "B. 0.3", "C. 0.6", "D. 0.7"]:
        p.t(o, x=80)
    p.finish()

    p = P(doc, footer="– 3 –")
    p.at(60, p.y, "5", size=11)
    p.t("Which graph best represents y = –x² + 1?", x=80)
    p.gap(4)
    for i, lab in enumerate(["A.", "B.", "C.", "D."]):  # graph options: letter only, picture is vector art
        x0 = 80 + (i % 2) * 230
        y0 = p.y + (i // 2) * 120
        p.at(x0, y0 + 10, lab)
        p.page.draw_rect(fitz.Rect(x0 + 20, y0, x0 + 200, y0 + 100), width=0.3)
        for k in range(20):
            s = 1 if i % 2 else -1
            p.page.draw_line((x0 + 20 + k * 9, y0 + 50 + ((k - 10) ** 2) * s * 0.4), (x0 + 29 + k * 9, y0 + 50 + ((k - 9) ** 2) * s * 0.4))
    p.y += 250
    p.t("6", x=60, size=11, dy=14)  # number on its own line above the stem
    p.t("What is the value of ∫₀¹ 2x dx ?", x=80)
    p.gap(4)
    for o in ["A. 0", "B. 1", "C. 2", "D. 4"]:
        p.t(o, x=80)
    p.gap(14)
    p.at(60, p.y, "7", size=11)
    p.t("The sum of the first n terms of a series is Sₙ = n² + n. What is T₅?", x=80)
    p.gap(4)
    for o in ["A. 10", "B. 20", "C. 30", "D. 50"]:
        p.t(o, x=80)
    p.finish()

    p = P(doc, footer="– 4 –")
    for n, stem, opts in [
        ("8", "An amount of $5000 is invested at 4% per annum, compounded annually. What is the value after 3 years, to the nearest dollar?",
         ["A. $5600", "B. $5624", "C. $5800", "D. $6083"]),
        ("9", "For which value of k is f(x) = kx(1 – x), 0 ≤ x ≤ 1, a probability density function?", ["A. 2", "B. 3", "C. 4", "D. 6"]),
        ("10", "What is the period of y = 3 sin(2x) + 1?", ["A. π/2", "B. π", "C. 2π", "D. 4π"]),
    ]:
        p.at(60, p.y, n, size=11)
        _wrap(p, stem, 80)
        p.gap(4)
        for o in opts:
            p.t(o, x=80)
        p.gap(14)
    p.finish()

    p = P(doc, footer="– 5 –")
    p.t("BLANK PAGE", x=250, size=14)
    p.finish()

    p = P(doc, footer="– 6 –", office=True, ruled=ruled)
    p.t("Section II", size=13, dy=18)
    p.t("90 marks")
    p.t("Attempt Questions 11–14")
    p.t("Allow about 2 hours and 45 minutes for this section")
    p.gap(4)
    p.t("Answer each question in the appropriate writing booklet. Extra writing booklets are available.")
    p.t("In Questions 11–14, your responses should include relevant mathematical reasoning and/or calculations.")
    p.gap(12)
    p.t("Question 11 (15 marks) Use the Question 11 Writing Booklet", size=11, dy=20)
    p.t("(a)", x=60, dy=0)
    p.t("Find the limiting sum of the geometric series 8 + 4 + 2 + ... .", x=85)
    p.mark(2)
    p.gap(10)
    p.t("(b)", x=60, dy=0)
    p.t("Consider the function f(x) = x³ – 3x + 1.", x=85)
    p.gap(4)
    p.t("(i)", x=85, dy=0)
    p.t("Find the coordinates of the stationary points and determine their nature.", x=110)
    p.mark(3)
    p.gap(4)
    p.t("(ii)", x=85, dy=0)
    p.t("Sketch the graph of y = f(x), showing the stationary points and the", x=110)
    p.t("y-intercept.", x=110)
    p.mark(2)
    p.gap(10)
    # typeset maths with a raised exponent: extracts lossily, so Maths parts are always cropped
    p.t("(c)", x=60, dy=0)
    x = 85
    for txt, raised in [("Differentiate y = x", False), ("3", True), ("e", False), ("2x", True), (".", False)]:
        size = 7 if raised else 10.5
        p.at(x + 0.5, p.y - (4 if raised else 0), txt, size=size)
        x += _width(txt, size) + 0.5
    p.y += 15
    p.mark(2)
    p.gap(10)
    p.t("Question 11 continues on page 7", x=200)
    p.finish()

    p = P(doc, footer="– 7 –", office=True, ruled=ruled)
    p.t("Question 11 (continued)", size=11, dy=20)
    p.t("(d)", x=60, dy=0)
    p.t("The graph of y = f(x), where f(x) = x³ – 3x + 1, is shown.", x=85)
    p.graph()
    p.t("(i)", x=85, dy=0)
    p.t("Find the area enclosed between the curve, the x-axis, x = 0 and x = 1.", x=110)
    p.mark(3)
    p.gap(4)
    p.t("(ii)", x=85, dy=0)
    p.t("Use the trapezoidal rule with three function values to estimate", x=110)
    p.t("the same area.", x=110)
    p.mark(3)
    p.gap(10)
    p.t("End of Question 11", x=230)
    p.finish()

    p = P(doc, footer="– 8 –", office=True, ruled=ruled)
    p.t("Question 12 (3 marks) Use the Question 12 Writing Booklet", size=11, dy=20)
    p.t("Solve 2 ln x = ln(3x + 4) for x.", x=60)
    p.mark(3)
    p.gap(16)
    p.t("Question 13 (15 marks) Use the Question 13 Writing Booklet", size=11, dy=20)
    p.t("(a)", x=60, dy=0)
    p.t("A particle moves along a line so that its velocity is v = 6t – 3t² m/s.", x=85)
    p.gap(4)
    p.t("(i)", x=85, dy=0)
    p.t("Find the acceleration of the particle when t = 1.", x=110)
    p.mark(1)
    p.gap(4)
    p.t("(ii)", x=85, dy=0)
    p.t("Hence, or otherwise, find the maximum velocity of the particle.", x=110)
    p.mark(2)
    p.gap(10)
    p.t("(b)", x=60, dy=0)
    p.t("Loan repayments of $M are made at the end of each month for 20 years on a", x=85)
    p.t("loan of $300 000 with interest of 6% per annum, compounded monthly.", x=85)
    p.gap(4)
    p.t("(i)", x=85, dy=0)
    p.t("Show that the amount owing after n months is given by", x=110)
    p.t("Aₙ = 300000(1.005)ⁿ – M(1.005ⁿ – 1)/0.005.", x=130)
    p.mark(2)
    p.gap(10)
    p.t("Question 13 continues on page 9", x=200)
    p.finish()

    p = P(doc, footer="– 9 –", office=True, ruled=ruled)
    p.t("Question 13 (continued)", size=11, dy=20)
    p.t("(ii)", x=85, dy=0)
    p.t("Find the value of M, correct to the nearest cent.", x=110)
    p.mark(2)
    p.gap(10)
    p.t("(c)", x=60, dy=0)
    p.t("The continuous random variable X has probability density function", x=85)
    p.t("f(x) = 3x² for 0 ≤ x ≤ 1. Find P(X < 0.5).", x=85)
    p.mark(2)
    p.gap(10)
    p.t("(d)", x=60, dy=0)
    p.t("Hence, or otherwise, find P(X > 0.5).", x=85)
    p.mark(2)
    p.gap(10)
    p.t("(e)", x=60, dy=0)
    p.t("A table of values for a function g is shown.", x=85)
    for xv, gv in [("x", "g(x)"), ("0", "1"), ("1", "4"), ("2", "9")]:
        p.at(150, p.y, xv)
        p.at(220, p.y, gv)
        p.y += 13
    p.t("Find the average rate of change of g between x = 0 and x = 2.", x=85)
    p.mark(4)
    p.gap(10)
    p.t("End of Question 13", x=230)
    p.finish()

    p = P(doc, footer="– 10 –", office=True)
    p.t("Question 14 (2 marks) Use the Question 14 Writing Booklet", size=11, dy=20)
    p.t("Use mathematical induction to prove that 6ⁿ – 1 is divisible by 5 for all", x=60)
    p.t("positive integers n.", x=60)
    p.mark(2)
    p.gap(16)
    p.t("End of paper", x=250, size=12)
    p.finish()
    doc.save(path)
    return path


def maths_guidelines(path: Path, year: int = 2025) -> Path:
    doc = fitz.open()
    hdr = f"NESA {year} HSC Mathematics Advanced Marking Guidelines"
    lines = [
        "Section I", "Multiple-choice Answer Key", "Question Answer",
        *[f"{n} {a}" for n, a in MATHS_KEY.items()], "",
        "Section II", "",
        "Question 11 (a)", "Criteria Marks", "• Provides correct solution 2", "• Identifies a and r, or equivalent merit 1",
        "Sample answer:", "a = 8, r = 1/2", "S = a/(1 – r) = 16", "",
        "Question 11 (b) (i)", "Criteria Marks", "• Provides correct solution 3", "• Finds both stationary points, or equivalent merit 2",
        "• Finds f′(x), or equivalent merit 1", "Sample answer:", "f′(x) = 3x² – 3 = 0 so x = ±1.", "",
        "Question 11 (b) (ii)", "Criteria Marks", "• Provides correct sketch 2", "• Provides a sketch showing some correct features 1", "",
        "Question 11 (c)", "Criteria Marks", "• Provides correct derivative 2", "• Uses the product rule 1", "",
        "Question 11 (d) (i)", "Criteria Marks", "• Provides correct solution 3", "• Obtains correct primitive 2", "• Attempts to integrate 1", "",
        "Question 11 (d) (ii)", "Criteria Marks", "• Provides correct solution 3", "• Correct function values 2", "• Correct h 1", "",
        "Question 12", "Criteria Marks", "• Provides correct solution 3", "• Obtains x² – 3x – 4 = 0 2", "• Uses a log law 1",
        "Sample answer:", "x² = 3x + 4, so x = 4 (x = –1 is rejected)", "",
        "Question 13 (a) (i)", "Criteria Marks", "• Provides correct answer 1", "",
        "Question 13 (a) (ii)", "Criteria Marks", "• Provides correct solution 2", "• Finds when a = 0 1", "",
        "Question 13 (b) (i)", "Criteria Marks", "• Provides correct proof 2", "• Finds A₂, or equivalent merit 1", "",
        "Question 13 (b) (ii)", "Criteria Marks", "• Provides correct solution 2", "• Uses A₂₄₀ = 0 1", "",
        "Question 13 (c)", "Criteria Marks", "• Provides correct solution 2", "• Integrates the pdf 1", "Sample answer:", "P(X < 0.5) = 0.125", "",
        "Question 13 (d)", "Criteria Marks", "• Provides correct answer 2", "• Uses the complement 1", "",
        "Question 13 (e)", "Criteria Marks", "• Provides correct solution 4", "• Finds g(2) – g(0) 2", "",
        "Question 14", "Criteria Marks", "• Provides correct proof 2", "",
        f"{year} HSC Mathematics Advanced Mapping Grid",
        "Section I", "Question Marks Content Syllabus outcomes Targeted performance bands",
        "1 1 MA-C2 Differential Calculus MA12-6 2–3", "2 1 MA-S2 Random variables MA12-8 3–4",
        "Section II", "Question Marks Content Syllabus outcomes Targeted performance bands",
        "11 (a) 2 MA-M1 Sequences and series MA12-4 2–3", "11 (b) (i) 3 MA-C3 Applications of Differentiation MA12-3 3–4",
        "14 2 ME-P1 Proof by induction ME12-1 E2–E3",
    ]
    page, y, pno = None, 0, 0

    def new_page():
        nonlocal page, y, pno
        if page is not None:
            page.insert_text((250, 822), f"Page {pno} of 5", fontsize=8, fontname=fn)
        page = doc.new_page(width=595, height=842)
        pno += 1
        fn_ = _font(page)
        page.insert_text((60, 36), hdr, fontsize=8, fontname=fn_)  # running header
        y = 70
        return fn_

    fn = new_page()
    for ln in lines:
        if y > 760:
            fn = new_page()
        ln = _t(ln)
        if ln.startswith("• ") and ln.rsplit(" ", 1)[-1].replace("–", "").isdigit():
            text, mk = ln.rsplit(" ", 1)
            page.insert_text((70, y), text, fontsize=10, fontname=fn)
            page.insert_text((520, y), mk, fontsize=10, fontname=fn)  # Marks column, separate text object
        elif ln == "Criteria Marks":
            page.insert_text((70, y), "Criteria", fontsize=10, fontname=fn)
            page.insert_text((515, y), "Marks", fontsize=10, fontname=fn)
        elif ln and ln[0].isdigit() and len(ln.split()) == 2 and len(ln) <= 4:
            a, b = ln.split()
            page.insert_text((80, y), a, fontsize=10, fontname=fn)
            page.insert_text((160, y), b, fontsize=10, fontname=fn)
        else:
            page.insert_text((60, y), ln, fontsize=10, fontname=fn)
        y += 15
    page.insert_text((250, 822), f"Page {pno} of 5", fontsize=8, fontname=fn)
    doc.save(path)
    return path


# ------------------------------------------------------------------------- English ---
def english_paper(path: Path) -> Path:
    doc = fitz.open()
    p = P(doc)
    p.t("NSW Education Standards Authority", size=9)
    p.gap(20)
    p.t("2025 HIGHER SCHOOL CERTIFICATE EXAMINATION", size=12)
    p.gap(10)
    p.t("English Advanced", size=20, dy=26)
    p.t("Paper 1 — Texts and Human Experiences", size=14, dy=26)
    p.t("General Instructions", size=11)
    p.t("• Reading time – 10 minutes", x=160)
    p.t("• Working time – 1 hour and 30 minutes", x=160)
    p.t("Total marks: 40", size=11)
    p.t("Section I – 20 marks (pages 2–3)", x=160)
    p.t("• Attempt ALL questions", x=170)
    p.t("Section II – 20 marks (page 4)", x=160)
    p.t("• Attempt Question 5", x=170)
    p.finish()
    p = P(doc, footer="– 2 –")
    p.t("Section I", size=13, dy=18)
    p.t("20 marks")
    p.t("Attempt ALL questions")
    p.t("Allow about 45 minutes for this section")
    p.t("Read the texts on pages 2–6 of the Stimulus Booklet carefully and then answer the questions in the")
    p.t("spaces provided. These spaces provide guidance for the expected length of response.")
    p.gap(14)
    p.t("Question 1 (3 marks)", size=11, dy=18)
    p.t("Text 1 — Prose fiction extract", size=10)
    p.t("How does the writer represent the narrator's sense of displacement?", x=60)
    p.mark(3)
    p.gap(14)
    p.t("Question 2 (4 marks)", size=11, dy=18)
    p.t("Text 2 — Poem", size=10)
    p.t("Analyse how the poet uses imagery to convey a changing understanding of home.", x=60)
    p.mark(4)
    p.gap(14)
    p.t("Question 3 (5 marks)", size=11, dy=18)
    p.t("Text 3 — Nonfiction extract", size=10)
    p.t("Explain how the writer uses anecdote to shape the reader's response to the human", x=60)
    p.t("experience of loss.", x=60)
    p.mark(5)
    p.finish()
    p = P(doc, footer="– 3 –")
    p.t("Question 4 (8 marks)", size=11, dy=18)
    p.t("Texts 1 and 4 — Prose fiction extract and Website extract", size=10)
    p.t("Compare how Texts 1 and 4 explore the tension between memory and belonging.", x=60)
    p.mark(8)
    p.finish()
    p = P(doc, footer="– 4 –")
    p.t("Section II", size=13, dy=18)
    p.t("20 marks")
    p.t("Attempt Question 5")
    p.t("Allow about 45 minutes for this section")
    p.t("Answer the question in a writing booklet. Extra writing booklets are available.")
    p.gap(14)
    p.t("Question 5 (20 marks)", size=11, dy=18)
    p.t("\"Human experiences are rarely simple.\"", x=60)
    p.t("To what extent does your prescribed text represent the complexity of individual and", x=60)
    p.t("collective experiences? In your response, make detailed reference to your prescribed text.", x=60)
    p.gap(10)
    p.t("End of paper", x=250)
    p.finish()
    doc.save(path)
    return path


def english_stimulus(path: Path) -> Path:
    doc = fitz.open()
    s = P(doc)
    s.t("2025 HIGHER SCHOOL CERTIFICATE EXAMINATION", size=12)
    s.t("English Advanced", size=18, dy=24)
    s.t("Paper 1 — Texts and Human Experiences", size=13, dy=22)
    s.t("Stimulus Booklet for Section I", size=13, dy=22)
    s.finish()
    s = P(doc, footer="– 2 –")
    s.t("Text 1 — Prose fiction extract", size=12, dy=20)
    for ln in ["The bus stopped where the road gave up and became a track. I had been told",
               "the house would be there, white against the hill, but the hill was only grass",
               "and the long shadow of my own uncertainty.", "",
               "My mother's language sat in my mouth like a stone I could not swallow and",
               "could not spit out."]:
        if ln:
            s.t(ln)
        else:
            s.gap(8)
    s.t("© A. Writer 2019, Example Press", size=8)
    s.gap(20)
    s.t("Text 2 — Poem", size=12, dy=20)
    for ln in ["Home was a kettle, a kitchen, a door;", "home is a word I carry, no more."]:
        s.t(ln, x=90)
    s.t("© B. Poet 2021", size=8)
    s.finish()
    s = P(doc, footer="– 3 –")
    s.t("Text 3 — Nonfiction extract", size=12, dy=20)
    for ln in ["When my grandfather died, the first thing we lost was the sound of his",
               "radio in the shed. Grief, I learned, is mostly a matter of silences."]:
        s.t(ln)
    s.t("© C. Essayist 2020, Example Journal", size=8)
    s.gap(20)
    s.t("Text 4 — Website extract", size=12, dy=20)
    s.page.draw_rect(fitz.Rect(80, s.y, 400, s.y + 120), width=0.8)  # the web page screenshot (visual text)
    s.at(100, s.y + 30, "Remember Us: a community memory project", size=11)
    s.at(100, s.y + 60, "Share the stories that made this town home.", size=9)
    s.y += 140
    s.t("© Example Community Archive 2023", size=8)
    s.finish()
    doc.save(path)
    return path


def english_guidelines(path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    fn = _font(page)
    y = 60
    for ln in ["2025 HSC English Advanced Paper 1 Marking Guidelines", "Section I",
               "Question 1", "Criteria Marks", "• Skilfully explains how the writer represents displacement 3",
               "• Explains how the writer represents displacement 2", "• Provides some relevant information 1",
               "Sample answer:", "The narrator's simile of the stone ...", "",
               "Question 2", "Criteria Marks", "• Skilfully analyses how imagery conveys a changing understanding of home 4", "",
               "Question 3", "Criteria Marks", "• Effectively explains 5", "",
               "Question 4", "Criteria Marks", "• Skilfully compares 7–8", "• Compares 5–6", "",
               "Section II", "Question 5", "Criteria Marks", "• Presents a sophisticated response 17–20", "• Presents a well-developed response 13–16"]:
        ln = _t(ln)
        if ln.startswith("• "):
            text, mk = ln.rsplit(" ", 1)
            page.insert_text((70, y), text, fontsize=10, fontname=fn)
            page.insert_text((515, y), mk, fontsize=10, fontname=fn)
        else:
            page.insert_text((60, y), ln, fontsize=10, fontname=fn)
        y += 15
    doc.save(path)
    return path


# --------------------------------------------------------------------------- Legal ---
LEGAL_KEY = {1: "B", 2: "B", 3: "B", 4: "A", 5: "B"}


def legal_paper(path: Path, year: int = 2025) -> Path:
    doc = fitz.open()
    p = P(doc)
    p.t("NSW Education Standards Authority", size=9)
    p.gap(20)
    p.t(f"{year} HIGHER SCHOOL CERTIFICATE EXAMINATION", size=12)
    p.gap(10)
    p.t("Legal Studies", size=20, dy=30)
    p.t("General Instructions", size=11)
    p.t("• Reading time – 5 minutes", x=160)
    p.t("Total marks: 100", size=11)
    p.t("Section I – 20 marks (pages 2–3)", x=160)
    p.t("• Attempt Questions 1–5", x=170)
    p.t("Section II – 15 marks (page 4)", x=160)
    p.t("Section III – 15 marks (page 5)", x=160)
    p.t("Section IV – 50 marks (pages 6–7)", x=160)
    p.finish()
    p = P(doc, footer="– 2 –")
    p.t("Section I", size=13, dy=18)
    p.t("20 marks")
    p.t("Attempt Questions 1–5")
    p.t("Allow about 35 minutes for this section")
    p.t("Use the multiple-choice answer sheet for Questions 1–5.")
    p.gap(14)
    for n, stem, opts in [
        ("1", "Which of the following best describes the burden of proof in a criminal trial?",
         ["A. The accused must prove innocence on the balance of probabilities.", "B. The prosecution must prove guilt beyond reasonable doubt.",
          "C. The judge must prove guilt beyond reasonable doubt.", "D. The jury must prove guilt on the balance of probabilities."]),
        ("2", "Which of the following is an example of a summary offence?", ["A. Murder", "B. Offensive language", "C. Armed robbery", "D. Manslaughter"]),
        ("3", "What is the main purpose of a plea bargain?", ["A. To increase the sentence", "B. To reduce the cost and time of trials",
                                                          "C. To allow the victim to choose the sentence", "D. To avoid police investigation"]),
    ]:
        p.at(60, p.y, n, size=11)
        p.t(stem, x=80)
        p.gap(4)
        for o in opts:
            p.t(o, x=80)
        p.gap(12)
    p.finish()
    p = P(doc, footer="– 3 –")
    p.at(60, p.y, "4", size=11)
    p.t("Read the scenario and answer the question.", x=80)
    p.t("Mia, aged 12, took a bicycle from outside a shop. Which principle is most relevant?", x=80)
    p.gap(4)
    yy = p.y
    for i, o in enumerate(["A. Doli incapax", "B. Strict liability", "C. Double jeopardy", "D. Habeas corpus"]):
        p.at(80 + (i % 2) * 220, yy + (i // 2) * 15, o)
    p.y += 40
    p.at(60, p.y, "5", size=11)
    p.t("Which body is primarily responsible for monitoring the ICCPR?", x=80)
    p.gap(4)
    for o in ["A. The Security Council", "B. The Human Rights Committee", "C. The General Assembly", "D. The International Court of Justice"]:
        p.t(o, x=80)
    p.finish()
    p = P(doc, footer="– 4 –")
    p.t("Section II", size=13, dy=18)
    p.t("15 marks")
    p.t("Attempt Question 21")
    p.t("Allow about 25 minutes for this section")
    p.gap(10)
    p.t("Question 21 (15 marks)", size=11, dy=18)
    p.t("(a)", x=60, dy=0)
    p.t("Outline the role of police discretion in the criminal investigation process.", x=85)
    p.mark(3)
    p.gap(10)
    p.t("(b)", x=60, dy=0)
    p.t("Explain how bail balances the rights of the accused and the protection of the", x=85)
    p.t("community.", x=85)
    p.mark(4)
    p.gap(10)
    p.t("(c)", x=60, dy=0)
    p.t("Assess the effectiveness of sentencing in achieving justice for victims.", x=85)
    p.mark(8)
    p.finish()
    p = P(doc, footer="– 5 –")
    p.t("Section III", size=13, dy=18)
    p.t("15 marks")
    p.t("Attempt Question 22")
    p.t("Allow about 30 minutes for this section")
    p.t("Answer the question in a writing booklet. Extra writing booklets are available.")
    p.gap(10)
    p.t("Question 22 (15 marks)", size=11, dy=18)
    p.t("Evaluate the effectiveness of legal and non-legal measures in promoting and enforcing", x=60)
    p.t("ONE human right.", x=60)
    p.t("In your answer, refer to relevant examples.", x=60)
    p.finish()
    p = P(doc, footer="– 6 –")
    p.t("Section IV", size=13, dy=18)
    p.t("50 marks")
    p.t("Attempt TWO questions from Questions 23–24")
    p.t("Allow about 1 hour and 45 minutes for this section")
    p.gap(10)
    p.t("Question 23 — Consumers (25 marks)", size=11, dy=18)
    p.t("Answer EITHER part (a) OR part (b).", x=60)
    p.gap(6)
    p.t("(a)", x=60, dy=0)
    p.t("Evaluate the effectiveness of the law in protecting consumers who enter", x=85)
    p.t("into contracts online.", x=85)
    p.gap(6)
    p.t("OR", x=250)
    p.gap(6)
    p.t("(b)", x=60, dy=0)
    p.t("To what extent has law reform improved consumer protection?", x=85)
    p.finish()
    p = P(doc, footer="– 7 –")
    p.t("Question 24 — Family (25 marks)", size=11, dy=18)
    p.t("Answer EITHER part (a) OR part (b).", x=60)
    p.gap(6)
    p.t("(a)", x=60, dy=0)
    p.t("Evaluate the effectiveness of the legal system in protecting children", x=85)
    p.t("in family disputes.", x=85)
    p.gap(6)
    p.t("OR", x=250)
    p.gap(6)
    p.t("(b)", x=60, dy=0)
    p.t("Assess the extent to which the law reflects changing values about the family.", x=85)
    p.gap(10)
    p.t("End of paper", x=250)
    p.finish()
    doc.save(path)
    return path


def legal_guidelines(path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    fn = _font(page)
    y = 60
    for ln in ["2025 HSC Legal Studies Marking Guidelines", "Section I", "Multiple-choice Answer Key", "Question", "Answer",
               *[str(x) for kv in LEGAL_KEY.items() for x in kv],  # vertical key: one token per line
               "Section II", "Question 21 (a)", "Criteria Marks", "• Clearly outlines the role of police discretion 3", "• Describes police discretion 2", "",
               "Question 21 (b)", "Criteria Marks", "• Clearly explains how bail balances competing rights 4", "",
               "Question 21 (c)", "Criteria Marks", "• Makes a well-reasoned judgement about sentencing and victims 7–8", "Answers could include:",
               "• Sentencing purposes", "• Victim impact statements", "",
               "Section III", "Question 22", "Criteria Marks", "• Makes a well-reasoned judgement about legal and non-legal measures 13–15", "",
               "Section IV", "Question 23 (a)", "Criteria Marks", "• Makes a well-reasoned judgement 21–25", "",
               "Question 23 (b)", "Criteria Marks", "• Makes a well-reasoned judgement 21–25", "",
               "Question 24 (a)", "Criteria Marks", "• Makes a well-reasoned judgement 21–25", "Question 24 (b)", "Criteria Marks", "• Makes a well-reasoned judgement 21–25"]:
        ln = _t(ln)
        if ln.startswith("• ") and ln.rsplit(" ", 1)[-1].replace("–", "").isdigit():
            text, mk = ln.rsplit(" ", 1)
            page.insert_text((70, y), text, fontsize=10, fontname=fn)
            page.insert_text((515, y), mk, fontsize=10, fontname=fn)
        else:
            page.insert_text((60, y), ln, fontsize=10, fontname=fn)
        y += 14
        if y > 800:
            page = doc.new_page()
            fn = _font(page)
            y = 60
    doc.save(path)
    return path


def build_all(out: Path) -> dict[str, Path]:
    out.mkdir(parents=True, exist_ok=True)
    return {
        "maths": maths_paper(out / "maths_2025.pdf"),
        "maths_booklet": maths_paper(out / "maths_2025_booklet.pdf", ruled=18),
        "maths_mg": maths_guidelines(out / "maths_2025_mg.pdf"),
        "english": english_paper(out / "english_p1_2025.pdf"),
        "english_stimulus": english_stimulus(out / "english_p1_2025_stimulus.pdf"),
        "english_mg": english_guidelines(out / "english_p1_2025_mg.pdf"),
        "legal": legal_paper(out / "legal_2025.pdf"),
        "legal_mg": legal_guidelines(out / "legal_2025_mg.pdf"),
    }


if __name__ == "__main__":  # pragma: no cover - manual inspection
    import sys

    print(build_all(Path(sys.argv[1] if len(sys.argv) > 1 else "fixtures_out")))
