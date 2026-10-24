"""Generates the hero banner graphic for SkillSprint AI (GEN_AI_IMG.png)."""
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches

fig = plt.figure(figsize=(16, 9), facecolor='#070D17')
ax = fig.add_subplot(111)
ax.set_facecolor('#070D17')
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis('off')

# Glowing background backdrop
glow = patches.Ellipse((50, 50), 90, 70, facecolor='#10233D', alpha=0.5, edgecolor='none')
ax.add_patch(glow)

# Header badge
badge = patches.FancyBboxPatch((35, 83), 30, 6, boxstyle="round,pad=0.4,rounding_size=1.0",
                               facecolor='#1E293B', edgecolor='#0284C7', linewidth=1.5)
ax.add_patch(badge)
ax.text(50, 86, "TECHWIZ 7 · GENERATIVE AI POWERPLAY", fontsize=11, fontweight='bold', color='#38BDF8', ha='center', va='center')

# Title & Subtitle
ax.text(50, 74, "SkillSprint AI", fontsize=44, fontweight='bold', color='#FFFFFF', ha='center', va='center')
ax.text(50, 66, "Enterprise Onboarding Intelligence & Knowledge Grounding Platform", fontsize=17, color='#94A3B8', ha='center', va='center')
ax.text(50, 61, "Theme: OnboardVerse  |  Fictional Enterprise: Nexora Labs  |  Category: GenAI PowerPlay", fontsize=11, color='#64748B', ha='center', va='center')

# Central Architecture Cards
cards = [
    ("Pipeline 1: GenAI Engine", "• Staged Day 1 → 90 Plans\n• Modules, Tasks, Checklists\n• Scenario Quizzes & Rubrics\n• Fallback: Claude/Gemini/Ollama", 10, 24, 24, 28, '#064E3B', '#10B981', '#34D399'),
    ("Dual-Pipeline Verification", "• Independent Python Validation\n• Zero Generative AI in Verifier\n• 100% Mandatory Coverage\n• 100% Source Traceability Check", 38, 24, 24, 28, '#1E1B4B', '#8B5CF6', '#C084FC'),
    ("Enterprise Governance", "• 150+ Role Requirement Matrix\n• 13 Deterministic Python Rules\n• Precedence DAG & Impact Diff\n• Reviewer Override & Full Audit", 66, 24, 24, 28, '#701A75', '#EC4899', '#F472B6'),
]

for title, content, x, y, w, h, bg, border, accent in cards:
    card = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.8,rounding_size=1.5",
                                  facecolor=bg, edgecolor=border, linewidth=2, alpha=0.85)
    ax.add_patch(card)
    ax.text(x + w / 2, y + h - 4, title, fontsize=12, fontweight='bold', color=accent, ha='center', va='center')
    ax.text(x + 2, y + h / 2 - 2, content, fontsize=9.5, color='#F8FAFC', va='center', linespacing=1.5)

# Metrics bar at the bottom
metrics = [
    ("41", "Company Policies & SOPs"),
    ("10", "Distinct Job Roles"),
    ("150+", "Ground-Truth Requirements"),
    ("100%", "Mandatory Plan Coverage"),
    ("13", "Deterministic Python Rules"),
    ("0%", "Hallucination Tolerance"),
]

mx_box = patches.FancyBboxPatch((6, 5), 88, 12, boxstyle="round,pad=0.6,rounding_size=1.0",
                                facecolor='#0F172A', edgecolor='#334155', linewidth=1.5)
ax.add_patch(mx_box)

for i, (val, label) in enumerate(metrics):
    cx = 13 + i * 14.8
    ax.text(cx, 12, val, fontsize=18, fontweight='bold', color='#38BDF8', ha='center', va='center')
    ax.text(cx, 8, label, fontsize=7.5, color='#94A3B8', ha='center', va='center')

out_paths = [
    Path("SkillSprint_Submission/GEN_AI_IMG.png"),
    Path("SkillSprint_Submission/SkillSprint_AI_Banner.png"),
    Path("docs/brand/SkillSprint_AI_Banner.png"),
]
for p in out_paths:
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p, dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor(), edgecolor='none')
plt.close(fig)
print("Banner saved successfully!")
