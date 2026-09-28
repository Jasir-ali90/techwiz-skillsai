import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.core.deps import get_current_user, require_roles
from src.models.enums import Priority, RequirementType, UserType
from src.services.matrix_service import MatrixService

ADMIN = require_roles(UserType.ADMIN)
ADMIN_TM = require_roles(UserType.ADMIN, UserType.TRAINING_MANAGER)

router = APIRouter(tags=["role requirement matrix"])


class ExtractRequest(BaseModel):
    document_id: uuid.UUID | None = None
    force: bool = False


class MapRolesRequest(BaseModel):
    job_role_id: uuid.UUID | None = None


class RequirementPatch(BaseModel):
    requirement_type: RequirementType | None = None
    is_mandatory: bool | None = None
    priority: Priority | None = None
    competency: str | None = Field(None, max_length=150)
    assessment_required: bool | None = None
    assessment_topic: str | None = None
    is_compliance: bool | None = None
    is_active: bool | None = None
    reason: str | None = None


class ManualMapping(BaseModel):
    job_role_id: uuid.UUID
    reason: str = Field(min_length=3)


@router.post("/matrix/extract")
async def extract(
    payload: ExtractRequest | None = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(ADMIN_TM),
):
    payload = payload or ExtractRequest()
    return await MatrixService(session).extract(payload.document_id, force=payload.force)


@router.post("/matrix/map-roles")
async def map_roles(
    payload: MapRolesRequest | None = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(ADMIN_TM),
):
    payload = payload or MapRolesRequest()
    return await MatrixService(session).map_roles(payload.job_role_id)


@router.post("/matrix/prerequisites")
async def prerequisites(session: AsyncSession = Depends(get_session), _=Depends(ADMIN_TM)):
    return await MatrixService(session).build_prerequisites()


@router.post("/matrix/resolve-conflicts")
async def resolve_conflicts(session: AsyncSession = Depends(get_session), _=Depends(ADMIN_TM)):
    """Apply document precedence to the Matrix: where two active documents
    disagree on the same obligation, the lower-ranked clause's requirement is
    marked overridden (kept on record, removed from every role's answer key)."""
    return await MatrixService(session).apply_precedence()


@router.get("/matrix/summary")
async def summary(session: AsyncSession = Depends(get_session), _=Depends(get_current_user)):
    return await MatrixService(session).summary()


@router.get("/matrix/role/{job_role_id}")
async def role_matrix(
    job_role_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _=Depends(get_current_user),
):
    """The answer key for one role."""
    return await MatrixService(session).role_matrix(job_role_id)


@router.get("/requirements")
async def list_requirements(
    requirement_type: RequirementType | None = None,
    is_mandatory: bool | None = None,
    priority: Priority | None = None,
    document_id: uuid.UUID | None = None,
    job_role_id: uuid.UUID | None = None,
    include_inactive: bool = False,
    session: AsyncSession = Depends(get_session),
    _=Depends(get_current_user),
):
    return await MatrixService(session).list_requirements(
        requirement_type=requirement_type, is_mandatory=is_mandatory, priority=priority,
        document_id=document_id, job_role_id=job_role_id, include_inactive=include_inactive,
    )


@router.get("/requirements/{code}")
async def get_requirement(code: str, session: AsyncSession = Depends(get_session), _=Depends(get_current_user)):
    return await MatrixService(session).get_requirement(code)


@router.patch("/requirements/{code}")
async def patch_requirement(
    code: str,
    payload: RequirementPatch,
    session: AsyncSession = Depends(get_session),
    user=Depends(ADMIN),
):
    changes = payload.model_dump(exclude_unset=True)
    reason = changes.pop("reason", None)
    return await MatrixService(session).patch_requirement(code, changes, user.id, reason)


@router.post("/requirements/{code}/roles")
async def add_manual_mapping(
    code: str,
    payload: ManualMapping,
    session: AsyncSession = Depends(get_session),
    user=Depends(ADMIN),
):
    return await MatrixService(session).add_manual_mapping(code, payload.job_role_id, payload.reason, user.id)
