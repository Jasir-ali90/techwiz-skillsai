"""Comparison, consistency, review workflow, append-only audit trail,
progress, dashboards, reports, export and global search."""
import io

import pandas as pd
import pytest

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
async def all_plans(client, admin, employees_by_code, backend_plan, seo_plan):
    for code, employee in employees_by_code.items():
        if code not in ("EMP-001", "EMP-002"):
            response = await client.post("/plans/generate", headers=admin, json={"employee_id": employee["id"]})
            assert response.status_code == 200, response.text
    return (await client.get("/plans", headers=admin, params={"current_only": True})).json()


# ------------------------------------------------------------ comparison and consistency
async def test_comparison_rows_and_csv_export(client, admin, backend_plan):
    report = (await client.post(f"/comparison/{backend_plan['id']}", headers=admin)).json()
    roles = {r["code"]: r["id"] for r in (await client.get("/roles", headers=admin)).json()}
    matrix = (await client.get(f"/matrix/role/{roles['BACKEND_DEV']}", headers=admin)).json()
    assert report["summary"]["rows"] == matrix["total"]
    row = report["rows"][0]
    for key in ("requirement_code", "role", "required_policy", "required_competency", "mandatory_or_optional",
                "learning_module_category", "source_document_id", "source_section_id", "priority", "due_stage",
                "compliance_requirement", "required_task", "required_assessment_topic", "python_expected_result",
                "genai_result", "match", "coverage_status", "traceability_status", "validation_status",
                "explanation"):
        assert key in row
    csv = await client.get(f"/comparison/{backend_plan['id']}/export", headers=admin)
    assert csv.headers["content-type"].startswith("text/csv")
    df = pd.read_csv(io.StringIO(csv.text))
    assert len(df) == matrix["total"] and "explanation" in df.columns


async def test_consistency_runs_as_a_background_job(client, admin, backend_plan):
    started = await client.post(f"/consistency/{backend_plan['id']}", headers=admin, json={"run_count": 2})
    assert started.status_code == 202
    params = started.json()["parameters"]
    assert {"temperature", "seed", "prompt_version", "fixed_chunk_set"} <= set(params)
    results = (await client.get(f"/consistency/{backend_plan['id']}", headers=admin)).json()
    latest = results[0]
    assert latest["status"] == "COMPLETED", latest
    assert latest["consistency_score"] == 100.0 and latest["major_differences"] == []
    assert len(latest["runs"]) == 2


# ------------------------------------------------------------ review workflow and audit
async def test_review_override_keeps_original_and_decision(client, admin, reviewer, backend_plan):
    import uuid

    from src.core.db import SessionLocal
    from src.repositories.plan import PlanRepository

    plan = (await client.get(f"/plans/{backend_plan['id']}", headers=admin)).json()
    item = next(c for m in plan["modules"] for c in m["checklist"])
    async with SessionLocal() as session:   # a claim no document supports, so something is flagged
        row = await PlanRepository(session).item("checklist_item", uuid.UUID(item["id"]))
        row.activity = "All employees must register their personal vehicle with facilities within two days."
        await session.commit()
    await client.post(f"/validation/run/{backend_plan['id']}", headers=admin)
    queue = (await client.get("/review/queue", headers=reviewer)).json()
    finding = next(f for f in queue if f["plan_id"] == backend_plan["id"] and f["item_id"] == item["id"])
    assert finding["rule"] == "hallucination" and finding["severity"] == "ERROR"
    decided = await client.post(f"/review/{finding['id']}/decision", headers=reviewer,
                                json={"decision": "APPROVE", "reason": "Resolved by precedence; acceptable"})
    assert decided.status_code == 200
    body = decided.json()
    assert body["review_status"] == "APPROVED" and body["original_result"]["message"] == finding["message"]
    audit = (await client.get(f"/audit/finding/{finding['id']}", headers=admin)).json()
    assert audit["history"][-1]["action"] == "review_approve"
    assert audit["history"][-1]["before"]["finding"]["message"] == finding["message"]
    assert audit["review_decisions"][0]["original_finding"]["id"] == finding["id"]
    assert audit["review_decisions"][0]["decision"] == "APPROVE"
    again = (await client.post(f"/validation/run/{backend_plan['id']}", headers=admin)).json()
    carried = [f for f in again["findings"] if f["message"] == finding["message"] and f["item_id"] == finding["item_id"]]
    assert carried and carried[0]["review_status"] == "APPROVED"


async def test_reviewer_edit_is_applied_and_audited(client, admin, reviewer, backend_plan):
    from src.core.db import SessionLocal
    from src.repositories.plan import PlanRepository

    plan = (await client.get(f"/plans/{backend_plan['id']}", headers=admin)).json()
    task = next(t for m in plan["modules"] for t in m["tasks"])
    async with SessionLocal() as session:
        row = await PlanRepository(session).item("task", __import__("uuid").UUID(task["id"]))
        row.description = "Employees must file a travel expense claim within two days of every trip."
        await session.commit()
    result = (await client.post(f"/validation/run/{backend_plan['id']}", headers=admin)).json()
    flag = next(f for f in result["findings"] if f["rule"] == "hallucination" and f["item_id"] == task["id"])
    edit = await client.post(f"/review/{flag['id']}/decision", headers=reviewer, json={
        "decision": "EDIT", "reason": "Restore the source wording", "edits": {"description": task["description"]}})
    assert edit.status_code == 200 and edit.json()["original_item"]["description"].startswith("Employees must file")
    after = (await client.post(f"/validation/run/{backend_plan['id']}", headers=admin)).json()
    assert not [f for f in after["findings"] if f["rule"] == "hallucination" and f["item_id"] == task["id"]
                and f["severity"] == "ERROR"]
    trail = (await client.get(f"/audit/task/{task['id']}", headers=admin)).json()["history"]
    assert trail[-1]["action"] == "reviewer_edit" and trail[-1]["before"]["description"].startswith("Employees must file")


async def test_audit_log_and_review_decisions_are_append_only():
    from sqlalchemy import select, text

    from src.core.db import SessionLocal
    from src.models.audit import AppendOnlyError, AuditLog
    from src.models.review import ReviewDecision

    async with SessionLocal() as session:
        entry = await session.scalar(select(AuditLog).limit(1))
        entry.reason = "tampered"
        with pytest.raises(AppendOnlyError):
            await session.flush()
        await session.rollback()
    async with SessionLocal() as session:
        decision = await session.scalar(select(ReviewDecision).limit(1))
        await session.delete(decision)
        with pytest.raises(AppendOnlyError):
            await session.flush()
        await session.rollback()
    for statement in ("UPDATE audit_log SET reason = 'x'", "DELETE FROM audit_log",
                      "UPDATE review_decisions SET reason = 'x'", "DELETE FROM review_decisions"):
        async with SessionLocal() as session:
            with pytest.raises(Exception, match="append-only"):
                await session.execute(text(statement))
            await session.rollback()


# ------------------------------------------------------------ progress and dashboards
async def test_employee_progress_quiz_weak_area_and_dashboard(client, admin, employee_login, backend_plan):
    plan = (await client.get(f"/plans/{backend_plan['id']}", headers=admin)).json()
    task = next(t for m in plan["modules"] for t in m["tasks"])
    done = await client.post(f"/progress/items/task/{task['id']}", headers=employee_login, json={"status": "COMPLETED"})
    assert done.status_code == 200 and done.json()["progress"]["by_type"]["task"]["completed"] >= 1

    module = next(m for m in plan["modules"] if m["quiz"])
    question = module["quiz"][0]
    wrong = [o for o in question["options"] if o not in question["correct_answer"]][0]
    for _ in range(2):
        r = await client.post(f"/progress/quiz/{question['id']}/attempt", headers=employee_login, json={"answer": [wrong]})
        assert r.json()["is_correct"] is False
    right = await client.post(f"/progress/quiz/{question['id']}/attempt", headers=employee_login,
                              json={"answer": question["correct_answer"]})
    assert right.json()["is_correct"] is True

    dashboard = (await client.get("/dashboard/me", headers=employee_login)).json()
    assert dashboard["employee"]["code"] == "EMP-001"
    weak = {w["competency"] for w in dashboard["weak_areas"]}
    assert module["competency"] in weak
    assert any(r["type"] == "ADDITIONAL_QUIZ" and r["competency"] == module["competency"]
               for r in dashboard["recommendations"])
    for key in ("onboarding_progress", "assigned_modules", "completed_modules", "tasks", "quiz_scores",
                "upcoming_activities", "milestones"):
        assert key in dashboard


async def test_employee_cannot_touch_someone_elses_progress(client, admin, employee_login, seo_plan):
    plan = (await client.get(f"/plans/{seo_plan['id']}", headers=admin)).json()
    task = next(t for m in plan["modules"] for t in m["tasks"])
    denied = await client.post(f"/progress/items/task/{task['id']}", headers=employee_login, json={"status": "COMPLETED"})
    assert denied.status_code == 403
    assert (await client.get(f"/progress/{seo_plan['employee_id']}", headers=employee_login)).status_code == 403


async def test_assessment_result_recorded_by_staff(client, admin, backend_plan):
    plan = (await client.get(f"/plans/{backend_plan['id']}", headers=admin)).json()
    assessment = next(a for m in plan["modules"] for a in m["assessments"])
    r = await client.post(f"/progress/assessments/{assessment['id']}/result", headers=admin, json={"score": 55})
    assert r.status_code == 200 and r.json()["passed"] is False


async def test_admin_and_role_dashboards(client, admin, all_plans):
    dashboard = (await client.get("/dashboard/admin", headers=admin)).json()
    assert len(dashboard["compliance_coverage"]) == 10
    assert all(row["plans"] >= 1 for row in dashboard["compliance_coverage"])
    assert dashboard["flagged_content"]["suspicious_chunks"] >= 1
    assert dashboard["training_plans"]["current"] >= 10
    roles = (await client.get("/dashboard/roles", headers=admin)).json()
    assert len(roles) == 10 and all("completion" in r and "requirements" in r for r in roles)


async def test_plan_comparison_across_dimensions(client, admin, all_plans):
    for dimension in ("role", "department", "experience_level", "document_version"):
        r = await client.get("/plans/compare", headers=admin, params={"dimension": dimension})
        assert r.status_code == 200 and r.json()["groups"], dimension
    by_role = (await client.get("/plans/compare", headers=admin, params={"dimension": "role"})).json()
    assert len(by_role["groups"]) == 10 and by_role["pairwise"]


# ------------------------------------------------------------ reports, export, search
REPORT_NAMES = ["employee-progress", "role-coverage", "mandatory-training", "assessment-results",
                "source-traceability", "hallucination-flags", "policy-coverage", "comparison"]


@pytest.mark.parametrize("name", REPORT_NAMES)
async def test_every_report_exports_in_all_formats(client, admin, all_plans, name):
    js = await client.get(f"/reports/{name}", headers=admin)
    assert js.status_code == 200 and "rows" in js.json()
    csv = await client.get(f"/reports/{name}", headers=admin, params={"format": "csv"})
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv")
    xlsx = await client.get(f"/reports/{name}", headers=admin, params={"format": "xlsx"})
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"
    pdf = await client.get(f"/reports/{name}", headers=admin, params={"format": "pdf"})
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


async def test_comparison_report_has_at_least_100_rows_with_explanations(client, admin, all_plans):
    report = (await client.get("/reports/comparison", headers=admin)).json()
    assert report["summary"]["rows"] >= 100 and report["summary"]["meets_100_row_minimum"]
    assert all(r["explanation"] for r in report["rows"])
    df = pd.read_csv(io.BytesIO((await client.get("/reports/comparison", headers=admin,
                                                  params={"format": "csv"})).content))
    assert len(df) >= 100 and df["explanation"].notna().all()


async def test_global_search_filters_and_paginates(client, admin, all_plans):
    everyone = (await client.get("/search/records", headers=admin, params={"page_size": 3})).json()
    assert everyone["total"] == 10 and len(everyone["results"]) == 3 and everyone["pages"] == 4
    backend = (await client.get("/search/records", headers=admin, params={"role": "backend"})).json()
    assert backend["total"] == 1 and backend["results"][0]["role"] == "Backend Developer"
    by_policy = (await client.get("/search/records", headers=admin,
                                  params={"policy": "SOP-DEPLOY", "department": "Infrastructure"})).json()
    assert by_policy["total"] >= 1
    by_module = (await client.get("/search/records", headers=admin, params={"module": "release management"})).json()
    assert all(r["matched_modules"] for r in by_module["results"])
    verified = (await client.get("/search/records", headers=admin, params={"verification": "VERIFIED_WITH_WARNING"})).json()
    assert all(r["verification_status"] == "VERIFIED_WITH_WARNING" for r in verified["results"])
    ranged = (await client.get("/search/records", headers=admin, params={"progress_min": 0, "progress_max": 100})).json()
    assert ranged["total"] == 10
