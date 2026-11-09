"""Builds docs/Lumen_Documentation.pdf from docs/DOCUMENTATION.md.

  cd backend && uv run python ../scripts/build_docs_pdf.py

Needs reportlab (already a backend dependency). Uses Segoe UI and Consolas from C:\\Windows\\Fonts; on other systems
point FONT_DIR at a folder with any TTF family that has arrows and box-drawing characters (for example DejaVu).
The four Mermaid diagrams in the markdown are redrawn here as vector graphics.
"""
import re
import sys
import zlib
from datetime import date
from pathlib import Path
from textwrap import wrap as _wrap

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate, Paragraph, Preformatted,
                                Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "DOCUMENTATION.md"
OUT = ROOT / "docs" / "Lumen_Documentation.pdf"
FONT_DIR = Path(r"C:\Windows\Fonts")

# ---------------------------------------------------------------- fonts and colours
for name, file in (("Seg", "segoeui.ttf"), ("Seg-B", "segoeuib.ttf"), ("Seg-I", "segoeuii.ttf"), ("Seg-BI", "segoeuiz.ttf"),
                   ("Mono", "consola.ttf"), ("Mono-B", "consolab.ttf")):
    pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / file)))
pdfmetrics.registerFontFamily("Seg", normal="Seg", bold="Seg-B", italic="Seg-I", boldItalic="Seg-BI")
pdfmetrics.registerFontFamily("Mono", normal="Mono", bold="Mono-B", italic="Mono", boldItalic="Mono-B")

ACCENT = colors.HexColor("#0b8f6e")
ACCENT_DARK = colors.HexColor("#075c46")
INK = colors.HexColor("#1b2421")
MUTED = colors.HexColor("#5b6b66")
LINE = colors.HexColor("#d5ddd9")
SOFT = colors.HexColor("#eef5f2")
CODE_BG = colors.HexColor("#f3f6f5")
LINK = colors.HexColor("#0b6fa8")

PAGE_W, PAGE_H = A4
MARGIN = 2 * cm
CONTENT_W = PAGE_W - 2 * MARGIN

S = {
    "body": ParagraphStyle("body", fontName="Seg", fontSize=9.6, leading=14, textColor=INK, spaceAfter=6, alignment=TA_LEFT),
    "h2": ParagraphStyle("H2", fontName="Seg-B", fontSize=17, leading=21, textColor=ACCENT_DARK, spaceBefore=18, spaceAfter=8,
                         keepWithNext=1),
    "h3": ParagraphStyle("H3", fontName="Seg-B", fontSize=12, leading=16, textColor=INK, spaceBefore=12, spaceAfter=4,
                         keepWithNext=1),
    "h4": ParagraphStyle("H4", fontName="Seg-B", fontSize=10, leading=14, textColor=ACCENT_DARK, spaceBefore=8, spaceAfter=3,
                         keepWithNext=1),
    "cell": ParagraphStyle("cell", fontName="Seg", fontSize=8.3, leading=11, textColor=INK),
    "cellh": ParagraphStyle("cellh", fontName="Seg-B", fontSize=8.3, leading=11, textColor=colors.white),
    "bullet": ParagraphStyle("bullet", fontName="Seg", fontSize=9.6, leading=14, textColor=INK, spaceAfter=2.5, leftIndent=16,
                             bulletIndent=4),
    "bullet2": ParagraphStyle("bullet2", fontName="Seg", fontSize=9.2, leading=13.2, textColor=INK, spaceAfter=2, leftIndent=34,
                              bulletIndent=22),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=7.6, leading=9.8, textColor=colors.HexColor("#14302a"),
                           backColor=CODE_BG, borderPadding=(6, 7, 6, 7), borderColor=LINE, borderWidth=0.6, spaceBefore=4,
                           spaceAfter=10, leftIndent=7, rightIndent=7),
    "toc0": ParagraphStyle("toc0", fontName="Seg-B", fontSize=10, leading=15, textColor=INK, leftIndent=0, spaceBefore=4),
    "toc1": ParagraphStyle("toc1", fontName="Seg", fontSize=8.6, leading=12, textColor=MUTED, leftIndent=16),
    "cover_title": ParagraphStyle("ct", fontName="Seg-B", fontSize=34, leading=38, textColor=colors.white),
    "cover_sub": ParagraphStyle("cs", fontName="Seg", fontSize=14, leading=19, textColor=colors.HexColor("#cfeee5")),
    "cover_text": ParagraphStyle("cx", fontName="Seg", fontSize=10.5, leading=16, textColor=INK, spaceAfter=8),
    "toc_title": ParagraphStyle("tt", fontName="Seg-B", fontSize=20, leading=24, textColor=ACCENT_DARK, spaceAfter=10),
}


# ---------------------------------------------------------------- inline markdown -> reportlab markup
def esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(text: str) -> str:
    out = []
    for i, piece in enumerate(re.split(r"(`[^`]+`)", text)):
        if i % 2 == 1:  # code span
            out.append(f'<font name="Mono" size="8.3" color="#0a4a3b" backColor="#e8efec">{esc(piece[1:-1])}</font>')
            continue
        t = esc(piece)
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
        t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", rf'<a href="\2" color="{LINK.hexval().replace("0x", "#")}">\1</a>', t)
        t = re.sub(r"\[([^\]]+)\]\((?!https?://)[^)]+\)", r"\1", t)  # relative links: keep the text only
        out.append(t)
    return "".join(out)


# ---------------------------------------------------------------- diagrams (the markdown's Mermaid blocks)
def _wrap_w(text, font, size, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if pdfmetrics.stringWidth(trial, font, size) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    return lines + [cur] if cur else lines


def box(d, x, y, w, h, text, fill=SOFT, stroke=ACCENT, size=8.4, bold=False, color=INK):
    d.add(Rect(x, y, w, h, rx=5, ry=5, fillColor=fill, strokeColor=stroke, strokeWidth=0.9))
    font = "Seg-B" if bold else "Seg"
    lines = _wrap_w(text, font, size, w - 10)
    lead = size + 2.2
    top = y + h / 2 + (len(lines) * lead) / 2 - size + 1.6
    for i, ln in enumerate(lines):
        d.add(String(x + w / 2, top - i * lead, ln, fontName=font, fontSize=size, fillColor=color, textAnchor="middle"))


def arrow(d, x1, y1, x2, y2, color=MUTED):
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=1))
    dx, dy = x2 - x1, y2 - y1
    n = (dx * dx + dy * dy) ** 0.5 or 1
    ux, uy = dx / n, dy / n
    px, py = -uy, ux
    a = 5
    d.add(Polygon([x2, y2, x2 - ux * a * 1.6 + px * a * 0.8, y2 - uy * a * 1.6 + py * a * 0.8,
                   x2 - ux * a * 1.6 - px * a * 0.8, y2 - uy * a * 1.6 - py * a * 0.8], fillColor=color, strokeColor=color))


def label(d, x, y, text, size=7.4, anchor="start", color=MUTED):
    d.add(String(x, y, text, fontName="Seg-I", fontSize=size, fillColor=color, textAnchor=anchor))


def diagram_architecture():
    W, H = CONTENT_W, 285
    d = Drawing(W, H)
    box(d, 40, H - 44, 190, 34, "Admin dashboard (React app)", fill=colors.white, bold=True)
    box(d, W - 230, H - 44, 190, 34, "Visitor chat or embed.js bubble (React app)", fill=colors.white, bold=True)
    d.add(Rect(8, 98, W - 16, 100, rx=8, ry=8, fillColor=colors.HexColor("#f7fbf9"), strokeColor=ACCENT, strokeWidth=1.2))
    d.add(String(18, 183, "FastAPI server: one process, port 8000", fontName="Seg-B", fontSize=9.4, fillColor=ACCENT_DARK))
    inner = ["REST and streaming API", "Serves the built website", "Question engine", "PDF ingest pipeline"]
    bw = (W - 16 - 5 * 10) / 4
    for i, t in enumerate(inner):
        box(d, 8 + 10 + i * (bw + 10), 108, bw, 52, t, fill=colors.white)
    arrow(d, 135, H - 44, 135, 198)
    label(d, 143, H - 70, "JWT login")
    arrow(d, W - 135, H - 44, W - 135, 198)
    label(d, W - 127, H - 70, "assistant token")
    bw3 = (W - 20 - 2 * 14) / 3
    texts = ["SQLite database and uploaded PDFs", "System 1 models: embeddings, reranker, classifier",
             "Language model (Groq or Ollama): wording only"]
    for i, t in enumerate(texts):
        x = 10 + i * (bw3 + 14)
        box(d, x, 8, bw3, 46, t, fill=colors.white)
        arrow(d, x + bw3 / 2, 98, x + bw3 / 2, 54)
    return d


def diagram_er():
    W, H = CONTENT_W, 150
    d = Drawing(W, H)
    box(d, W / 2 - 60, H - 42, 120, 32, "organizations", bold=True)
    names = ["question_logs", "chunks", "documents", "rules"]
    bw, gap = 100, (W - 4 * 100) / 5
    centers = []
    for i, n in enumerate(names):
        x = gap + i * (bw + gap)
        box(d, x, 36, bw, 32, n, fill=colors.white, bold=True)
        centers.append(x + bw / 2)
        d.add(Line(W / 2, H - 42, x + bw / 2, 68, strokeColor=MUTED, strokeWidth=0.9))
    label(d, W / 2, 14, "Every table carries org_id. documents are split into chunks and yield rules; deleting cascades.",
          anchor="middle")
    d.add(Line(centers[1] + bw / 2, 52, centers[2] - bw / 2, 52, strokeColor=ACCENT, strokeWidth=1.6))
    d.add(Line(centers[2] + bw / 2, 52, centers[3] - bw / 2, 52, strokeColor=ACCENT, strokeWidth=1.6))
    return d


def vflow(steps, width=300, h=27, gap=13, fills=None):
    W = CONTENT_W
    H = len(steps) * h + (len(steps) - 1) * gap + 6
    d = Drawing(W, H)
    x = (W - width) / 2
    for i, t in enumerate(steps):
        y = H - 3 - (i + 1) * h - i * gap
        fill = (fills or {}).get(i, colors.white)
        box(d, x, y, width, h, t, fill=fill, bold=(i in (0, len(steps) - 1)))
        if i < len(steps) - 1:
            arrow(d, W / 2, y, W / 2, y - gap)
    return d


def diagram_ingest():
    return vflow(["Admin drops a PDF", "Validate: real PDF? size, pages, document count",
                  "Save the file, create the document row (status: processing)", "Respond 201 at once, background job starts",
                  "Extract the text, page by page", "Split each page into passages of about 650 characters",
                  "Embed every passage into 384 numbers", "Mine rule cards with patterns",
                  "status: ready  (any failure: status failed with a readable reason)"], width=360,
                 fills={0: SOFT, 8: SOFT})


def diagram_question():
    main = ["Visitor question + context + recent history", "Router: can the app answer it itself?",
            "1. Retrieve passages (this organization only)", "2. Classify the question type",
            "3. Grounding guard: any real evidence?", "4. Choose the policy or benefit",
            "5. Extract stated facts  and  evidence score (in parallel)", "6. Boolean checks, one per rule (in parallel)",
            "7. Combine: AND, missing information, amount tiers", "8. LLM writes the answer from the verdict",
            "9. Guards: contradiction check, citation fix", "Final answer + sources + follow-up chips + history log"]
    side = {1: "Yes: instant reply (greeting, thanks, injection, gibberish, language, human, vague)",
            4: "No: helpful not-found reply, what we cover, starter chips"}
    h, gap, bw = 28, 12, 270
    W = CONTENT_W
    H = len(main) * h + (len(main) - 1) * gap + 6
    d = Drawing(W, H)
    for i, t in enumerate(main):
        y = H - 3 - (i + 1) * h - i * gap
        box(d, 6, y, bw, h, t, fill=SOFT if i in (0, len(main) - 1) else colors.white, bold=i in (0, len(main) - 1))
        if i < len(main) - 1:
            arrow(d, 6 + bw / 2, y, 6 + bw / 2, y - gap)
        if i in side:
            sx = 6 + bw + 28
            box(d, sx, y - 6, W - sx - 4, h + 12, side[i], fill=colors.HexColor("#fff6e6"), stroke=colors.HexColor("#d99a2b"),
                size=7.9)
            arrow(d, 6 + bw, y + h / 2, sx, y + h / 2)
    return d


DIAGRAMS = [diagram_architecture, diagram_er, diagram_ingest, diagram_question]


# ---------------------------------------------------------------- markdown -> flowables
def table_flowable(rows):
    head, body = rows[0], rows[1:]
    ncol = len(head)
    weights = []
    for c in range(ncol):
        longest = max(len(re.sub(r"[`*]", "", r[c])) if c < len(r) else 0 for r in rows)
        weights.append(min(max(longest, 9), 70))
    # no column may be narrower than its longest unbreakable word (so `small_talk` is never split mid-word)
    floor = []
    for c in range(ncol):
        words = [w for r in rows if c < len(r) for w in re.sub(r"[*]", "", r[c]).split()]
        floor.append(max((len(w) for w in words), default=4) * 4.7 + 14)
    total = sum(weights)
    widths = [max(CONTENT_W * w / total, 1.6 * cm, f) for w, f in zip(weights, floor)]
    extra = sum(widths) - CONTENT_W
    if extra > 0:  # take the excess from the columns that have room above their floor
        room = [w - f for w, f in zip(widths, floor)]
        tot = sum(room) or 1
        widths = [w - extra * r / tot for w, r in zip(widths, room)]
    data = [[Paragraph(inline(c), S["cellh"]) for c in head]]
    for r in body:
        r = (r + [""] * ncol)[:ncol]
        data.append([Paragraph(inline(c), S["cell"]) for c in r])
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [("BACKGROUND", (0, 0), (-1, 0), ACCENT_DARK), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("GRID", (0, 0), (-1, -1), 0.4, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
             ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f6faf8")))
    t.setStyle(TableStyle(style))
    return [Spacer(1, 3), t, Spacer(1, 9)]


def code_flowable(lines):
    out = []
    for ln in lines:
        indent = len(ln) - len(ln.lstrip(" "))
        if len(ln) <= 112:
            out.append(ln)
        else:
            parts = _wrap(ln.strip(), 112 - indent - 4, break_long_words=True) or [ln]
            out.append(" " * indent + parts[0])
            out += [" " * (indent + 4) + p for p in parts[1:]]
    return Preformatted("\n".join(out), S["code"])


def parse(md: str):
    lines = md.splitlines()
    story, cover = [], {"title": "", "intro": ""}
    i, diag_i, skipping = 0, 0, False
    para: list[str] = []

    def flush_para():
        if para:
            story.append(Paragraph(inline(" ".join(para)), S["body"]))
            para.clear()

    while i < len(lines):
        ln = lines[i]
        if ln.strip() == "**Contents**":
            skipping = True
            i += 1
            continue
        if skipping:
            if ln.startswith("---"):
                skipping = False
            i += 1
            continue
        if ln.startswith("```"):
            flush_para()
            lang, buf = ln[3:].strip(), []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            if lang == "mermaid":
                story += [Spacer(1, 4), KeepTogether([DIAGRAMS[diag_i]()]), Spacer(1, 8)]
                diag_i += 1
            else:
                story.append(code_flowable(buf))
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", ln)
        if m:
            flush_para()
            level, text = len(m.group(1)), m.group(2).strip()
            if level == 1:
                cover["title"] = text
            else:
                nxt = next((x for x in lines[i + 1:] if x.strip()), "")
                style = S[f"h{level}"]
                if nxt.startswith("```") and not nxt.startswith("```mermaid"):
                    style = ParagraphStyle(style.name + "x", parent=style, keepWithNext=0)  # keeps the TOC hook (name starts with H)
                story.append(Paragraph(inline(text), style))
            i += 1
            continue
        if re.match(r"^---+\s*$", ln):
            flush_para()
            i += 1
            continue
        if ln.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            flush_para()
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                if not re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i]):
                    cells = [c.strip() for c in re.split(r"(?<!\\)\|", lines[i].strip().strip("|"))]
                    rows.append([c.replace("\\|", "|") for c in cells])
                i += 1
            story += table_flowable(rows)
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)", ln)
        if m:
            flush_para()
            indent, marker, text = len(m.group(1)), m.group(2), m.group(3)
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]) \
                    and not lines[i].lstrip().startswith(("|", "```", "#")) and lines[i].startswith(" "):
                text += " " + lines[i].strip()
                i += 1
            style = S["bullet2"] if indent >= 2 else S["bullet"]
            bullet = "•" if marker in "-*" else marker
            story.append(Paragraph(inline(text), style, bulletText=bullet if indent < 2 else "–"))
            continue
        if not ln.strip():
            flush_para()
            i += 1
            continue
        if not cover["intro"] and cover["title"] and not story:
            cover["intro"] = ln.strip()
            i += 1
            continue
        para.append(ln.strip())
        i += 1
    flush_para()
    return cover, story


# ---------------------------------------------------------------- document
class Doc(BaseDocTemplate):
    def __init__(self, path, **kw):
        super().__init__(path, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=2.2 * cm, bottomMargin=2 * cm,
                         title="Lumen: complete documentation (A to Z)", author="Lumen", subject="Architecture, usage and operations",
                         **kw)
        frame = Frame(MARGIN, self.bottomMargin, CONTENT_W, PAGE_H - self.topMargin - self.bottomMargin, id="f", leftPadding=0,
                      rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="cover", frames=[frame], onPage=self._cover_bg, autoNextPageTemplate="main"),
                               PageTemplate(id="main", frames=[frame], onPage=self._page)])
        self._n = 0

    @staticmethod
    def _cover_bg(c, doc):
        c.saveState()
        c.setFillColor(colors.HexColor("#0c1210"))
        c.rect(0, PAGE_H * 0.46, PAGE_W, PAGE_H * 0.54, stroke=0, fill=1)
        c.setFillColor(ACCENT)
        c.rect(0, PAGE_H * 0.46 - 6, PAGE_W, 6, stroke=0, fill=1)
        c.restoreState()

    @staticmethod
    def _page(c, doc):
        c.saveState()
        c.setStrokeColor(LINE)
        c.setLineWidth(0.5)
        c.line(MARGIN, PAGE_H - 1.5 * cm, PAGE_W - MARGIN, PAGE_H - 1.5 * cm)
        c.line(MARGIN, 1.5 * cm, PAGE_W - MARGIN, 1.5 * cm)
        c.setFont("Seg", 8)
        c.setFillColor(MUTED)
        c.drawString(MARGIN, PAGE_H - 1.35 * cm, "Lumen: complete documentation")
        c.drawRightString(PAGE_W - MARGIN, 1.0 * cm, f"Page {doc.page}")
        c.drawString(MARGIN, 1.0 * cm, "github.com/salman-kv/lumen")
        c.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name[:2] in ("H2", "H3"):
            level = 0 if flowable.style.name[:2] == "H2" else 1
            text = flowable.getPlainText()
            key = f"h{zlib.crc32(text.encode()):08x}"  # stable across passes, or the contents never settles
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level, closed=level == 0)
            self.notify("TOCEntry", (level, text, self.page, key))


def main():
    cover, body = parse(SRC.read_text(encoding="utf-8"))
    story = [Spacer(1, 3.2 * cm), Paragraph("Lumen", S["cover_title"]), Spacer(1, 6),
             Paragraph("Complete documentation, A to Z", S["cover_sub"]), Spacer(1, 9.4 * cm),
             Paragraph(inline(cover["intro"]), S["cover_text"]), Spacer(1, 6),
             Paragraph(f"<b>Repository:</b> github.com/salman-kv/lumen<br/><b>Version of this document:</b> {date.today():%d %B %Y}",
                       S["cover_text"]), PageBreak()]
    toc = TableOfContents()
    toc.levelStyles = [S["toc0"], S["toc1"]]
    toc.dotsMinLevel = 0
    story += [Paragraph("Contents", S["toc_title"]), toc, PageBreak()] + body
    doc = Doc(str(OUT))
    doc.multiBuild(story)
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    sys.exit(main())
