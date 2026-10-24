"""Enterprise Webhook & Live Notifications Service (Slack & MS Teams).

Dispatches structured event cards to organizational webhooks for plan verification,
onboarding milestones, attrition risk alerts, and policy changes.
"""
import logging
from typing import Any
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.app_config import get_config

logger = logging.getLogger("skillsprint.webhooks")


class WebhookService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_config(self) -> dict[str, Any]:
        cfg = await get_config(self.session, "webhooks")
        return {
            "slack_url": cfg.get("slack_url", ""),
            "teams_url": cfg.get("teams_url", ""),
            "custom_url": cfg.get("custom_url", ""),
            "enabled_events": cfg.get("enabled_events", [
                "PLAN_VERIFIED", "BEHIND_SCHEDULE_ALERT", "CERTIFICATE_ISSUED", "POLICY_UPDATED"
            ]),
        }

    async def test_webhook(self, webhook_url: str, provider: str = "slack") -> dict[str, Any]:
        """Dispatches a test notification card to verify URL connectivity."""
        if not webhook_url or not webhook_url.startswith("http"):
            return {"success": False, "status_code": 400, "message": "Invalid or missing webhook URL."}

        # Rich Slack block kit test payload
        payload = {
            "text": "SkillSprint AI Integration Connected Successfully",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "SkillSprint AI · Webhook Connected", "emoji": True}
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Nexora Labs Enterprise Onboarding Intelligence*\nYour webhook integration has been validated. Real-time alerts for plan completions, verification outcomes, and policy changes will now be delivered here."
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": "Platform: *SkillSprint AI v0.2.0* · Category: *Generative AI PowerPlay*"}
                    ]
                }
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(webhook_url, json=payload)
                return {
                    "success": 200 <= res.status_code < 300,
                    "status_code": res.status_code,
                    "message": "Notification dispatched successfully." if 200 <= res.status_code < 300 else f"HTTP {res.status_code}: {res.text[:200]}",
                }
        except Exception as exc:
            logger.warning("Webhook dispatch failed: %s", exc)
            return {"success": False, "status_code": 500, "message": str(exc)}

    async def dispatch_event(self, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        """Dispatches event to active webhook URLs if enabled."""
        cfg = await self.get_config()
        if event_type not in cfg.get("enabled_events", []):
            return {"dispatched": False, "reason": "Event type not enabled in webhook configuration"}

        urls = [u for u in [cfg.get("slack_url"), cfg.get("teams_url"), cfg.get("custom_url")] if u and u.startswith("http")]
        if not urls:
            return {"dispatched": False, "reason": "No webhook URLs configured"}

        payload = {
            "event": event_type,
            "text": f"SkillSprint AI Notification: {event_type}",
            "data": data,
        }

        results = []
        async with httpx.AsyncClient(timeout=6.0) as client:
            for url in urls:
                try:
                    res = await client.post(url, json=payload)
                    results.append({"url": url[:30] + "...", "status": res.status_code, "success": res.status_code < 300})
                except Exception as exc:
                    results.append({"url": url[:30] + "...", "error": str(exc), "success": False})

        return {"dispatched": True, "results": results}
