import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.core.deps import get_current_user, require_roles, require_staff
from src.models.enums import UserType
from src.services.audit_service import AuditService
from src.services.review_service import ReviewService

REVIEWERS = require_roles(UserType.ADMIN, UserType.REVIEWER, UserType.TRAINING_MANAGER)

router = APIRouter(tags=["comparison, consistency, review, audit"])


class Decision(BaseModel):
    decision: str = Field(description="APPROVE, REJECT, EDIT, REGENERATE or COMMENT")
    reason: str = Field(min_length=3)
    edits: dict | None = Field(None, description="Fields to change, for EDIT")


class ConsistencyRequest(BaseModel):
    run_count: int = Field(3, ge=2, le=5)


@router.post("/comparison/{plan_id}")
async def compare(plan_id: uuid.UUID, session: AsyncSession = Depends(get_session), _=Depends(REVIEWERS)):
    return await ReviewService(session).compare(plan_id)


@router.get("/comparison/{plan_id}")
async def comparison(plan_id: uuid.UUID, session: AsyncSession = Depends(get_session), _=Depends(require_staff)):
    return await ReviewService(session).latest_comparison(plan_id)


@router.get("/comparison/{plan_id}/export")
async def export_comparison(plan_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                            _=Depends(require_staff)):
    service = ReviewService(session)
    try:
        report = await service.latest_comparison(plan_id)
    except Exception:
        report = await service.compare(plan_id)
    return Response(service.to_csv(report["rows"]), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="comparison_{plan_id}.csv"'})


@router.post("/consistency/{plan_id}", status_code=202)
async def start_consistency(plan_id: uuid.UUID, background: BackgroundTasks,
                            payload: ConsistencyRequest | None = None,
                            session: AsyncSession = Depends(get_session), _=Depends(REVIEWERS)):
    """Runs in the background so the standard generate-and-validate path stays
    inside 30 seconds. Poll GET /consistency/{plan_id}."""
    payload = payload or ConsistencyRequest()
    run = await ReviewService(session).start_consistency(plan_id, payload.run_count)
    background.add_task(ReviewService.execute_consistency, run.id)
    return {"consistency_run_id": str(run.id), "status": run.status, "parameters": run.parameters}


@router.get("/consistency/{plan_id}")
async def consistency(plan_id: uuid.UUID, session: AsyncSession = Depends(get_session), _=Depends(require_staff)):
    return await ReviewService(session).consistency_results(plan_id)


@router.get("/review/queue")
async def queue(
    status: str | None = Query(None, description="OPEN (default), APPROVED, REJECTED, EDITED, REGENERATED"),
    severity: str | None = None,
    job_role_id: uuid.UUID | None = None,
    reviewer_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(REVIEWERS),
):
    return await ReviewService(session).queue(status, severity, job_role_id, reviewer_id)


@router.post("/review/{finding_id}/decision")
async def decide(finding_id: uuid.UUID, payload: Decision, session: AsyncSession = Depends(get_session),
                 user=Depends(REVIEWERS)):
    return await ReviewService(session).decide(finding_id, payload.decision, payload.reason, user.id, payload.edits)


@router.get("/audit/{entity_type}/{entity_id}")
async def audit(entity_type: str, entity_id: str, session: AsyncSession = Depends(get_session),
                _=Depends(require_staff)):
    """Full, append-only history. Review decisions carry both the original
    result and the reviewer's decision."""
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "history": await AuditService(session).history(entity_type, entity_id),
        "review_decisions": await ReviewService(session).decisions_for(entity_type, entity_id),
    }
