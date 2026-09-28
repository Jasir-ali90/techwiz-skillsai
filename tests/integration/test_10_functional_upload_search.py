"""Functional flow, document upload, semantic search and the Matrix, through
the HTTP API against a real database."""
import io
from pathlib import Path

import pytest
from reportlab.pdfgen import canvas

pytestmark = pytest.mark.db
SAMPLES = Path("sample_documents")


def pdf_bytes(lines: list[str]) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    y = 800
    for line in lines:
        c.drawString(40, y, line)
        y -= 18
    c.save()
    return buffer.getvalue()


async def test_health_and_login(client, admin):
    health = (await client.get("/health")).json()
    assert health == {"status": "ok", "database": "connected", "pgvector": True}
    me = await client.get("/auth/me", headers=admin)
    assert me.json()["user_type"] == "ADMIN"


async def test_documents_are_loaded_parsed_and_embedded(client, admin):
    docs = (await client.get("/documents", headers=admin)).json()
    assert {d["document_code"] for d in docs} >= {"POL-INFOSEC-001", "SOP-DEPLOY-007", "FAQ-ENG-002"}
    embedded = await client.post("/search/embed-all", headers=admin, params={"force": True})
    assert embedded.status_code == 200 and embedded.json()["chunks_embedded"] > 50
    coverage = (await client.get("/search/coverage", headers=admin)).json()
    assert coverage["total_chunks"] > 50 and coverage["pending"] == 0 and coverage["embedded"] == coverage["total_chunks"]


async def test_upload_rejects_invalid_duplicate_and_stale_version(client, admin):
    form = {"document_code": "POL-TEST-900", "title": "Test", "document_type": "HR_POLICY",
            "version": "1", "effective_date": "2026-01-01"}
    fake = await client.post("/documents", headers=admin, data=form,
                             files={"file": ("fake.pdf", b"MZ this is an executable" * 10, "application/pdf")})
    assert fake.status_code == 422
    assert any(c["check"] == "file_type" and not c["passed"] for c in fake.json()["details"]["checks"])

    existing = (SAMPLES / "SOP-DEPLOY-007_v1.pdf").read_bytes()
    duplicate = await client.post("/documents", headers=admin, data=form,
                                  files={"file": ("dup.pdf", existing, "application/pdf")})
    assert duplicate.status_code == 422
    assert any(c["check"] == "duplicate_document" and not c["passed"] for c in duplicate.json()["details"]["checks"])

    stale = await client.post("/documents", headers=admin,
                              data={**form, "document_code": "SOP-DEPLOY-007", "version": "1"},
                              files={"file": ("new.pdf", pdf_bytes(["1. Scope", "1.1 Test clause."]), "application/pdf")})
    assert stale.status_code == 422
    assert any(c["check"] == "version" and not c["passed"] for c in stale.json()["details"]["checks"])

    bad_dates = await client.post("/documents", headers=admin, data={**form, "expiry_date": "2025-01-01"},
                                  files={"file": ("d.pdf", pdf_bytes(["x" * 50]), "application/pdf")})
    assert bad_dates.status_code == 422


async def test_semantic_search_finds_policy_and_contradicting_faq(client, admin):
    r = (await client.get("/search", headers=admin,
                          params={"q": "How long do I have to complete the security training?", "limit": 5})).json()
    assert r["grounded"]
    docs = {(x["document"]["document_code"], x["document"]["precedence_rank"]) for x in r["results"]}
    assert ("POL-INFOSEC-001", 20) in docs and ("FAQ-ENG-002", 60) in docs


async def test_topic_absent_from_every_document_returns_nothing(client, admin):
    r = (await client.get("/search", headers=admin, params={"q": "company pet insurance for veterinary bills",
                                                            "min_similarity": 0.45})).json()
    assert r["count"] == 0 and r["grounded"] is False


async def test_matrix_summary_and_role_matrices_differ(client, admin):
    summary = (await client.get("/matrix/summary", headers=admin)).json()
    assert summary["requirements"] > 40 and summary["mandatory"] > 30 and summary["role_specific"] > 0
    roles = {r["code"]: r["id"] for r in (await client.get("/roles", headers=admin)).json()}
    backend = (await client.get(f"/matrix/role/{roles['BACKEND_DEV']}", headers=admin)).json()
    seo = (await client.get(f"/matrix/role/{roles['SEO_SPEC']}", headers=admin)).json()
    b_codes = {r["requirement_code"] for r in backend["requirements"]}
    s_codes = {r["requirement_code"] for r in seo["requirements"]}
    assert b_codes != s_codes and b_codes - s_codes
    secrets = next(r for r in backend["requirements"] if "commit secrets" in r["statement"])
    assert secrets["mapping_method"] == "EXPLICIT_ROLE_MENTION"
    assert secrets["requirement_code"] not in s_codes


async def test_requirement_detail_and_manual_override_is_audited(client, admin):
    reqs = (await client.get("/requirements", headers=admin, params={"requirement_type": "RECOMMENDED"})).json()
    code = reqs[0]["requirement_code"]
    detail = (await client.get(f"/requirements/{code}", headers=admin)).json()
    assert detail["source_chunk"]["content"] and detail["mapped_roles"]
    patched = await client.patch(f"/requirements/{code}", headers=admin,
                                 json={"priority": "MEDIUM", "reason": "Reviewed with the policy owner"})
    assert patched.status_code == 200 and patched.json()["changed_fields"] == ["priority"]
    history = (await client.get(f"/audit/requirement/{code}", headers=admin)).json()["history"]
    assert history[-1]["action"] == "manual_override" and history[-1]["reason"] == "Reviewed with the policy owner"


async def test_runtime_config_edit_for_quiz_types(client, admin):
    current = (await client.get("/config/quiz_types", headers=admin)).json()
    types = current["value"]["types"] + [{"code": "ORDERING", "description": "Put steps in order",
                                          "min_options": 3, "max_correct": 4}]
    updated = await client.put("/config/quiz_types", headers=admin, json={**current["value"], "types": types})
    assert updated.status_code == 200 and updated.json()["source"] == "database"
    assert "ORDERING" in [t["code"] for t in (await client.get("/config/quiz_types", headers=admin)).json()["value"]["types"]]
    await client.delete("/config/quiz_types", headers=admin)
    assert (await client.get("/config/quiz_types", headers=admin)).json()["source"] == "yaml"


async def test_all_employees_clause_maps_to_all_ten_roles(client, admin):
    reqs = (await client.get("/requirements", headers=admin)).json()
    mfa = next(r for r in reqs if r["statement"].startswith("All employees must enable multi-factor"))
    roles = (await client.get(f"/requirements/{mfa['requirement_code']}", headers=admin)).json()["mapped_roles"]
    assert len(roles) == 10 and {r["method"] for r in roles} == {"APPLIES_TO_ALL"}


async def test_onboarding_duration_is_a_data_edit(client, admin):
    stages = {s["code"]: s for s in (await client.get("/stages", headers=admin)).json()}
    week2 = stages["WEEK_2"]
    changed = await client.patch(f"/stages/{week2['id']}", headers=admin, json={"offset_days": 21})
    assert changed.status_code == 200 and changed.json()["offset_days"] == 21
    restored = await client.patch(f"/stages/{week2['id']}", headers=admin, json={"offset_days": week2["offset_days"]})
    assert restored.json()["offset_days"] == week2["offset_days"]


async def test_policy_precedence_is_a_runtime_edit(client, admin):
    docs = {d["document_code"]: d for d in (await client.get("/documents", headers=admin)).json()}
    pair = [docs["FAQ-ENG-002"]["id"], docs["POL-INFOSEC-001"]["id"]]
    before = (await client.post("/config/precedence/resolve", headers=admin, json=pair)).json()
    assert before["winner"]["document_code"] == "POL-INFOSEC-001"
    config = (await client.get("/config/precedence", headers=admin)).json()["value"]
    flipped = {**config, "rules": [
        {"rank": 5, "document_types": ["FAQ"], "reason": "evaluator test"},
        *[{**r, "document_types": [t for t in r["document_types"] if t != "FAQ"]} for r in config["rules"]
          if [t for t in r["document_types"] if t != "FAQ"]],
    ]}
    assert (await client.put("/config/precedence", headers=admin, json=flipped)).status_code == 200
    await client.post("/config/precedence/reapply", headers=admin)
    after = (await client.post("/config/precedence/resolve", headers=admin, json=pair)).json()
    assert after["winner"]["document_code"] == "FAQ-ENG-002"
    await client.delete("/config/precedence", headers=admin)
    await client.post("/config/precedence/reapply", headers=admin)
    reset = (await client.post("/config/precedence/resolve", headers=admin, json=pair)).json()
    assert reset["winner"]["document_code"] == "POL-INFOSEC-001"
