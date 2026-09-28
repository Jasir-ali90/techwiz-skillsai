from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.app_config import AppConfig

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def load_yaml(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


async def get_config(session: AsyncSession, key: str) -> dict[str, Any]:
    """Database value wins over the YAML default, so an evaluator can change
    precedence or rules at runtime without touching the source code."""
    row = await session.scalar(select(AppConfig).where(AppConfig.key == key))
    if row is not None:
        return row.value
    return load_yaml(key)


async def set_config(
    session: AsyncSession, key: str, value: dict[str, Any], description: str | None = None
) -> AppConfig:
    row = await session.scalar(select(AppConfig).where(AppConfig.key == key))
    if row is None:
        row = AppConfig(key=key, value=value, version=1, description=description)
        session.add(row)
    else:
        row.value = value
        row.version += 1
        if description:
            row.description = description
    await session.commit()
    await session.refresh(row)
    return row


def resolve_precedence_rank(config: dict[str, Any], document_type: str) -> int:
    for rule in config.get("rules", []):
        if document_type in rule.get("document_types", []):
            return int(rule["rank"])
    return int(config.get("default_rank", 50))