import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.core.deps import get_current_user, require_roles
from src.models.enums import UserType
from src.services.progress_service import ProgressService

STAFF = require_roles(UserType.ADMIN, UserType.TRAINING_MANAGER, UserType.MANAGER, UserType.REVIEWER)

router = APIRouter(tags=["progress and dashboards"])


class CompletionUpdate(BaseModel):
    status: str = Field("COMPLETED", description="NOT_STARTED, IN_PROGRESS or COMPLETED")


class QuizAnswer(BaseModel):
    answer: list[str] = Field(min_length=1)


class AssessmentScore(BaseModel):
    score: float = Field(ge=0, le=100)
    notes: str | None = None
    criteria_scores: dict | None = None


@router.get("/progress/{employee_id}")
async def progress(employee_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                   user=Depends(get_current_user)):
    service = ProgressService(session)
    await service.check_access(user, employee_id)
    return await service.progress(employee_id)


@router.post("/progress/items/{item_type}/{item_id}")
async def set_completion(item_type: str, item_id: uuid.UUID, payload: CompletionUpdate,
                         session: AsyncSession = Depends(get_session), user=Depends(get_current_user)):
    return await ProgressService(session).set_completion(item_type, item_id, payload.status, user)


@router.post("/progress/quiz/{question_id}/attempt")
async def attempt_quiz(question_id: uuid.UUID, payload: QuizAnswer, session: AsyncSession = Depends(get_session),
                       user=Depends(get_current_user)):
    return await ProgressService(session).attempt_quiz(question_id, payload.answer, user)


@router.post("/progress/assessments/{assessment_id}/result")
async def record_assessment(assessment_id: uuid.UUID, payload: AssessmentScore,
                            session: AsyncSession = Depends(get_session), user=Depends(STAFF)):
    return await ProgressService(session).record_assessment(assessment_id, payload.score, payload.notes,
                                                            payload.criteria_scores, user)


@router.get("/dashboard/me")
async def my_dashboard(session: AsyncSession = Depends(get_session), user=Depends(get_current_user)):
    service = ProgressService(session)
    return await service.employee_dashboard(await service.employee_for_user(user))


@router.get("/dashboard/employee/{employee_id}")
async def employee_dashboard(employee_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                             user=Depends(get_current_user)):
    service = ProgressService(session)
    await service.check_access(user, employee_id)
    return await service.employee_dashboard(employee_id)


@router.get("/dashboard/admin")
async def admin_dashboard(session: AsyncSession = Depends(get_session), _=Depends(STAFF)):
    return await ProgressService(session).admin_dashboard()


@router.get("/dashboard/roles")
async def role_dashboards(session: AsyncSession = Depends(get_session), _=Depends(STAFF)):
    return await ProgressService(session).role_dashboard()


@router.get("/dashboard/role/{job_role_id}")
async def role_dashboard(job_role_id: uuid.UUID, session: AsyncSession = Depends(get_session), _=Depends(STAFF)):
    return await ProgressService(session).role_dashboard(job_role_id)
