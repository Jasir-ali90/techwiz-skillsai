"""Batch converts all Markdown (.md) documentation files in SkillSprint_Submission
into beautifully styled, executive-grade PDF documents with consistent enterprise styling,
calibrated tables, headers, footers, code formatting, and page numbers.
"""
import re
import os
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable, Preformatted
)
from reportlab.pdfgen import canvas

PRINTABLE_WIDTH = 504  # 612 - 108

class EnterpriseCanvas(canvas.Canvas):
    """Running header and footer with dynamic Page X of Y numbering."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self.doc_title = "Technical Documentation"

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (pages after page 1)
        if self._pageNumber > 1:
            title_text = f"SkillSprint AI — {self.doc_title}  |  TECHWIZ 7"
            if len(title_text) > 65:
                title_text = title_text[:62] + "..."
            self.drawString(54, letter[1] - 36, title_text)
            self.drawRightString(letter[0] - 54, letter[1] - 36, "Nexora Labs · OnboardVerse")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)
        
        # Running Footer on all pages
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 46, letter[0] - 54, 46)
        self.drawString(54, 34, "CONFIDENTIAL  ·  Aptech World Tech Championship  ·  Jasir Ali")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 54, 34, page_str)
        self.restoreState()


def inline_markdown_to_xml(text: str) -> str:
    """Converts common inline markdown tags to ReportLab XML tags."""
    # Strip raw html images or unsupported container tags that break ReportLab parser
    text = re.sub(r'<img[^>]*>', '', text)
    text = re.sub(r'</?(?:div|span|p|a|center|details|summary)[^>]*>', '', text)
    # Escape raw ampersands not part of XML entities
    text = re.sub(r'&(?!(?:amp|lt|gt|quot|apos);)', '&amp;', text)
    # Inline code: `code`
    text = re.sub(r'`([^`]+)`', r'<font name="Courier" color="#0369A1"><b>\1</b></font>', text)
    # Bold italic: ***text*** or ___text___
    text = re.sub(r'\*\*\*([^*]+)\*\*\*', r'<b><i>\1</i></b>', text)
    # Bold: **text**
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    # Italic: *text* (avoiding bullet points)
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<i>\1</i>', text)
    # Markdown links: [text](url) -> <u>text</u>
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'<font color="#0284C7"><u>\1</u></font>', text)
    return text


def md_table_to_flowable(table_lines, styles, c_navy, c_body):
    """Parses markdown table lines and returns a styled ReportLab Table flowable."""
    if len(table_lines) < 2:
        return None

    raw_rows = []
    for line in table_lines:
        line = line.strip()
        if not line or not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.split('|')[1:-1]]
        if cells:
            raw_rows.append(cells)

    if not raw_rows:
        return None

    # Check if second row is separator like |---|---|
    header = raw_rows[0]
    data_rows = []
    start_idx = 1
    if len(raw_rows) > 1 and all(set(c).issubset({'-', ':', ' '}) for c in raw_rows[1]):
        start_idx = 2

    data_rows = raw_rows[start_idx:]
    num_cols = len(header)
    if num_cols == 0:
        return None

    # Normalise row lengths
    norm_header = [header[i] if i < len(header) else "" for i in range(num_cols)]
    norm_data = []
    for row in data_rows:
        norm_data.append([row[i] if i < len(row) else "" for i in range(num_cols)])

    # Compute column weights based on content length
    col_lens = [len(norm_header[i]) for i in range(num_cols)]
    for row in norm_data:
        for i in range(num_cols):
            col_lens[i] = max(col_lens[i], len(row[i]))

    total_len = sum(col_lens) or 1
    # Minimum col width
    min_col_w = max(40, int(PRINTABLE_WIDTH / num_cols * 0.4))
    raw_widths = [max(min_col_w, int(PRINTABLE_WIDTH * (l / total_len))) for l in col_lens]
    
    # Scale to exactly PRINTABLE_WIDTH
    scale = PRINTABLE_WIDTH / sum(raw_widths)
    col_widths = [int(w * scale) for w in raw_widths]
    # adjust rounding error
    diff = PRINTABLE_WIDTH - sum(col_widths)
    col_widths[-1] += diff

    th_style = ParagraphStyle(
        'TH', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=7.5, leading=10,
        textColor=colors.white
    )
    td_style = ParagraphStyle(
        'TD', parent=styles['Normal'],
        fontName='Helvetica', fontSize=7, leading=9.5,
        textColor=c_body
    )

    table_data = []
    # Header row
    h_row = [Paragraph(inline_markdown_to_xml(c), th_style) for c in norm_header]
    table_data.append(h_row)

    # Data rows
    for r in norm_data:
        row_cells = [Paragraph(inline_markdown_to_xml(c), td_style) for c in r]
        table_data.append(row_cells)

    t = Table(table_data, colWidths=col_widths)
    t_style = [
        ('BACKGROUND', (0,0), (-1,0), c_navy),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]
    for row_idx in range(1, len(table_data)):
        if row_idx % 2 == 1:
            t_style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#F8FAFC")))
    t.setStyle(TableStyle(t_style))
    return t


def convert_md_file_to_pdf(md_path: Path, output_pdf_path: Path = None):
    """Parses a markdown file and compiles a styled PDF with ReportLab."""
    if output_pdf_path is None:
        output_pdf_path = md_path.with_suffix('.pdf')

    print(f"Converting: {md_path} -> {output_pdf_path.name}")
    text = md_path.read_text(encoding='utf-8', errors='ignore')
    lines = text.splitlines()

    # Extract primary doc title
    doc_title = md_path.stem.replace('_', ' ')
    for line in lines[:10]:
        if line.startswith('# '):
            clean_t = line[2:].strip()
            # clean formatting
            clean_t = re.sub(r'[*_`#]', '', clean_t)
            if '—' in clean_t:
                clean_t = clean_t.split('—')[0].strip()
            if '-' in clean_t and len(clean_t) > 30:
                clean_t = clean_t.split('-')[0].strip()
            doc_title = clean_t[:50]
            break

    doc = SimpleDocTemplate(
        str(output_pdf_path),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    c_primary = colors.HexColor("#0B132B")
    c_accent = colors.HexColor("#0284C7")
    c_navy = colors.HexColor("#0F172A")
    c_body = colors.HexColor("#1E293B")
    c_muted = colors.HexColor("#64748B")

    h1_style = ParagraphStyle(
        'DocH1', parent=styles['Heading1'],
        fontName='Helvetica-Bold', fontSize=15, leading=19,
        textColor=c_primary, spaceBefore=14, spaceAfter=6, keepWithNext=True
    )
    h2_style = ParagraphStyle(
        'DocH2', parent=styles['Heading2'],
        fontName='Helvetica-Bold', fontSize=12, leading=16,
        textColor=c_accent, spaceBefore=10, spaceAfter=4, keepWithNext=True
    )
    h3_style = ParagraphStyle(
        'DocH3', parent=styles['Heading3'],
        fontName='Helvetica-Bold', fontSize=10, leading=14,
        textColor=c_navy, spaceBefore=8, spaceAfter=3, keepWithNext=True
    )
    body_style = ParagraphStyle(
        'DocBody', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8.5, leading=12.5,
        textColor=c_body, spaceAfter=5
    )
    bullet_style = ParagraphStyle(
        'DocBullet', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8.5, leading=12,
        textColor=c_body, leftIndent=14, spaceAfter=3
    )
    quote_style = ParagraphStyle(
        'DocQuote', parent=styles['Normal'],
        fontName='Helvetica-Oblique', fontSize=8, leading=12,
        textColor=colors.HexColor("#0C4A6E")
    )
    code_style = ParagraphStyle(
        'DocCode', parent=styles['Code'],
        fontName='Courier', fontSize=7.5, leading=10,
        textColor=colors.HexColor("#0F172A")
    )
    meta_tag_style = ParagraphStyle(
        'DocMetaTag', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=8, leading=11,
        textColor=colors.HexColor("#0284C7"), alignment=1
    )

    story = []

    # Document Header Badge
    badge_table = Table([[
        Paragraph(f"<b>TECHWIZ 7 · OFFICIAL SUBMISSION COMPONENT · {doc_title.upper()}</b>", meta_tag_style)
    ]], colWidths=[PRINTABLE_WIDTH])
    badge_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#E0F2FE")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#38BDF8")),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(badge_table)
    story.append(Spacer(1, 10))

    # Parser state machine
    i = 0
    in_code_block = False
    code_lines = []
    in_table = False
    table_lines = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Handle Code Blocks ```
        if stripped.startswith('```'):
            if in_code_block:
                # End of code block
                in_code_block = False
                code_text = "\n".join(code_lines)
                code_p = Preformatted(code_text, code_style)
                code_table = Table([[code_p]], colWidths=[PRINTABLE_WIDTH])
                code_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
                    ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
                    ('TOPPADDING', (0,0), (-1,-1), 6),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                    ('LEFTPADDING', (0,0), (-1,-1), 8),
                    ('RIGHTPADDING', (0,0), (-1,-1), 8),
                ]))
                story.append(code_table)
                story.append(Spacer(1, 6))
                code_lines = []
            else:
                # Start of code block
                in_code_block = True
                code_lines = []
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # Handle Markdown Tables
        if stripped.startswith('|') and stripped.endswith('|'):
            if not in_table:
                in_table = True
                table_lines = [stripped]
            else:
                table_lines.append(stripped)
            i += 1
            continue
        else:
            if in_table:
                # Process accumulated table
                t_flowable = md_table_to_flowable(table_lines, styles, c_navy, c_body)
                if t_flowable:
                    story.append(t_flowable)
                    story.append(Spacer(1, 8))
                in_table = False
                table_lines = []

        # Empty lines
        if not stripped:
            i += 1
            continue

        # Horizontal Rule
        if stripped in ['---', '***', '___']:
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E1"), spaceBefore=6, spaceAfter=8))
            i += 1
            continue

        # Headings
        if stripped.startswith('# '):
            h_text = inline_markdown_to_xml(stripped[2:].strip())
            story.append(Paragraph(h_text, h1_style))
            i += 1
            continue
        elif stripped.startswith('## '):
            h_text = inline_markdown_to_xml(stripped[3:].strip())
            story.append(Paragraph(h_text, h2_style))
            i += 1
            continue
        elif stripped.startswith('### '):
            h_text = inline_markdown_to_xml(stripped[4:].strip())
            story.append(Paragraph(h_text, h3_style))
            i += 1
            continue
        elif stripped.startswith('#### '):
            h_text = inline_markdown_to_xml(stripped[5:].strip())
            story.append(Paragraph(f"<b>{h_text}</b>", body_style))
            i += 1
            continue

        # Blockquote >
        if stripped.startswith('>'):
            q_text = inline_markdown_to_xml(stripped[1:].strip())
            q_table = Table([[Paragraph(q_text, quote_style)]], colWidths=[PRINTABLE_WIDTH])
            q_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F0F9FF")),
                ('LINELEFT', (0,0), (0,-1), 2.5, c_accent),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('LEFTPADDING', (0,0), (-1,-1), 8),
                ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(q_table)
            story.append(Spacer(1, 4))
            i += 1
            continue

        # Bullet lists (- or * or 1.)
        bullet_match = re.match(r'^(?:[-*]|\d+\.)\s+(.+)', stripped)
        if bullet_match:
            b_text = inline_markdown_to_xml(bullet_match.group(1).strip())
            story.append(Paragraph(f"• {b_text}", bullet_style))
            i += 1
            continue

        # Regular Body Paragraph
        p_text = inline_markdown_to_xml(stripped)
        story.append(Paragraph(p_text, body_style))
        i += 1

    # End of file cleanups
    if in_table and table_lines:
        t_flowable = md_table_to_flowable(table_lines, styles, c_navy, c_body)
        if t_flowable:
            story.append(t_flowable)
            story.append(Spacer(1, 8))

    # Custom canvas with document title
    def canvas_maker(*args, **kwargs):
        c = EnterpriseCanvas(*args, **kwargs)
        c.doc_title = doc_title
        return c

    doc.build(story, canvasmaker=canvas_maker)
    print(f"Generated: {output_pdf_path} ({output_pdf_path.stat().st_size:,} bytes)")


def batch_convert_submission_docs():
    """Finds and converts all relevant documentation MD files in SkillSprint_Submission."""
    base_dir = Path("SkillSprint_Submission")
    
    # Specific documentation categories
    target_dirs = [
        base_dir / "1. Documentation",
        base_dir / "2. GitHub",
        base_dir / "3. Project Demonstration Video",
        base_dir / "5. UI & UX Figma Design (Optional)",
        base_dir / "6. Website Hosted Link",
    ]

    converted_count = 0
    for target in target_dirs:
        if not target.exists():
            continue
        for md_file in target.rglob("*.md"):
            # Skip Project_Report md since it has dedicated compiler with high-res diagrams
            if "SkillSprint_AI_Project_Report.md" in md_file.name:
                continue
            try:
                convert_md_file_to_pdf(md_file)
                converted_count += 1
            except Exception as e:
                print(f"Error converting {md_file}: {e}")

    # Also convert root README in 4. Source Code
    src_readme = base_dir / "4. Source Code" / "README.md"
    if src_readme.exists():
        try:
            convert_md_file_to_pdf(src_readme)
            converted_count += 1
        except Exception as e:
            print(f"Error converting {src_readme}: {e}")

    print(f"\nBatch conversion complete! Total converted PDFs: {converted_count}")


if __name__ == '__main__':
    batch_convert_submission_docs()
