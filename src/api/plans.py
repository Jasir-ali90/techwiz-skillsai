import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.core.deps import get_current_user, require_roles
from src.models.enums import UserType
from src.services.generation_service import GenerationService

GENERATORS = require_roles(UserType.ADMIN, UserType.TRAINING_MANAGER)

router = APIRouter(tags=["plans"])


class GenerateRequest(BaseModel):
    employee_id: uuid.UUID
    prompt_version: str | None = None
    extra_topics: list[str] = Field(default_factory=list, max_length=20,
                                    description="Topics to cover; any no document supports becomes a recorded gap")
    simulate_malformed: int = Field(0, ge=0, le=5,
                                    description="Offline provider only: return broken JSON for the first N attempts")
    validate_after: bool = Field(True, description="Run Pipeline 2 immediately after generation")


@router.post("/plans/generate")
async def generate(payload: GenerateRequest, session: AsyncSession = Depends(get_session),
                   user=Depends(GENERATORS)):
    plan = await GenerationService(session).generate_plan(
        payload.employee_id, prompt_version=payload.prompt_version, extra_topics=payload.extra_topics,
        simulate_malformed=payload.simulate_malformed, actor_id=user.id,
    )
    if payload.validate_after:
        from src.services.validation_service import ValidationService

        report = await ValidationService(session).run(uuid.UUID(plan["id"]))
        plan["validation"] = {k: report[k] for k in ("verification_status", "metrics", "counts_by_severity")}
    return plan


@router.get("/plans")
async def list_plans(
    employee_id: uuid.UUID | None = None,
    job_role_id: uuid.UUID | None = None,
    status: str | None = None,
    verification_status: str | None = None,
    current_only: bool = False,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_roles(UserType.ADMIN, UserType.TRAINING_MANAGER, UserType.MANAGER, UserType.REVIEWER)),
):
    return await GenerationService(session).list_plans(
        employee_id=employee_id, job_role_id=job_role_id, status=status,
        verification_status=verification_status, current_only=current_only,
    )


@router.get("/plans/compare")
async def compare_plans(
    dimension: str | None = Query(None, description="role, department, experience_level, document_version or plan"),
    plan_ids: list[uuid.UUID] | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_roles(UserType.ADMIN, UserType.TRAINING_MANAGER, UserType.MANAGER, UserType.REVIEWER)),
):
    """SRS Step 60: compare plans across roles, departments, employee levels and document versions."""
    from src.services.progress_service import ProgressService

    return await ProgressService(session).compare_plans(dimension, plan_ids)


STAFF_ONLY = require_roles(UserType.ADMIN, UserType.TRAINING_MANAGER, UserType.MANAGER, UserType.REVIEWER)


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: uuid.UUID, session: AsyncSession = Depends(get_session), user=Depends(get_current_user)):
    plan = await GenerationService(session).get_plan(plan_id)
    if user.user_type == UserType.EMPLOYEE:
        # An employee may open only their own plan, and must not receive the
        # quiz answers before attempting it (the attempt endpoint marks them).
        from src.services.progress_service import ProgressService

        await ProgressService(session).check_access(user, uuid.UUID(plan["employee_id"]))
        for module in plan["modules"]:
            for question in module["quiz"]:
                question.pop("correct_answer", None)
                question.pop("explanation", None)
    return plan


@router.get("/plans/{plan_id}/generation-run")
async def generation_run(plan_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                         _=Depends(STAFF_ONLY)):
    """The audit record: prompt version, model, timing, attempts, source versions."""
    runs = await GenerationService(session).generation_runs(plan_id)
    return {"plan_id": str(plan_id), "runs": runs, "latest": runs[-1] if runs else None}


@router.get("/prompt-templates")
async def prompt_templates(session: AsyncSession = Depends(get_session), _=Depends(get_current_user)):
    return await GenerationService(session).list_templates()
