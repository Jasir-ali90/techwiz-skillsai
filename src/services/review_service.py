"""Comparison, consistency testing and the human review workflow (SRS Steps 44-49)."""
import csv
import enum
import io
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import Uuid as _Uuid
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import UUID as _PgUUID
from sqlalchemy.ext.asyncio import AsyncSession

from src.comparison_engine.compare import (
    CSV_COLUMNS,
    build_rows,
    consistency,
    csv_row,
    signature,
    summarise,
)
from src.core.app_config import get_config
from src.core.db import SessionLocal
from src.core.exceptions import NotFoundError, ValidationFailedError
from src.models.plan import OnboardingPlan
from src.models.review import ComparisonReport, ConsistencyRun, ReviewDecision
from src.repositories.organization import StageRepository
from src.repositories.plan import PlanRepository
from src.repositories.requirement import RoleRepository
from src.repositories.validation import ValidationRepository
from src.services.audit_service import AuditService, jsonable
from src.services.matrix_service import MatrixService
from src.services.plan_views import flat_items, plan_dict
from src.services.validation_service import ValidationService

logger = logging.getLogger("skillsprint.review")

DECISIONS = {"APPROVE": "APPROVED", "REJECT": "REJECTED", "EDIT": "EDITED",
             "REGENERATE": "REGENERATED", "COMMENT": None}
UUID_TYPES = (_Uuid, _PgUUID)

EDITABLE = {
    "module": {"title", "purpose", "learning_objectives", "key_concepts", "learning_activities",
               "completion_criteria", "due_stage", "priority", "mandatory", "source_document_id",
               "source_section_id", "source_chunk_code", "requirement_code", "requirement_codes"},
    "checklist_item": {"activity", "is_required", "responsible_person", "due_stage", "priority", "mandatory",
                       "source_document_id", "source_section_id", "source_chunk_code", "requirement_code"},
    "task": {"description", "expected_outcome", "completion_criteria", "difficulty", "due_stage", "priority",
             "mandatory", "source_document_id", "source_section_id", "source_chunk_code", "requirement_code"},
    "quiz_question": {"question", "options", "correct_answer", "explanation", "difficulty", "due_stage",
                      "source_document_id", "source_section_id", "source_chunk_code", "requirement_code"},
    "assessment": {"title", "topic", "passing_score", "due_stage", "source_document_id", "source_section_id",
                   "source_chunk_code", "requirement_code"},
}


class ReviewService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.plans = PlanRepository(session)
        self.results = ValidationRepository(session)
        self.audit = AuditService(session)

    # ------------------------------------------------------------ comparison
    async def compare(self, plan_id: uuid.UUID) -> dict:
        plan = await self.plans.full(plan_id)
        if plan is None:
            raise NotFoundError("Plan not found")
        result = await self.results.latest(plan_id)
        if result is None:
            await ValidationService(self.session).run(plan_id)
            plan = await self.plans.full(plan_id)
            result = await self.results.latest(plan_id)
        role = await RoleRepository(self.session).get(plan.job_role_id)
        matrix = (await MatrixService(self.session).role_matrix(plan.job_role_id))["requirements"]
        items = flat_items(plan_dict(plan))
        vs = ValidationService(self.session)
        ctx, _ = await vs.build_context(plan_id)
        findings = [vs.finding_dict(f) for f in await self.results.findings(result.id)]
        rows = build_rows({"id": str(role.id), "title": role.title, "code": role.code}, matrix, items,
                          ctx.documents, ctx.stages, findings)
        report = ComparisonReport(plan_id=plan_id, validation_result_id=result.id, rows=jsonable(rows),
                                  summary=summarise(rows))
        self.session.add(report)
        await self.session.commit()
        return self._report_dict(report, plan)

    def _report_dict(self, report: ComparisonReport, plan: OnboardingPlan | None = None) -> dict:
        return {"id": str(report.id), "plan_id": str(report.plan_id),
                "validation_result_id": str(report.validation_result_id) if report.validation_result_id else None,
                "verification_status": plan.verification_status if plan else None,
                "created_at": report.created_at.isoformat() if report.created_at else None,
                "summary": report.summary, "rows": report.rows}

    async def latest_comparison(self, plan_id: uuid.UUID) -> dict:
        report = await self.session.scalar(
            select(ComparisonReport).where(ComparisonReport.plan_id == plan_id)
            .order_by(ComparisonReport.created_at.desc()).limit(1))
        if report is None:
            raise NotFoundError("No comparison yet. POST /comparison/{plan_id}")
        return self._report_dict(report, await self.plans.get(plan_id))

    async def comparison_rows(self, plan_ids: list[uuid.UUID] | None = None) -> list[dict]:
        """Latest comparison rows across plans (for the 100-row deliverable)."""
        plans = [p for p in await self.plans.filtered(current_only=True)
                 if plan_ids is None or p.id in set(plan_ids)]
        rows = []
        for plan in plans:
            try:
                report = await self.latest_comparison(plan.id)
            except NotFoundError:
                report = await self.compare(plan.id)
            rows.extend({"plan_id": str(plan.id), **r} for r in report["rows"])
        return rows

    @staticmethod
    def to_csv(rows: list[dict]) -> str:
        buffer = io.StringIO()
        columns = (["plan_id"] if rows and "plan_id" in rows[0] else []) + CSV_COLUMNS
        writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({**csv_row(row), **({"plan_id": row["plan_id"]} if "plan_id" in row else {})})
        return buffer.getvalue()

    # ------------------------------------------------------------ consistency
    async def start_consistency(self, plan_id: uuid.UUID, run_count: int) -> ConsistencyRun:
        plan = await self.plans.get(plan_id)
        if plan is None:
            raise NotFoundError("Plan not found")
        if not 2 <= run_count <= 5:
            raise ValidationFailedError("run_count must be between 2 and 5")
        config = await get_config(self.session, "generation")
        params = config.get("parameters", {})
        chunk_codes = sorted({c for d in [plan.raw_response or {}] for m in d.get("modules", [])
                              for c in [m.get("source_chunk_code")] +
                              [x.get("source_chunk_code") for x in m.get("tasks", []) + m.get("checklist", []) + m.get("quiz", [])]
                              if c})
        run = ConsistencyRun(
            plan_id=plan_id, status="PENDING", run_count=run_count,
            parameters={"temperature": params.get("temperature", 0.0), "seed": params.get("seed", 42),
                        "prompt_version": plan.prompt_version, "fixed_chunk_set": chunk_codes,
                        "note": "Temperature and seed are recorded; providers that fix sampling server-side "
                                "ignore them, which is why the chunk set and prompt version are pinned."},
        )
        self.session.add(run)
        await self.session.commit()
        return run

    @staticmethod
    async def execute_consistency(run_id: uuid.UUID) -> None:
        """Background job with its own session."""
        from src.services.generation_service import GenerationService

        async with SessionLocal() as session:
            run = await session.get(ConsistencyRun, run_id)
            plan = await session.get(OnboardingPlan, run.plan_id)
            run.status = "RUNNING"
            await session.commit()
            try:
                signatures, records = [], []
                for index in range(run.run_count):
                    payload, info = await GenerationService(session).generate_payload(
                        plan.employee_id, run.parameters["prompt_version"],
                        run.parameters["fixed_chunk_set"] or None,
                        {"temperature": run.parameters["temperature"], "seed": run.parameters["seed"]},
                    )
                    sig = signature(payload)
                    signatures.append(sig)
                    records.append({"run": index + 1, **info, "signature": sig})
                score, per_dim, major = consistency(signatures)
                run.runs = records
                run.comparison = per_dim
                run.consistency_score = score
                run.major_differences = major
                run.status = "COMPLETED"
            except Exception as exc:  # recorded, never raised out of a background task
                logger.exception("Consistency run %s failed", run_id)
                # A database error leaves the session unusable until rolled back;
                # without this the FAILED status could never be saved and the run
                # would show RUNNING forever.
                await session.rollback()
                run = await session.get(ConsistencyRun, run_id)
                run.status = "FAILED"
                run.error = str(exc)[:1000]
            run.finished_at = datetime.now(timezone.utc)
            await session.commit()

    async def consistency_results(self, plan_id: uuid.UUID) -> list[dict]:
        rows = await self.session.scalars(
            select(ConsistencyRun).where(ConsistencyRun.plan_id == plan_id).order_by(ConsistencyRun.created_at.desc()))
        return [
            {"id": str(r.id), "status": r.status, "run_count": r.run_count, "parameters": r.parameters,
             "consistency_score": r.consistency_score, "per_dimension": r.comparison,
             "major_differences": r.major_differences, "runs": r.runs, "error": r.error,
             "created_at": r.created_at.isoformat() if r.created_at else None,
             "finished_at": r.finished_at.isoformat() if r.finished_at else None}
            for r in rows
        ]

    # ------------------------------------------------------------ review
    async def queue(self, status: str | None, severity: str | None, job_role_id: uuid.UUID | None,
                    reviewer_id: uuid.UUID | None) -> list[dict]:
        plan_ids = None
        if job_role_id:
            plan_ids = [p.id for p in await self.plans.filtered(job_role_id=job_role_id, current_only=True)]
        else:
            plan_ids = [p.id for p in await self.plans.filtered(current_only=True)]
        severities = [severity] if severity else ["CRITICAL", "ERROR", "WARNING"]
        findings = await self.results.queue(plan_ids, severities, status or "OPEN")
        if reviewer_id:
            decided = set(await self.session.scalars(
                select(ReviewDecision.finding_id).where(ReviewDecision.reviewer_id == reviewer_id)))
            findings = [f for f in findings if f.id in decided]
        plans = {p.id: p for p in await self.plans.filtered()}
        return [
            {**ValidationService.finding_dict(f), "plan_title": plans[f.plan_id].title if f.plan_id in plans else None}
            for f in findings
        ]

    async def decide(self, finding_id: uuid.UUID, decision: str, reason: str, reviewer_id: uuid.UUID,
                     edits: dict | None = None) -> dict:
        decision = decision.upper()
        if decision not in DECISIONS:
            raise ValidationFailedError(f"decision must be one of {', '.join(DECISIONS)}")
        finding = await self.results.finding(finding_id)
        if finding is None:
            raise NotFoundError("Finding not found")
        original_finding = ValidationService.finding_dict(finding)
        item = None
        original_item = None
        if finding.item_type in EDITABLE and finding.item_id:
            try:
                item = await self.plans.item(finding.item_type, uuid.UUID(finding.item_id))
            except ValueError:
                item = None
            if item is not None:
                original_item = {k: getattr(item, k) for k in EDITABLE[finding.item_type] if hasattr(item, k)}

        outcome: dict = {}
        if decision == "EDIT":
            if item is None:
                raise ValidationFailedError("This finding does not point at an editable plan item")
            edits = edits or {}
            bad = set(edits) - EDITABLE[finding.item_type]
            if bad or not edits:
                raise ValidationFailedError(f"Editable fields for {finding.item_type}: "
                                            f"{', '.join(sorted(EDITABLE[finding.item_type]))}")
            for name, value in edits.items():
                setattr(item, name, _checked_edit(item, name, value))
            outcome = {"edited": sorted(edits), "next_step": "Re-run POST /validation/run/{plan_id}"}
        elif decision == "REGENERATE":
            code = finding.requirement_code or (getattr(item, "requirement_code", None) if item else None)
            if not code:
                raise ValidationFailedError("No requirement to regenerate for this finding")
            from src.services.generation_service import GenerationService

            outcome = await GenerationService(self.session).regenerate_modules(
                finding.plan_id, {code}, [{"reason": f"Reviewer requested regeneration: {reason}"}], reviewer_id)
            finding = await self.results.finding(finding_id)

        new_status = DECISIONS[decision]
        if new_status:
            finding.review_status = new_status
        record = ReviewDecision(
            finding_id=finding_id, plan_id=finding.plan_id, reviewer_id=reviewer_id, decision=decision,
            reason=reason, original_finding=jsonable(original_finding), original_item=jsonable(original_item),
            edited_fields=jsonable(edits) if decision == "EDIT" else None, outcome=jsonable(outcome),
        )
        self.session.add(record)
        self.audit.record("finding", finding_id, f"review_{decision.lower()}", actor_id=reviewer_id,
                          before={"finding": original_finding, "item": original_item},
                          after={"review_status": finding.review_status, "edits": edits, "outcome": outcome},
                          reason=reason)
        if item is not None and decision == "EDIT":
            self.audit.record(finding.item_type, finding.item_id, "reviewer_edit", actor_id=reviewer_id,
                              before=original_item, after=edits, reason=reason)
        self.audit.record("plan", finding.plan_id, f"review_{decision.lower()}", actor_id=reviewer_id,
                          after={"finding_id": str(finding_id)}, reason=reason)
        await self.session.commit()
        return {"decision_id": str(record.id), "finding_id": str(finding_id), "decision": decision,
                "review_status": finding.review_status, "original_result": original_finding,
                "original_item": jsonable(original_item), "outcome": jsonable(outcome)}

    async def decisions_for(self, entity_type: str, entity_id: str) -> list[dict]:
        column = {"finding": ReviewDecision.finding_id, "plan": ReviewDecision.plan_id}.get(entity_type)
        if column is None:
            return []
        try:
            key = uuid.UUID(entity_id)
        except ValueError:
            return []
        rows = await self.session.scalars(select(ReviewDecision).where(column == key).order_by(ReviewDecision.created_at))
        return [{"id": str(r.id), "finding_id": str(r.finding_id), "reviewer_id": str(r.reviewer_id),
                 "decision": r.decision, "reason": r.reason, "original_finding": r.original_finding,
                 "original_item": r.original_item, "edited_fields": r.edited_fields, "outcome": r.outcome,
                 "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows]


def _checked_edit(item, name: str, value):
    """Validates one reviewer edit against the type of the value it replaces, so
    e.g. correct_answer stays a list of strings (a bare string would be graded
    character by character) and passing_score stays a number."""
    current = getattr(item, name, None)
    column = item.__table__.columns.get(name)
    wrong = ValidationFailedError(f"'{name}' must be {_describe(current, column)}")
    if value is None:
        if column is not None and not column.nullable:
            raise wrong
        return None
    if isinstance(current, enum.Enum):
        try:
            return type(current)(value)
        except ValueError:
            raise ValidationFailedError(f"'{name}' must be one of: {', '.join(m.value for m in type(current))}")
    if isinstance(current, uuid.UUID) or (column is not None and isinstance(column.type, UUID_TYPES)):
        try:
            return uuid.UUID(str(value))
        except ValueError:
            raise wrong
    if isinstance(current, bool):
        if not isinstance(value, bool):
            raise wrong
    elif isinstance(current, (int, float)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise wrong
    elif isinstance(current, list):
        if not isinstance(value, list) or not all(isinstance(v, (str, int, float, dict)) for v in value):
            raise wrong
    elif isinstance(current, dict):
        if not isinstance(value, dict):
            raise wrong
    elif isinstance(current, str) or current is None:
        if not isinstance(value, str):
            raise wrong
    return value


def _describe(current, column) -> str:
    if isinstance(current, uuid.UUID) or (column is not None and isinstance(column.type, UUID_TYPES)):
        return "a valid ID"
    if isinstance(current, bool):
        return "true or false"
    if isinstance(current, (int, float)):
        return "a number"
    if isinstance(current, list):
        return "a list, e.g. [\"A\", \"B\"]"
    if isinstance(current, dict):
        return "an object"
    return "text"
