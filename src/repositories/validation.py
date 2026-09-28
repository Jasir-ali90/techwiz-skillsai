import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.validation import ValidationFinding, ValidationResult
from src.repositories.base import BaseRepository


class ValidationRepository(BaseRepository[ValidationResult]):
    model = ValidationResult

    async def latest(self, plan_id: uuid.UUID) -> ValidationResult | None:
        return await self.session.scalar(
            select(ValidationResult).where(ValidationResult.plan_id == plan_id)
            .order_by(ValidationResult.run_at.desc()).limit(1)
        )

    async def latest_for_plans(self, plan_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, ValidationResult]:
        if not plan_ids:
            return {}
        rows = await self.session.scalars(
            select(ValidationResult).where(ValidationResult.plan_id.in_(plan_ids))
            .order_by(ValidationResult.run_at)
        )
        return {r.plan_id: r for r in rows}

    async def history(self, plan_id: uuid.UUID) -> list[ValidationResult]:
        rows = await self.session.scalars(
            select(ValidationResult).where(ValidationResult.plan_id == plan_id).order_by(ValidationResult.run_at)
        )
        return list(rows)

    async def findings(self, result_id: uuid.UUID, rule: str | None = None, severity: str | None = None,
                       review_status: str | None = None) -> list[ValidationFinding]:
        stmt = select(ValidationFinding).where(ValidationFinding.result_id == result_id)
        if rule:
            stmt = stmt.where(ValidationFinding.rule_name == rule)
        if severity:
            stmt = stmt.where(ValidationFinding.severity == severity)
        if review_status:
            stmt = stmt.where(ValidationFinding.review_status == review_status)
        return list(await self.session.scalars(stmt.order_by(ValidationFinding.rule_name)))

    async def decided_fingerprints(self, plan_id: uuid.UUID) -> dict[str, str]:
        """Reviewer decisions carry over to later runs of the same plan."""
        rows = await self.session.execute(
            select(ValidationFinding.fingerprint, ValidationFinding.review_status)
            .where(ValidationFinding.plan_id == plan_id, ValidationFinding.review_status != "OPEN")
            .order_by(ValidationFinding.created_at)
        )
        return {fp: status for fp, status in rows.all()}

    async def finding(self, finding_id: uuid.UUID) -> ValidationFinding | None:
        return await self.session.get(ValidationFinding, finding_id)

    async def queue(self, plan_ids: Sequence[uuid.UUID] | None, severities: Sequence[str],
                    review_status: str | None) -> list[ValidationFinding]:
        latest_ids = select(ValidationResult.id).distinct(ValidationResult.plan_id).order_by(
            ValidationResult.plan_id, ValidationResult.run_at.desc()
        )
        stmt = select(ValidationFinding).where(
            ValidationFinding.result_id.in_(latest_ids), ValidationFinding.severity.in_(severities)
        )
        if plan_ids is not None:
            stmt = stmt.where(ValidationFinding.plan_id.in_(plan_ids))
        if review_status:
            stmt = stmt.where(ValidationFinding.review_status == review_status)
        return list(await self.session.scalars(stmt.order_by(ValidationFinding.created_at.desc())))
