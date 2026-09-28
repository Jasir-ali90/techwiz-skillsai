"""Policy version diffing, contradiction detection across documents,
comparison and consistency scoring, progress assessment, weak areas,
recommendations and report export formats."""
import io
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.comparison_engine.compare import CSV_COLUMNS, build_rows, consistency, signature, summarise
from src.contradiction_checks.detector import ChunkFact, PolarityChecker, detect_corpus, numeric_conflict, resolve
from src.core.app_config import load_yaml
from src.document_processing.chunker import chunk_document
from src.document_processing.pdf_parser import parse_pdf
from src.impact.diff import diff_versions
from src.progress import engine as progress
from src.reports.export import render
from tests.factories import MATRIX, STAGES, DOC, good_plan, items_of

SAMPLES = Path("sample_documents")


# ------------------------------------------------------------ policy version
@pytest.fixture(scope="module")
def infosec_diff():
    old = chunk_document(parse_pdf(str(SAMPLES / "POL-INFOSEC-001_v1.pdf")), "POL-INFOSEC-001")
    new = chunk_document(parse_pdf(str(SAMPLES / "POL-INFOSEC-001_v2.pdf")), "POL-INFOSEC-001")
    return diff_versions(old, new)


def test_v1_to_v2_diff_names_the_three_changed_clauses(infosec_diff):
    modified = {m["section_id"]: m for m in infosec_diff["modified"]}
    assert "seven" in modified["2.3"]["summary"] and "three" in modified["2.3"]["summary"]
    assert "hardware security key" in modified["2.1"]["new_text"]
    assert "multi-factor" in modified["2.1"]["old_text"]
    assert "must not" in modified["3.3"]["old_text"] and "read-only" in modified["3.3"]["new_text"]


def test_diff_reports_added_and_unchanged_sections(infosec_diff):
    added = {a["section_id"] for a in infosec_diff["added"]}
    assert {"8.1", "8.2", "8.3"} <= added
    unchanged = {u["section_id"] for u in infosec_diff["unchanged"]}
    assert "3.1" in unchanged and "2.3" not in unchanged
    assert infosec_diff["counts"]["removed"] == 0


def test_numeric_changes_are_extracted(infosec_diff):
    section = next(m for m in infosec_diff["modified"] if m["section_id"] == "6.1")
    change = section["numeric_changes"][0]
    assert change["removed"] == ["one hour"] and change["added"] == ["thirty minutes"]


# ------------------------------------------------------------ contradiction detection
def fact(code, doc_code, dtype, text, rank, version=1, status="ACTIVE", section="2.1", effective=date(2026, 1, 1)):
    return ChunkFact(code, doc_code + str(version), doc_code, dtype, version, status, rank, effective, section, text)


def test_numeric_conflict_between_faq_and_policy_resolves_to_policy(embedder):
    policy = fact("P#1", "POL", "INFOSEC_POLICY", "Employees must complete the Information Security Basics "
                  "module within seven calendar days of their joining date.", 20, section="2.3")
    faq = fact("F#1", "FAQ", "FAQ", "You have a full two weeks from your joining date to complete Information "
               "Security Basics.", 60)
    for f, v in zip((policy, faq), embedder([policy.content, faq.content])):
        f.vector = v
    found = detect_corpus([policy, faq], PolarityChecker([], []), pair_similarity=0.3)
    assert len(found) == 1
    c = found[0].as_dict()
    assert c["kind"] == "FAQ_VS_POLICY" and c["category"] == "NUMERIC"
    assert c["winner"]["document_code"] == "POL" and "outranks" in c["resolution"]


def test_polarity_conflict(embedder):
    config = load_yaml("validation_rules")
    checker = PolarityChecker(config["permissive_patterns"], config["prohibitive_patterns"])
    sop = fact("S#1", "SOP", "DEPARTMENT_SOP", "No production release shall take place on a Friday after 13:00.", 30)
    faq = fact("F#2", "FAQ", "FAQ", "A quick Friday evening production release is usually fine.", 60)
    for f, v in zip((sop, faq), embedder([sop.content, faq.content])):
        f.vector = v
    found = detect_corpus([sop, faq], checker, polarity_similarity=0.2)
    assert found and found[0].category == "POLARITY" and found[0].winner.document_code == "SOP"


def test_old_versus_new_version_is_detected_and_new_wins():
    old = fact("P#1", "POL", "INFOSEC_POLICY", "within seven calendar days", 20, version=1, status="OBSOLETE")
    new = fact("P#1", "POL", "INFOSEC_POLICY", "within three calendar days", 20, version=2)
    found = detect_corpus([old, new], PolarityChecker([], []))
    assert found[0].kind == "OLD_VS_NEW_VERSION" and found[0].winner.version == 2
    assert "seven calendar days became three calendar days" in found[0].detail


def test_role_description_versus_sop_and_tie_break_on_date():
    a = fact("R#1", "ROLE", "ROLE_DESCRIPTION", "x", 40, effective=date(2026, 1, 1))
    b = fact("S#1", "SOP", "DEPARTMENT_SOP", "x", 40, effective=date(2026, 6, 1))
    winner, _ = resolve(a, b)
    assert winner.document_code == "SOP"
    assert numeric_conflict("at least two reviewers", "at least one reviewers")["kind"] == "count"


# ------------------------------------------------------------ comparison and consistency
def test_comparison_rows_compare_attributes_not_wording():
    plan = good_plan()
    documents = {DOC: {"id": DOC, "document_code": "POL", "version": 2, "status": "ACTIVE"}}
    rows = build_rows({"title": "Backend Developer"}, MATRIX, items_of(plan), documents, STAGES, [])
    assert [r["requirement_code"] for r in rows] == ["R001", "R002", "R003"]
    assert all(r["match"] == "MATCH" for r in rows)
    assert set(CSV_COLUMNS) <= set(rows[0])
    plan["modules"] = plan["modules"][:2]
    plan["modules"][0]["tasks"][0]["priority"] = "LOW"
    rows = build_rows({"title": "Backend Developer"}, MATRIX, items_of(plan), documents, STAGES, [])
    by_code = {r["requirement_code"]: r for r in rows}
    assert by_code["R003"]["coverage_status"] == "MISSING" and by_code["R003"]["validation_status"] == "REQUIREMENT_MISSING"
    assert "priority LOW vs expected HIGH" in by_code["R001"]["explanation"]
    assert summarise(rows)["mismatches"] == 2


def test_consistency_score_and_major_differences():
    base = {"modules": [{"category": "A", "requirement_code": "R1", "source_chunk_code": "C1", "mandatory": True,
                         "checklist": [], "tasks": [], "quiz": [], "scenarios": [], "assessment": {"topic": "A"}}]}
    other = {"modules": [{"category": "B", "requirement_code": "R2", "source_chunk_code": "C2", "mandatory": True,
                          "checklist": [], "tasks": [], "quiz": [], "scenarios": [], "assessment": None}]}
    score_same, _, major_same = consistency([signature(base), signature(base)])
    assert score_same == 100.0 and major_same == []
    score, per_dim, major = consistency([signature(base), signature(other)])
    assert score < 50 and per_dim["mandatory_requirements"] == 0
    assert {"MANDATORY_REQUIREMENT_UNSTABLE"} <= {m["type"] for m in major}


# ------------------------------------------------------------ progress, weak areas, recommendations
def plan_for_progress():
    from src.services.plan_views import flat_items  # noqa: F401  (shape reference)

    plan = good_plan()
    for m in plan["modules"]:
        m["checklist"] = []
    return plan


def test_forty_days_in_with_twenty_percent_is_behind_schedule():
    plan = plan_for_progress()
    stages = {"DAY_1": {"sequence": 1, "offset_days": 1, "name": "Day 1"},
              "WEEK_1": {"sequence": 2, "offset_days": 7, "name": "Week 1"},
              "DAY_30": {"sequence": 4, "offset_days": 30, "name": "Day 30"}}
    items = [t for m in plan["modules"] for t in m["tasks"]]
    for extra in range(8):
        plan["modules"][0]["tasks"].append(dict(items[0], id=f"extra-{extra}"))
    plan["modules"][0]["tasks"][0]["completion_status"] = "COMPLETED"
    plan["modules"][1]["tasks"][0]["completion_status"] = "COMPLETED"
    config = load_yaml("progress")
    report = progress.assess(plan, [], [], stages, date.today() - timedelta(days=40), date.today(), config)
    assert report["overall_progress"] <= 25
    assert report["status"] == "BEHIND_SCHEDULE"
    assert any(r["type"] == "MANAGER_REVIEW" for r in report["recommendations"])


def test_on_track_early_and_completed_and_assessment_required():
    plan = plan_for_progress()
    config = load_yaml("progress")
    fresh = progress.assess(plan, [], [], STAGES, date.today(), date.today(), config)
    assert fresh["status"] == "ON_TRACK"
    for m in plan["modules"]:
        m["completion_status"] = "COMPLETED"
        for t in m["tasks"]:
            t["completion_status"] = "COMPLETED"
    attempts = [{"question_id": q["id"], "is_correct": True, "competency": m["competency"]}
                for m in plan["modules"] for q in m["quiz"]]
    pending = progress.assess(plan, attempts, [], STAGES, date.today() - timedelta(days=5), date.today(), config)
    assert pending["status"] == "ASSESSMENT_REQUIRED"
    results = [{"assessment_id": a["id"], "passed": True, "score": 90, "competency": m["competency"]}
               for m in plan["modules"] for a in m["assessments"]]
    done = progress.assess(plan, attempts, results, STAGES, date.today() - timedelta(days=5), date.today(), config)
    assert done["status"] == "COMPLETED" and done["overall_progress"] == 100.0


def test_two_failed_quizzes_on_one_competency_give_weak_area_and_revision():
    plan = plan_for_progress()
    question = plan["modules"][0]["quiz"][0]["id"]
    attempts = [{"question_id": question, "is_correct": False, "competency": "Security Awareness"},
                {"question_id": question, "is_correct": False, "competency": "Security Awareness"}]
    report = progress.assess(plan, attempts, [], STAGES, date.today() - timedelta(days=2), date.today(),
                             load_yaml("progress"))
    weak = {w["competency"]: {s["signal"] for s in w["signals"]} for w in report["weak_areas"]}
    assert {"low_quiz_accuracy", "repeated_error"} <= weak["Security Awareness"]
    recs = {(r["type"], r["competency"]) for r in report["recommendations"]}
    assert ("REVISION_MODULE", "Security Awareness") in recs
    assert ("ADDITIONAL_QUIZ", "Security Awareness") in recs


def test_failed_assessment_and_overdue_tasks_are_weak_area_signals():
    plan = plan_for_progress()
    assessment = plan["modules"][1]["assessments"][0]["id"]
    results = [{"assessment_id": assessment, "passed": False, "score": 40, "competency": "Account Security"}]
    report = progress.assess(plan, [], results, STAGES, date.today() - timedelta(days=20), date.today(),
                             load_yaml("progress"))
    signals = {s["signal"] for w in report["weak_areas"] if w["competency"] == "Account Security" for s in w["signals"]}
    assert {"failed_assessment", "overdue_tasks"} <= signals


# ------------------------------------------------------------ export
ROWS = [{"requirement_code": f"R{i:03d}", "match": "MATCH" if i % 2 else "MISMATCH",
         "explanation": "priority LOW vs expected HIGH" if i % 2 == 0 else "matches",
         "python_expected_result": {"mandatory": True}} for i in range(120)]


def test_csv_export():
    df = pd.read_csv(io.BytesIO(render(ROWS, "csv", "Comparison")))
    assert len(df) == 120 and list(df.columns)[:2] == ["requirement_code", "match"]


def test_excel_export_has_report_and_summary_sheets():
    content = render(ROWS, "xlsx", "Comparison", {"rows": 120})
    sheets = pd.read_excel(io.BytesIO(content), sheet_name=None)
    assert set(sheets) == {"Report", "Summary"} and len(sheets["Report"]) == 120


def test_pdf_export_is_a_pdf():
    content = render(ROWS, "pdf", "Comparison", {"rows": 120})
    assert content.startswith(b"%PDF") and len(content) > 5000
