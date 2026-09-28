"""Rules 1-3: schema, coverage, traceability."""
import re
import uuid

from src.python_validation.base import (
    MANUAL_REVIEW_REQUIRED,
    OUTDATED_SOURCE,
    REQUIREMENT_MISSING,
    SOURCE_SUPPORT_MISSING,
    UNSUPPORTED_REQUIREMENT,
    Finding,
    Rule,
    RuleOutput,
    ValidationContext,
    register,
)

PRIORITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
REQUIRED_FIELDS = {
    "module": ["title", "purpose", "learning_objectives", "completion_criteria", "estimated_duration_minutes"],
    "checklist_item": ["activity", "is_required"],
    "task": ["description", "expected_outcome", "completion_criteria", "difficulty"],
    "quiz_question": ["question_type", "question", "options", "correct_answer", "explanation"],
    "assessment": ["title", "assessment_type", "passing_score"],
    "scenario": ["title", "situation", "expected_action"],
}
TYPES = {
    "title": str, "purpose": str, "learning_objectives": list, "completion_criteria": str,
    "estimated_duration_minutes": int, "activity": str, "is_required": bool, "description": str,
    "expected_outcome": str, "difficulty": str, "question_type": str, "question": str,
    "options": list, "correct_answer": list, "explanation": str, "assessment_type": str,
    "passing_score": (int, float), "situation": str, "expected_action": str,
}
SECTION_RE = re.compile(r"^\d{1,2}(\.\d{1,2}){0,3}$")


def _is_uuid(value) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False


@register
class SchemaRule(Rule):
    name = "schema"
    description = "Missing fields, wrong types, invalid ids, unknown role, duplicates, missing mandatory status"

    def run(self, ctx: ValidationContext, settings: dict) -> RuleOutput:
        out = RuleOutput()
        add = out.findings.append
        raw = ctx.plan.get("raw_response") or {}
        role_code = raw.get("role_code")
        if role_code and role_code not in ctx.known_role_codes:
            add(Finding(self.name, "ERROR", f"Unknown role '{role_code}' in the plan envelope",
                        MANUAL_REVIEW_REQUIRED, "plan", ctx.plan["id"], evidence={"field": "role_code",
                                                                                  "value": role_code}))
        elif role_code and role_code != ctx.role["code"]:
            add(Finding(self.name, "ERROR", f"Plan was written for role '{role_code}' but the employee's "
                        f"role is '{ctx.role['code']}'", MANUAL_REVIEW_REQUIRED, "plan", ctx.plan["id"],
                        evidence={"field": "role_code", "value": role_code, "expected": ctx.role["code"]}))

        seen_ids: dict[str, str] = {}
        for item in ctx.items:
            kind, iid = item["item_type"], str(item.get("id"))
            if iid in seen_ids:
                add(Finding(self.name, "ERROR", f"Duplicate id {iid}", MANUAL_REVIEW_REQUIRED, kind, iid,
                            evidence={"field": "id", "value": iid}))
            seen_ids[iid] = kind
            for fname in REQUIRED_FIELDS.get(kind, []):
                value = item.get(fname)
                if value is None or (isinstance(value, (str, list)) and len(value) == 0):
                    add(Finding(self.name, "ERROR", f"{kind} is missing '{fname}'", MANUAL_REVIEW_REQUIRED,
                                kind, iid, item.get("requirement_code"), {"field": fname, "value": value}))
                elif fname in TYPES and not isinstance(value, TYPES[fname]):
                    add(Finding(self.name, "ERROR", f"{kind}.{fname} has type {type(value).__name__}",
                                MANUAL_REVIEW_REQUIRED, kind, iid, item.get("requirement_code"),
                                {"field": fname, "value": str(value)[:100]}))
            if item.get("mandatory") is None:
                add(Finding(self.name, "ERROR", f"{kind} has no mandatory status", MANUAL_REVIEW_REQUIRED,
                            kind, iid, item.get("requirement_code"), {"field": "mandatory", "value": None}))
            if item.get("priority") not in PRIORITIES:
                add(Finding(self.name, "ERROR", f"{kind} priority '{item.get('priority')}' is not valid",
                            MANUAL_REVIEW_REQUIRED, kind, iid, item.get("requirement_code"),
                            {"field": "priority", "value": item.get("priority")}))
            if item.get("due_stage") not in ctx.stages:
                add(Finding(self.name, "ERROR", f"{kind} due_stage '{item.get('due_stage')}' is not a configured stage",
                            MANUAL_REVIEW_REQUIRED, kind, iid, item.get("requirement_code"),
                            {"field": "due_stage", "value": item.get("due_stage")}))
            if not item.get("requirement_code"):
                add(Finding(self.name, "ERROR", f"{kind} has no requirement_code", MANUAL_REVIEW_REQUIRED,
                            kind, iid, evidence={"field": "requirement_code", "value": None}))
            elif item["requirement_code"] not in ctx.requirements:
                add(Finding(self.name, "ERROR", f"{kind} cites requirement '{item['requirement_code']}', "
                            "which does not exist", UNSUPPORTED_REQUIREMENT, kind, iid, item["requirement_code"],
                            {"field": "requirement_code", "value": item["requirement_code"]}))
            doc_id = item.get("source_document_id")
            if not _is_uuid(doc_id):
                add(Finding(self.name, "ERROR", f"{kind} source_document_id '{doc_id}' is not a valid id",
                            SOURCE_SUPPORT_MISSING, kind, iid, item.get("requirement_code"),
                            {"field": "source_document_id", "value": doc_id}))
            elif str(doc_id) not in ctx.documents:
                add(Finding(self.name, "ERROR", f"{kind} cites document {doc_id}, which does not exist",
                            SOURCE_SUPPORT_MISSING, kind, iid, item.get("requirement_code"),
                            {"field": "source_document_id", "value": doc_id}))
            section = item.get("source_section_id")
            if section is not None and not SECTION_RE.match(str(section)):
                add(Finding(self.name, "ERROR", f"{kind} source_section_id '{section}' is malformed",
                            SOURCE_SUPPORT_MISSING, kind, iid, item.get("requirement_code"),
                            {"field": "source_section_id", "value": section}))
            if kind == "quiz_question":
                qtype = item.get("question_type")
                if qtype not in ctx.quiz_types:
                    add(Finding(self.name, "ERROR", f"Quiz type '{qtype}' is not configured",
                                MANUAL_REVIEW_REQUIRED, kind, iid, item.get("requirement_code"),
                                {"field": "question_type", "value": qtype, "allowed": sorted(ctx.quiz_types)}))
                options = item.get("options") or []
                for answer in item.get("correct_answer") or []:
                    if answer not in options:
                        add(Finding(self.name, "ERROR", f"Correct answer '{answer}' is not one of the options",
                                    MANUAL_REVIEW_REQUIRED, kind, iid, item.get("requirement_code"),
                                    {"field": "correct_answer", "value": answer, "options": options}))
        out.summary = {"items_checked": len(ctx.items), "failures": len(out.findings)}
        return out


def covered_codes(ctx: ValidationContext) -> dict[str, list[dict]]:
    covered: dict[str, list[dict]] = {}
    for item in ctx.items:
        codes = {item.get("requirement_code")}
        if item["item_type"] == "module":
            codes |= set(item.get("requirement_codes") or [])
        for code in codes:
            if code:
                covered.setdefault(code, []).append(item)
    return covered


@register
class CoverageRule(Rule):
    name = "coverage"
    description = "Mandatory Matrix requirements covered by the plan (SRS Step 29)"

    def run(self, ctx: ValidationContext, settings: dict) -> RuleOutput:
        out = RuleOutput()
        covered = covered_codes(ctx)
        matrix = ctx.matrix_by_code
        mandatory = [r for r in ctx.matrix if r["is_mandatory"]]
        gaps = {g.get("requirement_code") for g in ctx.plan.get("gaps", []) if g.get("requirement_code")}
        hit = [r for r in mandatory if r["requirement_code"] in covered]
        missing = [r for r in mandatory if r["requirement_code"] not in covered]
        for r in missing:
            note = " The generator recorded it as a gap (no supporting source)." if r["requirement_code"] in gaps else ""
            out.findings.append(Finding(
                self.name, "ERROR", f"Mandatory requirement {r['requirement_code']} is not covered.{note}",
                REQUIREMENT_MISSING, "requirement", r["requirement_code"], r["requirement_code"],
                {"statement": r["statement"], "priority": r["priority"], "source": r["source_document_code"],
                 "section": r["source_section_id"]},
            ))
        unsupported = sorted(code for code in covered if code not in matrix)
        for code in unsupported:
            out.findings.append(Finding(
                self.name, "ERROR", f"The plan covers {code}, which is not in this role's Matrix",
                UNSUPPORTED_REQUIREMENT, covered[code][0]["item_type"], str(covered[code][0].get("id")), code,
                {"items": len(covered[code]), "exists": code in ctx.requirements},
            ))
        total = len(mandatory)
        score = round(100 * len(hit) / total, 2) if total else 100.0
        out.summary = {
            "mandatory_total": total, "covered": len(hit), "missing": len(missing),
            "coverage_percent": score, "status": "COMPLETE" if not missing else "INCOMPLETE",
            "missing_requirements": [{"code": r["requirement_code"], "statement": r["statement"]} for r in missing],
            "unsupported_requirements": unsupported,
            "optional_covered": sum(1 for r in ctx.matrix if not r["is_mandatory"] and r["requirement_code"] in covered),
        }
        out.metrics = {"mandatory_coverage_score": score, "missing_requirement_count": len(missing),
                       "unsupported_requirement_codes": len(unsupported)}
        return out


@register
class TraceabilityRule(Rule):
    name = "traceability"
    description = "Every citation resolves to a live document, section and chunk (SRS Step 30)"

    def run(self, ctx: ValidationContext, settings: dict) -> RuleOutput:
        out = RuleOutput()
        valid = total = m_valid = m_total = 0
        for item in ctx.items:
            kind, iid, code = item["item_type"], str(item.get("id")), item.get("requirement_code")
            total += 1
            is_mandatory = bool(item.get("mandatory"))
            m_total += is_mandatory
            problems = []
            status = SOURCE_SUPPORT_MISSING
            doc = ctx.documents.get(str(item.get("source_document_id")))
            if doc is None:
                problems.append("cited document does not exist")
            else:
                if doc["status"] != "ACTIVE":
                    problems.append(f"{doc['document_code']} v{doc['version']} is {doc['status']}")
                    status = OUTDATED_SOURCE
                section = item.get("source_section_id")
                if section and section not in ctx.document_sections.get(doc["id"], set()):
                    problems.append(f"section {section} does not exist in {doc['document_code']} v{doc['version']}")
                    status = SOURCE_SUPPORT_MISSING
                chunks = ctx.document_chunks.get(doc["id"], {})
                chunk_code = item.get("source_chunk_code")
                if chunk_code not in chunks:
                    problems.append(f"chunk {chunk_code} does not resolve in {doc['document_code']} v{doc['version']}")
                    status = SOURCE_SUPPORT_MISSING
                elif section and chunks[chunk_code] and chunks[chunk_code] != section:
                    problems.append(f"chunk {chunk_code} is in section {chunks[chunk_code]}, not {section}")
            if problems:
                out.findings.append(Finding(
                    self.name, "ERROR" if is_mandatory else "WARNING",
                    f"{kind} citation is not valid and current: {'; '.join(problems)}", status, kind, iid, code,
                    {"source_document_id": item.get("source_document_id"),
                     "source_section_id": item.get("source_section_id"),
                     "source_chunk_code": item.get("source_chunk_code"), "problems": problems},
                ))
            else:
                valid += 1
                m_valid += is_mandatory
        score = round(100 * valid / total, 2) if total else 100.0
        m_score = round(100 * m_valid / m_total, 2) if m_total else 100.0
        out.summary = {"items": total, "valid": valid, "traceability_percent": score,
                       "mandatory_items": m_total, "mandatory_valid": m_valid,
                       "mandatory_traceability_percent": m_score,
                       "mandatory_target_met": m_score == 100.0}
        out.metrics = {"source_traceability_score": score, "mandatory_traceability_score": m_score}
        return out
