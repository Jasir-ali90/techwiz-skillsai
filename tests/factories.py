"""Small, fully controlled fixtures for Pipeline 2 unit tests. Three mandatory
requirements, mirroring the SRS worked example."""
import copy
import uuid

import numpy as np

from src.core.app_config import load_yaml
from src.python_validation.base import ActiveChunk, ValidationContext

DOC = "11111111-1111-1111-1111-111111111111"
OLD_DOC = "00000000-0000-0000-0000-000000000000"
FAQ = "22222222-2222-2222-2222-222222222222"

CHUNKS = {
    "POL#C001": ("2.3", "Employees must complete the Information Security Basics module within three calendar days "
                        "of their joining date."),
    "POL#C002": ("2.1", "All employees must authenticate using a company-issued hardware security key."),
    "POL#C003": ("3.1", "Backend Developers must not commit secrets, API keys or connection strings to any repository."),
    "POL#C004": ("7.2", "All engineering staff must complete the Secure Coding assessment before the end of their "
                        "first thirty days."),
}
OLD_CHUNKS = {"POL#C001": ("2.3", "Employees must complete the Information Security Basics module within seven "
                                  "calendar days of their joining date.")}

MATRIX = [
    {"requirement_code": "R001", "statement": CHUNKS["POL#C001"][1], "requirement_type": "MUST_COMPLETE",
     "competency": "Security Awareness", "is_mandatory": True, "priority": "HIGH", "deadline_days": 3,
     "source_document_id": DOC, "source_document_code": "POL", "source_section_id": "2.3",
     "source_chunk_code": "POL#C001", "assessment_required": True, "assessment_topic": "Security Awareness",
     "prerequisites": [], "mapping_method": "APPLIES_TO_ALL", "is_compliance": False,
     "policy_requirement": "InfoSec §2.3", "process_requirement": None},
    {"requirement_code": "R002", "statement": CHUNKS["POL#C002"][1], "requirement_type": "MUST_COMPLETE",
     "competency": "Account Security", "is_mandatory": True, "priority": "CRITICAL", "deadline_days": None,
     "source_document_id": DOC, "source_document_code": "POL", "source_section_id": "2.1",
     "source_chunk_code": "POL#C002", "assessment_required": True, "assessment_topic": "Account Security",
     "prerequisites": [], "mapping_method": "APPLIES_TO_ALL", "is_compliance": False,
     "policy_requirement": "InfoSec §2.1", "process_requirement": None},
    {"requirement_code": "R003", "statement": CHUNKS["POL#C003"][1], "requirement_type": "MUST_KNOW",
     "competency": "Secrets Management", "is_mandatory": True, "priority": "HIGH", "deadline_days": None,
     "source_document_id": DOC, "source_document_code": "POL", "source_section_id": "3.1",
     "source_chunk_code": "POL#C003", "assessment_required": False, "assessment_topic": None,
     "prerequisites": [], "mapping_method": "EXPLICIT_ROLE_MENTION", "is_compliance": False,
     "policy_requirement": "InfoSec §3.1", "process_requirement": None},
]
STAGES = {"DAY_1": {"sequence": 1, "offset_days": 1, "name": "Day 1"},
          "WEEK_1": {"sequence": 2, "offset_days": 7, "name": "Week 1"},
          "WEEK_2": {"sequence": 3, "offset_days": 14, "name": "Week 2"},
          "DAY_30": {"sequence": 4, "offset_days": 30, "name": "Day 30"}}


def ref(code: str, chunk: str, stage: str = "DAY_1", doc: str = DOC) -> dict:
    req = next(r for r in MATRIX if r["requirement_code"] == code)
    return {"requirement_code": code, "source_document_id": doc, "source_section_id": CHUNKS[chunk][0],
            "source_chunk_code": chunk, "mandatory": req["is_mandatory"], "priority": req["priority"],
            "due_stage": stage}


def _id() -> str:
    return str(uuid.uuid4())


def module(competency: str, codes: list[str], lead: tuple[str, str], stage="DAY_1", **parts) -> dict:
    return {
        "id": _id(), "sequence": 1, "title": f"{competency} module", "category": competency,
        "competency": competency, "purpose": f"Learn the {competency.lower()} requirements.",
        "learning_objectives": [f"Apply the {competency.lower()} requirements."], "key_concepts": [competency], "required_source_documents": ["POL"],
        "estimated_duration_minutes": 30, "learning_activities": ["Review the module and take notes."],
        "assessment_summary": "One quiz question.", "completion_criteria": "All checklist items complete.",
        "requirement_codes": codes, "regeneration_count": 0, "completion_status": "NOT_STARTED",
        "completed_at": None, "is_outdated": False, "scenarios": [],
        "checklist": parts.get("checklist", []), "tasks": parts.get("tasks", []), "quiz": parts.get("quiz", []),
        "assessments": parts.get("assessments", []), **ref(*lead, stage=stage),
    }


def task(code, chunk, text, stage="DAY_1", difficulty="BASIC", doc=DOC) -> dict:
    return {"id": _id(), "description": text, "expected_outcome": "Done.", "completion_criteria": "Confirmed.",
            "difficulty": difficulty, "completion_status": "NOT_STARTED", "completed_at": None, "is_outdated": False,
            **ref(code, chunk, stage, doc)}


def quiz(code, chunk, question, options, correct, qtype="MULTIPLE_CHOICE", stage="DAY_1") -> dict:
    return {"id": _id(), "question_type": qtype, "question": question, "options": options,
            "correct_answer": correct, "explanation": f"See section {CHUNKS[chunk][0]}.", "difficulty": "BASIC",
            "is_outdated": False, **ref(code, chunk, stage)}


def assessment(code, chunk, stage="WEEK_1") -> dict:
    return {"id": _id(), "title": "Practical assessment", "assessment_type": "PRACTICAL", "topic": "Security",
            "passing_score": 80.0, "completion_status": "NOT_STARTED", "completed_at": None, "is_outdated": False,
            "rubric": [{"id": _id(), "criterion": "Performs it", "weight": 100.0, "expected_performance": "Right",
                        "pass_condition": "Once", "requirement_code": code}], **ref(code, chunk, stage)}


def good_plan() -> dict:
    m1 = module("Security Awareness", ["R001"], ("R001", "POL#C001"), tasks=[
        task("R001", "POL#C001", "Complete the Information Security Basics module within three calendar days of "
                                 "your joining date.")],
        quiz=[quiz("R001", "POL#C001", "Complete the requirement: \"Employees must complete the Information "
                   "Security Basics module within ...\"",
                   ["one calendar days", "three calendar days", "seven calendar days"], ["three calendar days"])],
        assessments=[assessment("R001", "POL#C001", stage="DAY_1")])
    m2 = module("Account Security", ["R002"], ("R002", "POL#C002"), tasks=[
        task("R002", "POL#C002", "Authenticate using a company-issued hardware security key.")],
        assessments=[assessment("R002", "POL#C002", stage="DAY_1")])
    m3 = module("Secrets Management", ["R003"], ("R003", "POL#C003"), stage="WEEK_1", quiz=[
        quiz("R003", "POL#C003", "True or false: Backend Developers must not commit secrets, API keys or "
             "connection strings to any repository.", ["True", "False"], ["True"], qtype="TRUE_FALSE",
             stage="WEEK_1")])
    return {"id": _id(), "title": "Test plan", "gaps": [], "modules": [m1, m2, m3],
            "raw_response": {"role_code": "BACKEND_DEV"}}


def items_of(plan: dict) -> list[dict]:
    from src.services.plan_views import flat_items

    return flat_items(plan)


def context(plan: dict, embed, matrix=None, prerequisites=None, contradictions=None, config=None,
            business_rules=None, extra_documents=None) -> ValidationContext:
    config = copy.deepcopy(config or load_yaml("validation_rules"))
    documents = {DOC: {"id": DOC, "document_code": "POL", "version": 2, "status": "ACTIVE",
                       "document_type": "INFOSEC_POLICY", "precedence_rank": 20},
                 OLD_DOC: {"id": OLD_DOC, "document_code": "POL", "version": 1, "status": "OBSOLETE",
                           "document_type": "INFOSEC_POLICY", "precedence_rank": 20}}
    documents.update(extra_documents or {})
    chunk_text = {(DOC, code): text for code, (_, text) in CHUNKS.items()}
    chunk_text.update({(OLD_DOC, code): text for code, (_, text) in OLD_CHUNKS.items()})
    active = [ActiveChunk(code, DOC, "POL", sec, text) for code, (sec, text) in CHUNKS.items()]
    matrix = matrix if matrix is not None else copy.deepcopy(MATRIX)
    requirements = {r["requirement_code"]: dict(r) for r in MATRIX}
    requirements["R099"] = {"requirement_code": "R099", "statement": "The QA Engineer must sign off the regression suite.",
                            "is_mandatory": True, "priority": "HIGH"}
    return ValidationContext(
        plan=plan, items=items_of(plan), role={"id": "role", "code": "BACKEND_DEV", "title": "Backend Developer"},
        known_role_codes={"BACKEND_DEV", "QA_ENG", "SEO_SPEC"}, matrix=matrix, requirements=requirements,
        requirement_roles={"R099": ["QA Engineer"], **{r["requirement_code"]: ["Backend Developer"] for r in MATRIX}},
        documents=documents,
        document_sections={DOC: {s for s, _ in CHUNKS.values()}, OLD_DOC: {"2.3"}},
        document_chunks={DOC: {c: s for c, (s, _) in CHUNKS.items()}, OLD_DOC: {c: s for c, (s, _) in OLD_CHUNKS.items()}},
        active_chunks=active, active_vectors=embed([c.content for c in active]), chunk_text=chunk_text,
        prerequisites=prerequisites or [], stages=STAGES,
        quiz_types={"MULTIPLE_CHOICE", "MULTIPLE_RESPONSE", "TRUE_FALSE", "SCENARIO"}, config=config,
        business_rules=business_rules if business_rules is not None else load_yaml("business_rules")["rules"],
        contradictions=contradictions or [], embed=embed,
    )


def findings(report: dict, rule: str | None = None, severity: str | None = None) -> list[dict]:
    return [f for f in report["findings"] if (rule is None or f["rule"] == rule)
            and (severity is None or f["severity"] == severity)]


np.set_printoptions(precision=3)
