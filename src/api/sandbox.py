from typing import Any
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.core.deps import get_current_user
from src.services.sandbox_service import SandboxService

router = APIRouter(prefix="/sandbox", tags=["sandbox"])


class EvaluateCodeRequest(BaseModel):
    challenge_id: str = Field(..., description="Challenge ID to evaluate")
    code: str = Field(..., description="Submitted code solution")
    employee_id: str | None = Field(default=None, description="Optional employee ID to credit progress")


@router.get("/challenges")
async def get_challenges(
    role_code: str = Query("BACKEND_DEV", description="Job role code"),
    session: AsyncSession = Depends(get_session),
    _=Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Returns practical role-specific onboarding challenges."""
    service = SandboxService(session)
    return service.get_challenges_for_role(role_code)


@router.post("/evaluate")
async def evaluate_code(
    payload: EvaluateCodeRequest,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
) -> dict[str, Any]:
    """Deterministically evaluates submitted challenge code against automated unit tests."""
    service = SandboxService(session)
    result = service.evaluate(payload.challenge_id, payload.code)
    return result
