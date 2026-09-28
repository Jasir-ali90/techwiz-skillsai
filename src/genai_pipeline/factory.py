"""Builds the provider chain: the primary provider, then the fallbacks.

Provider, model and key come from Settings; provider endpoints and default
models come from config/generation.yaml. Nothing is hard-coded beyond a
default model name when GENAI_MODEL is left empty.
"""
import logging

from src.core.config import get_settings
from src.genai_pipeline.client import GenAIClient, GenAIPermanentError, PermanentFailure

logger = logging.getLogger("skillsprint.genai")
DEFAULT_MODELS = {"anthropic": "claude-opus-5"}


def _build_one(name: str, config: dict) -> GenAIClient:
    settings = get_settings()
    params = config.get("parameters", {})
    timeout = float(params.get("timeout_seconds", 120))
    if name == "anthropic":
        from src.genai_pipeline.anthropic_client import AnthropicClient

        return AnthropicClient(api_key=settings.genai_api_key,
                               model=settings.genai_model or DEFAULT_MODELS["anthropic"], timeout_seconds=timeout)
    if name == "offline":
        from src.genai_pipeline.offline_client import OfflineClient

        offline = config.get("offline", {})
        return OfflineClient(model=offline.get("model", "deterministic-template-v1"), config=offline)
    preset = (config.get("providers") or {}).get(name)
    if preset is None:
        raise PermanentFailure("unknown_provider", f"Unknown GenAI provider '{name}'")
    from src.genai_pipeline.openai_compat_client import OpenAICompatibleClient

    key = getattr(settings, preset["key_setting"], "") if preset.get("key_setting") else None
    model = (getattr(settings, preset["model_setting"], "") if preset.get("model_setting") else "") or preset["model"]
    base_url = (getattr(settings, preset["base_url_setting"], "") if preset.get("base_url_setting") else "") \
        or preset["base_url"]
    # The primary provider may use GENAI_MODEL / GENAI_API_KEY instead.
    if name == settings.genai_provider.lower():
        model = settings.genai_model or model
        key = key or settings.genai_api_key or None
    if preset.get("key_setting") and not key and not preset.get("key_optional"):
        raise PermanentFailure("missing_api_key", f"{preset['key_setting'].upper()} is not set")
    return OpenAICompatibleClient(name, base_url, model, key or None, int(preset.get("max_tokens", 32000)),
                                  preset.get("json_mode", "json_object"),
                                  float(preset.get("timeout_seconds", timeout)),
                                  max_request_tokens=preset.get("max_request_tokens"),
                                  limit_note=preset.get("limit_note"), local=bool(preset.get("local")))


def chain_names(config: dict) -> list[str]:
    settings = get_settings()
    primary = (settings.genai_provider or "offline").lower()
    raw = settings.genai_fallback_providers.strip()
    if raw.lower() == "none":
        fallbacks: list[str] = []
    elif raw:
        fallbacks = [p.strip().lower() for p in raw.split(",") if p.strip()]
    else:
        fallbacks = [p.lower() for p in config.get("fallback_chain", [])]
    return list(dict.fromkeys([primary] + fallbacks))


def build_chain(config: dict) -> tuple[list[GenAIClient], list[dict]]:
    """Returns the usable clients in order, and why any provider was skipped."""
    clients, skipped = [], []
    for name in chain_names(config):
        try:
            clients.append(_build_one(name, config))
        except PermanentFailure as exc:
            skipped.append({"provider": name, "kind": exc.kind, "reason": str(exc)})
            logger.info("GenAI provider %s skipped: %s", name, exc)
    if not clients:
        raise GenAIPermanentError(
            "No GenAI provider is usable: " + "; ".join(f"{s['provider']}: {s['reason']}" for s in skipped)
            + ". Set GENAI_API_KEY or GEMINI_API_KEY, or add 'offline' to GENAI_FALLBACK_PROVIDERS.",
            details={"skipped": skipped},
        )
    return clients, skipped


def build_client(config: dict) -> GenAIClient:
    """The first usable provider (kept for callers that need a single client)."""
    return build_chain(config)[0][0]
