"""The provider fallback chain and the OpenAI-compatible (Gemini) client.
Every provider is mocked: no network, no key, no cost."""
import asyncio
import json

import httpx
import pytest

from src.core.app_config import load_yaml
from src.core.config import get_settings
from src.genai_pipeline.client import (
    Completion,
    GenAIClient,
    GenAIPermanentError,
    GenAIRequest,
    GenAIRetriesExhausted,
    PermanentFailure,
    RetryableFailure,
    generate_with_fallback,
)
from src.genai_pipeline.factory import build_chain, chain_names
from src.genai_pipeline.openai_compat_client import OpenAICompatibleClient
from src.schemas.generation import GeneratedPlan

PLAN = {"employee_code": "E1", "role_code": "BACKEND_DEV", "plan_title": "t", "summary": "s", "modules": [], "gaps": []}


def request():
    return GenAIRequest(system="s", prompt="Return JSON.", output_model=GeneratedPlan, context={},
                        parameters={"temperature": 0.0, "seed": 42})


class Scripted(GenAIClient):
    def __init__(self, provider, script):
        self.provider, self.model, self.script, self.calls = provider, f"{provider}-model", list(script), 0

    async def complete(self, req, attempt):
        self.calls += 1
        step = self.script.pop(0) if self.script else self.script[-1]
        if isinstance(step, Exception):
            raise step
        return Completion(text=step)


def run(clients):
    return asyncio.run(generate_with_fallback(clients, request(), max_attempts=3, backoff_seconds=0))


# ------------------------------------------------------------ chain behaviour
def test_primary_success_never_touches_the_fallback():
    primary, fallback = Scripted("anthropic", [json.dumps(PLAN)]), Scripted("gemini", [json.dumps(PLAN)])
    outcome = run([primary, fallback])
    assert outcome.client is primary and fallback.calls == 0


def test_permanent_failure_falls_back_immediately():
    primary = Scripted("anthropic", [PermanentFailure("quota_exhausted", "no credit")])
    fallback = Scripted("gemini", [json.dumps(PLAN)])
    outcome = run([primary, fallback])
    assert outcome.client is fallback and primary.calls == 1
    assert [(a["provider"], a["status"]) for a in outcome.attempts] == [
        ("anthropic", "permanent_failure"), ("gemini", "ok")]


def test_exhausted_retries_fall_back_after_three_attempts():
    primary = Scripted("anthropic", [RetryableFailure("rate_limit", "429")] * 5)
    fallback = Scripted("gemini", ["not json", json.dumps(PLAN)])
    outcome = run([primary, fallback])
    assert primary.calls == 3 and fallback.calls == 2 and outcome.client is fallback
    assert len(outcome.attempts) == 5


def test_every_provider_failing_is_bounded_and_structured():
    clients = [Scripted(p, ["broken"] * 10) for p in ("anthropic", "gemini", "offline")]
    with pytest.raises(GenAIRetriesExhausted) as err:
        run(clients)
    assert [c.calls for c in clients] == [3, 3, 3]
    assert err.value.details["providers_tried"] == ["anthropic", "gemini", "offline"]
    assert {a["provider"] for a in err.value.details["attempts"]} == {"anthropic", "gemini", "offline"}


# ------------------------------------------------------------ chain construction
@pytest.fixture
def settings(monkeypatch):
    s = get_settings()
    for name, value in {"genai_provider": "anthropic", "genai_api_key": "", "genai_fallback_providers": "",
                        "gemini_api_key": "", "gemini_model": "", "genai_model": "",
                        "ollama_base_url": "", "ollama_model": "", "ollama_api_key": ""}.items():
        monkeypatch.setattr(s, name, value)
    return s


def test_default_chain_is_primary_then_gemini_then_local_llm_then_offline(settings):
    assert chain_names(load_yaml("generation")) == ["anthropic", "gemini", "ollama", "offline"]


def test_providers_without_keys_are_skipped_with_reason(settings):
    clients, skipped = build_chain(load_yaml("generation"))
    # Ollama needs no key, so it stays in the chain even with nothing configured.
    assert [c.provider for c in clients] == ["ollama", "offline"]
    assert {s["provider"]: s["kind"] for s in skipped} == {"anthropic": "missing_api_key", "gemini": "missing_api_key"}


def test_ollama_defaults_and_environment_overrides(settings):
    config = load_yaml("generation")
    local = next(c for c in build_chain(config)[0] if c.provider == "ollama")
    assert (local.base_url, local.model, local.api_key) == ("http://localhost:11434/v1/", "qwen2.5:3b", None)
    assert local.timeout >= 600 and local.max_request_tokens == 8000 and local.json_mode == "json_schema"
    settings.ollama_base_url, settings.ollama_model, settings.ollama_api_key = "http://ollama:11434/v1", "llama3.2:3b", "k"
    local = next(c for c in build_chain(config)[0] if c.provider == "ollama")
    assert (local.base_url, local.model, local.api_key) == ("http://ollama:11434/v1/", "llama3.2:3b", "k")


def test_prompt_too_big_for_local_model_skips_it_with_a_clear_reason(settings):
    calls = []
    local = next(c for c in build_chain(load_yaml("generation"))[0] if c.provider == "ollama")
    local.transport = httpx.MockTransport(lambda req: calls.append(req))
    big = GenAIRequest(system="s", prompt="x" * 160_000, output_model=GeneratedPlan, context={})
    with pytest.raises(PermanentFailure) as err:
        asyncio.run(local.complete(big, 1))
    assert err.value.kind == "request_too_large" and "context window" in str(err.value) and calls == []


def test_local_server_not_running_moves_on_without_retrying(settings):
    def refuse(req):
        raise httpx.ConnectError("connection refused", request=req)

    local = next(c for c in build_chain(load_yaml("generation"))[0] if c.provider == "ollama")
    local.transport = httpx.MockTransport(refuse)
    with pytest.raises(PermanentFailure) as err:
        asyncio.run(local.complete(request(), 1))
    assert err.value.kind == "not_running"


def test_gemini_key_enables_the_free_fallback(settings):
    settings.gemini_api_key = "AIza-test"
    clients, _ = build_chain(load_yaml("generation"))
    gemini = clients[0]
    assert gemini.provider == "gemini" and gemini.model == "gemini-3.8-flash"
    assert gemini.base_url == "https://generativelanguage.googleapis.com/v1beta/openai/"
    settings.gemini_model = "gemini-3.5-flash"
    assert build_chain(load_yaml("generation"))[0][0].model == "gemini-3.5-flash"


def test_gemini_as_primary_provider(settings):
    settings.genai_provider = "gemini"
    settings.genai_api_key = "AIza-primary"
    assert [c.provider for c in build_chain(load_yaml("generation"))[0]] == ["gemini", "ollama", "offline"]


def test_env_override_and_disable(settings):
    settings.genai_fallback_providers = "none"
    with pytest.raises(GenAIPermanentError, match="No GenAI provider is usable"):
        build_chain(load_yaml("generation"))
    settings.genai_fallback_providers = "offline"
    assert chain_names(load_yaml("generation")) == ["anthropic", "offline"]


# ------------------------------------------------------------ OpenAI-compatible client
def client_with(handler) -> OpenAICompatibleClient:
    return OpenAICompatibleClient("gemini", "https://generativelanguage.googleapis.com/v1beta/openai/",
                                  "gemini-3.8-flash", "AIza-test", 65536, "json_object",
                                  transport=httpx.MockTransport(handler))


def test_request_shape_and_successful_parse():
    seen = {}

    def handler(req: httpx.Request):
        seen["url"], seen["auth"], seen["body"] = str(req.url), req.headers["authorization"], json.loads(req.content)
        return httpx.Response(200, json={"id": "x", "choices": [{"message": {"content": json.dumps(PLAN)},
                                                                  "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 100, "completion_tokens": 50}})

    completion = asyncio.run(client_with(handler).complete(request(), 1))
    assert seen["url"].endswith("/v1beta/openai/chat/completions") and seen["auth"] == "Bearer AIza-test"
    assert seen["body"]["model"] == "gemini-3.8-flash"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in seen["body"]["messages"]] == ["system", "user"]
    assert json.loads(completion.text)["role_code"] == "BACKEND_DEV"
    assert completion.usage == {"input_tokens": 100, "output_tokens": 50}


@pytest.mark.parametrize("status, body, expected, kind", [
    (429, "Rate limit reached for requests per minute", RetryableFailure, "rate_limit"),
    (429, "Quota exceeded for quota metric GenerateRequestsPerDay", PermanentFailure, "quota_exhausted"),
    (401, "API key not valid", PermanentFailure, "authentication"),
    (403, "forbidden", PermanentFailure, "authentication"),
    (404, "model not found", PermanentFailure, "model_not_found"),
    (500, "internal", RetryableFailure, "server_error"),
    (503, "overloaded", RetryableFailure, "server_error"),
    (400, "bad request", PermanentFailure, "http_400"),
])
def test_http_errors_map_to_retryable_or_permanent(status, body, expected, kind):
    with pytest.raises(expected) as err:
        asyncio.run(client_with(lambda req: httpx.Response(status, text=body)).complete(request(), 1))
    assert err.value.kind == kind


def test_truncated_output_and_timeouts_are_retryable():
    truncated = lambda req: httpx.Response(200, json={"choices": [{"message": {"content": "{"},
                                                                   "finish_reason": "length"}]})
    with pytest.raises(RetryableFailure, match="max_tokens"):
        asyncio.run(client_with(truncated).complete(request(), 1))

    def slow(req):
        raise httpx.ReadTimeout("slow", request=req)

    with pytest.raises(RetryableFailure) as err:
        asyncio.run(client_with(slow).complete(request(), 1))
    assert err.value.kind == "timeout"


def test_oversized_request_is_skipped_before_any_call():
    calls = []
    client = OpenAICompatibleClient("groq", "https://api.groq.com/openai/v1", "openai/gpt-oss-120b", "gsk-test",
                                    32000, "json_object", max_request_tokens=8000,
                                    transport=httpx.MockTransport(lambda req: calls.append(req)))
    big = GenAIRequest(system="s", prompt="x" * 40000, output_model=GeneratedPlan, context={})
    with pytest.raises(PermanentFailure) as err:
        asyncio.run(client.complete(big, 1))
    assert err.value.kind == "request_too_large" and calls == []


def test_small_request_passes_the_size_check():
    ok = {"choices": [{"message": {"content": json.dumps(PLAN)}, "finish_reason": "stop"}]}
    client = OpenAICompatibleClient("groq", "https://api.groq.com/openai/v1", "openai/gpt-oss-120b", "gsk-test",
                                    32000, "json_object", max_request_tokens=8000,
                                    transport=httpx.MockTransport(lambda req: httpx.Response(200, json=ok)))
    assert json.loads(asyncio.run(client.complete(request(), 1)).text)["role_code"] == "BACKEND_DEV"


def test_http_413_is_request_too_large():
    with pytest.raises(PermanentFailure) as err:
        asyncio.run(client_with(lambda req: httpx.Response(413, text="Request too large")).complete(request(), 1))
    assert err.value.kind == "request_too_large"


def test_json_schema_mode_sends_a_bounded_schema():
    seen = {}

    def handler(req):
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(PLAN)}, "finish_reason": "stop"}]})

    client = OpenAICompatibleClient("ollama", "http://localhost:11434/v1", "qwen2.5:3b", None, 4096, "json_schema",
                                    transport=httpx.MockTransport(handler), local=True)
    asyncio.run(client.complete(request(), 1))
    fmt = seen["body"]["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["name"] == "GeneratedPlan"
    text = json.dumps(fmt["json_schema"]["schema"])
    assert '"maxLength": 600' in text and '"maxItems": 15' in text
