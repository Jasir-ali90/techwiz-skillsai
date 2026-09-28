import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.core.deps import get_current_user, require_roles, require_staff
from src.models.enums import UserType
from src.services.validation_service import ValidationService

ADMIN = require_roles(UserType.ADMIN)
RUNNERS = require_roles(UserType.ADMIN, UserType.TRAINING_MANAGER, UserType.REVIEWER)

router = APIRouter(prefix="/validation", tags=["validation (pipeline 2)"])


@router.get("/rules")
async def rules(session: AsyncSession = Depends(get_session), _=Depends(require_staff)):
    """The active rule set and which rules are enabled."""
    return await ValidationService(session).rules()


@router.put("/rules")
async def update_rules(changes: dict[str, dict], session: AsyncSession = Depends(get_session),
                       user=Depends(ADMIN)):
    """Toggle rules and thresholds at runtime, e.g. {"duplicates": {"enabled": false}}."""
    return await ValidationService(session).update_rules(changes, user.id)


@router.get("/contradictions")
async def corpus_contradictions(include_obsolete: bool = True, session: AsyncSession = Depends(get_session),
                                _=Depends(require_staff)):
    """Every contradiction found in the document corpus, with its precedence resolution."""
    found = await ValidationService(session).corpus_contradictions(include_obsolete)
    return {"count": len(found), "contradictions": found}


@router.post("/run/{plan_id}")
async def run(plan_id: uuid.UUID, session: AsyncSession = Depends(get_session), _=Depends(RUNNERS)):
    return await ValidationService(session).run(plan_id)


@router.get("/{plan_id}")
async def result(plan_id: uuid.UUID, include_findings: bool = True, session: AsyncSession = Depends(get_session),
                 _=Depends(require_staff)):
    return await ValidationService(session).get_result(plan_id, include_findings)


@router.get("/{plan_id}/findings")
async def findings(plan_id: uuid.UUID, rule: str | None = None, severity: str | None = None,
                   session: AsyncSession = Depends(get_session), _=Depends(require_staff)):
    return await ValidationService(session).findings(plan_id, rule, severity)
