"""Pipeline 1 and Pipeline 2 end to end: generation, JSON, traceability,
coverage, rule toggles, the 30-second budget and the Verified flip."""
import time
import uuid
from collections import Counter

import pytest

pytestmark = pytest.mark.db


def items(plan):
    for m in plan["modules"]:
        yield "module", m
        for kind in ("checklist", "tasks", "quiz", "assessments", "scenarios"):
            for x in m[kind]:
                yield kind, x


async def test_backend_and_seo_plans_are_visibly_different(backend_plan, seo_plan):
    b_titles = {m["competency"] for m in backend_plan["modules"]}
    s_titles = {m["competency"] for m in seo_plan["modules"]}
    assert b_titles != s_titles and len(b_titles - s_titles) >= 2
    b_codes = {c for m in backend_plan["modules"] for c in m["requirement_codes"]}
    s_codes = {c for m in seo_plan["modules"] for c in m["requirement_codes"]}
    assert b_codes - s_codes
    b_quiz = {q["requirement_code"] for m in backend_plan["modules"] for q in m["quiz"]}
    s_quiz = {q["requirement_code"] for m in seo_plan["modules"] for q in m["quiz"]}
    assert b_quiz != s_quiz
    b_tasks = {t["requirement_code"] for m in backend_plan["modules"] for t in m["tasks"]}
    s_tasks = {t["requirement_code"] for m in seo_plan["modules"] for t in m["tasks"]}
    assert b_tasks != s_tasks
    b_priority = Counter(x["priority"] for kind, x in items(backend_plan) if kind != "module")
    s_priority = Counter(x["priority"] for kind, x in items(seo_plan) if kind != "module")
    assert b_priority != s_priority


async def test_no_plan_puts_everything_on_day_one(backend_plan, seo_plan):
    for plan in (backend_plan, seo_plan):
        stages = Counter(x["due_stage"] for kind, x in items(plan) if kind != "module")
        assert len(stages) >= 3
        assert stages["DAY_1"] / sum(stages.values()) < 0.6


async def test_every_item_carries_document_section_and_chunk(backend_plan):
    for kind, x in items(backend_plan):
        assert x["source_document_id"] and x["source_section_id"] and x["source_chunk_code"], (kind, x)
        assert x["source_document_code"] and x["source_chunk_code"].startswith(x["source_document_code"] + "#")
        assert x["source_document_version"] and x["source_document_status"] == "ACTIVE"
        assert x["requirement_code"]


async def test_generation_run_is_recorded(client, admin, backend_plan):
    run = (await client.get(f"/plans/{backend_plan['id']}/generation-run", headers=admin)).json()["latest"]
    assert run["prompt_template_version"] == "plan_generation_v1"
    assert run["provider"] == "offline" and run["model"]
    assert run["started_at"] and run["finished_at"] and run["duration_ms"] is not None
    assert run["attempt_count"] == 1 and run["status"] == "SUCCEEDED"
    assert {d["document_code"] for d in run["source_documents"]} >= {"POL-INFOSEC-001"}
    assert all("version" in d for d in run["source_documents"])
    assert "<untrusted_document_data>" in run["raw_request"]
    templates = (await client.get("/prompt-templates", headers=admin)).json()
    assert {(t["name"], t["version"]) for t in templates} >= {("plan_generation", "v1"), ("module_regeneration", "v1")}


async def test_suspicious_chunk_is_excluded_from_the_prompt(client, admin, backend_plan):
    assert any(c["chunk_code"].startswith("FAQ-ENG-002") for c in backend_plan["excluded_chunks"]) or \
        "ignore all previous instructions" not in \
        (await client.get(f"/plans/{backend_plan['id']}/generation-run", headers=admin)).json()["latest"]["raw_request"]
    raw = (await client.get(f"/plans/{backend_plan['id']}/generation-run", headers=admin)).json()["latest"]["raw_request"]
    assert "ignore all previous instructions" not in raw.lower()


async def test_unsupported_topic_becomes_a_recorded_gap(client, admin, employees_by_code):
    plan = (await client.post("/plans/generate", headers=admin, json={
        "employee_id": employees_by_code["EMP-006"]["id"],
        "extra_topics": ["company pet insurance for dogs"]})).json()
    gap = next(g for g in plan["gaps"] if "pet insurance" in g["topic"])
    assert "No active document covers this topic" in gap["reason"]
    text = str(plan["modules"]).lower()
    assert "pet insurance" not in text


async def test_malformed_output_is_retried_logged_and_capped(client, admin, employees_by_code):
    ok = await client.post("/plans/generate", headers=admin, json={
        "employee_id": employees_by_code["EMP-003"]["id"], "simulate_malformed": 2})
    assert ok.status_code == 200 and ok.json()["attempt_count"] == 3
    failed = await client.post("/plans/generate", headers=admin, json={
        "employee_id": employees_by_code["EMP-003"]["id"], "simulate_malformed": 3})
    assert failed.status_code == 502
    body = failed.json()
    assert body["error"] == "genai_retries_exhausted" and len(body["details"]["attempts"]) == 3
    assert body["details"]["generation_run_id"]


async def test_standard_plan_generates_and_validates_within_30_seconds(client, admin, employees_by_code):
    started = time.perf_counter()
    response = await client.post("/plans/generate", headers=admin,
                                 json={"employee_id": employees_by_code["EMP-007"]["id"]})
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    assert response.json()["validation"]["verification_status"]
    assert elapsed < 30, f"generate + validate took {elapsed:.1f}s"


async def test_validation_result_findings_and_metrics(client, admin, backend_plan):
    result = (await client.get(f"/validation/{backend_plan['id']}", headers=admin)).json()
    assert result["metrics"]["mandatory_requirement_coverage_score"] == 100.0
    assert result["metrics"]["source_traceability_score"] == 100.0
    assert result["verification_status"] in ("VERIFIED", "VERIFIED_WITH_WARNING")
    warnings = (await client.get(f"/validation/{backend_plan['id']}/findings", headers=admin,
                                 params={"severity": "WARNING"})).json()
    assert all(f["severity"] == "WARNING" for f in warnings)


async def test_disabling_a_rule_through_the_api_changes_the_next_run(client, admin, backend_plan):
    before = (await client.post(f"/validation/run/{backend_plan['id']}", headers=admin)).json()
    assert "contradictions" in before["enabled_rules"]
    assert before["rule_summaries"]["contradictions"]["findings"] >= 1
    toggled = await client.put("/validation/rules", headers=admin, json={"contradictions": {"enabled": False}})
    assert toggled.status_code == 200
    after = (await client.post(f"/validation/run/{backend_plan['id']}", headers=admin)).json()
    assert "contradictions" not in after["enabled_rules"]
    assert not [f for f in after["findings"] if f["rule"] == "contradictions"]
    await client.put("/validation/rules", headers=admin, json={"contradictions": {"enabled": True}})


async def test_missing_mandatory_requirement_is_incomplete_then_fixed_is_verified(client, admin, backend_plan):
    from src.core.db import SessionLocal
    from src.repositories.plan import PlanRepository
    from src.services.generation_service import GenerationService

    plan_id = uuid.UUID(backend_plan["id"])
    async with SessionLocal() as session:
        plan = await PlanRepository(session).full(plan_id)
        victim = next(m for m in plan.modules if m.competency == "Secrets Management")
        codes = set(victim.requirement_codes)
        await session.delete(victim)
        await session.commit()
    broken = (await client.post(f"/validation/run/{plan_id}", headers=admin)).json()
    assert broken["verification_status"] == "INCOMPLETE"
    assert broken["metrics"]["mandatory_requirement_coverage_score"] < 100
    assert broken["metrics"]["missing_requirement_count"] == len(codes)

    async with SessionLocal() as session:
        await GenerationService(session).regenerate_modules(plan_id, codes, [{"reason": "restore missing module"}])
    fixed = (await client.post(f"/validation/run/{plan_id}", headers=admin)).json()
    assert fixed["metrics"]["mandatory_requirement_coverage_score"] == 100.0
    assert fixed["verification_status"] == "VERIFIED", fixed["status_reasons"]
    assert fixed["is_verified"] is True
