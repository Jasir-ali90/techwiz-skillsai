"""Visibility into Pipeline 1's providers: the fallback chain as configured
right now, and a live ping per provider. Keys are never returned."""
import asyncio
import time

import httpx
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.app_config import get_config
from src.core.config import get_settings
from src.genai_pipeline.client import GenAIError, GenAIRequest, generate_structured
from src.genai_pipeline.factory import _build_one, build_chain, chain_names
from src.genai_pipeline.client import PermanentFailure


class _Ping(BaseModel):
    ok: bool


async def _probe_local(client) -> str | None:
    """For a local server (Ollama): None when it is up and has the model,
    otherwise a plain reason. Fast, so the status page never hangs on it."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as http:
            response = await http.get(client.base_url + "models")
        models = [m.get("id", "") for m in (response.json().get("data") or [])] if response.status_code == 200 else []
    except (httpx.HTTPError, ValueError):
        return f"Not running at {client.base_url.rstrip('/')}. Start it with: docker compose --profile llm up -d"
    if client.model not in models and f"{client.model}:latest" not in models:
        return f"Running, but model {client.model} is not downloaded yet (ollama pull {client.model})"
    return None


class GenAIService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def status(self) -> dict:
        config = await get_config(self.session, "generation")
        settings = get_settings()
        names = chain_names(config)
        try:
            clients, skipped = build_chain(config)
        except GenAIError as exc:
            clients, skipped = [], exc.details.get("skipped", [])
        usable = {c.provider: c.model for c in clients}
        presets = config.get("providers", {}) or {}
        local = [c for c in clients if presets.get(c.provider, {}).get("local")]
        down = dict(zip([c.provider for c in local], await asyncio.gather(*(_probe_local(c) for c in local))))
        providers = []
        for name in names:
            preset = presets.get(name, {})
            key_setting = preset.get("key_setting") or ("genai_api_key" if name == "anthropic" else None)
            providers.append({
                "provider": name,
                "role": "primary" if name == names[0] else "fallback",
                "usable": name in usable and not down.get(name),
                "local": bool(preset.get("local")) or name == "offline",
                "model": usable.get(name) or preset.get("model"),
                "key_configured": None if preset.get("key_optional") or not key_setting
                else bool(getattr(settings, key_setting, "")),
                "skip_reason": down.get(name) or next((s["reason"] for s in skipped if s["provider"] == name), None),
                "free_tier": name in ("gemini", "groq", "openrouter", "ollama", "offline"),
                "max_request_tokens": preset.get("max_request_tokens"),
                "limit_note": preset.get("limit_note"),
            })
        return {
            "primary": names[0],
            "chain": providers,
            "first_configured": clients[0].provider if clients else None,
            "retry": config.get("retry", {}),
            "available_providers": ["anthropic", *presets.keys(), "offline"],
        }

    async def test(self, provider: str) -> dict:
        config = await get_config(self.session, "generation")
        started = time.perf_counter()
        try:
            client = _build_one(provider.lower(), config)
        except PermanentFailure as exc:
            return {"provider": provider, "ok": False, "kind": exc.kind, "message": str(exc), "duration_ms": 0}
        request = GenAIRequest("Reply with JSON only.", 'Return {"ok": true} as JSON.', _Ping,
                               {"mode": "plan", "employee": {"employee_code": "PING", "full_name": "Ping"},
                                "role": {"code": "PING", "title": "Ping"}, "stages": [
                                    {"code": "DAY_1", "name": "Day 1", "sequence": 1, "offset_days": 1}],
                                "requirements": [], "gaps": []}, {})
        try:
            if provider.lower() == "offline":
                ok, message = True, "The offline generator needs no network or key."
            else:
                result = await generate_structured(client, request, max_attempts=1, backoff_seconds=0)
                ok, message = result.payload.ok, "Provider answered with valid JSON."
            return {"provider": provider, "model": client.model, "ok": ok, "message": message,
                    "duration_ms": int((time.perf_counter() - started) * 1000)}
        except GenAIError as exc:
            last = (exc.details.get("attempts") or [{}])[-1]
            return {"provider": provider, "model": client.model, "ok": False, "kind": last.get("kind"),
                    "message": last.get("error") or exc.message,
                    "duration_ms": int((time.perf_counter() - started) * 1000)}
