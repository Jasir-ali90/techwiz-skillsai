"""Serialisers for plans and their items, shared by API responses, validation
input and reports."""
from src.models.plan import OnboardingPlan, PlanModule

REF_FIELDS = ("requirement_code", "source_document_id", "source_section_id",
              "source_chunk_code", "mandatory", "priority", "due_stage")


def ref(obj) -> dict:
    return {k: getattr(obj, k) for k in REF_FIELDS}


def completion(obj) -> dict:
    return {
        "completion_status": getattr(obj, "completion_status", None),
        "completed_at": obj.completed_at.isoformat() if getattr(obj, "completed_at", None) else None,
        "is_outdated": getattr(obj, "is_outdated", False),
    }


def module_dict(m: PlanModule) -> dict:
    return {
        "id": str(m.id),
        "sequence": m.sequence,
        "title": m.title,
        "category": m.category,
        "competency": m.competency,
        "purpose": m.purpose,
        "learning_objectives": m.learning_objectives,
        "key_concepts": m.key_concepts,
        "required_source_documents": m.required_source_documents,
        "estimated_duration_minutes": m.estimated_duration_minutes,
        "learning_activities": m.learning_activities,
        "assessment_summary": m.assessment_summary,
        "completion_criteria": m.completion_criteria,
        "requirement_codes": m.requirement_codes,
        "regeneration_count": m.regeneration_count,
        **ref(m),
        **completion(m),
        "scenarios": m.scenarios,
        "checklist": [
            {"id": str(c.id), "activity": c.activity, "is_required": c.is_required,
             "responsible_person": c.responsible_person, **ref(c), **completion(c)}
            for c in m.checklist
        ],
        "tasks": [
            {"id": str(t.id), "description": t.description, "expected_outcome": t.expected_outcome,
             "completion_criteria": t.completion_criteria, "difficulty": t.difficulty, **ref(t), **completion(t)}
            for t in m.tasks
        ],
        "quiz": [
            {"id": str(q.id), "question_type": q.question_type, "question": q.question, "options": q.options,
             "correct_answer": q.correct_answer, "explanation": q.explanation, "difficulty": q.difficulty,
             "is_outdated": q.is_outdated, **ref(q)}
            for q in m.quiz
        ],
        "assessments": [
            {"id": str(a.id), "title": a.title, "assessment_type": a.assessment_type, "topic": a.topic,
             "passing_score": a.passing_score, **ref(a), **completion(a),
             "rubric": [
                 {"id": str(r.id), "criterion": r.criterion, "weight": r.weight,
                  "expected_performance": r.expected_performance, "pass_condition": r.pass_condition,
                  "requirement_code": r.requirement_code}
                 for r in a.rubric
             ]}
            for a in m.assessments
        ],
    }


def plan_header(p: OnboardingPlan) -> dict:
    return {
        "id": str(p.id),
        "employee_id": str(p.employee_id),
        "job_role_id": str(p.job_role_id),
        "title": p.title,
        "summary": p.summary,
        "status": p.status,
        "verification_status": p.verification_status,
        "is_current": p.is_current,
        "prompt_version": p.prompt_version,
        "provider": p.provider,
        "model": p.model,
        "generated_at": p.generated_at.isoformat() if p.generated_at else None,
        "source_document_versions": p.source_document_versions,
        "gaps": p.gaps,
        "excluded_chunks": p.excluded_chunks,
    }


def plan_dict(p: OnboardingPlan) -> dict:
    modules = [module_dict(m) for m in sorted(p.modules, key=lambda m: m.sequence)]
    counts = {
        "modules": len(modules),
        "checklist_items": sum(len(m["checklist"]) for m in modules),
        "tasks": sum(len(m["tasks"]) for m in modules),
        "quiz_questions": sum(len(m["quiz"]) for m in modules),
        "assessments": sum(len(m["assessments"]) for m in modules),
        "scenarios": sum(len(m["scenarios"]) for m in modules),
    }
    return {**plan_header(p), "counts": counts, "modules": modules}


def flat_items(plan: dict) -> list[dict]:
    """Every generated item of a serialised plan, tagged with its type."""
    items: list[dict] = []
    for m in plan["modules"]:
        module = {k: v for k, v in m.items() if k not in ("checklist", "tasks", "quiz", "assessments", "scenarios")}
        items.append({"item_type": "module", "module_id": m["id"], **module})
        for c in m["checklist"]:
            items.append({"item_type": "checklist_item", "module_id": m["id"], **c})
        for t in m["tasks"]:
            items.append({"item_type": "task", "module_id": m["id"], **t})
        for q in m["quiz"]:
            items.append({"item_type": "quiz_question", "module_id": m["id"], **q})
        for a in m["assessments"]:
            items.append({"item_type": "assessment", "module_id": m["id"], **a})
        for i, s in enumerate(m["scenarios"]):
            items.append({"item_type": "scenario", "module_id": m["id"], "id": f"{m['id']}:scenario:{i}", **s})
    return items


def with_document_codes(plan: dict, documents: dict[str, tuple[str, int, str]]) -> dict:
    """Adds source_document_code, version and status beside every cited
    source_document_id, so each item names its document the way people do."""
    def tag(item: dict) -> None:
        doc = documents.get(str(item.get("source_document_id")))
        item["source_document_code"] = doc[0] if doc else None
        item["source_document_version"] = doc[1] if doc else None
        item["source_document_status"] = doc[2] if doc else None

    for m in plan["modules"]:
        tag(m)
        for kind in ("checklist", "tasks", "quiz", "assessments", "scenarios"):
            m[kind] = [dict(item) for item in m[kind]]  # never mutate ORM-owned JSON
            for item in m[kind]:
                tag(item)
    return plan
