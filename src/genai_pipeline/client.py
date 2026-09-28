"""Provider-agnostic GenAI client with bounded retries (SRS Step 39).

Pipeline 1 generates only. Nothing here validates, approves or scores a plan
beyond checking that the response has the required JSON shape.
"""
import asyncio
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from src.core.exceptions import AppError

logger = logging.getLogger("skillsprint.genai")

HARD_ATTEMPT_CAP = 3


class GenAIError(AppError):
    status_code = 502
    code = "genai_error"


class GenAIPermanentError(GenAIError):
    """Bad key, exhausted quota, rejected request. Retrying cannot help."""
    status_code = 503
    code = "genai_permanent_error"


class GenAIRetriesExhausted(GenAIError):
    code = "genai_retries_exhausted"


class RetryableFailure(Exception):
    def __init__(self, kind: str, message: str):
        self.kind = kind
        super().__init__(message)


class PermanentFailure(Exception):
    def __init__(self, kind: str, message: str):
        self.kind = kind
        super().__init__(message)


@dataclass
class GenAIRequest:
    system: str
    prompt: str
    output_model: type[BaseModel]
    context: dict[str, Any]
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class Completion:
    text: str
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] | None = None


@dataclass
class GenAIResult:
    payload: BaseModel
    raw_text: str
    usage: dict[str, Any]
    attempts: list[dict]


class GenAIClient(ABC):
    provider: str = "abstract"
    model: str = ""

    @abstractmethod
    async def complete(self, request: GenAIRequest, attempt: int) -> Completion:
        """One call to the provider. Raise RetryableFailure or PermanentFailure."""


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_json(text: str, model: type[BaseModel]) -> BaseModel:
    cleaned = _FENCE.sub("", text.strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise RetryableFailure("invalid_json", "Response contained no JSON object")
    try:
        data = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError as exc:
        raise RetryableFailure("invalid_json", f"Malformed JSON: {exc}") from exc
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        details = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:5])
        raise RetryableFailure("schema_mismatch", f"JSON does not match {model.__name__}: {details}") from exc


async def generate_structured(
    client: GenAIClient,
    request: GenAIRequest,
    max_attempts: int = 3,
    backoff_seconds: float = 1.0,
    backoff_cap_seconds: float = 8.0,
) -> GenAIResult:
    """Calls the provider until the response parses and matches the schema.

    The attempt count is capped at HARD_ATTEMPT_CAP whatever the config says,
    so a bad setting can never produce an unbounded loop.
    """
    max_attempts = max(1, min(int(max_attempts), HARD_ATTEMPT_CAP))
    attempts: list[dict] = []
    usage_total: dict[str, int] = {}

    for attempt in range(1, max_attempts + 1):
        started = time.perf_counter()
        record: dict[str, Any] = {"attempt": attempt}
        try:
            completion = await client.complete(request, attempt)
            for key, value in (completion.usage or {}).items():
                if isinstance(value, (int, float)):
                    usage_total[key] = usage_total.get(key, 0) + value
            payload = parse_json(completion.text, request.output_model)
            record.update(status="ok", duration_ms=_ms(started))
            attempts.append(record)
            logger.info("GenAI attempt %s/%s succeeded (%s)", attempt, max_attempts, client.provider)
            return GenAIResult(payload, completion.text, usage_total, attempts)
        except PermanentFailure as exc:
            record.update(status="permanent_failure", kind=exc.kind, error=str(exc), duration_ms=_ms(started))
            attempts.append(record)
            logger.error("GenAI attempt %s failed permanently: %s", attempt, exc)
            raise GenAIPermanentError(
                f"The GenAI provider rejected the request ({exc.kind}): {exc}",
                details={"attempts": attempts},
            ) from exc
        except RetryableFailure as exc:
            record.update(status="retryable_failure", kind=exc.kind, error=str(exc)[:500],
                          duration_ms=_ms(started))
            attempts.append(record)
            logger.warning("GenAI attempt %s/%s failed (%s): %s", attempt, max_attempts, exc.kind, exc)
        except Exception as exc:  # anything unexpected is treated as transient once
            record.update(status="retryable_failure", kind="unexpected", error=repr(exc)[:500],
                          duration_ms=_ms(started))
            attempts.append(record)
            logger.exception("GenAI attempt %s/%s raised unexpectedly", attempt, max_attempts)

        if attempt < max_attempts:
            await asyncio.sleep(min(backoff_cap_seconds, backoff_seconds * 2 ** (attempt - 1)))

    raise GenAIRetriesExhausted(
        f"No valid response after {max_attempts} attempts; the last failure was "
        f"{attempts[-1].get('kind')}: {attempts[-1].get('error')}",
        details={"attempts": attempts},
    )


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


@dataclass
class FallbackResult:
    result: GenAIResult
    client: GenAIClient
    attempts: list[dict]


async def generate_with_fallback(
    clients: list[GenAIClient],
    request: GenAIRequest,
    max_attempts: int = 3,
    backoff_seconds: float = 1.0,
    backoff_cap_seconds: float = 8.0,
) -> FallbackResult:
    """Tries each provider in turn, each with its own capped retries. The chain
    is finite, so the total number of calls is at most HARD_ATTEMPT_CAP per
    provider. Every attempt is logged with the provider that made it."""
    attempts: list[dict] = []
    last: GenAIError | None = None
    for index, client in enumerate(clients):
        try:
            result = await generate_structured(client, request, max_attempts, backoff_seconds, backoff_cap_seconds)
        except GenAIError as exc:
            for a in exc.details.get("attempts", []):
                attempts.append({**a, "provider": client.provider, "model": client.model})
            last = exc
            if index + 1 < len(clients):
                logger.warning("GenAI provider %s failed (%s); falling back to %s",
                               client.provider, exc.code, clients[index + 1].provider)
            continue
        attempts.extend({**a, "provider": client.provider, "model": client.model} for a in result.attempts)
        result.attempts = attempts
        return FallbackResult(result, client, attempts)
    last.details["attempts"] = attempts
    last.details["providers_tried"] = [c.provider for c in clients]
    raise last
