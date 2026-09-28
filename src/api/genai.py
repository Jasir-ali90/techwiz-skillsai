from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.core.deps import get_current_user, require_roles, require_staff
from src.models.enums import UserType
from src.services.genai_service import GenAIService

ADMIN_TM = require_roles(UserType.ADMIN, UserType.TRAINING_MANAGER)

router = APIRouter(prefix="/genai", tags=["genai providers"])


@router.get("/status")
async def status(session: AsyncSession = Depends(get_session), _=Depends(require_staff)):
    """The provider chain as configured now: primary, fallbacks, which one will
    serve, and why any is skipped. API keys are never returned."""
    return await GenAIService(session).status()


@router.post("/test/{provider}")
async def test_provider(provider: str, session: AsyncSession = Depends(get_session), _=Depends(ADMIN_TM)):
    """One tiny live call to a provider, to check its key and model."""
    return await GenAIService(session).test(provider)
