"""The eight SRS Step 62 reports, and paginated global search (Step 61)."""
import uuid
from collections import Counter

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.repositories.document import DocumentRepository
from src.repositories.organization import DepartmentRepository, EmployeeRepository
from src.repositories.plan import PlanRepository
from src.repositories.progress import ProgressRepository
from src.repositories.requirement import RequirementRepository, RoleRepository, RoleRequirementRepository
from src.repositories.validation import ValidationRepository
from src.services.matrix_service import MatrixService
from src.services.plan_views import flat_items, plan_dict
from src.services.progress_service import ProgressService
from src.services.review_service import ReviewService

REPORTS = {
    "employee-progress": "Employee progress",
    "role-coverage": "Role coverage",
    "mandatory-training": "Mandatory training",
    "assessment-results": "Assessment results",
    "source-traceability": "Source traceability",
    "hallucination-flags": "Hallucination flags",
    "policy-coverage": "Policy coverage",
    "comparison": "GenAI versus Python comparison",
}
PDF_COLUMNS = {
    "comparison": ["role", "requirement_code", "mandatory_or_optional", "priority", "source_document_code",
                   "source_section_id", "due_stage", "match", "validation_status", "explanation"],
    "mandatory-training": ["employee_code", "role", "requirement_code", "competency", "due_stage",
                           "in_plan", "completed", "statement"],
}


class ReportService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.plans = PlanRepository(session)
        self.employees = EmployeeRepository(session)
        self.results = ValidationRepository(session)

    async def build(self, name: str) -> tuple[list[dict], dict]:
        builder = {
            "employee-progress": self.employee_progress,
            "role-coverage": self.role_coverage,
            "mandatory-training": self.mandatory_training,
            "assessment-results": self.assessment_results,
            "source-traceability": self.source_traceability,
            "hallucination-flags": self.hallucination_flags,
            "policy-coverage": self.policy_coverage,
            "comparison": self.comparison,
        }.get(name)
        if builder is None:
            raise NotFoundError(f"Unknown report '{name}'", details={"reports": sorted(REPORTS)})
        return await builder()

    async def _context(self):
        roles = {r.id: r for r in await RoleRepository(self.session).list()}
        depts = {d.id: d for d in await DepartmentRepository(self.session).list()}
        plans = await self.plans.filtered(current_only=True)
        return roles, depts, plans, await self.results.latest_for_plans([p.id for p in plans])

    async def employee_progress(self):
        roles, depts, _, _ = await self._context()
        progress = ProgressService(self.session)
        rows = []
        for e in await self.employees.list():
            p = await progress.progress(e.id, sync=False)
            rows.append({"employee_code": e.employee_code, "name": e.full_name, "role": roles[e.job_role_id].title,
                         "department": depts[e.department_id].name, "joining_date": str(e.joining_date),
                         "days_since_joining": p["days_since_joining"], "status": p["status"],
                         "overall_progress": p.get("overall_progress"), "expected_progress": p.get("expected_progress"),
                         "quiz_score": p.get("quiz_score"), "assessment_score": p.get("assessment_score"),
                         "weak_areas": ", ".join(w["competency"] for w in p.get("weak_areas", [])),
                         "plan_verification": p.get("plan_verification_status")})
        return rows, {"employees": len(rows), "by_status": dict(Counter(r["status"] for r in rows))}

    async def role_coverage(self):
        roles, depts, plans, results = await self._context()
        matrix = MatrixService(self.session)
        rows = []
        for role in roles.values():
            m = await matrix.role_matrix(role.id)
            role_plans = [p for p in plans if p.job_role_id == role.id]
            cov = [results[p.id].mandatory_requirement_coverage_score for p in role_plans if p.id in results]
            rows.append({"role_code": role.code, "role": role.title, "department": depts[role.department_id].name,
                         "requirements": m["total"], "mandatory": m["mandatory"],
                         "role_specific": sum(1 for r in m["requirements"] if r["mapping_method"] != "APPLIES_TO_ALL"),
                         "plans": len(role_plans), "average_mandatory_coverage": round(sum(cov) / len(cov), 2) if cov else None,
                         "verified_plans": sum(1 for p in role_plans if p.verification_status in ("VERIFIED", "VERIFIED_WITH_WARNING"))})
        return rows, {"roles": len(rows)}

    async def mandatory_training(self):
        roles, _, plans, _ = await self._context()
        employees = {e.id: e for e in await self.employees.list()}
        matrix = MatrixService(self.session)
        rows = []
        for plan in plans:
            e = employees.get(plan.employee_id)
            items = flat_items(plan_dict(await self.plans.full(plan.id)))
            by_code: dict[str, list] = {}
            for i in items:
                if i["item_type"] in ("task", "checklist_item", "quiz_question", "assessment"):
                    by_code.setdefault(i.get("requirement_code"), []).append(i)
            for r in (await matrix.role_matrix(plan.job_role_id))["requirements"]:
                if not r["is_mandatory"]:
                    continue
                related = by_code.get(r["requirement_code"], [])
                trackable = [i for i in related if i["item_type"] in ("task", "checklist_item")]
                rows.append({"employee_code": e.employee_code if e else None, "employee": e.full_name if e else None,
                             "role": roles[plan.job_role_id].title, "requirement_code": r["requirement_code"],
                             "competency": r["competency"], "priority": r["priority"],
                             "due_stage": min((i.get("due_stage") for i in related if i.get("due_stage")), default=None),
                             "in_plan": bool(related),
                             "completed": bool(trackable) and all(i.get("completion_status") == "COMPLETED" for i in trackable),
                             "statement": r["statement"]})
        done = sum(1 for r in rows if r["completed"])
        return rows, {"rows": len(rows), "completed": done, "in_plan": sum(1 for r in rows if r["in_plan"])}

    async def assessment_results(self):
        roles, _, plans, _ = await self._context()
        employees = {e.id: e for e in await self.employees.list()}
        results = await ProgressRepository(self.session).results_for_plans([p.id for p in plans])
        rows = [{"employee_code": employees[r.employee_id].employee_code, "employee": employees[r.employee_id].full_name,
                 "competency": r.competency, "score": r.score, "passed": r.passed,
                 "assessed_at": r.assessed_at.isoformat() if r.assessed_at else None, "notes": r.notes}
                for r in results if r.employee_id in employees]
        return rows, {"results": len(rows), "pass_rate": round(100 * sum(r["passed"] for r in rows) / len(rows), 2)
                      if rows else None}

    async def source_traceability(self):
        roles, _, plans, results = await self._context()
        rows = []
        for p in plans:
            r = results.get(p.id)
            if not r:
                continue
            trace = (r.rule_summaries or {}).get("traceability", {})
            rows.append({"plan_id": str(p.id), "plan": p.title, "role": roles[p.job_role_id].title,
                         "items": trace.get("items"), "valid_references": trace.get("valid"),
                         "traceability_score": r.source_traceability_score,
                         "mandatory_traceability_score": (r.extra_metrics or {}).get("mandatory_traceability_score"),
                         "mandatory_target_met": trace.get("mandatory_target_met"),
                         "verification_status": r.verification_status})
        return rows, {"plans": len(rows)}

    async def hallucination_flags(self):
        roles, _, plans, results = await self._context()
        titles = {p.id: p.title for p in plans}
        rows = []
        for pid, r in results.items():
            for f in await self.results.findings(r.id, rule="hallucination"):
                rows.append({"plan": titles.get(pid), "severity": f.severity, "item_type": f.item_type,
                             "item_id": f.item_id, "requirement_code": f.requirement_code,
                             "category": f.evidence.get("category"), "claim": f.evidence.get("claim"),
                             "best_similarity": f.evidence.get("best_similarity"),
                             "closest_chunk": f.evidence.get("closest_chunk"), "review_status": f.review_status})
        for pid, r in results.items():
            summary = (r.rule_summaries or {}).get("hallucination", {})
            rows.append({"plan": titles.get(pid), "severity": "SUMMARY", "item_type": None, "item_id": None,
                         "requirement_code": None, "category": "counts", "claim": _counts(summary),
                         "best_similarity": None, "closest_chunk": None, "review_status": None})
        return rows, {"flags": sum(1 for r in rows if r["severity"] != "SUMMARY")}

    async def policy_coverage(self):
        docs = await DocumentRepository(self.session).list_all()
        reqs = await RequirementRepository(self.session).list()
        roles_by_req: dict = {}
        for m, role in await RoleRequirementRepository(self.session).roles_for_requirements([r.id for r in reqs]):
            roles_by_req.setdefault(m.requirement_id, set()).add(role.title)
        cited = Counter()
        for p in await self.plans.filtered(current_only=True):
            for i in flat_items(plan_dict(await self.plans.full(p.id))):
                cited[i.get("source_document_id")] += 1
        rows = []
        for d in docs:
            doc_reqs = [r for r in reqs if r.source_document_id == d.id and r.is_active]
            rows.append({"document_code": d.document_code, "title": d.title, "version": d.version,
                         "status": d.status.value, "type": d.document_type.value, "precedence_rank": d.precedence_rank,
                         "requirements": len(doc_reqs), "mandatory": sum(r.is_mandatory for r in doc_reqs),
                         "roles_covered": len(set().union(*[roles_by_req.get(r.id, set()) for r in doc_reqs]))
                         if doc_reqs else 0,
                         "plan_items_citing": cited.get(str(d.id), 0),
                         "chunks": (d.parse_meta or {}).get("chunks_created"),
                         "suspicious_chunks": (d.parse_meta or {}).get("suspicious_chunks")})
        return rows, {"documents": len(rows), "active": sum(1 for r in rows if r["status"] == "ACTIVE")}

    async def comparison(self):
        rows = await ReviewService(self.session).comparison_rows()
        matches = sum(1 for r in rows if r["match"] == "MATCH")
        return rows, {"rows": len(rows), "matches": matches, "mismatches": len(rows) - matches,
                      "meets_100_row_minimum": len(rows) >= 100}

    # ------------------------------------------------------------ search
    async def search(self, employee: str | None, role: str | None, department: str | None, module: str | None,
                     policy: str | None, status: str | None, verification: str | None,
                     progress_min: float | None, progress_max: float | None, page: int, page_size: int) -> dict:
        roles, depts, plans, results = await self._context()
        plan_by_emp = {p.employee_id: p for p in plans}
        docs = {str(d.id): d for d in await DocumentRepository(self.session).list_all()}
        progress = ProgressService(self.session)
        records = []
        for e in await self.employees.list():
            role_obj, dept_obj = roles.get(e.job_role_id), depts.get(e.department_id)
            if employee and employee.lower() not in f"{e.employee_code} {e.full_name}".lower():
                continue
            if role and role.lower() not in f"{role_obj.code} {role_obj.title}".lower():
                continue
            if department and department.lower() not in f"{dept_obj.code} {dept_obj.name}".lower():
                continue
            plan = plan_by_emp.get(e.id)
            if verification and (plan is None or (plan.verification_status or "").upper() != verification.upper()):
                continue
            modules, cited_docs = [], set()
            if plan and (module or policy):
                full = plan_dict(await self.plans.full(plan.id))
                modules = [m["title"] for m in full["modules"]
                           if not module or module.lower() in f"{m['title']} {m['competency']}".lower()]
                cited_docs = {docs[i["source_document_id"]].document_code for i in flat_items(full)
                              if i.get("source_document_id") in docs}
                if module and not modules:
                    continue
                if policy and not any(policy.lower() in c.lower() for c in cited_docs):
                    continue
            p = await progress.progress(e.id, sync=False)
            if status and p["status"] != status.upper():
                continue
            overall = p.get("overall_progress", 0.0)
            if progress_min is not None and overall < progress_min:
                continue
            if progress_max is not None and overall > progress_max:
                continue
            records.append({"employee_id": str(e.id), "employee_code": e.employee_code, "name": e.full_name,
                            "role": role_obj.title, "department": dept_obj.name,
                            "plan_id": str(plan.id) if plan else None,
                            "verification_status": plan.verification_status if plan else None,
                            "training_status": p["status"], "overall_progress": overall,
                            "matched_modules": modules or None,
                            "cites_policies": sorted(cited_docs) or None})
        total = len(records)
        start = (page - 1) * page_size
        return {"total": total, "page": page, "page_size": page_size,
                "pages": (total + page_size - 1) // page_size, "results": records[start:start + page_size]}


def _counts(summary: dict) -> str:
    keys = ("claims_checked", "source_supported", "instructional", "plan_mechanics", "unsupported_rule_claim", "weak_general")
    return ", ".join(f"{k}={summary.get(k)}" for k in keys if k in summary)
