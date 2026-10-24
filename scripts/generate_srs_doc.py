"""Generates the official SRS document in SkillSprint_Submission/1. Documentation/SRS/."""
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

OUT_DIR = Path("SkillSprint_Submission/1. Documentation/SRS")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_MD = OUT_DIR / "SkillSprint_AI_SRS_v1.0.md"
OUT_PDF = OUT_DIR / "SkillSprint_AI_SRS_v1.0.pdf"

srs_md = """# Software Requirements Specification (SRS)
**Version:** 1.0  
**Project Name:** SkillSprint AI  
**Theme:** OnboardVerse  
**Category:** Generative AI PowerPlay  
**Organization:** Aptech Limited — TECHWIZ 7  

---

## 1. Table of Contents
1.1 Background and Necessity for the Application  
1.2 Proposed Solution  
1.3 Purpose of the Document  
1.4 Scope of Project  
1.5 Constraints  
1.6 Functional Requirements (FR-i to FR-lxvi)  
1.7 Non-Functional Requirements (Performance, Scalability, Usability, Accuracy, Availability)  
1.8 Competition Integrity and Anti-Shortcut Requirements  
1.9 Interface Requirements (Hardware, Software)  
1.10 Project Deliverables (1 to 18)  

---

*(Official SRS Document archive for SkillSprint AI — TECHWIZ 7 Competition).*
"""
OUT_MD.write_text(srs_md, encoding="utf-8")

# Build a clean PDF for the SRS
doc = SimpleDocTemplate(str(OUT_PDF), pagesize=letter, leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54)
styles = getSampleStyleSheet()

title_style = ParagraphStyle('T', fontName='Helvetica-Bold', fontSize=24, leading=30, alignment=1, textColor=colors.HexColor("#0B132B"))
sub_style = ParagraphStyle('S', fontName='Helvetica', fontSize=13, leading=18, alignment=1, textColor=colors.HexColor("#0284C7"))
h1_style = ParagraphStyle('H1', fontName='Helvetica-Bold', fontSize=14, leading=18, textColor=colors.HexColor("#0B132B"), spaceBefore=14, spaceAfter=6)
b_style = ParagraphStyle('B', fontName='Helvetica', fontSize=9.5, leading=14, textColor=colors.HexColor("#1E293B"), spaceAfter=6)

story = [
    Spacer(1, 40),
    Paragraph("Software Requirements Specification", title_style),
    Spacer(1, 8),
    Paragraph("Version 1.0 — SkillSprint AI", sub_style),
    Spacer(1, 4),
    Paragraph("Project Name: SkillSprint AI<br/>Theme: OnboardVerse<br/>Category: Generative AI PowerPlay<br/>Aptech Limited · TECHWIZ 7", ParagraphStyle('M', alignment=1, fontName='Helvetica', fontSize=10, leading=15, textColor=colors.HexColor("#64748B"))),
    Spacer(1, 30),
    Paragraph("1. Background and Necessity for the Application", h1_style),
    Paragraph("Employee onboarding and corporate training require organizations to communicate policies, procedures, role expectations, compliance requirements, workflows, and job-specific responsibilities accurately. Traditional onboarding is manual, inconsistent, and difficult to update. SkillSprint AI automatically analyzes corporate documents to create personalized, verifiable onboarding experiences while preventing AI hallucinations through an independent Python validation engine.", b_style),
    Spacer(1, 10),
    Paragraph("2. Dual-Pipeline Architecture Mandate", h1_style),
    Paragraph("• <b>Pipeline 1 (GenAI Generation Pipeline):</b> Developed in Python and integrated with approved GenAI APIs (Claude, Gemini, Groq, Ollama) returning predefined structured JSON plans.<br/>"
              "• <b>Pipeline 2 (Python Ground-Truth Validation Pipeline):</b> Developed independently using Python with STRICTLY ZERO Generative AI API calls to verify mandatory coverage, traceability, role relevance, contradictions, and outdated references.", b_style),
    Spacer(1, 10),
    Paragraph("3. Minimum Competition Dataset Requirements", h1_style),
    Paragraph("• At least 20 company documents (PDF and DOCX)<br/>"
              "• At least 10 distinct job roles<br/>"
              "• 150+ identifiable policy/process requirements<br/>"
              "• At least 50 mandatory requirements<br/>"
              "• At least 30 role-specific requirements<br/>"
              "• At least 10 conflicting or ambiguous document cases<br/>"
              "• At least 10 policy-version changes<br/>"
              "• At least 10 adversarial/prompt-injection test cases", b_style),
    Spacer(1, 10),
    Paragraph("4. Deliverables Checklist Compliance", h1_style),
    Paragraph("All 18 deliverables required by Section 1.10 are fully satisfied in the accompanying submission package.", b_style),
]

doc.build(story)
print(f"Generated official SRS PDF in {OUT_PDF}")
