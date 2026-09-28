"""Client for any OpenAI-compatible chat completions endpoint: Google Gemini
(free tier), Groq, OpenRouter or a local Ollama. Plain HTTP via httpx, so no
extra SDK is needed. The response is requested in JSON mode and then checked
against the plan schema like every other provider."""
from typing import Any

import httpx

from src.genai_pipeline.client import (
    Completion,
    GenAIClient,
    GenAIRequest,
    PermanentFailure,
    RetryableFailure,
)

DAILY_QUOTA_MARKERS = ("per day", "perday", "daily", "quota exceeded for quota metric", "billing")
# Limits added to the schema sent in json_schema mode. Small local models can get
# stuck repeating inside one string; with constrained decoding, a length cap is
# the only thing that stops them. Validation still uses the full Pydantic model.
MAX_STRING = 600
MAX_ITEMS = 15


def bounded_schema(node: Any) -> Any:
    """A copy of a JSON schema with maxLength on strings and maxItems on arrays."""
    if isinstance(node, list):
        return [bounded_schema(n) for n in node]
    if not isinstance(node, dict):
        return node
    out = {k: bounded_schema(v) for k, v in node.items()}
    if out.get("type") == "string" and "enum" not in out and "format" not in out:
        out.setdefault("maxLength", MAX_STRING)
    if out.get("type") == "array":
        out.setdefault("maxItems", MAX_ITEMS)
    return out


class OpenAICompatibleClient(GenAIClient):
    def __init__(self, provider: str, base_url: str, model: str, api_key: str | None,
                 max_tokens: int = 32000, json_mode: str | None = "json_object", timeout_seconds: float = 120.0,
                 transport: httpx.AsyncBaseTransport | None = None, max_request_tokens: int | None = None,
                 limit_note: str | None = None, local: bool = False):
        if not model:
            raise PermanentFailure("missing_model", f"No model configured for provider '{provider}'")
        self.provider = provider
        self.model = model
        self.base_url = base_url.rstrip("/") + "/"
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.json_mode = json_mode
        self.timeout = timeout_seconds
        self.transport = transport  # injectable for tests
        # Cap on prompt size per request, if known: a free tier's tokens-per-minute
        # limit, or a local model's context window. `limit_note` says which.
        self.max_request_tokens = max_request_tokens
        self.limit_note = limit_note or "tokens per minute on this tier"
        # A local server that refuses the connection is simply not running; retrying
        # it only delays the next provider, so that case is treated as permanent.
        self.local = local

    async def complete(self, request: GenAIRequest, attempt: int) -> Completion:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": request.system},
                         {"role": "user", "content": request.prompt}],
            "max_tokens": int(self.max_tokens),
        }
        if request.parameters.get("temperature") is not None:
            body["temperature"] = request.parameters["temperature"]
        if request.parameters.get("seed") is not None and self.provider in ("groq", "ollama", "openrouter"):
            body["seed"] = request.parameters["seed"]
        if self.json_mode == "json_schema" and request.output_model is not None:
            # Constrained decoding (Ollama structured outputs): the reply cannot
            # omit a required field, which small models otherwise often do.
            body["response_format"] = {"type": "json_schema", "json_schema": {
                "name": request.output_model.__name__, "strict": True,
                "schema": bounded_schema(request.output_model.model_json_schema())}}
        elif self.json_mode:
            body["response_format"] = {"type": "json_object" if self.json_mode == "json_schema" else self.json_mode}
        if self.max_request_tokens:
            # Rough prompt-size check (4 characters a token) so a request the
            # provider is certain to refuse is skipped without spending a call.
            estimate = (len(request.system) + len(request.prompt)) // 4
            if estimate > self.max_request_tokens:
                raise PermanentFailure(
                    "request_too_large",
                    f"{self.provider} accepts about {self.max_request_tokens} tokens ({self.limit_note}); "
                    f"this prompt alone is about {estimate}")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                response = await client.post(self.base_url + "chat/completions", json=body, headers=headers)
        except httpx.TimeoutException as exc:
            raise RetryableFailure("timeout", f"{self.provider} did not respond in time") from exc
        except httpx.ConnectError as exc:
            if self.local:
                raise PermanentFailure("not_running", f"{self.provider} is not running at {self.base_url}") from exc
            raise RetryableFailure("connection", f"Could not reach {self.provider}: {exc}") from exc
        except httpx.TransportError as exc:
            raise RetryableFailure("connection", f"Could not reach {self.provider}: {exc}") from exc

        if response.status_code != 200:
            self._raise_for(response)
        try:
            data = response.json()
            choice = data["choices"][0]
            text = choice["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise RetryableFailure("invalid_response", f"{self.provider} returned an unexpected body") from exc
        if choice.get("finish_reason") == "length":
            raise RetryableFailure("truncated", "The response hit max_tokens before the JSON closed")
        usage = data.get("usage") or {}
        return Completion(
            text=text,
            usage={"input_tokens": usage.get("prompt_tokens", 0), "output_tokens": usage.get("completion_tokens", 0)},
            raw={"id": data.get("id"), "finish_reason": choice.get("finish_reason"), "provider": self.provider},
        )

    def _raise_for(self, response: httpx.Response) -> None:
        status = response.status_code
        detail = response.text[:300]
        if status == 429:
            # A per-minute limit is worth retrying; an exhausted daily quota is
            # not, so the chain moves straight to the next provider.
            if any(m in detail.lower() for m in DAILY_QUOTA_MARKERS):
                raise PermanentFailure("quota_exhausted", f"{self.provider}: {detail}")
            raise RetryableFailure("rate_limit", f"{self.provider}: {detail}")
        if status in (401, 403):
            # 403 can mean a bad key, an API not enabled, or a project the
            # provider has blocked; pass the provider's own words through.
            raise PermanentFailure("authentication", f"{self.provider} refused the request ({status}): {detail}")
        if status == 404:
            raise PermanentFailure("model_not_found", f"{self.provider} has no model '{self.model}'")
        if status == 413:
            raise PermanentFailure("request_too_large", f"{self.provider}: {detail}")
        if status == 402:
            raise PermanentFailure("quota_exhausted", f"{self.provider}: {detail}")
        if status >= 500:
            raise RetryableFailure("server_error", f"{self.provider} {status}: {detail}")
        raise PermanentFailure(f"http_{status}", f"{self.provider} {status}: {detail}")
