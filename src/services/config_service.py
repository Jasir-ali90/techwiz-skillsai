from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.app_config import CONFIG_DIR, get_config, load_yaml, resolve_precedence_rank, set_config
from src.core.exceptions import NotFoundError, ValidationFailedError
from src.models.app_config import AppConfig
from src.models.document import Document
from src.schemas.config import PrecedenceConfig


class ConfigService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def read(self, key: str) -> dict[str, Any]:
        row = await self.session.scalar(select(AppConfig).where(AppConfig.key == key))
        if row is not None:
            return {
                "key": key,
                "value": row.value,
                "version": row.version,
                "description": row.description,
                "source": "database",
            }
        return {
            "key": key,
            "value": load_yaml(key),
            "version": 0,
            "description": "Default loaded from config/%s.yaml" % key,
            "source": "yaml",
        }

    async def write_precedence(self, config: PrecedenceConfig) -> dict[str, Any]:
        seen: set[str] = set()
        for rule in config.rules:
            for doc_type in rule.document_types:
                if doc_type in seen:
                    raise ValidationFailedError(
                        f"'{doc_type}' appears in more than one precedence rule"
                    )
                seen.add(doc_type)

        row = await set_config(
            self.session,
            "precedence",
            config.model_dump(),
            description="Policy precedence updated at runtime",
        )
        return {
            "key": row.key,
            "value": row.value,
            "version": row.version,
            "description": row.description,
            "source": "database",
        }

    async def reapply_precedence(self) -> tuple[int, list[dict]]:
        """Re-rank every stored document against the current precedence rules.
        Run this after changing precedence so existing documents follow the new order."""
        config = await get_config(self.session, "precedence")
        documents = list(await self.session.scalars(select(Document)))

        changes: list[dict] = []
        for doc in documents:
            new_rank = resolve_precedence_rank(config, doc.document_type.value)
            if new_rank != doc.precedence_rank:
                changes.append({
                    "document_code": doc.document_code,
                    "version": doc.version,
                    "document_type": doc.document_type.value,
                    "old_rank": doc.precedence_rank,
                    "new_rank": new_rank,
                })
                doc.precedence_rank = new_rank

        if changes:
            await self.session.commit()
        return len(changes), changes

    async def resolve_conflict(self, document_ids: list) -> dict[str, Any]:
        """Given two or more documents, say which one wins and why.
        Lower rank wins; ties break on the later effective date."""
        docs = [await self.session.get(Document, d) for d in document_ids]
        docs = [d for d in docs if d is not None]
        if len(docs) < 2:
            raise ValidationFailedError("Provide at least two valid document ids")

        ordered = sorted(docs, key=lambda d: (d.precedence_rank, -d.effective_date.toordinal()))
        winner = ordered[0]
        runner_up = ordered[1]
        if winner.precedence_rank == runner_up.precedence_rank:
            reason = (
                f"Both rank {winner.precedence_rank}. "
                f"'{winner.document_code}' wins on the later effective date "
                f"({winner.effective_date})."
            )
        else:
            reason = (
                f"'{winner.document_code}' ranks {winner.precedence_rank}, ahead of "
                f"'{runner_up.document_code}' at {runner_up.precedence_rank}."
            )

        return {
            "winner": {
                "id": str(winner.id),
                "document_code": winner.document_code,
                "version": winner.version,
                "document_type": winner.document_type.value,
                "precedence_rank": winner.precedence_rank,
                "effective_date": str(winner.effective_date),
            },
            "ordering": [
                {
                    "document_code": d.document_code,
                    "version": d.version,
                    "document_type": d.document_type.value,
                    "precedence_rank": d.precedence_rank,
                    "effective_date": str(d.effective_date),
                }
                for d in ordered
            ],
            "reason": reason,
        }
    # ------------------------------------------------------------ generic keys
    @staticmethod
    def known_keys() -> list[str]:
        return sorted(p.stem for p in CONFIG_DIR.glob("*.yaml"))

    def _check_key(self, key: str) -> None:
        if key not in self.known_keys():
            raise NotFoundError(f"Unknown configuration key '{key}'", details={"known": self.known_keys()})

    async def list_keys(self) -> list[dict]:
        overrides = {r.key: r for r in await self.session.scalars(select(AppConfig))}
        return [
            {"key": k, "source": "database" if k in overrides else "yaml",
             "version": overrides[k].version if k in overrides else 0}
            for k in self.known_keys()
        ]

    async def read_known(self, key: str) -> dict[str, Any]:
        self._check_key(key)
        return await self.read(key)

    async def write_generic(self, key: str, value: dict[str, Any]) -> dict[str, Any]:
        self._check_key(key)
        if key == "precedence":
            return await self.write_precedence(PrecedenceConfig.model_validate(value))
        validate_config(key, value)
        row = await set_config(self.session, key, value, description=f"{key} updated at runtime")
        _clear_caches(key)
        return {"key": row.key, "value": row.value, "version": row.version,
                "description": row.description, "source": "database"}

    async def reset(self, key: str) -> dict[str, Any]:
        self._check_key(key)
        row = await self.session.scalar(select(AppConfig).where(AppConfig.key == key))
        if row is not None:
            await self.session.delete(row)
            await self.session.commit()
        _clear_caches(key)
        return {"key": key, "source": "yaml", "reset": row is not None}


def validate_config(key: str, value: dict[str, Any]) -> None:
    """Light structural checks so a typo cannot break the engine at runtime."""
    if key == "quiz_types":
        types = value.get("types")
        if not isinstance(types, list) or not all(isinstance(t, dict) and t.get("code") for t in types):
            raise ValidationFailedError("quiz_types needs a 'types' list of objects with a 'code'")
    if key == "validation_rules":
        if not isinstance(value.get("rules"), dict):
            raise ValidationFailedError("validation_rules needs a 'rules' mapping")
    if key == "business_rules":
        if not isinstance(value.get("rules"), list):
            raise ValidationFailedError("business_rules needs a 'rules' list")


def _clear_caches(key: str) -> None:
    if key == "adversarial_patterns":
        from src.security.adversarial import _compiled

        _compiled.cache_clear()
