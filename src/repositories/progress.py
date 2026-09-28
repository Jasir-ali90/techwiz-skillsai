import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import DocumentChunk
from src.models.progress import AssessmentResult, QuizAttempt
from src.repositories.base import BaseRepository


class ProgressRepository(BaseRepository[QuizAttempt]):
    model = QuizAttempt

    async def attempts(self, employee_id: uuid.UUID, plan_id: uuid.UUID | None = None) -> list[QuizAttempt]:
        stmt = select(QuizAttempt).where(QuizAttempt.employee_id == employee_id)
        if plan_id:
            stmt = stmt.where(QuizAttempt.plan_id == plan_id)
        return list(await self.session.scalars(stmt.order_by(QuizAttempt.attempted_at)))

    async def results(self, employee_id: uuid.UUID, plan_id: uuid.UUID | None = None) -> list[AssessmentResult]:
        stmt = select(AssessmentResult).where(AssessmentResult.employee_id == employee_id)
        if plan_id:
            stmt = stmt.where(AssessmentResult.plan_id == plan_id)
        return list(await self.session.scalars(stmt.order_by(AssessmentResult.assessed_at)))

    async def attempts_for_plans(self, plan_ids: Sequence[uuid.UUID]) -> list[QuizAttempt]:
        if not plan_ids:
            return []
        return list(await self.session.scalars(select(QuizAttempt).where(QuizAttempt.plan_id.in_(plan_ids))))

    async def results_for_plans(self, plan_ids: Sequence[uuid.UUID]) -> list[AssessmentResult]:
        if not plan_ids:
            return []
        return list(await self.session.scalars(select(AssessmentResult).where(AssessmentResult.plan_id.in_(plan_ids))))

    async def suspicious_chunk_count(self) -> int:
        return await self.session.scalar(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.is_suspicious.is_(True))) or 0
