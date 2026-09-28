import uuid
from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.enums import MappingMethod
from src.models.organization import Department, JobRole
from src.models.requirement import Prerequisite, Requirement, RoleRequirement
from src.repositories.base import BaseRepository


class RequirementRepository(BaseRepository[Requirement]):
    model = Requirement

    async def by_source_keys(self, keys: Sequence[str]) -> dict[str, Requirement]:
        if not keys:
            return {}
        rows = await self.session.scalars(select(Requirement).where(Requirement.source_key.in_(keys)))
        return {r.source_key: r for r in rows}

    async def for_document_codes(self, codes: Sequence[str]) -> list[Requirement]:
        rows = await self.session.scalars(
            select(Requirement).where(Requirement.source_document_code.in_(codes))
        )
        return list(rows)

    async def max_code_number(self) -> int:
        codes = await self.session.scalars(select(Requirement.requirement_code))
        numbers = [int(c[1:]) for c in codes if c[1:].isdigit()]
        return max(numbers, default=0)

    async def by_code(self, code: str) -> Requirement | None:
        return await self.session.scalar(select(Requirement).where(Requirement.requirement_code == code))

    async def by_codes(self, codes: Sequence[str]) -> dict[str, Requirement]:
        if not codes:
            return {}
        rows = await self.session.scalars(select(Requirement).where(Requirement.requirement_code.in_(codes)))
        return {r.requirement_code: r for r in rows}

    async def active(self) -> list[Requirement]:
        rows = await self.session.scalars(
            select(Requirement).where(Requirement.is_active.is_(True)).order_by(Requirement.requirement_code)
        )
        return list(rows)

    async def filtered(
        self,
        requirement_type=None,
        is_mandatory: bool | None = None,
        priority=None,
        document_id: uuid.UUID | None = None,
        job_role_id: uuid.UUID | None = None,
        include_inactive: bool = False,
    ) -> list[Requirement]:
        stmt = select(Requirement).order_by(Requirement.requirement_code)
        if not include_inactive:
            stmt = stmt.where(Requirement.is_active.is_(True))
        if requirement_type:
            stmt = stmt.where(Requirement.requirement_type == requirement_type)
        if is_mandatory is not None:
            stmt = stmt.where(Requirement.is_mandatory.is_(is_mandatory))
        if priority:
            stmt = stmt.where(Requirement.priority == priority)
        if document_id:
            stmt = stmt.where(Requirement.source_document_id == document_id)
        if job_role_id:
            stmt = stmt.join(RoleRequirement, RoleRequirement.requirement_id == Requirement.id).where(
                RoleRequirement.job_role_id == job_role_id
            )
        return list(await self.session.scalars(stmt))


class RoleRequirementRepository(BaseRepository[RoleRequirement]):
    model = RoleRequirement

    async def delete_generated(self, job_role_id: uuid.UUID | None = None,
                               requirement_ids: Sequence[uuid.UUID] | None = None) -> None:
        """Removes rule-generated mappings; MANUAL mappings survive a re-map."""
        stmt = delete(RoleRequirement).where(RoleRequirement.mapping_method != MappingMethod.MANUAL)
        if job_role_id:
            stmt = stmt.where(RoleRequirement.job_role_id == job_role_id)
        if requirement_ids is not None:
            stmt = stmt.where(RoleRequirement.requirement_id.in_(requirement_ids))
        await self.session.execute(stmt)

    async def manual_pairs(self) -> set[tuple[uuid.UUID, uuid.UUID]]:
        rows = await self.session.execute(
            select(RoleRequirement.job_role_id, RoleRequirement.requirement_id).where(
                RoleRequirement.mapping_method == MappingMethod.MANUAL
            )
        )
        return {(a, b) for a, b in rows.all()}

    async def matrix_for_role(self, job_role_id: uuid.UUID) -> list[tuple[RoleRequirement, Requirement]]:
        rows = await self.session.execute(
            select(RoleRequirement, Requirement)
            .join(Requirement, Requirement.id == RoleRequirement.requirement_id)
            .where(RoleRequirement.job_role_id == job_role_id, Requirement.is_active.is_(True),
                   Requirement.overridden_by.is_(None), Requirement.override_reason.is_(None))
            .order_by(Requirement.requirement_code)
        )
        return [(m, r) for m, r in rows.all()]

    async def roles_for_requirements(self, requirement_ids: Sequence[uuid.UUID]) -> list[tuple[RoleRequirement, JobRole]]:
        if not requirement_ids:
            return []
        rows = await self.session.execute(
            select(RoleRequirement, JobRole)
            .join(JobRole, JobRole.id == RoleRequirement.job_role_id)
            .where(RoleRequirement.requirement_id.in_(requirement_ids))
        )
        return [(m, j) for m, j in rows.all()]

    async def counts_by_role(self) -> list[tuple[str, str, int, int]]:
        rows = await self.session.execute(
            select(
                JobRole.code, JobRole.title,
                func.count(RoleRequirement.id),
                func.count(RoleRequirement.id).filter(RoleRequirement.is_mandatory_for_role.is_(True)),
            )
            .join(RoleRequirement, RoleRequirement.job_role_id == JobRole.id, isouter=True)
            .join(Requirement, Requirement.id == RoleRequirement.requirement_id, isouter=True)
            .where((Requirement.is_active.is_(True)) | (Requirement.id.is_(None)))
            .group_by(JobRole.code, JobRole.title)
            .order_by(JobRole.code)
        )
        return [tuple(r) for r in rows.all()]

    async def role_counts_per_requirement(self) -> dict[uuid.UUID, int]:
        rows = await self.session.execute(
            select(RoleRequirement.requirement_id, func.count(RoleRequirement.id)).group_by(
                RoleRequirement.requirement_id
            )
        )
        return {a: b for a, b in rows.all()}


class PrerequisiteRepository(BaseRepository[Prerequisite]):
    model = Prerequisite

    async def replace_generated(self, edges: list[dict]) -> None:
        await self.session.execute(delete(Prerequisite).where(Prerequisite.method != "MANUAL"))
        for edge in edges:
            self.session.add(Prerequisite(**edge))

    async def all_edges(self) -> list[Prerequisite]:
        return list(await self.session.scalars(select(Prerequisite)))

    async def for_requirements(self, ids: Sequence[uuid.UUID]) -> list[Prerequisite]:
        if not ids:
            return []
        return list(await self.session.scalars(select(Prerequisite).where(Prerequisite.requirement_id.in_(ids))))


class RoleRepository(BaseRepository[JobRole]):
    model = JobRole

    async def active_with_departments(self, job_role_id: uuid.UUID | None = None) -> list[tuple[JobRole, Department]]:
        stmt = (
            select(JobRole, Department)
            .join(Department, Department.id == JobRole.department_id)
            .where(JobRole.is_active.is_(True))
            .order_by(JobRole.code)
        )
        if job_role_id:
            stmt = stmt.where(JobRole.id == job_role_id)
        rows = await self.session.execute(stmt)
        return [(r, d) for r, d in rows.all()]
