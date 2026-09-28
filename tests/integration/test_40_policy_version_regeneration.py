"""Policy version upload, obsolete handling, impact analysis and selective
regeneration (SRS Steps 57-59)."""
from pathlib import Path

import pytest

pytestmark = pytest.mark.db
V2 = Path("sample_documents/POL-INFOSEC-001_v2.pdf")


@pytest.fixture(scope="module")
async def v2_upload(client, admin, backend_plan):
    plan = (await client.get(f"/plans/{backend_plan['id']}", headers=admin)).json()
    preserved = next(m for m in plan["modules"] if m["competency"] == "Release Management")
    await client.post(f"/progress/items/module/{preserved['id']}", headers=admin, json={"status": "COMPLETED"})
    response = await client.post("/documents", headers=admin, data={
        "document_code": "POL-INFOSEC-001", "title": "Information Security Policy", "document_type": "INFOSEC_POLICY",
        "version": "2", "effective_date": "2026-07-01"}, files={"file": (V2.name, V2.read_bytes(), "application/pdf")})
    assert response.status_code == 201, response.text
    doc = response.json()
    parsed = await client.post(f"/documents/{doc['document']['id']}/parse", headers=admin)
    assert parsed.status_code == 200
    return {"doc": doc, "preserved_module": preserved, "plan_id": backend_plan["id"]}


async def test_v2_upload_marks_v1_obsolete(client, admin, v2_upload):
    assert v2_upload["doc"]["superseded_document_id"]
    old = (await client.get(f"/documents/{v2_upload['doc']['superseded_document_id']}", headers=admin)).json()
    assert old["status"] == "OBSOLETE"


async def test_obsolete_chunks_hidden_from_search_unless_asked(client, admin, v2_upload):
    q = {"q": "complete the Information Security Basics module within seven calendar days", "limit": 10}
    live = (await client.get("/search", headers=admin, params=q)).json()
    assert all(r["document"]["status"] == "ACTIVE" for r in live["results"])
    everything = (await client.get("/search", headers=admin, params={**q, "active_only": False})).json()
    assert any(r["document"]["status"] == "OBSOLETE" for r in everything["results"])


async def test_plan_citing_the_obsolete_version_fails_traceability(client, admin, v2_upload):
    result = (await client.post(f"/validation/run/{v2_upload['plan_id']}", headers=admin)).json()
    assert result["metrics"]["source_traceability_score"] < 100
    assert result["verification_status"] in ("UNSUPPORTED", "CONTRADICTORY")
    outdated = [f for f in result["findings"] if f["item_status"] == "OUTDATED_SOURCE"]
    assert outdated


async def test_diff_names_the_three_changed_clauses(client, admin, v2_upload):
    doc_id = v2_upload["doc"]["document"]["id"]
    impact = (await client.post(f"/impact/analyse/{doc_id}", headers=admin)).json()
    modified = {m["section_id"]: m for m in impact["diff"]["modified"]}
    assert "seven" in modified["2.3"]["summary"] and "three" in modified["2.3"]["summary"]
    assert "hardware security key" in modified["2.1"]["new_text"]
    assert "read-only" in modified["3.3"]["new_text"]
    assert impact["previous_version_status"] == "OBSOLETE"
    assert impact["affected_plan_ids"] and impact["affected_employee_ids"]
    affected = (await client.get(f"/impact/{doc_id}/affected", headers=admin)).json()
    assert {"module", "quiz_question"} <= set(affected["items"])
    assert any(r["section"] == "2.3" for r in affected["requirements"])


async def test_quiz_citing_a_changed_section_is_outdated(client, admin, v2_upload):
    out = (await client.get(f"/plans/{v2_upload['plan_id']}/outdated", headers=admin)).json()
    assert any(i["item_type"] == "quiz_question" and i["status"] == "SECTION_CHANGED" for i in out["items"])


async def test_dry_run_changes_nothing(client, admin, v2_upload):
    doc_id = v2_upload["doc"]["document"]["id"]
    before = (await client.get(f"/plans/{v2_upload['plan_id']}", headers=admin)).json()
    dry = (await client.post(f"/impact/{doc_id}/regenerate", headers=admin, params={"dry_run": True})).json()
    assert dry["dry_run"] is True and dry["would_change"]["re_extract_sections"]
    plan_action = next(p for p in dry["would_change"]["plans"] if p["plan_id"] == v2_upload["plan_id"])
    assert plan_action["modules_to_regenerate"] and plan_action["modules_preserved"]
    after = (await client.get(f"/plans/{v2_upload['plan_id']}", headers=admin)).json()
    assert [m["id"] for m in before["modules"]] == [m["id"] for m in after["modules"]]


async def test_selective_regeneration_preserves_untouched_modules(client, admin, v2_upload):
    doc_id = v2_upload["doc"]["document"]["id"]
    before = (await client.get(f"/plans/{v2_upload['plan_id']}", headers=admin)).json()
    result = (await client.post(f"/impact/{doc_id}/regenerate", headers=admin, params={"dry_run": False})).json()
    assert result["dry_run"] is False and result["references_repointed"] > 0
    ours = next(p for p in result["plans"] if p["plan_id"] == v2_upload["plan_id"])
    assert ours["modules_replaced"] and len(ours["modules_replaced"]) < len(before["modules"])
    after = (await client.get(f"/plans/{v2_upload['plan_id']}", headers=admin)).json()
    kept = next(m for m in after["modules"] if m["id"] == v2_upload["preserved_module"]["id"])
    assert kept["completion_status"] == "COMPLETED"
    rewritten = [m for m in after["modules"] if m["regeneration_count"] > 0]
    assert rewritten
    security = next(m for m in rewritten if any("three calendar days" in (t["description"] or "")
                                                for t in m["tasks"]) or m["competency"] == "Security Awareness")
    assert security
    result = (await client.get(f"/validation/{v2_upload['plan_id']}", headers=admin)).json()
    assert result["metrics"]["source_traceability_score"] == 100.0
    assert result["verification_status"] in ("VERIFIED", "VERIFIED_WITH_WARNING", "MANUAL_REVIEW_REQUIRED")
