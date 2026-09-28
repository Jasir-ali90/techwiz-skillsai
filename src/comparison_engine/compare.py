"""GenAI plan versus Python expected result, one row per Matrix requirement
(SRS Step 46, FR xlii).

Structured attributes and source references are compared, never sentence
wording: the two pipelines are not expected to produce the same prose.
"""
from src.python_validation.base import (
    ITEM_STATUSES,
    REQUIREMENT_MISSING,
    SEVERITY_RANK,
    VERIFIED,
)

STATUS_ORDER = {s: i for i, s in enumerate([
    "CONTRADICTION_DETECTED", "OUTDATED_SOURCE", "SOURCE_SUPPORT_MISSING", "REQUIREMENT_MISSING",
    "UNSUPPORTED_REQUIREMENT", "MANUAL_REVIEW_REQUIRED", "PARTIALLY_VERIFIED", "VERIFIED_WITH_WARNING",
    "VERIFIED",
])}
TASK_TYPES = {"MUST_COMPLETE", "MUST_DEMONSTRATE"}
CSV_COLUMNS = [
    "requirement_code", "role", "required_policy", "required_competency", "mandatory_or_optional",
    "learning_module_category", "source_document_id", "source_document_code", "source_section_id",
    "priority", "due_stage", "compliance_requirement", "required_task", "required_assessment_topic",
    "python_expected_result", "genai_result", "match", "coverage_status", "traceability_status",
    "validation_status", "explanation",
]


def expected_stage(requirement: dict, stages: dict[str, dict]) -> str | None:
    """The latest stage that still meets the requirement's onboarding deadline."""
    days = requirement.get("deadline_days")
    if not days:
        return None
    ordered = sorted(stages.items(), key=lambda kv: kv[1]["sequence"])
    eligible = [code for code, s in ordered if s["offset_days"] <= days]
    return eligible[-1] if eligible else ordered[0][0]


def worst_status(statuses: list[str]) -> str:
    known = [s for s in statuses if s in ITEM_STATUSES]
    return min(known, key=lambda s: STATUS_ORDER.get(s, 99)) if known else VERIFIED


def build_rows(role: dict, matrix: list[dict], items: list[dict], documents: dict[str, dict],
               stages: dict[str, dict], findings: list[dict]) -> list[dict]:
    by_code: dict[str, list[dict]] = {}
    for item in items:
        codes = {item.get("requirement_code")}
        if item["item_type"] == "module":
            codes |= set(item.get("requirement_codes") or [])
        for code in codes:
            if code:
                by_code.setdefault(code, []).append(item)
    findings_by_code: dict[str, list[dict]] = {}
    for f in findings:
        if f.get("requirement_code") and f.get("review_status") != "APPROVED":
            findings_by_code.setdefault(f["requirement_code"], []).append(f)
    seq = {code: s["sequence"] for code, s in stages.items()}

    rows = []
    for req in matrix:
        code = req["requirement_code"]
        related = by_code.get(code, [])
        direct = [i for i in related if i.get("requirement_code") == code and i["item_type"] != "module"]
        modules = [i for i in related if i["item_type"] == "module"]
        exp_stage = expected_stage(req, stages)
        expected = {
            "covered": True if req["is_mandatory"] else "optional",
            "mandatory": req["is_mandatory"],
            "priority": req["priority"],
            "source_document_code": req["source_document_code"],
            "source_document_id": req["source_document_id"],
            "source_section_id": req["source_section_id"],
            "due_by_stage": exp_stage,
            "task_required": req["requirement_type"] in TASK_TYPES,
            "assessment_required": req["assessment_required"],
            "acknowledgement_required": req["requirement_type"] == "MUST_ACKNOWLEDGE",
        }
        cited = next((i for i in direct if i.get("source_document_id")), direct[0] if direct else None)
        cited_doc = documents.get(str(cited.get("source_document_id"))) if cited else None
        stages_used = sorted({i.get("due_stage") for i in direct if i.get("due_stage")},
                             key=lambda c: seq.get(c, 99))
        assessments = [i for i in items if i["item_type"] == "assessment" and (
            i.get("requirement_code") == code or code in {r.get("requirement_code") for r in i.get("rubric", [])})]
        genai = {
            "covered": bool(related),
            "mandatory": cited.get("mandatory") if cited else None,
            "priority": cited.get("priority") if cited else None,
            "source_document_code": cited_doc["document_code"] if cited_doc else None,
            "source_document_id": str(cited.get("source_document_id")) if cited else None,
            "source_document_status": cited_doc["status"] if cited_doc else None,
            "source_section_id": cited.get("source_section_id") if cited else None,
            "due_stage": stages_used[0] if stages_used else None,
            "has_task": any(i["item_type"] == "task" for i in direct),
            "has_assessment": bool(assessments),
            "has_acknowledgement": any(i["item_type"] == "checklist_item" for i in direct),
            "item_count": len(direct),
        }

        differences = []
        if req["is_mandatory"] and not genai["covered"]:
            differences.append("mandatory requirement not covered by the plan")
        if genai["covered"]:
            if genai["mandatory"] is not None and genai["mandatory"] != expected["mandatory"]:
                differences.append(f"mandatory flag {genai['mandatory']} vs expected {expected['mandatory']}")
            if genai["priority"] and genai["priority"] != expected["priority"]:
                differences.append(f"priority {genai['priority']} vs expected {expected['priority']}")
            if genai["source_document_id"] and genai["source_document_id"] != expected["source_document_id"]:
                differences.append(
                    f"cites {genai['source_document_code'] or genai['source_document_id']} "
                    f"({genai['source_document_status'] or 'unknown'}) instead of "
                    f"{expected['source_document_code']}")
            if genai["source_section_id"] and genai["source_section_id"] != expected["source_section_id"]:
                differences.append(f"cites section {genai['source_section_id']} instead of {expected['source_section_id']}")
            if exp_stage and genai["due_stage"] and seq.get(genai["due_stage"], 0) > seq.get(exp_stage, 0):
                differences.append(f"due at {genai['due_stage']}, later than the deadline stage {exp_stage}")
            if expected["task_required"] and not genai["has_task"]:
                differences.append("no task although the requirement must be completed or demonstrated")
            if expected["assessment_required"] and req["is_mandatory"] and not genai["has_assessment"]:
                differences.append("no assessment although assessment is required")
            if expected["acknowledgement_required"] and not genai["has_acknowledgement"]:
                differences.append("no acknowledgement checklist item")

        req_findings = findings_by_code.get(code, [])
        trace_findings = [f for f in req_findings if f["rule"] == "traceability"]
        coverage_status = ("COVERED" if genai["covered"] else
                           ("MISSING" if req["is_mandatory"] else "NOT_INCLUDED_OPTIONAL"))
        traceability_status = ("NOT_APPLICABLE" if not genai["covered"] else
                               ("INVALID" if trace_findings else "VALID"))
        statuses = [f["item_status"] for f in req_findings if SEVERITY_RANK.get(f["severity"], 9) <= 2]
        if req["is_mandatory"] and not genai["covered"]:
            statuses.append(REQUIREMENT_MISSING)
        if differences and not statuses:
            statuses.append("PARTIALLY_VERIFIED")
        validation_status = worst_status(statuses)
        explanation = "; ".join(differences) if differences else (
            "Plan matches the expected attributes and sources" if genai["covered"]
            else "Optional requirement not included; no disagreement")
        if req_findings:
            explanation += ". Findings: " + " | ".join(f["message"] for f in req_findings[:3])

        rows.append({
            "requirement_code": code,
            "role": role["title"],
            "required_policy": req.get("policy_requirement") or req.get("process_requirement"),
            "required_competency": req["competency"],
            "mandatory_or_optional": "MANDATORY" if req["is_mandatory"] else "OPTIONAL",
            "learning_module_category": modules[0].get("category") if modules else None,
            "source_document_id": req["source_document_id"],
            "source_document_code": req["source_document_code"],
            "source_section_id": req["source_section_id"],
            "priority": req["priority"],
            "due_stage": genai["due_stage"] or exp_stage,
            "compliance_requirement": bool(req.get("is_compliance")),
            "required_task": expected["task_required"],
            "required_assessment_topic": req.get("assessment_topic"),
            "python_expected_result": expected,
            "genai_result": genai,
            "match": "MATCH" if not differences else "MISMATCH",
            "coverage_status": coverage_status,
            "traceability_status": traceability_status,
            "validation_status": validation_status,
            "explanation": explanation,
        })
    return rows


def summarise(rows: list[dict]) -> dict:
    total = len(rows)
    matches = sum(1 for r in rows if r["match"] == "MATCH")
    statuses: dict[str, int] = {}
    for r in rows:
        statuses[r["validation_status"]] = statuses.get(r["validation_status"], 0) + 1
    return {"rows": total, "matches": matches, "mismatches": total - matches,
            "agreement_percent": round(100 * matches / total, 2) if total else 100.0,
            "by_validation_status": statuses}


def csv_row(row: dict) -> dict:
    flat = {}
    for col in CSV_COLUMNS:
        value = row.get(col)
        if isinstance(value, dict):
            value = "; ".join(f"{k}={v}" for k, v in value.items())
        flat[col] = value
    return flat


def signature(plan_payload: dict) -> dict:
    """What consistency testing compares: requirements, sources, module
    categories and assessment topics, never wording."""
    reqs, sources, categories, topics, mandatory = set(), set(), set(), set(), set()
    for m in plan_payload.get("modules", []):
        categories.add(m.get("category"))
        for part in [m] + m.get("checklist", []) + m.get("tasks", []) + m.get("quiz", []) + m.get("scenarios", []) + \
                ([m["assessment"]] if m.get("assessment") else []):
            if part.get("requirement_code"):
                reqs.add(part["requirement_code"])
                sources.add(f"{part['requirement_code']}@{part.get('source_chunk_code')}")
                if part.get("mandatory"):
                    mandatory.add(part["requirement_code"])
        if m.get("assessment"):
            topics.add(m["assessment"].get("topic"))
    return {"requirements": sorted(reqs), "mandatory_requirements": sorted(mandatory), "sources": sorted(sources),
            "module_categories": sorted(c for c in categories if c), "assessment_topics": sorted(t for t in topics if t)}


def jaccard(a: list, b: list) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


def consistency(signatures: list[dict], weights: dict | None = None) -> tuple[float, dict, list[dict]]:
    weights = weights or {"mandatory_requirements": 0.4, "sources": 0.3, "module_categories": 0.15,
                          "assessment_topics": 0.15}
    if len(signatures) < 2:
        return 100.0, {}, []
    per_dimension = {}
    for dim in weights:
        scores = [jaccard(signatures[i][dim], signatures[j][dim])
                  for i in range(len(signatures)) for j in range(i + 1, len(signatures))]
        per_dimension[dim] = round(100 * sum(scores) / len(scores), 2)
    score = round(sum(per_dimension[d] * w for d, w in weights.items()) / sum(weights.values()), 2)
    major = []
    union = set().union(*[set(s["mandatory_requirements"]) for s in signatures])
    for code in sorted(union):
        present = [i + 1 for i, s in enumerate(signatures) if code in s["mandatory_requirements"]]
        if len(present) != len(signatures):
            major.append({"type": "MANDATORY_REQUIREMENT_UNSTABLE", "requirement_code": code, "present_in_runs": present})
    for dim in ("module_categories", "assessment_topics"):
        union = set().union(*[set(s[dim]) for s in signatures])
        for value in sorted(union):
            present = [i + 1 for i, s in enumerate(signatures) if value in s[dim]]
            if len(present) != len(signatures):
                major.append({"type": f"{dim.upper()}_UNSTABLE", "value": value, "present_in_runs": present})
    return score, per_dimension, major
