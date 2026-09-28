"""Progress tracking and the three dashboards (SRS Steps 50-56, 60)."""
import uuid
from collections import Counter
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.comparison_engine.compare import jaccard, signature
from src.core.app_config import get_config
from src.core.exceptions import NotFoundError, PermissionDeniedError, ValidationFailedError
from src.models.enums import TrainingStatus, UserType
from src.models.organization import User
from src.models.progress import AssessmentResult, QuizAttempt
from src.progress import engine
from src.repositories.document import DocumentRepository
from src.repositories.organization import DepartmentRepository, EmployeeRepository, StageRepository
from src.repositories.plan import PlanRepository
from src.repositories.progress import ProgressRepository
from src.repositories.requirement import RoleRepository
from src.repositories.validation import ValidationRepository
from src.services.audit_service import AuditService
from src.services.matrix_service import MatrixService
from src.services.plan_views import plan_dict

COMPLETION_STATES = {"NOT_STARTED", "IN_PROGRESS", "COMPLETED"}
STAFF = {UserType.ADMIN, UserType.TRAINING_MANAGER, UserType.MANAGER, UserType.REVIEWER}


def _attempt(a: QuizAttempt) -> dict:
    return {"question_id": str(a.question_id) if a.question_id else None, "is_correct": a.is_correct,
            "competency": a.competency, "requirement_code": a.requirement_code,
            "attempted_at": a.attempted_at.isoformat() if a.attempted_at else None}


def _result(r: AssessmentResult) -> dict:
    return {"assessment_id": str(r.assessment_id) if r.assessment_id else None, "score": r.score,
            "passed": r.passed, "competency": r.competency,
            "assessed_at": r.assessed_at.isoformat() if r.assessed_at else None}


class ProgressService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.employees = EmployeeRepository(session)
        self.plans = PlanRepository(session)
        self.repo = ProgressRepository(session)
        self.audit = AuditService(session)

    async def _stages(self) -> dict:
        return {s.code: {"sequence": s.sequence, "offset_days": s.offset_days, "name": s.name}
                for s in await StageRepository(self.session).list() if s.is_active}

    async def check_access(self, user: User, employee_id: uuid.UUID) -> None:
        if user.user_type in STAFF:
            return
        employee = await self.employees.get(employee_id)
        if employee is None or employee.user_id != user.id:
            raise PermissionDeniedError("Employees can only see their own progress")

    async def employee_for_user(self, user: User) -> uuid.UUID:
        employee = await self.employees.get_by(user_id=user.id)
        if employee is None:
            raise NotFoundError("No employee record is linked to this login")
        return employee.id

    # ------------------------------------------------------------ progress
    async def progress(self, employee_id: uuid.UUID, today: date | None = None, sync: bool = True) -> dict:
        employee = await self.employees.get(employee_id)
        if employee is None:
            raise NotFoundError("Employee not found")
        plan = await self.plans.current_for_employee(employee_id)
        full = plan_dict(await self.plans.full(plan.id)) if plan else None
        attempts = [_attempt(a) for a in await self.repo.attempts(employee_id, plan.id if plan else None)]
        results = [_result(r) for r in await self.repo.results(employee_id, plan.id if plan else None)]
        config = await get_config(self.session, "progress")
        report = engine.assess(full, attempts, results, await self._stages(), employee.joining_date,
                               today or date.today(), config)
        if sync and report["status"] in TrainingStatus.__members__ and \
                employee.training_status.value != report["status"]:
            employee.training_status = TrainingStatus(report["status"])
            await self.session.commit()
        return {"employee_id": str(employee.id), "employee_code": employee.employee_code,
                "full_name": employee.full_name, "joining_date": str(employee.joining_date),
                "plan_id": str(plan.id) if plan else None,
                "plan_verification_status": plan.verification_status if plan else None, **report}

    async def set_completion(self, item_type: str, item_id: uuid.UUID, status: str, user: User) -> dict:
        if status not in COMPLETION_STATES:
            raise ValidationFailedError(f"status must be one of {', '.join(sorted(COMPLETION_STATES))}")
        if item_type not in ("module", "checklist_item", "task"):
            raise ValidationFailedError("Only modules, checklist items and tasks are completed this way")
        item = await self.plans.item(item_type, item_id)
        if item is None:
            raise NotFoundError(f"{item_type} not found")
        plan = await self.plans.get(item.plan_id)
        await self.check_access(user, plan.employee_id)
        before = item.completion_status
        item.completion_status = status
        item.completed_at = datetime.now(timezone.utc) if status == "COMPLETED" else None
        self.audit.record(item_type, item_id, "completion_changed", actor_id=user.id,
                          before={"completion_status": before}, after={"completion_status": status})
        await self.session.commit()
        return {"item_type": item_type, "item_id": str(item_id), "completion_status": status,
                "progress": await self.progress(plan.employee_id)}

    async def attempt_quiz(self, question_id: uuid.UUID, answer: list[str], user: User) -> dict:
        question = await self.plans.item("quiz_question", question_id)
        if question is None:
            raise NotFoundError("Quiz question not found")
        plan = await self.plans.get(question.plan_id)
        await self.check_access(user, plan.employee_id)
        module = (await self.plans.modules_by_ids([question.module_id]))[0]
        correct = sorted(a.strip().lower() for a in question.correct_answer or [])
        given = sorted(a.strip().lower() for a in answer)
        attempt = QuizAttempt(employee_id=plan.employee_id, plan_id=plan.id, question_id=question.id,
                              requirement_code=question.requirement_code,
                              competency=module.competency or module.category,
                              answer=answer, is_correct=correct == given)
        self.session.add(attempt)
        await self.session.commit()
        return {"question_id": str(question_id), "is_correct": attempt.is_correct,
                "explanation": question.explanation if attempt.is_correct else
                "Incorrect. Review the cited section and try again.",
                "competency": attempt.competency}

    async def record_assessment(self, assessment_id: uuid.UUID, score: float, notes: str | None,
                                criteria_scores: dict | None, user: User) -> dict:
        if user.user_type not in STAFF:
            raise PermissionDeniedError("Only staff record assessment results")
        assessment = await self.plans.item("assessment", assessment_id)
        if assessment is None:
            raise NotFoundError("Assessment not found")
        plan = await self.plans.get(assessment.plan_id)
        module = (await self.plans.modules_by_ids([assessment.module_id]))[0]
        passed = score >= assessment.passing_score
        result = AssessmentResult(employee_id=plan.employee_id, plan_id=plan.id, assessment_id=assessment.id,
                                  competency=module.competency or module.category, score=score, passed=passed,
                                  assessor_id=user.id, notes=notes, criteria_scores=criteria_scores or {})
        assessment.completion_status = "COMPLETED" if passed else "IN_PROGRESS"
        self.session.add(result)
        self.audit.record("assessment", assessment_id, "result_recorded", actor_id=user.id,
                          after={"score": score, "passed": passed})
        await self.session.commit()
        return {"assessment_id": str(assessment_id), "score": score, "passing_score": assessment.passing_score,
                "passed": passed}

    # ------------------------------------------------------------ dashboards
    async def employee_dashboard(self, employee_id: uuid.UUID) -> dict:
        employee = await self.employees.get(employee_id)
        if employee is None:
            raise NotFoundError("Employee not found")
        progress = await self.progress(employee_id)
        role = await RoleRepository(self.session).get(employee.job_role_id)
        department = await DepartmentRepository(self.session).get(employee.department_id)
        plan = await self.plans.current_for_employee(employee_id)
        modules, tasks, quiz_scores = [], [], []
        if plan:
            full = plan_dict(await self.plans.full(plan.id))
            attempts = await self.repo.attempts(employee_id, plan.id)
            by_q: dict = {}
            for a in attempts:
                by_q.setdefault(str(a.question_id), []).append(a.is_correct)
            for m in full["modules"]:
                modules.append({"id": m["id"], "title": m["title"], "competency": m["competency"],
                                "due_stage": m["due_stage"], "completion_status": m["completion_status"],
                                "estimated_duration_minutes": m["estimated_duration_minutes"],
                                "is_outdated": m["is_outdated"],
                                "source_documents": m["required_source_documents"]})
                tasks += [{"id": t["id"], "module": m["title"], "description": t["description"],
                           "due_stage": t["due_stage"], "completion_status": t["completion_status"]}
                          for t in m["tasks"]]
                for q in m["quiz"]:
                    tries = by_q.get(q["id"], [])
                    quiz_scores.append({"question_id": q["id"], "module": m["title"], "attempts": len(tries),
                                        "correct": sum(tries), "last_correct": tries[-1] if tries else None})
        return {
            "employee": {"id": str(employee.id), "code": employee.employee_code, "name": employee.full_name,
                         "role": role.title if role else None, "department": department.name if department else None,
                         "experience_level": employee.experience_level.value,
                         "joining_date": str(employee.joining_date),
                         "training_status": progress["status"]},
            "onboarding_progress": {k: progress.get(k) for k in (
                "status", "overall_progress", "expected_progress", "days_since_joining", "quiz_score",
                "assessment_score", "by_type")},
            "assigned_modules": modules,
            "completed_modules": [m for m in modules if m["completion_status"] == "COMPLETED"],
            "tasks": tasks,
            "quiz_scores": quiz_scores,
            "upcoming_activities": progress.get("upcoming_activities", []),
            "milestones": progress.get("milestones", []),
            "weak_areas": progress.get("weak_areas", []),
            "recommendations": progress.get("recommendations", []),
            "plan": {"id": progress.get("plan_id"), "verification_status": progress.get("plan_verification_status")},
        }

    async def admin_dashboard(self) -> dict:
        employees = await self.employees.list()
        roles = await RoleRepository(self.session).active_with_departments()
        plans = await self.plans.filtered(current_only=True)
        results = await ValidationRepository(self.session).latest_for_plans([p.id for p in plans])
        progress = [await self.progress(e.id) for e in employees]
        assessments = await self.repo.results_for_plans([p.id for p in plans])
        matrix = MatrixService(self.session)
        compliance = []
        for role, dept in roles:
            role_matrix = await matrix.role_matrix(role.id)
            role_plans = [p for p in plans if p.job_role_id == role.id]
            coverages = [results[p.id].mandatory_requirement_coverage_score for p in role_plans if p.id in results]
            compliance.append({
                "role_code": role.code, "role_title": role.title, "department": dept.name,
                "mandatory_requirements": role_matrix["mandatory"],
                "compliance_requirements": sum(1 for r in role_matrix["requirements"] if r["is_compliance"]),
                "plans": len(role_plans),
                "average_mandatory_coverage": round(sum(coverages) / len(coverages), 2) if coverages else None,
                "verified_plans": sum(1 for p in role_plans if p.verification_status in ("VERIFIED", "VERIFIED_WITH_WARNING")),
            })
        from src.repositories.validation import ValidationRepository as VR

        queue = await VR(self.session).queue([p.id for p in plans], ["CRITICAL", "ERROR", "WARNING"], "OPEN")
        return {
            "employees": {"total": len(employees),
                          "by_status": dict(Counter(p["status"] for p in progress))},
            "roles": {"total": len(roles)},
            "training_plans": {"current": len(plans),
                               "by_verification_status": dict(Counter(p.verification_status for p in plans))},
            "completion": {
                "average_overall_progress": round(sum(p.get("overall_progress", 0) for p in progress) / len(progress), 2)
                if progress else None,
                "completed_employees": sum(1 for p in progress if p["status"] == "COMPLETED"),
            },
            "assessment_scores": {
                "results": len(assessments),
                "average": round(sum(a.score for a in assessments) / len(assessments), 2) if assessments else None,
                "pass_rate": round(100 * sum(a.passed for a in assessments) / len(assessments), 2) if assessments else None,
            },
            "compliance_coverage": compliance,
            "flagged_content": {
                "suspicious_chunks": await self.repo.suspicious_chunk_count(),
                "open_findings_by_severity": dict(Counter(f.severity for f in queue)),
            },
            "manual_reviews": {"open": len(queue),
                               "by_rule": dict(Counter(f.rule_name for f in queue))},
            "employees_behind_schedule": [
                {"employee_id": p["employee_id"], "employee_code": p["employee_code"], "name": p["full_name"],
                 "progress": p.get("overall_progress"),
                 "expected": p.get("expected_progress"), "days": p["days_since_joining"]}
                for p in progress if p["status"] in ("BEHIND_SCHEDULE", "REQUIRES_ATTENTION")
            ],
        }

    async def role_dashboard(self, job_role_id: uuid.UUID | None = None) -> list[dict] | dict:
        roles = await RoleRepository(self.session).active_with_departments(job_role_id)
        if job_role_id and not roles:
            raise NotFoundError("Role not found")
        employees = await self.employees.list()
        plans = await self.plans.filtered(current_only=True)
        results = await ValidationRepository(self.session).latest_for_plans([p.id for p in plans])
        out = []
        for role, dept in roles:
            matrix = await MatrixService(self.session).role_matrix(role.id)
            role_emps = [e for e in employees if e.job_role_id == role.id]
            progress = [await self.progress(e.id, sync=False) for e in role_emps]
            role_plans = [p for p in plans if p.job_role_id == role.id]
            out.append({
                "role_code": role.code, "role_title": role.title, "department": dept.name,
                "requirements": {
                    "total": matrix["total"], "mandatory": matrix["mandatory"],
                    "by_type": dict(Counter(r["requirement_type"] for r in matrix["requirements"])),
                    "by_priority": dict(Counter(r["priority"] for r in matrix["requirements"])),
                    "by_mapping_method": dict(Counter(r["mapping_method"] for r in matrix["requirements"])),
                    "competencies": sorted({r["competency"] for r in matrix["requirements"]}),
                },
                "employees": len(role_emps),
                "completion": {
                    "average_progress": round(sum(p.get("overall_progress", 0) for p in progress) / len(progress), 2)
                    if progress else None,
                    "by_status": dict(Counter(p["status"] for p in progress)),
                },
                "plans": {"current": len(role_plans),
                          "by_verification_status": dict(Counter(p.verification_status for p in role_plans)),
                          "average_coverage": round(sum(results[p.id].mandatory_requirement_coverage_score
                                                        for p in role_plans if p.id in results) /
                                                    max(1, sum(1 for p in role_plans if p.id in results)), 2)
                          if role_plans else None},
            })
        return out[0] if job_role_id else out

    # ------------------------------------------------------------ plan comparison
    async def compare_plans(self, dimension: str | None, plan_ids: list[uuid.UUID] | None) -> dict:
        """SRS Step 60: compare plans across roles, departments, employee levels
        and document versions."""
        plans = await self.plans.filtered(current_only=plan_ids is None)
        if plan_ids:
            plans = [p for p in plans if p.id in set(plan_ids)]
        employees = {e.id: e for e in await self.employees.list()}
        roles = {r.id: r for r in await RoleRepository(self.session).list()}
        depts = {d.id: d for d in await DepartmentRepository(self.session).list()}
        results = await ValidationRepository(self.session).latest_for_plans([p.id for p in plans])

        def key(p) -> str:
            e = employees.get(p.employee_id)
            if dimension == "department":
                return depts[e.department_id].name if e else "unknown"
            if dimension == "experience_level":
                return e.experience_level.value if e else "unknown"
            if dimension == "document_version":
                return ", ".join(sorted(f"{d['document_code']} v{d['version']}" for d in p.source_document_versions))
            if dimension in (None, "role"):
                return roles[p.job_role_id].title
            if dimension == "plan":
                return f"{p.title} ({str(p.id)[:8]})"
            raise ValidationFailedError("dimension must be role, department, experience_level, document_version or plan")

        groups: dict[str, list] = {}
        for p in plans:
            groups.setdefault(key(p), []).append(p)
        summary, sigs = [], {}
        for name, members in sorted(groups.items()):
            member_sigs = [signature(p.raw_response or {}) for p in members]
            reqs = set().union(*[set(s["requirements"]) for s in member_sigs]) if member_sigs else set()
            cats = set().union(*[set(s["module_categories"]) for s in member_sigs]) if member_sigs else set()
            sigs[name] = {"requirements": reqs, "module_categories": cats}
            coverage = [results[p.id].mandatory_requirement_coverage_score for p in members if p.id in results]
            summary.append({
                "group": name, "plans": len(members),
                "average_modules": round(sum(len((p.raw_response or {}).get("modules", [])) for p in members) / len(members), 2),
                "requirements_covered": len(reqs), "module_categories": sorted(cats),
                "average_coverage": round(sum(coverage) / len(coverage), 2) if coverage else None,
                "verification_statuses": dict(Counter(p.verification_status for p in members)),
                "document_versions": sorted({f"{d['document_code']} v{d['version']}"
                                             for p in members for d in p.source_document_versions}),
            })
        names = sorted(sigs)
        pairs = []
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                pairs.append({
                    "a": a, "b": b,
                    "requirement_overlap": round(jaccard(list(sigs[a]["requirements"]), list(sigs[b]["requirements"])), 3),
                    "only_in_a": sorted(sigs[a]["requirements"] - sigs[b]["requirements"])[:50],
                    "only_in_b": sorted(sigs[b]["requirements"] - sigs[a]["requirements"])[:50],
                    "categories_only_in_a": sorted(sigs[a]["module_categories"] - sigs[b]["module_categories"]),
                    "categories_only_in_b": sorted(sigs[b]["module_categories"] - sigs[a]["module_categories"]),
                })
        return {"dimension": dimension or "role", "groups": summary, "pairwise": pairs}
