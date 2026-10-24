from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.core.deps import get_current_user
from src.services.copilot_service import CopilotService

router = APIRouter(prefix="/copilot", tags=["copilot"])


class CopilotAskRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000, description="The employee question or inquiry")
    role_id: str | None = Field(default=None, description="Optional job role UUID context")
    employee_id: str | None = Field(default=None, description="Optional employee UUID context")


@router.post("/ask")
async def ask_copilot(
    payload: CopilotAskRequest,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
) -> dict[str, Any]:
    """Answers employee questions with zero hallucinations, citing verified active document chunks."""
    # If the user is an employee and employee_id wasn't specified, use their linked employee_id
    employee_id = payload.employee_id
    if not employee_id and hasattr(current_user, "employee_id") and current_user.employee_id:
        employee_id = str(current_user.employee_id)

    service = CopilotService(session)
    return await service.ask(
        question=payload.question,
        role_id=payload.role_id,
        employee_id=employee_id,
    )
