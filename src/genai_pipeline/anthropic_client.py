"""Claude implementation of the GenAI client, using structured outputs so the
response is constrained to the plan schema."""
from typing import Any

import anthropic

from src.genai_pipeline.client import (
    Completion,
    GenAIClient,
    GenAIRequest,
    PermanentFailure,
    RetryableFailure,
)


class AnthropicClient(GenAIClient):
    provider = "anthropic"

    def __init__(self, api_key: str, model: str, timeout_seconds: float = 120.0):
        if not api_key:
            raise PermanentFailure("missing_api_key", "GENAI_API_KEY is not set")
        self.model = model
        # Retries are ours (bounded, logged); the SDK's own retries are off.
        self._client = anthropic.AsyncAnthropic(api_key=api_key, max_retries=0, timeout=timeout_seconds)

    async def complete(self, request: GenAIRequest, attempt: int) -> Completion:
        params = request.parameters
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": int(params.get("max_tokens", 16000)),
            "system": request.system,
            "messages": [{"role": "user", "content": request.prompt}],
            "output_format": request.output_model,
        }
        if params.get("effort"):
            kwargs["output_config"] = {"effort": params["effort"]}
        try:
            response = await self._client.messages.parse(**kwargs)
        except anthropic.AuthenticationError as exc:
            raise PermanentFailure("authentication", "The API key was rejected") from exc
        except anthropic.PermissionDeniedError as exc:
            raise PermanentFailure("permission_denied", str(exc)) from exc
        except anthropic.NotFoundError as exc:
            raise PermanentFailure("model_not_found", f"Model '{self.model}' is not available") from exc
        except anthropic.RateLimitError as exc:
            raise RetryableFailure("rate_limit", str(exc)) from exc
        except anthropic.BadRequestError as exc:
            message = str(exc)
            if "credit" in message.lower() or "billing" in message.lower():
                raise PermanentFailure("quota_exhausted", message) from exc
            raise PermanentFailure("bad_request", message) from exc
        except anthropic.APITimeoutError as exc:
            raise RetryableFailure("timeout", "The provider did not respond in time") from exc
        except anthropic.InternalServerError as exc:
            raise RetryableFailure("server_error", str(exc)) from exc
        except anthropic.APIConnectionError as exc:
            raise RetryableFailure("connection", str(exc)) from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code == 402:
                raise PermanentFailure("quota_exhausted", str(exc)) from exc
            if exc.status_code >= 500 or exc.status_code == 429:
                raise RetryableFailure("transient_status", str(exc)) from exc
            raise PermanentFailure(f"http_{exc.status_code}", str(exc)) from exc
        except ValueError as exc:  # structured output failed to parse client-side
            raise RetryableFailure("invalid_json", str(exc)) from exc

        if response.stop_reason == "refusal":
            raise PermanentFailure("refusal", "The model declined the request")
        if response.stop_reason == "max_tokens":
            raise RetryableFailure("truncated", "The response hit max_tokens before the JSON closed")
        text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        return Completion(text=text, usage=usage, raw={"id": response.id, "stop_reason": response.stop_reason})
