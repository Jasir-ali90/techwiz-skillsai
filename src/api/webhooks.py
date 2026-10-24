from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.app_config import set_config
from src.core.db import get_session
from src.core.deps import require_roles
from src.models.enums import UserType
from src.services.webhook_service import WebhookService

ADMIN = require_roles(UserType.ADMIN)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookConfigRequest(BaseModel):
    slack_url: str = Field("", description="Slack incoming webhook URL")
    teams_url: str = Field("", description="Microsoft Teams webhook URL")
    custom_url: str = Field("", description="Generic webhook URL")
    enabled_events: list[str] = Field(default_factory=lambda: ["PLAN_VERIFIED", "BEHIND_SCHEDULE_ALERT", "CERTIFICATE_ISSUED", "POLICY_UPDATED"])


class TestWebhookRequest(BaseModel):
    webhook_url: str = Field(..., description="Target webhook URL to test")
    provider: str = Field("slack", description="slack, teams, or generic")


@router.get("/config")
async def get_webhook_config(session: AsyncSession = Depends(get_session), _=Depends(ADMIN)) -> dict[str, Any]:
    return await WebhookService(session).get_config()


@router.put("/config")
async def update_webhook_config(
    payload: WebhookConfigRequest,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(ADMIN),
) -> dict[str, Any]:
    await set_config(
        session=session,
        key="webhooks",
        value=payload.model_dump(),
        user_id=current_user.id,
        reason="Updated organizational webhook notification settings",
    )
    return await WebhookService(session).get_config()


@router.post("/test")
async def test_webhook(
    payload: TestWebhookRequest,
    session: AsyncSession = Depends(get_session),
    _=Depends(ADMIN),
) -> dict[str, Any]:
    return await WebhookService(session).test_webhook(payload.webhook_url, payload.provider)
