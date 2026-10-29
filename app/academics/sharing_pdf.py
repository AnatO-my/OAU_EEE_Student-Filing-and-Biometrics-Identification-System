"""Deterministic, immutable guardian statement snapshots (no delivery side effects)."""
import base64
import hashlib
import io
import re
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

from django.core.exceptions import ValidationError
import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                               Spacer, Table, TableStyle, KeepTogether)

VERSION = 1
NAVY = colors.HexColor("#17334b")
TEAL = colors.HexColor("#087e8b")


def _styles():
    # Vera ships with ReportLab, so installed and portable deployments use the same fonts.
    fonts = Path(reportlab.__file__).parent / "fonts"
    for name, filename in (("Statement", "Vera.ttf"), ("StatementBold", "VeraBd.ttf")):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(fonts / filename)))
    return {
        "body": ParagraphStyle("body", fontName="Statement", fontSize=9, leading=13,
                               textColor=NAVY, spaceAfter=5, splitLongWords=True),
        "small": ParagraphStyle("small", fontName="Statement", fontSize=7.5, leading=11,
                                textColor=NAVY, spaceAfter=4),
        "title": ParagraphStyle("title", fontName="StatementBold", fontSize=21, leading=26,
                                textColor=NAVY, spaceAfter=8),
        "heading": ParagraphStyle("heading", fontName="StatementBold", fontSize=10,
                                  leading=14, textColor=TEAL, spaceAfter=8),
        "stat": ParagraphStyle("stat", fontName="StatementBold", fontSize=23, leading=29,
                               alignment=TA_CENTER, textColor=NAVY),
        "label": ParagraphStyle("label", fontName="Statement", fontSize=8, leading=12,
                                alignment=TA_CENTER, textColor=NAVY),
        "header": ParagraphStyle("header", fontName="StatementBold", fontSize=8,
                                 leading=11, textColor=colors.white),
    }


def render_statement(*, name, identifier, session, semester, report, university="",
                     department="", is_revised=False):
    """Render only verified report fields. No clock, random identifier or grading policy."""
    styles = _styles()
    def p(value, style="body"):
        return Paragraph(escape(str(value)), styles[style])
    rows = [row for row in report["records"]
            if row["session"] == session and row["semester"] == semester]
    units = sum(Decimal(str(row["units"])) for row in rows)
    cumulative_units = sum(Decimal(str(row["units"])) for row in report["records"])
    content = io.BytesIO()
    doc = BaseDocTemplate(content, pagesize=A4, leftMargin=42, rightMargin=42,
                          topMargin=42, bottomMargin=53, invariant=1,
                          title="Semester Result Statement", author=university or department)
    def footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#cbd5dc"))
        canvas.line(42, 43, A4[0] - 42, 43)
        canvas.setFont("Statement", 7)
        canvas.setFillColor(NAVY)
        canvas.drawString(42, 31, "Confidential | For the registered recipient")
        canvas.drawRightString(A4[0] - 42, 31, f"Page {document.page}")
        canvas.restoreState()
    doc.addPageTemplates(PageTemplate(id="statement", frames=[Frame(
        42, 53, A4[0] - 84, A4[1] - 95, leftPadding=0, rightPadding=0,
        topPadding=0, bottomPadding=0)], onPage=footer))
    story = []
    if university:
        story.append(p(university.upper(), "heading"))
    if department:
        story.append(p(department, "body"))
    story += [Spacer(1, 8), p("Revised Result" if is_revised else "Semester Result Statement", "title"),
              p("Verified recorded results for the selected academic period.", "small"),
              Spacer(1, 13), p("STUDENT & ACADEMIC PERIOD", "heading")]
    info = Table([[p("Student"), p(name), p("Session"), p(session)],
                  [p("Identifier"), p(identifier), p("Semester"), p(semester.title())]],
                 colWidths=[58, 219, 68, A4[0] - 429], hAlign="LEFT")
    info.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f6f8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story += [info, Spacer(1, 17)]
    cards = Table([[p(report["gpa"], "stat"), p(report["cgpa"], "stat"), p(units, "stat")],
                   [p("Calculated semester GPA", "label"), p("Calculated CGPA through period", "label"),
                    p("Recorded semester credits", "label")]], colWidths=[(A4[0] - 84) / 3] * 3)
    cards.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eaf3f4")),
        ("TOPPADDING", (0, 0), (-1, 0), 10), ("BOTTOMPADDING", (0, -1), (-1, -1), 10)]))
    story += [cards, Spacer(1, 18), p("SEMESTER COURSE RESULTS", "heading")]
    data = [[p(v, "header") for v in ("Course / title", "Units", "Score", "Grade point", "Credit points")]]
    for row in sorted(rows, key=lambda r: (r["course"], r["attempt"], r["id"])):
        course = p(f'{row["course"]} - {row["title"]}' if row.get("title") else row["course"])
        # Attempt labels distinguish repeat sittings; all attempts remain in existing calculations.
        data.append([course, p(row["units"]), p(row["score"]), p(row["grade_point"]),
                     p(Decimal(str(row["units"])) * Decimal(row["grade_point"]))])
        if row["attempt"] > 1:
            data[-1][0] = p(f'{row["course"]} - {row.get("title", "")} (attempt {row["attempt"]})')
    table = Table(data, colWidths=[A4[0] - 304, 42, 45, 63, 70], repeatRows=1,
                  hAlign="LEFT", splitInRow=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6f8")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, 0), 1, TEAL)]))
    story += [table, Spacer(1, 15), KeepTogether([
        p("ABOUT THIS STATEMENT", "heading"),
        p(f"CGPA uses verified recorded attempts through {session} / {semester.title()}; "
          f"recorded cumulative credits: {cumulative_units}. Later results are excluded. "
          "GPA and CGPA follow the recorded grading scales and existing calculation policy.", "small"),
        p("This is a summary of verified recorded results, not an official transcript or "
          "certification of complete academic history. Contact the department about discrepancies.", "small")])]
    doc.build(story)
    return content.getvalue()


def make_snapshot(**kwargs):
    content = render_statement(**kwargs)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", str(kwargs["identifier"])).strip(".-")[:60] or "student"
    period = re.sub(r"[^A-Za-z0-9_-]+", "-", kwargs["session"] + "-" + kwargs["semester"])
    return {"version": VERSION, "filename": f"result-statement-{safe}-{period}.pdf",
            "sha256": hashlib.sha256(content).hexdigest(), "size": len(content),
            "content_base64": base64.b64encode(content).decode("ascii")}


def snapshot_bytes(snapshot):
    try:
        content = base64.b64decode(snapshot["content_base64"], validate=True)
        valid = (content.startswith(b"%PDF-") and len(content) == snapshot["size"]
                 and hashlib.sha256(content).hexdigest() == snapshot["sha256"])
        if not valid:
            raise ValueError("Invalid PDF snapshot")
        return content
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("The reviewed PDF snapshot is invalid. Create a fresh preview.") from exc


def uses_pdf(preview):
    return any((item.get("report") or {}).get("pdf") for item in preview)
