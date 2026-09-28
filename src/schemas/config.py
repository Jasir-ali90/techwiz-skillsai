from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PrecedenceRule(BaseModel):
    rank: int = Field(ge=1, le=999)
    document_types: list[str] = Field(min_length=1)
    reason: str | None = None


class PrecedenceConfig(BaseModel):
    version: int = 1
    description: str | None = None
    rules: list[PrecedenceRule]
    default_rank: int = 50
    tie_breaker: str = "latest_effective_date"


class ConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: dict[str, Any]
    version: int
    description: str | None
    source: str


class ReindexResult(BaseModel):
    documents_updated: int
    changes: list[dict]