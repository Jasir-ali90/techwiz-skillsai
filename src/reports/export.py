"""Tabular export in CSV, Excel and PDF (SRS Step 63), using pandas,
openpyxl and reportlab."""
import io
import json
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

MEDIA_TYPES = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}
PDF_MAX_COLUMNS = 10
PDF_CELL_CHARS = 180


def _flat(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    return value


def frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{k: _flat(v) for k, v in r.items()} for r in rows])


def to_csv(rows: list[dict]) -> bytes:
    return frame(rows).to_csv(index=False).encode("utf-8")


def to_xlsx(rows: list[dict], title: str, summary: dict | None = None) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df = frame(rows)
        (df if not df.empty else pd.DataFrame({"message": ["No rows"]})).to_excel(
            writer, sheet_name="Report", index=False)
        sheet = writer.sheets["Report"]
        for column in sheet.columns:
            width = min(60, max(10, max(len(str(c.value or "")) for c in column[:200]) + 2))
            sheet.column_dimensions[column[0].column_letter].width = width
        sheet.freeze_panes = "A2"
        meta = pd.DataFrame([{"field": "report", "value": title},
                             {"field": "generated_at", "value": datetime.now().isoformat(timespec="seconds")},
                             {"field": "rows", "value": len(rows)}] +
                            [{"field": k, "value": _flat(v)} for k, v in (summary or {}).items()])
        meta.to_excel(writer, sheet_name="Summary", index=False)
    return buffer.getvalue()


def to_pdf(rows: list[dict], title: str, summary: dict | None = None, columns: list[str] | None = None) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm, title=title, author="SkillSprint AI")
    styles = getSampleStyleSheet()
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=6.5, leading=8)
    head = ParagraphStyle("head", parent=cell, fontName="Helvetica-Bold")
    story = [Paragraph(title, styles["Title"]),
             Paragraph(f"Generated {datetime.now():%Y-%m-%d %H:%M} · {len(rows)} rows", styles["Normal"]),
             Spacer(1, 4 * mm)]
    if summary:
        story.append(Paragraph(" · ".join(f"<b>{_escape(str(k))}</b>: {_escape(str(_flat(v)))}" for k, v in list(summary.items())[:12]),
                               styles["Normal"]))
        story.append(Spacer(1, 4 * mm))
    if rows:
        cols = columns or list(rows[0].keys())[:PDF_MAX_COLUMNS]
        data = [[Paragraph(str(c), head) for c in cols]]
        for r in rows:
            data.append([Paragraph(_escape(str(_flat(r.get(c, "")) or "")[:PDF_CELL_CHARS]), cell) for c in cols])
        width = (landscape(A4)[0] - 20 * mm) / len(cols)
        table = Table(data, colWidths=[width] * len(cols), repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2933")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c9c4b8")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f2ee")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("No rows.", styles["Normal"]))
    doc.build(story)
    return buffer.getvalue()


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(rows: list[dict], fmt: str, title: str, summary: dict | None = None,
           pdf_columns: list[str] | None = None) -> bytes:
    if fmt == "csv":
        return to_csv(rows)
    if fmt == "xlsx":
        return to_xlsx(rows, title, summary)
    if fmt == "pdf":
        return to_pdf(rows, title, summary, pdf_columns)
    raise ValueError(fmt)
