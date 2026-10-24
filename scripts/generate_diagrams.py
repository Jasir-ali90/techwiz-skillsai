"""Generates the 6 high-resolution system diagrams required by the SkillSprint AI SRS:
1. Architecture_Diagram.png
2. Data_Flow_Diagram.png
3. Use_Case_Diagram.png
4. Activity_Diagram.png
5. Sequence_Diagram.png
6. Database_ER_Diagram.png

Outputs are saved in:
- SkillSprint_Submission/1. Documentation/Diagrams/
- docs/diagrams/
"""
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches

OUT_DIRS = [
    Path("SkillSprint_Submission/1. Documentation/Diagrams"),
    Path("docs/diagrams"),
]
for d in OUT_DIRS:
    d.mkdir(parents=True, exist_ok=True)


def save_fig(fig, filename):
    for d in OUT_DIRS:
        fig.savefig(d / filename, dpi=300, bbox_inches='tight', facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    print(f"Saved {filename}")


# -------------------------------------------------------------
# 1. Architecture Diagram
# -------------------------------------------------------------
def make_architecture_diagram():
    fig = plt.figure(figsize=(16, 11), facecolor='#0B111A')
    ax = fig.add_subplot(111)
    ax.set_facecolor('#0B111A')
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    # Title
    ax.text(50, 96.5, "SkillSprint AI — Dual-Pipeline System Architecture",
            fontsize=20, fontweight='bold', color='#FFFFFF', ha='center')
    ax.text(50, 93.8, "Nexora Labs · OnboardVerse · Generative AI PowerPlay (TECHWIZ 7)",
            fontsize=11, color='#8E9BAE', ha='center')

    # Layer 1: Knowledge Sources
    box_sources = patches.FancyBboxPatch((4, 76), 92, 13.5, boxstyle="round,pad=0.8,rounding_size=1.2",
                                         facecolor='#161F2E', edgecolor='#2D3F59', linewidth=1.5)
    ax.add_patch(box_sources)
    ax.text(7, 86.8, "1. ENTERPRISE KNOWLEDGE SOURCES & MULTI-STAGE INGESTION",
            fontsize=12, fontweight='bold', color='#38BDF8')

    sources = [
        ("Company Handbook\n(HBK-GEN-001)", 6, 78, 16, 7),
        ("HR & Conduct Policies\n(POL-HR, CONDUCT)", 24, 78, 16, 7),
        ("InfoSec & Privacy\n(POL-INFOSEC, PRIV)", 42, 78, 16, 7),
        ("Department SOPs\n(Deploy, Escalate, QA)", 60, 78, 16, 7),
        ("10 Job Descriptions\n(Eng, Infra, QA, PM...)", 78, 78, 16, 7),
    ]
    for text, x, y, w, h in sources:
        p = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=0.6",
                                   facecolor='#1F2D42', edgecolor='#3B82F6', linewidth=1)
        ax.add_patch(p)
        ax.text(x + w / 2, y + h / 2, text, fontsize=8.5, color='#F1F5F9', ha='center', va='center', fontweight='medium')

    # Arrow Down
    ax.annotate('', xy=(50, 72), xytext=(50, 76),
                arrowprops=dict(facecolor='#38BDF8', edgecolor='none', width=2, headwidth=8))

    # Layer 2: Ingestion & Matrix Engine
    box_ingest = patches.FancyBboxPatch((4, 56.5), 92, 15, boxstyle="round,pad=0.8,rounding_size=1.2",
                                        facecolor='#161F2E', edgecolor='#2D3F59', linewidth=1.5)
    ax.add_patch(box_ingest)
    ax.text(7, 68.8, "2. DOCUMENT VALIDATION, CHUNKING & ROLE REQUIREMENT MATRIX ENGINE",
            fontsize=12, fontweight='bold', color='#A78BFA')

    proc_boxes = [
        ("9-Point Document Validation\n(Type, Size, SHA-256 Dups,\nVersion, Category, Expiry)", 6, 58.5, 20, 9),
        ("Section-Aware Chunking\n(Hierarchy, Heading Path,\nPage/Paragraph Traceability)", 28, 58.5, 20, 9),
        ("Semantic Embeddings\n(all-MiniLM-L6-v2, 384 dims\nPostgreSQL pgvector / HNSW)", 50, 58.5, 20, 9),
        ("Role Requirement Matrix\n(150+ Requirements, Roles,\nMandatory vs Optional, DAG Prereqs)", 72, 58.5, 22, 9),
    ]
    for text, x, y, w, h in proc_boxes:
        p = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=0.6",
                                   facecolor='#26203D', edgecolor='#8B5CF6', linewidth=1)
        ax.add_patch(p)
        ax.text(x + w / 2, y + h / 2, text, fontsize=8.5, color='#EDE9FE', ha='center', va='center')

    # Arrows to dual pipelines
    ax.annotate('', xy=(26, 51.5), xytext=(38, 56.5),
                arrowprops=dict(facecolor='#10B981', edgecolor='none', width=2, headwidth=8))
    ax.annotate('', xy=(74, 51.5), xytext=(62, 56.5),
                arrowprops=dict(facecolor='#F59E0B', edgecolor='none', width=2, headwidth=8))

    # Layer 3: Dual Pipelines
    # Pipeline 1 (GenAI)
    p1 = patches.FancyBboxPatch((4, 28), 44, 23, boxstyle="round,pad=0.8,rounding_size=1.2",
                                facecolor='#0D281E', edgecolor='#059669', linewidth=2)
    ax.add_patch(p1)
    ax.text(6, 48.5, "PIPELINE 1 — PYTHON GenAI GENERATION",
            fontsize=11.5, fontweight='bold', color='#34D399')
    p1_items = (
        "• Structured Prompt Templates (v1.0 & Version Registry)\n"
        "• Model Fallback Chain: Claude / Gemini / Groq / Ollama / Offline\n"
        "• Strict JSON Schema Decoding (Pydantic / Constraints)\n"
        "• Staged Day 1 → Day 90 Personalized Onboarding Plans\n"
        "• Dynamic Learning Modules, Objectives, Checklists & Tasks\n"
        "• Scenario Quizzes & Detailed Assessment Rubrics\n"
        "• Prompt Injection Defense (Data-Sandboxing & Guardrails)"
    )
    ax.text(6.5, 37.5, p1_items, fontsize=8.5, color='#D1FAE5', va='center')

    # Pipeline 2 (Python Ground Truth)
    p2 = patches.FancyBboxPatch((52, 28), 44, 23, boxstyle="round,pad=0.8,rounding_size=1.2",
                                facecolor='#2C1E0A', edgecolor='#D97706', linewidth=2)
    ax.add_patch(p2)
    ax.text(54, 48.5, "PIPELINE 2 — PYTHON GROUND-TRUTH VALIDATION",
            fontsize=11.5, fontweight='bold', color='#FBBF24')
    p2_items = (
        "• 100% Deterministic Engine (STRICTLY NO AI IMPORTS)\n"
        "• 13 Dedicated Validation Rules against Ground-Truth Matrix\n"
        "• Mandatory Requirement Coverage Score (Target 100%)\n"
        "• Source Traceability Score (Section & Document ID Checks)\n"
        "• Hallucination & Unsupported Content Detection (Vector Sim)\n"
        "• Cross-Policy Contradiction Detection & Precedence Hierarchy\n"
        "• Learning Sequence & DAG Prerequisite Dependency Validation"
    )
    ax.text(54.5, 37.5, p2_items, fontsize=8.5, color='#FEF3C7', va='center')

    # Arrows to Comparison
    ax.annotate('', xy=(42, 23), xytext=(32, 28),
                arrowprops=dict(facecolor='#10B981', edgecolor='none', width=2, headwidth=8))
    ax.annotate('', xy=(58, 23), xytext=(68, 28),
                arrowprops=dict(facecolor='#F59E0B', edgecolor='none', width=2, headwidth=8))

    # Layer 4: Comparison & Decision Engine
    box_comp = patches.FancyBboxPatch((20, 14.5), 60, 8.5, boxstyle="round,pad=0.8,rounding_size=1.2",
                                      facecolor='#1F1D36', edgecolor='#C084FC', linewidth=1.5)
    ax.add_patch(box_comp)
    ax.text(50, 20.8, "RESULT COMPARISON & VERIFICATION DECISION ENGINE",
            fontsize=11, fontweight='bold', color='#E9D5FF', ha='center')
    ax.text(50, 16.8, "Attributes Match/Mismatch · Coverage Score · Traceability Score · 100+ Requirements Audit\n"
                      "Statuses: Verified | Verified with Warning | Partially Verified | Review Required",
            fontsize=8.5, color='#F3E8FF', ha='center')

    # Arrow Down to Presentation Layer
    ax.annotate('', xy=(50, 10), xytext=(50, 14.5),
                arrowprops=dict(facecolor='#C084FC', edgecolor='none', width=2, headwidth=8))

    # Layer 5: Presentation & Dashboards
    box_pres = patches.FancyBboxPatch((4, 1.5), 92, 8.5, boxstyle="round,pad=0.8,rounding_size=1.2",
                                      facecolor='#161F2E', edgecolor='#2D3F59', linewidth=1.5)
    ax.add_patch(box_pres)
    ax.text(50, 7.8, "PRESENTATION LAYER, ROLE-BASED DASHBOARDS & ANALYTICS",
            fontsize=11, fontweight='bold', color='#38BDF8', ha='center')

    dash_items = [
        ("Employee Journey\n& Interactive Quizzes", 6, 2.5, 20, 4.5),
        ("Reviewer Queue &\nAudit Trail Overrides", 28, 2.5, 20, 4.5),
        ("Policy Version Updates &\nSelective Regeneration", 50, 2.5, 20, 4.5),
        ("Executive Analytics &\nMulti-Format Export (PDF/CSV)", 72, 2.5, 22, 4.5),
    ]
    for text, x, y, w, h in dash_items:
        p = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=0.5",
                                   facecolor='#1F2D42', edgecolor='#60A5FA', linewidth=1)
        ax.add_patch(p)
        ax.text(x + w / 2, y + h / 2, text, fontsize=8, color='#FFFFFF', ha='center', va='center')

    save_fig(fig, "Architecture_Diagram.png")


# -------------------------------------------------------------
# 2. Data Flow Diagram (DFD Level 0 & Level 1)
# -------------------------------------------------------------
def make_data_flow_diagram():
    fig = plt.figure(figsize=(16, 11), facecolor='#0B111A')
    ax = fig.add_subplot(111)
    ax.set_facecolor('#0B111A')
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    ax.text(50, 96.5, "SkillSprint AI — Data Flow Diagram (DFD Level 1)",
            fontsize=20, fontweight='bold', color='#FFFFFF', ha='center')
    ax.text(50, 93.8, "Complete Data Life Cycle: Document Parsing, Matrix Building, Generation, Validation & Feedback",
            fontsize=11, color='#8E9BAE', ha='center')

    # Entities (Rectangles)
    entities = [
        ("External Entity:\nADMIN / HR", 5, 75, 14, 8, '#0284C7'),
        ("External Entity:\nLLM PROVIDER\n(Gemini/Claude/Ollama)", 5, 45, 14, 8, '#059669'),
        ("External Entity:\nEMPLOYEE / LEARNER", 5, 15, 14, 8, '#D97706'),
        ("External Entity:\nQUALITY REVIEWER /\nEVALUATOR", 81, 45, 14, 8, '#7C3AED'),
    ]
    for text, x, y, w, h, col in entities:
        p = patches.FancyBboxPatch((x, y), w, h, boxstyle="square,pad=0.3",
                                   facecolor=col, edgecolor='#FFFFFF', linewidth=1.5)
        ax.add_patch(p)
        ax.text(x + w / 2, y + h / 2, text, fontsize=8.5, color='#FFFFFF', ha='center', va='center', fontweight='bold')

    # Processes (Circles / Ellipses)
    processes = [
        ("1.0 Document\nIngestion &\n9-Pt Validation", 28, 75, 14, 8),
        ("2.0 Section Chunking\n& Semantic\nEmbedding", 48, 75, 14, 8),
        ("3.0 Matrix Extraction\n& Precedence\nDAG Builder", 68, 75, 14, 8),
        ("4.0 GenAI Plan\nGeneration &\nJSON Formatting", 28, 45, 14, 8),
        ("5.0 Deterministic\nPython Ground-Truth\nValidation (13 Rules)", 48, 45, 14, 8),
        ("6.0 Result Comparison\n& Verification\nStatus Decision", 68, 45, 14, 8),
        ("7.0 Employee\nLearning Journey\n& Task Evaluation", 28, 15, 14, 8),
        ("8.0 Adaptive\nWeak-Area Detection\n& Recommendations", 48, 15, 14, 8),
        ("9.0 Policy Update\nImpact Analysis &\nSelective Regen", 68, 15, 14, 8),
    ]
    for text, x, y, w, h in processes:
        p = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5,rounding_size=2.0",
                                   facecolor='#1E293B', edgecolor='#38BDF8', linewidth=1.5)
        ax.add_patch(p)
        ax.text(x + w / 2, y + h / 2, text, fontsize=8.5, color='#F8FAFC', ha='center', va='center', fontweight='semibold')

    # Data Stores (Open-ended rects / parallel lines)
    datastores = [
        ("D1: Document Repository & Chunks Table (PostgreSQL)", 38, 88, 38, 4),
        ("D2: Role Requirement Matrix & Precedence DAG", 38, 62, 38, 4),
        ("D3: Onboarding Plans & Validation Audit Logs", 38, 32, 38, 4),
        ("D4: Employee Progress, Tasks & Quiz Records", 38, 4, 38, 4),
    ]
    for text, x, y, w, h in datastores:
        p = patches.Rectangle((x, y), w, h, facecolor='#0F172A', edgecolor='#94A3B8', linewidth=1.5, linestyle='--')
        ax.add_patch(p)
        ax.text(x + w / 2, y + h / 2, text, fontsize=8.5, color='#E2E8F0', ha='center', va='center', fontweight='bold')

    # Flow lines
    def arrow(x1, y1, x2, y2, label=""):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(facecolor='#38BDF8', edgecolor='none', width=1.5, headwidth=6))
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            ax.text(mx, my + 1.2, label, fontsize=7.5, color='#94A3B8', ha='center')

    arrow(19, 79, 28, 79, "Upload PDF/DOCX")
    arrow(42, 79, 48, 79, "Clean Text")
    arrow(62, 79, 68, 79, "Chunks")
    arrow(55, 75, 55, 66, "Store Requirements")
    arrow(19, 49, 28, 49, "Model Inference")
    arrow(28, 45, 19, 45, "Prompt + Data")
    arrow(42, 49, 48, 49, "Candidate Plan")
    arrow(55, 62, 55, 53, "RRM Truth")
    arrow(62, 49, 68, 49, "Validation Flags")
    arrow(81, 49, 82, 49)  # to reviewer
    arrow(81, 47, 75, 47, "Override/Approve")
    arrow(19, 19, 28, 19, "Task Completion")
    arrow(42, 19, 48, 19, "Quiz Scores")
    arrow(55, 32, 55, 23, "Assigned Plans")
    arrow(68, 19, 62, 19, "Regen Flag")

    save_fig(fig, "Data_Flow_Diagram.png")


# -------------------------------------------------------------
# 3. Use Case Diagram
# -------------------------------------------------------------
def make_use_case_diagram():
    fig = plt.figure(figsize=(16, 11), facecolor='#0B111A')
    ax = fig.add_subplot(111)
    ax.set_facecolor('#0B111A')
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    ax.text(50, 96.5, "SkillSprint AI — Multi-Role UML Use Case Diagram",
            fontsize=20, fontweight='bold', color='#FFFFFF', ha='center')
    ax.text(50, 93.8, "Role-Based Access Control: Admin, Training Manager, Reviewer, Manager, Employee & Evaluator",
            fontsize=11, color='#8E9BAE', ha='center')

    # System boundary
    boundary = patches.FancyBboxPatch((22, 4), 62, 87, boxstyle="round,pad=1.0,rounding_size=1.5",
                                      facecolor='#0F172A', edgecolor='#38BDF8', linewidth=2)
    ax.add_patch(boundary)
    ax.text(53, 89, "SkillSprint AI Application Boundary", fontsize=13, color='#38BDF8', fontweight='bold', ha='center')

    # Actors Left
    actors_left = [
        ("Administrator", 10, 75, '#38BDF8'),
        ("Training Manager", 10, 50, '#34D399'),
        ("Quality Reviewer", 10, 25, '#F472B6'),
    ]
    # Actors Right
    actors_right = [
        ("Competition Evaluator", 90, 75, '#FBBF24'),
        ("Department Manager", 90, 50, '#A78BFA'),
        ("Employee / Learner", 90, 25, '#FB7185'),
    ]

    for title, x, y, col in actors_left + actors_right:
        # stick figure / badge
        ax.plot(x, y + 3, 'o', color=col, markersize=12)
        ax.plot([x, x], [y + 1.8, y - 1], color=col, linewidth=2.5)
        ax.plot([x - 2, x + 2], [y + 0.8, y + 0.8], color=col, linewidth=2.5)
        ax.plot([x, x - 2], [y - 1, y - 3.5], color=col, linewidth=2.5)
        ax.plot([x, x + 2], [y - 1, y - 3.5], color=col, linewidth=2.5)
        ax.text(x, y - 5.5, title, fontsize=9, color=col, ha='center', fontweight='bold')

    # Use Cases inside system boundary
    use_cases = [
        ("Upload & Validate Company Documents (PDF/DOCX)", 53, 83),
        ("Extract & Configure Role Requirement Matrix", 53, 75),
        ("Configure Precedence & Conflict Rules", 53, 67),
        ("Generate Staged Onboarding Plan (GenAI Pipeline 1)", 53, 59),
        ("Execute Ground-Truth Validation (Python Pipeline 2)", 53, 51),
        ("Inspect GenAI vs Python Comparison & Discrepancies", 53, 43),
        ("Audit Review Queue & Apply Human Overrides", 53, 35),
        ("Perform Policy Update Impact Analysis & Selective Regen", 53, 27),
        ("View Learning Modules, Checklists & Tasks", 53, 19),
        ("Take Source-Grounded Interactive Quizzes", 53, 12),
        ("Export Compliance, Traceability & Progress Reports", 53, 5),
    ]

    for title, cx, cy in use_cases:
        p = patches.FancyBboxPatch((cx - 24, cy - 2.5), 48, 5, boxstyle="round,pad=0.5,rounding_size=2.5",
                                   facecolor='#1E293B', edgecolor='#94A3B8', linewidth=1)
        ax.add_patch(p)
        ax.text(cx, cy, title, fontsize=8.5, color='#F8FAFC', ha='center', va='center')

    # Connecting lines (Actor to Use Case)
    def link(x1, y1, x2, y2, col='#64748B'):
        ax.plot([x1, x2], [y1, y2], color=col, linewidth=1, linestyle='-')

    # Admin connections
    link(12, 75, 29, 83)
    link(12, 75, 29, 75)
    link(12, 75, 29, 67)
    link(12, 75, 29, 59)
    # Training Manager
    link(12, 50, 29, 59)
    link(12, 50, 29, 51)
    link(12, 50, 29, 43)
    link(12, 50, 29, 27)
    # Reviewer
    link(12, 25, 29, 43)
    link(12, 25, 29, 35)
    # Evaluator
    link(88, 75, 77, 83)
    link(88, 75, 77, 51)
    link(88, 75, 77, 43)
    link(88, 75, 77, 27)
    # Manager
    link(88, 50, 77, 35)
    link(88, 50, 77, 5)
    # Employee
    link(88, 25, 77, 19)
    link(88, 25, 77, 12)

    save_fig(fig, "Use_Case_Diagram.png")


# -------------------------------------------------------------
# 4. Activity Diagram
# -------------------------------------------------------------
def make_activity_diagram():
    fig = plt.figure(figsize=(16, 11), facecolor='#0B111A')
    ax = fig.add_subplot(111)
    ax.set_facecolor('#0B111A')
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    ax.text(50, 96.5, "SkillSprint AI — End-to-End Activity Diagram",
            fontsize=20, fontweight='bold', color='#FFFFFF', ha='center')
    ax.text(50, 93.8, "Swimlane Workflow: Ingestion → Ground Truth → Dual Processing → Review → Learner Execution",
            fontsize=11, color='#8E9BAE', ha='center')

    # Swimlanes
    lanes = [
        ("Admin / HR", 2, 21),
        ("Parser & Matrix Engine", 21, 40),
        ("Pipeline 1 (GenAI)", 40, 59),
        ("Pipeline 2 (Python)", 59, 78),
        ("Reviewer / Employee", 78, 98),
    ]
    for name, left, right in lanes:
        p = patches.Rectangle((left, 4), right - left, 87, facecolor='#111827', edgecolor='#374151', linewidth=1)
        ax.add_patch(p)
        ax.text((left + right) / 2, 88.5, name, fontsize=10, color='#38BDF8', fontweight='bold', ha='center')

    def act_box(x, y, text, col='#1E293B', border='#60A5FA'):
        p = patches.FancyBboxPatch((x - 7.5, y - 2.5), 15, 5, boxstyle="round,pad=0.3,rounding_size=1.0",
                                   facecolor=col, edgecolor=border, linewidth=1.2)
        ax.add_patch(p)
        ax.text(x, y, text, fontsize=7.5, color='#F8FAFC', ha='center', va='center')

    # Start node
    ax.plot(11.5, 83, 'o', color='#10B981', markersize=14)
    ax.text(11.5, 83, 'START', fontsize=6, color='#FFFFFF', ha='center', va='center', fontweight='bold')

    act_box(11.5, 74, "Upload Policies\n& SOPs (PDF/DOCX)")
    act_box(30.5, 74, "9-Point Validation\n& Text Chunking")
    act_box(30.5, 63, "Extract Requirements\n& Build RRM Matrix")
    act_box(11.5, 63, "Select Employee\n& Request Plan")

    act_box(49.5, 52, "GenAI Generates\nStaged Plan (JSON)")
    act_box(68.5, 52, "Deterministic Check\n(13 Python Rules)")

    act_box(68.5, 40, "Compare & Score\n(Coverage & Trace)")

    # Decision diamond
    def diamond(x, y, text):
        poly = patches.Polygon([[x, y + 3], [x + 4.5, y], [x, y - 3], [x - 4.5, y]],
                               facecolor='#4C1D95', edgecolor='#C084FC', linewidth=1.5)
        ax.add_patch(poly)
        ax.text(x, y, text, fontsize=7, color='#FFFFFF', ha='center', va='center', fontweight='bold')

    diamond(68.5, 28, "100% OK?")

    act_box(88, 38, "Human Review Queue\n(Override / Edit)")
    act_box(88, 28, "Publish Verified Plan\nto Employee Dashboard")
    act_box(88, 16, "Learner Completes Tasks\n& Takes Scored Quizzes")
    act_box(88, 7, "Weak-Area Analysis &\nAdaptive Reinforce")

    # Connectors
    def arrow(x1, y1, x2, y2, label=""):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(facecolor='#38BDF8', edgecolor='none', width=1.5, headwidth=5))
        if label:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 1, label, fontsize=7, color='#CBD5E1', ha='center')

    arrow(11.5, 81.5, 11.5, 76.5)
    arrow(19, 74, 23, 74)
    arrow(30.5, 71.5, 30.5, 65.5)
    arrow(23, 63, 19, 63)
    arrow(11.5, 60.5, 49.5, 54.5)
    arrow(30.5, 60.5, 68.5, 54.5)
    arrow(49.5, 49.5, 68.5, 42.5)
    arrow(68.5, 49.5, 68.5, 42.5)
    arrow(68.5, 37.5, 68.5, 31)

    arrow(73, 28, 83.5, 38, "Issues")
    arrow(83.5, 38, 88, 30.5, "Approved")
    arrow(73, 28, 80.5, 28, "Yes")
    arrow(88, 25.5, 88, 18.5)
    arrow(88, 13.5, 88, 9.5)

    save_fig(fig, "Activity_Diagram.png")


# -------------------------------------------------------------
# 5. Sequence Diagram
# -------------------------------------------------------------
def make_sequence_diagram():
    fig = plt.figure(figsize=(16, 11), facecolor='#0B111A')
    ax = fig.add_subplot(111)
    ax.set_facecolor('#0B111A')
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    ax.text(50, 96.5, "SkillSprint AI — Plan Generation & Independent Verification Sequence",
            fontsize=20, fontweight='bold', color='#FFFFFF', ha='center')
    ax.text(50, 93.8, "UML Sequence: Client → API Router → Pipeline 1 (GenAI) → Pipeline 2 (Python) → Audit Trail",
            fontsize=11, color='#8E9BAE', ha='center')

    lifelines = [
        ("Client UI\n(React 19)", 10),
        ("API Gateway\n(FastAPI / Router)", 28),
        ("Pipeline 1\n(GenAI Service)", 46),
        ("GenAI Provider\n(Claude/Gemini/Ollama)", 64),
        ("Pipeline 2\n(Python Verifier)", 80),
        ("Database &\nAudit Log", 93),
    ]

    for name, x in lifelines:
        p = patches.FancyBboxPatch((x - 6.5, 86), 13, 6, boxstyle="round,pad=0.3,rounding_size=0.8",
                                   facecolor='#1E293B', edgecolor='#38BDF8', linewidth=1.2)
        ax.add_patch(p)
        ax.text(x, 89, name, fontsize=8, color='#FFFFFF', ha='center', va='center', fontweight='bold')
        ax.plot([x, x], [86, 6], color='#334155', linestyle='--', linewidth=1.2)

    def msg(y, x1, x2, text, is_ret=False, col='#38BDF8'):
        style = ':' if is_ret else '-'
        ax.plot([x1, x2], [y, y], color=col, linestyle=style, linewidth=1.5)
        # Arrowhead
        dx = 1 if x2 > x1 else -1
        ax.plot([x2 - dx * 1.5, x2], [y + 0.6, y], color=col, linewidth=1.5)
        ax.plot([x2 - dx * 1.5, x2], [y - 0.6, y], color=col, linewidth=1.5)
        mx = (x1 + x2) / 2
        ax.text(mx, y + 1.1, text, fontsize=7.5, color='#F8FAFC', ha='center')

    msg(82, 10, 28, "POST /plans (employee_id, role, stage_cfg)")
    msg(78, 28, 93, "Fetch Employee Profile & Role Matrix")
    msg(74, 93, 28, "Return RRM Requirements", is_ret=True)
    msg(70, 28, 46, "generate_plan(employee, requirements)")
    msg(66, 46, 64, "invoke_model(rendered_prompt, schema)")
    msg(62, 64, 46, "return structured JSON plan", is_ret=True)
    msg(58, 46, 46, "validate_schema(pydantic) & retry if error", col='#A78BFA')
    msg(54, 46, 28, "PlanGeneratedEvent(json_plan)", is_ret=True)
    msg(50, 28, 80, "verify_ground_truth(json_plan, rrm_matrix)")
    msg(45, 80, 80, "Execute 13 Deterministic Python Rules", col='#FBBF24')
    msg(40, 80, 80, "Compute Coverage (100%) & Traceability (100%)", col='#FBBF24')
    msg(35, 80, 28, "ValidationResult(status, discrepancies, scores)", is_ret=True)
    msg(30, 28, 93, "INSERT INTO onboarding_plans, verification_results, audit_logs")
    msg(25, 93, 28, "Commit Transaction (Plan ID)", is_ret=True)
    msg(20, 28, 10, "201 Created (Verified Plan + Comparison Table)", is_ret=True)
    msg(15, 10, 10, "Render Plan, Modules, Tasks, Quizzes & Verification Badge", col='#34D399')

    save_fig(fig, "Sequence_Diagram.png")


# -------------------------------------------------------------
# 6. Database ER Diagram
# -------------------------------------------------------------
def make_database_er_diagram():
    fig = plt.figure(figsize=(16, 11), facecolor='#0B111A')
    ax = fig.add_subplot(111)
    ax.set_facecolor('#0B111A')
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    ax.text(50, 96.5, "SkillSprint AI — Database Entity-Relationship Diagram (ERD)",
            fontsize=20, fontweight='bold', color='#FFFFFF', ha='center')
    ax.text(50, 93.8, "PostgreSQL Relational Schema with pgvector Embeddings & Audit Trails",
            fontsize=11, color='#8E9BAE', ha='center')

    tables = [
        ("departments", 3, 73, 19, 17, [
            ("id", "UUID PK"),
            ("code", "VARCHAR(32) UNIQUE"),
            ("name", "VARCHAR(128)"),
            ("created_at", "TIMESTAMPTZ"),
        ]),
        ("job_roles", 26, 73, 22, 17, [
            ("id", "UUID PK"),
            ("department_id", "UUID FK -> depts"),
            ("code", "VARCHAR(32) UNIQUE"),
            ("title", "VARCHAR(128)"),
            ("created_at", "TIMESTAMPTZ"),
        ]),
        ("users", 52, 73, 21, 17, [
            ("id", "UUID PK"),
            ("email", "VARCHAR(255) UNIQUE"),
            ("hashed_password", "VARCHAR(255)"),
            ("role", "ENUM(UserRole)"),
            ("is_active", "BOOLEAN"),
        ]),
        ("employees", 76, 73, 21, 17, [
            ("id", "UUID PK"),
            ("employee_code", "VARCHAR(32) UNIQUE"),
            ("user_id", "UUID FK -> users"),
            ("job_role_id", "UUID FK -> job_roles"),
            ("experience_level", "ENUM"),
            ("joining_date", "DATE"),
        ]),
        ("documents", 3, 40, 21, 26, [
            ("id", "UUID PK"),
            ("document_code", "VARCHAR(64)"),
            ("title", "VARCHAR(255)"),
            ("document_type", "ENUM"),
            ("version", "INT"),
            ("supersedes_id", "UUID FK -> docs"),
            ("file_hash_sha256", "VARCHAR(64)"),
            ("department_id", "UUID FK"),
            ("is_active", "BOOLEAN"),
        ]),
        ("document_chunks", 26, 40, 23, 26, [
            ("id", "UUID PK"),
            ("document_id", "UUID FK -> docs"),
            ("chunk_code", "VARCHAR(64)"),
            ("section_id", "VARCHAR(32)"),
            ("heading_path", "VARCHAR(255)"),
            ("content", "TEXT"),
            ("embedding", "VECTOR(384) [HNSW]"),
            ("is_suspicious", "BOOLEAN"),
        ]),
        ("role_requirements", 52, 40, 22, 26, [
            ("id", "UUID PK"),
            ("requirement_code", "VARCHAR(64)"),
            ("source_chunk_id", "UUID FK -> chunks"),
            ("category", "ENUM(ReqCategory)"),
            ("is_mandatory", "BOOLEAN"),
            ("precedence_rank", "INT"),
            ("competency", "VARCHAR(128)"),
        ]),
        ("onboarding_plans", 76, 40, 21, 26, [
            ("id", "UUID PK"),
            ("employee_id", "UUID FK -> emps"),
            ("plan_version", "INT"),
            ("verification_status", "ENUM"),
            ("mandatory_coverage", "FLOAT"),
            ("traceability_score", "FLOAT"),
            ("raw_genai_output", "JSONB"),
        ]),
        ("learning_modules", 14, 7, 22, 26, [
            ("id", "UUID PK"),
            ("plan_id", "UUID FK -> plans"),
            ("stage", "ENUM(Stage)"),
            ("module_code", "VARCHAR(32)"),
            ("title", "VARCHAR(255)"),
            ("objectives", "JSONB"),
            ("tasks", "JSONB"),
            ("quiz", "JSONB"),
            ("rubric", "JSONB"),
        ]),
        ("verification_results", 42, 7, 25, 26, [
            ("id", "UUID PK"),
            ("plan_id", "UUID FK -> plans"),
            ("status", "VARCHAR(32)"),
            ("rule_breakdown", "JSONB"),
            ("missing_requirements", "JSONB"),
            ("unsupported_items", "JSONB"),
            ("contradictions", "JSONB"),
            ("consistency_score", "FLOAT"),
        ]),
        ("audit_logs", 72, 7, 24, 26, [
            ("id", "UUID PK"),
            ("entity_type", "VARCHAR(64)"),
            ("entity_id", "UUID"),
            ("action", "VARCHAR(32)"),
            ("actor_id", "UUID FK -> users"),
            ("old_state", "JSONB"),
            ("new_state", "JSONB"),
            ("comment", "TEXT"),
            ("created_at", "TIMESTAMPTZ"),
        ]),
    ]

    for name, x, y, w, h, cols in tables:
        # Header
        hdr = patches.FancyBboxPatch((x, y + h - 4), w, 4, boxstyle="round,pad=0.2,rounding_size=0.4",
                                     facecolor='#1E3A8A', edgecolor='#3B82F6', linewidth=1)
        ax.add_patch(hdr)
        ax.text(x + w / 2, y + h - 2, name.upper(), fontsize=8, color='#FFFFFF', fontweight='bold', ha='center', va='center')

        # Body
        body = patches.Rectangle((x, y), w, h - 4, facecolor='#111827', edgecolor='#374151', linewidth=1)
        ax.add_patch(body)

        cy = y + h - 6
        for col_name, col_type in cols:
            ax.text(x + 1, cy, col_name, fontsize=7, color='#F8FAFC', fontweight='medium')
            ax.text(x + w - 1, cy, col_type, fontsize=6.5, color='#94A3B8', ha='right')
            cy -= 2.2

    # Cardinality lines
    def rel(x1, y1, x2, y2, label="1:N"):
        ax.plot([x1, x2], [y1, y2], color='#60A5FA', linewidth=1.2, linestyle=':')
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.8, label, fontsize=6.5, color='#93C5FD', ha='center')

    rel(22, 82, 26, 82, "1:N")
    rel(48, 82, 76, 82, "1:N")
    rel(73, 82, 76, 82, "1:1")
    rel(24, 53, 26, 53, "1:N")
    rel(49, 53, 52, 53, "1:N")
    rel(76, 53, 74, 53, "N:M")
    rel(86.5, 40, 25, 33, "1:N")
    rel(86.5, 40, 54.5, 33, "1:1")
    rel(86.5, 40, 84, 33, "1:N")

    save_fig(fig, "Database_ER_Diagram.png")


if __name__ == '__main__':
    print("Generating diagrams...")
    make_architecture_diagram()
    make_data_flow_diagram()
    make_use_case_diagram()
    make_activity_diagram()
    make_sequence_diagram()
    make_database_er_diagram()
    print("All 6 diagrams generated successfully!")
