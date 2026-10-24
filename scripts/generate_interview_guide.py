"""Generates the Simple English Interview Preparation Guide for SkillSprint AI:
1. Markdown: docs/INTERVIEW_QA_PREPARATION_GUIDE.md
2. PDF: docs/INTERVIEW_QA_PREPARATION_GUIDE.pdf

Configured specifically for a 3-PERSON TEAM:
- Member 1: Team Lead & Lead Developer (Backend, AI Pipeline & Python Rules)
- Member 2: Frontend Developer (React 19, TypeScript UI & API Integration)
- Member 3: Documentation & System Analyst (SRS Reports, Diagrams, Manuals & Presentations)
"""
import os
import re
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.pdfgen import canvas

PRINTABLE_WIDTH = 504  # 612 - 108 (54pt margins each side)
DOCS_DIR = Path("docs")
DOCS_DIR.mkdir(parents=True, exist_ok=True)

OUT_MD = DOCS_DIR / "INTERVIEW_QA_PREPARATION_GUIDE.md"
OUT_PDF = DOCS_DIR / "INTERVIEW_QA_PREPARATION_GUIDE.pdf"


class SimpleInterviewGuideCanvas(canvas.Canvas):
    """Running header and footer with dynamic 'Page X of Y' numbering."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

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
        if self._pageNumber == 1:
            return

        self.saveState()
        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(colors.HexColor("#0284C7"))
        self.drawString(54, letter[1] - 34, "SkillSprint AI")
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(110, letter[1] - 34, "— 3-Member Team Interview Defense Guide (TECHWIZ 7)")
        self.drawRightString(letter[0] - 54, letter[1] - 34, "Nexora Labs")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, letter[1] - 38, letter[0] - 54, letter[1] - 38)

        # Footer
        self.line(54, 42, letter[0] - 54, 42)
        self.drawString(54, 30, "CONFIDENTIAL · Aptech World Tech Championship · 3-Person Team Speaking Guide")
        self.drawRightString(letter[0] - 54, 30, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


def inline_markdown_to_xml(text: str) -> str:
    text = re.sub(r'<img[^>]*>', '', text)
    text = re.sub(r'</?(?:div|span|p|a|center|details|summary)[^>]*>', '', text)
    text = re.sub(r'&(?!(?:amp|lt|gt|quot|apos);)', '&amp;', text)
    text = re.sub(r'`([^`]+)`', r'<font name="Courier" color="#0369A1"><b>\1</b></font>', text)
    text = re.sub(r'\*\*\*([^*]+)\*\*\*', r'<b><i>\1</i></b>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<i>\1</i>', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'<font color="#0284C7"><u>\1</u></font>', text)
    return text


def md_table_to_flowable(table_lines, styles, c_navy, c_body):
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

    header = raw_rows[0]
    data_rows = []
    start_idx = 1
    if len(raw_rows) > 1 and all(set(c).issubset({'-', ':', ' '}) for c in raw_rows[1]):
        start_idx = 2

    data_rows = raw_rows[start_idx:]
    num_cols = len(header)
    if num_cols == 0:
        return None

    norm_header = [header[i] if i < len(header) else "" for i in range(num_cols)]
    norm_data = []
    for row in data_rows:
        norm_data.append([row[i] if i < len(row) else "" for i in range(num_cols)])

    col_lens = [max(8, len(norm_header[i])) for i in range(num_cols)]
    for row in norm_data:
        for i in range(num_cols):
            col_lens[i] = max(col_lens[i], len(row[i]))

    total_len = sum(col_lens) or 1
    min_col_w = max(45, int(PRINTABLE_WIDTH / num_cols * 0.45))
    raw_widths = [max(min_col_w, int(PRINTABLE_WIDTH * (l / total_len))) for l in col_lens]

    scale = PRINTABLE_WIDTH / sum(raw_widths)
    col_widths = [int(w * scale) for w in raw_widths]
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
    table_data.append([Paragraph(inline_markdown_to_xml(c), th_style) for c in norm_header])
    for r in norm_data:
        table_data.append([Paragraph(inline_markdown_to_xml(c), td_style) for c in r])

    t = Table(table_data, colWidths=col_widths, repeatRows=1)
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


def build_3person_markdown_content() -> str:
    return """# SkillSprint AI — Simple English Interview Guide (3-Member Team)
**Aptech TECHWIZ 7 · OnboardVerse · Generative AI PowerPlay**  
**Team Structure:** 3 Members (Lead/Backend & AI, Frontend Developer, Documentation Specialist)  
**Style:** Simple Words, Short & To-The-Point Answers (30–45 Seconds per Answer)

---

## 1. Project Overview & Main Objectives
**Simple Answer:**  
"Our project is **SkillSprint AI**, an employee onboarding and training system for **Nexora Labs**.  
Our main goal is to create personalized 90-day learning plans for new employees so they can start their work quickly and follow all company rules.

We use a simple **two-step system**:
* **Step 1 (AI):** AI writes the personalized training plan with tasks, checklists, and quizzes.
* **Step 2 (Python):** Pure Python code checks the plan against real company policies to make sure the AI did not make up any fake rules or miss anything mandatory."

---

## 2. Project Features and Functionality
**Simple Answer:**  
"SkillSprint AI has five main features:
1. **Document Upload:** Admins upload company policy files (PDF and Word). The system checks file types, rejects fake files, and prevents duplicate uploads.
2. **Rule Matrix:** Python reads all company rules and organizes them by job role (like Backend Developer or QA Engineer).
3. **AI Plan Maker:** Generates Day 1 to Day 90 plans with learning modules, checklists, and quizzes.
4. **Python Checker (13 Rules):** Verifies that all required rules are covered, citations are real, and no contradictory rules exist.
5. **Smart Policy Updates:** When a company policy changes, the system updates only the affected modules without deleting the employee's completed quiz scores."

---

## 3. Technologies and Tools Used
**Simple Answer:**  
"We used modern and reliable tools:
* **Backend:** Python and FastAPI to build the fast web server.
* **Database:** PostgreSQL with `pgvector` to store data and search text quickly.
* **AI Models:** Claude, Google Gemini, and local Ollama to generate learning plans.
* **Frontend:** React and TypeScript with Vite to create a clean, responsive web interface.
* **Testing & Tools:** Docker to run everything easily, and Pytest with 232 automated tests."

---

## 4. Your Individual Contribution (3-Person Team Breakdown)

### Member 1: Team Lead & Lead Developer (Backend & AI)
*"I am the Team Lead and lead developer. I built the backend server using FastAPI and set up the PostgreSQL database with vector search. I also built the AI generation pipeline (Claude/Gemini/Ollama) and wrote the 13 Python validation rules that check the AI plans with zero AI imports."*

### Member 2: Frontend Developer & UI Integration
*"I built the web user interface using React and TypeScript across 18 pages. I created the login page, the plan viewer, and the employee quiz page, and connected the frontend with all backend APIs so users can complete tasks and see live progress."*

### Member 3: Documentation & System Analyst
*"I managed the complete technical documentation for the project. I authored the comprehensive SRS report, designed the 6 system architecture and UML diagrams, wrote the testing reports and user manual, and ensured all project deliverables matched the software 100%."*

---

## 5. How Your Team Worked Together
**Simple Answer:**  
"Our 3-member team worked closely using simple agile practices:
* **Daily 15-Minute Meetings:** Every morning we checked what was done, what was next, and solved any blockers.
* **Clear Team Roles:** Member 1 focused on the Backend & AI, Member 2 focused on the Frontend UI, and Member 3 managed the complete Documentation and system diagrams.
* **Data Planning First:** We agreed on API formats first so the frontend and backend could code smoothly while documentation was prepared in parallel.
* **Always Testing:** We made sure our 232 automated tests always passed before finishing any feature."

---

## 6. How Tasks Were Divided Among Team Members
**Simple Answer:**  
"We divided the project clearly into three distinct areas:
1. **Member 1 (Lead / Backend & AI):** Backend API, PostgreSQL database, AI generation prompts, and pure Python validation rules.
2. **Member 2 (Frontend & UI):** React 19 single-page app, 18 web views, user authentication, and API integration.
3. **Member 3 (Documentation & Analysis):** SRS documentation, UML/architecture diagrams, user guides, testing reports, and presentation slides.

We held weekly walkthroughs so all three members completely understand the entire system."

---

## 7. Challenges Faced During the Project
**Simple Answer:**  
"We faced four main practical challenges:
1. **AI Making Up Fake Rules:** AI models sometimes invent fake policy numbers or skip required tasks.
2. **File Size & Slow Responses:** Sending 39 full documents to the AI was too large and very slow.
3. **Trick Text in Files:** Some test documents had hidden text trying to trick the AI into approving everything.
4. **Keeping Docs in Sync:** As developers added new features quickly, documentation had to be updated rapidly to match the code."

---

## 8. How Your Team Solved Those Challenges
**Simple Answer:**  
"We solved them simply and cleanly:
1. **Pure Python Checking:** We used 13 strict Python rules to check the AI's plan against real database records.
2. **Backup AI Models:** If one AI fails or is slow, the system automatically switches to Gemini, Ollama, or an offline mode.
3. **Security Scanner:** We scan uploaded text first and remove any suspicious prompt text before calling the AI.
4. **Daily Sync for Documentation:** Developers gave live demos of any code changes so the documentation member could update diagrams and reports immediately."

---

## 9. Difficulties or Conflicts Within the Team & How Handled
**Simple Answer:**  
"We had a real team challenge regarding **feature changes versus documentation deadlines**:  
As our two developers were quickly improving the API and adding new features, our documentation member was finding it hard to keep the SRS report and architecture diagrams up to date.

**How We Handled It:**  
We set up a quick 10-minute daily demo. The developers walked through all new endpoints and UI screens, and provided sample API responses. This allowed our documentation specialist to update all diagrams and reports accurately without any delay or confusion."

---

## 10. What You Learned from Working as a Team
**Simple Answer:**  
"We learned three important lessons:
1. **Good Communication:** Daily sync-ups between developers and the documentation writer kept everyone on the same page.
2. **AI Needs Traditional Code:** In real enterprise software, AI cannot be trusted blindly; pure Python rules are necessary to verify results.
3. **Team Support:** Having clear ownership while helping each other ensured all 3 members finished the project on time."

---

## 11. What Would You Improve If You Had More Time
**Simple Answer:**  
"If we had more time, we would add:
1. **Voice AI Practice:** A voice assistant so employees can practice speaking to customers and managers.
2. **In-Browser Coding Practice:** Safe coding boxes in the browser for software trainees to write real code.
3. **HR System Sync:** Automatically connect to tools like Workday to import new employees.
4. **Short Quiz Reminders:** Send quick 1-minute refresher quizzes on Slack or Teams."

---

## Rapid-Fire Examiner Grilling Cheat Sheet (Simple 1-Line Answers)

| Question | Simple 1-Sentence Answer |
|---|---|
| **Why not just use LangChain?** | *"Because LangChain relies only on AI; we added pure Python rules to guarantee 100% accurate compliance."* |
| **Why pgvector over Pinecone?** | *"PostgreSQL keeps our normal tables and search data together in one place, so it is faster, simpler, and free."* |
| **What if the internet goes down?** | *"The system automatically runs our local Ollama model or offline engine, so it never stops working."* |
| **When is a plan considered 'Verified'?** | *"When 100% of required rules are covered, all citations are real, and there are zero policy conflicts."* |
| **Why is there no AI in Pipeline 2?** | *"Because we want our validation to be 100% consistent and rule-based every single time."* |
| **How do you stop SQL injection?** | *"We use SQLAlchemy safe queries where user input is never executed as raw database code."* |
| **How fast is plan generation?** | *"A full 30-module plan generates and gets checked by Python in under 20 seconds."* |
| **What happens if an employee fails quizzes?** | *"The system marks that topic as a Weak Area and suggests review lessons on their dashboard."* |
"""


def compile_3person_pdf(md_path: Path, output_pdf_path: Path):
    print(f"Compiling 3-Person Team PDF: {md_path} -> {output_pdf_path}")
    text = md_path.read_text(encoding='utf-8', errors='ignore')
    lines = text.splitlines()

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

    cover_title_style = ParagraphStyle(
        'CoverTitle', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=19, leading=24,
        textColor=c_primary, alignment=1, spaceAfter=5
    )
    cover_subtitle_style = ParagraphStyle(
        'CoverSubtitle', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=10.5, leading=14,
        textColor=c_accent, alignment=1, spaceAfter=8
    )
    cover_meta_style = ParagraphStyle(
        'CoverMeta', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8, leading=12,
        textColor=c_muted, alignment=1, spaceAfter=10
    )
    h1_style = ParagraphStyle(
        'DocH1', parent=styles['Heading1'],
        fontName='Helvetica-Bold', fontSize=11.5, leading=15,
        textColor=c_primary, spaceBefore=9, spaceAfter=3, keepWithNext=True
    )
    h2_style = ParagraphStyle(
        'DocH2', parent=styles['Heading2'],
        fontName='Helvetica-Bold', fontSize=9.5, leading=13,
        textColor=c_accent, spaceBefore=7, spaceAfter=2.5, keepWithNext=True
    )
    h3_style = ParagraphStyle(
        'DocH3', parent=styles['Heading3'],
        fontName='Helvetica-Bold', fontSize=8.5, leading=11.5,
        textColor=c_navy, spaceBefore=5, spaceAfter=2, keepWithNext=True
    )
    body_style = ParagraphStyle(
        'DocBody', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8, leading=11,
        textColor=c_body, spaceAfter=3
    )
    bullet_style = ParagraphStyle(
        'DocBullet', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8, leading=11,
        textColor=c_body, leftIndent=10, spaceAfter=2
    )
    badge_style = ParagraphStyle(
        'DocBadge', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=7.5, leading=10,
        textColor=colors.HexColor("#0369A1"), alignment=1
    )

    story = []

    # Title & Badge
    story.append(Spacer(1, 4))
    badge_table = Table([[
        Paragraph("<b>TECHWIZ 7 · OFFICIAL INTERVIEW COMPONENT · 3-MEMBER TEAM DEFENSE GUIDE</b>", badge_style)
    ]], colWidths=[PRINTABLE_WIDTH])
    badge_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#E0F2FE")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#38BDF8")),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(badge_table)
    story.append(Spacer(1, 6))

    # Cover Title & Metadata
    story.append(Paragraph("SkillSprint AI — 3-Member Team Interview Guide", cover_title_style))
    story.append(Paragraph("Lead/Backend & AI Developer · Frontend Developer · Documentation Specialist", cover_subtitle_style))
    story.append(Paragraph("<b>Aptech TECHWIZ 7</b> · Generative AI PowerPlay · OnboardVerse<br/>"
                           "Simple English Words, Short Answers (30–45 Seconds per Question)", cover_meta_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceBefore=2, spaceAfter=6))

    i = 0
    in_table = False
    table_lines = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Handle Tables
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
                t_flowable = md_table_to_flowable(table_lines, styles, c_navy, c_body)
                if t_flowable:
                    story.append(t_flowable)
                    story.append(Spacer(1, 4))
                in_table = False
                table_lines = []

        if not stripped:
            i += 1
            continue

        if stripped.startswith('# SkillSprint AI — Simple English Interview Guide (3-Member Team)'):
            i += 1
            while i < len(lines) and (lines[i].startswith('**') or lines[i].startswith('---')):
                i += 1
            continue

        if stripped in ['---', '***', '___']:
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2E8F0"), spaceBefore=3, spaceAfter=5))
            i += 1
            continue

        if stripped.startswith('## '):
            h_text = inline_markdown_to_xml(stripped[3:].strip())
            story.append(Paragraph(h_text, h1_style))
            i += 1
            continue
        elif stripped.startswith('### '):
            h_text = inline_markdown_to_xml(stripped[4:].strip())
            story.append(Paragraph(h_text, h2_style))
            i += 1
            continue
        elif stripped.startswith('#### '):
            h_text = inline_markdown_to_xml(stripped[5:].strip())
            story.append(Paragraph(f"<b>{h_text}</b>", h3_style))
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

    if in_table and table_lines:
        t_flowable = md_table_to_flowable(table_lines, styles, c_navy, c_body)
        if t_flowable:
            story.append(t_flowable)
            story.append(Spacer(1, 4))

    doc.build(story, canvasmaker=SimpleInterviewGuideCanvas)
    print(f"Generated 3-Person Team PDF: {output_pdf_path} ({output_pdf_path.stat().st_size:,} bytes)")


def main():
    content = build_3person_markdown_content()
    OUT_MD.write_text(content, encoding='utf-8')
    print(f"Saved 3-person team Markdown to {OUT_MD}")
    compile_3person_pdf(OUT_MD, OUT_PDF)


if __name__ == '__main__':
    main()
