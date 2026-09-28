import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.core.deps import get_current_user, require_roles, require_staff
from src.models.enums import UserType
from src.services.impact_service import ImpactService

ADMIN_TM = require_roles(UserType.ADMIN, UserType.TRAINING_MANAGER)

router = APIRouter(tags=["policy updates and impact"])


@router.post("/impact/analyse/{document_id}")
async def analyse(document_id: uuid.UUID, session: AsyncSession = Depends(get_session), user=Depends(ADMIN_TM)):
    """Diff a newly uploaded version against its predecessor and find every
    affected requirement, item, plan and employee."""
    return await ImpactService(session).analyse(document_id, user.id)


@router.get("/impact/{document_id}")
async def impact(document_id: uuid.UUID, session: AsyncSession = Depends(get_session), _=Depends(require_staff)):
    return await ImpactService(session).get(document_id)


@router.get("/impact/{document_id}/affected")
async def affected(document_id: uuid.UUID, session: AsyncSession = Depends(get_session), _=Depends(require_staff)):
    return await ImpactService(session).affected(document_id)


@router.post("/impact/{document_id}/regenerate")
async def regenerate(document_id: uuid.UUID, dry_run: bool = True, session: AsyncSession = Depends(get_session),
                     user=Depends(ADMIN_TM)):
    """Selective regeneration. dry_run=true (the default) shows what would
    change before anything changes."""
    return await ImpactService(session).regenerate(document_id, dry_run=dry_run, actor_id=user.id)


@router.get("/plans/{plan_id}/outdated")
async def outdated(plan_id: uuid.UUID, session: AsyncSession = Depends(get_session), _=Depends(require_staff)):
    """Which parts of a plan reference obsolete sources or changed sections."""
    return await ImpactService(session).outdated(plan_id)
