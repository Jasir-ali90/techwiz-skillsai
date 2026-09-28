"""Boundary tests (limits, malformed and out-of-range input, unknown ids) and
role relevance against a live plan."""
import uuid

import pytest

pytestmark = pytest.mark.db
MISSING = str(uuid.UUID(int=0))


@pytest.mark.parametrize("params", [
    {"q": "a"}, {"q": "x" * 501}, {"q": "security", "limit": 0}, {"q": "security", "limit": 51},
    {"q": "security", "min_similarity": 1.5}, {"q": "security", "min_similarity": -0.1},
])
async def test_search_rejects_out_of_range_parameters(client, admin, params):
    assert (await client.get("/search", headers=admin, params=params)).status_code == 422


async def test_search_accepts_the_limits_themselves(client, admin):
    for params in ({"q": "ab", "limit": 1}, {"q": "security", "limit": 50, "min_similarity": 1.0}):
        assert (await client.get("/search", headers=admin, params=params)).status_code == 200


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 101},
                                    {"progress_min": -1}, {"progress_max": 101}])
async def test_record_search_rejects_bad_paging_and_ranges(client, admin, params):
    assert (await client.get("/search/records", headers=admin, params=params)).status_code == 422


async def test_record_search_past_the_last_page_is_empty(client, admin):
    r = (await client.get("/search/records", headers=admin, params={"page": 99})).json()
    assert r["results"] == [] and r["total"] >= 1


@pytest.mark.parametrize("body", [
    {"simulate_malformed": 6}, {"simulate_malformed": -1}, {"extra_topics": [f"t{i}" for i in range(21)]},
])
async def test_generate_rejects_out_of_range_options(client, admin, employees_by_code, body):
    r = await client.post("/plans/generate", headers=admin,
                          json={"employee_id": employees_by_code["EMP-001"]["id"], **body})
    assert r.status_code == 422


async def test_unknown_ids_return_404_not_500(client, admin):
    assert (await client.post("/plans/generate", headers=admin, json={"employee_id": MISSING})).status_code == 404
    assert (await client.get(f"/plans/{MISSING}", headers=admin)).status_code == 404
    assert (await client.post(f"/validation/run/{MISSING}", headers=admin)).status_code == 404
    assert (await client.get(f"/matrix/role/{MISSING}", headers=admin)).status_code == 404
    assert (await client.get("/requirements/R99999", headers=admin)).status_code == 404
    assert (await client.post(f"/impact/analyse/{MISSING}", headers=admin)).status_code == 404
    assert (await client.get("/documents/chunks/NOPE%23C001/trace", headers=admin)).status_code == 404


async def test_malformed_ids_and_bodies_are_422(client, admin):
    assert (await client.get("/plans/not-a-uuid", headers=admin)).status_code == 422
    assert (await client.post("/auth/login", json={})).status_code == 422
    assert (await client.post("/auth/login", json={"email": "not-an-email", "password": "x"})).status_code == 422


async def test_consistency_run_count_limits(client, admin, backend_plan):
    for count in (1, 6):
        r = await client.post(f"/consistency/{backend_plan['id']}", headers=admin, json={"run_count": count})
        assert r.status_code == 422


async def test_assessment_score_and_quiz_answer_limits(client, admin, backend_plan):
    plan = (await client.get(f"/plans/{backend_plan['id']}", headers=admin)).json()
    assessment = next(a for m in plan["modules"] for a in m["assessments"])
    question = next(q for m in plan["modules"] for q in m["quiz"])
    for score in (-1, 100.5):
        r = await client.post(f"/progress/assessments/{assessment['id']}/result", headers=admin, json={"score": score})
        assert r.status_code == 422
    assert (await client.post(f"/progress/quiz/{question['id']}/attempt", headers=admin,
                              json={"answer": []})).status_code == 422
    assert (await client.post(f"/progress/items/task/{MISSING}", headers=admin,
                              json={"status": "COMPLETED"})).status_code == 404
    task = next(t for m in plan["modules"] for t in m["tasks"])
    assert (await client.post(f"/progress/items/task/{task['id']}", headers=admin,
                              json={"status": "HALF_DONE"})).status_code == 422


async def test_unknown_rule_config_key_and_report_format(client, admin):
    assert (await client.put("/validation/rules", headers=admin, json={"no_such_rule": {"enabled": False}})).status_code == 422
    assert (await client.get("/config/no_such_key", headers=admin)).status_code == 404
    assert (await client.put("/config/quiz_types", headers=admin, json={"types": "none"})).status_code == 422
    assert (await client.get("/reports/comparison", headers=admin, params={"format": "docx"})).status_code == 422


async def test_upload_boundaries(client, admin):
    form = {"document_code": "POL-BOUND-001", "title": "t", "document_type": "HR_POLICY", "effective_date": "2026-01-01"}
    tiny = b"%PDF-1.4\n" + b"x" * 80
    assert (await client.post("/documents", headers=admin, data={**form, "version": "0"},
                              files={"file": ("a.pdf", tiny, "application/pdf")})).status_code == 422
    assert (await client.post("/documents", headers=admin, data={**form, "version": "1", "document_type": "MEMO"},
                              files={"file": ("a.pdf", tiny, "application/pdf")})).status_code == 422
    just_under = b"%PDF-1.4\n" + b"x" * 60   # 69 bytes: above the 64-byte empty threshold
    r = await client.post("/documents", headers=admin, data={**form, "version": "1"},
                          files={"file": ("a.pdf", just_under, "application/pdf")})
    assert r.status_code == 201


# ------------------------------------------------------------ role relevance, live
async def test_content_for_another_role_is_flagged_irrelevant(client, admin, backend_plan):
    from src.core.db import SessionLocal
    from src.repositories.plan import PlanRepository

    roles = {r["code"]: r["id"] for r in (await client.get("/roles", headers=admin)).json()}
    backend = {r["requirement_code"] for r in (await client.get(f"/matrix/role/{roles['BACKEND_DEV']}",
                                                                headers=admin)).json()["requirements"]}
    devops = (await client.get(f"/matrix/role/{roles['DEVOPS_ENG']}", headers=admin)).json()["requirements"]
    foreign = next(r for r in devops if r["requirement_code"] not in backend)
    plan = (await client.get(f"/plans/{backend_plan['id']}", headers=admin)).json()
    task = next(t for m in plan["modules"] for t in m["tasks"])
    async with SessionLocal() as session:
        row = await PlanRepository(session).item("task", uuid.UUID(task["id"]))
        original = row.requirement_code
        row.requirement_code = foreign["requirement_code"]
        await session.commit()
    try:
        result = (await client.post(f"/validation/run/{backend_plan['id']}", headers=admin)).json()
        flagged = [f for f in result["findings"] if f["rule"] == "role_relevance" and f["item_id"] == task["id"]]
        assert flagged and "DevOps Engineer" in flagged[0]["evidence"]["maps_to_roles"]
        assert "not to Backend Developer" in flagged[0]["message"]
        assert result["verification_status"] != "VERIFIED"
    finally:
        async with SessionLocal() as session:
            row = await PlanRepository(session).item("task", uuid.UUID(task["id"]))
            row.requirement_code = original
            await session.commit()
        await client.post(f"/validation/run/{backend_plan['id']}", headers=admin)


async def test_relevant_plans_have_no_role_relevance_findings(client, admin, backend_plan, seo_plan):
    for plan in (backend_plan, seo_plan):
        result = (await client.post(f"/validation/run/{plan['id']}", headers=admin)).json()
        assert not [f for f in result["findings"] if f["rule"] == "role_relevance"]
