import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.audit import AuditLog


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(v) for v in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (uuid.UUID, date, datetime)):
        return str(value)
    return value


class AuditService:
    """Write and read only. There is deliberately no update or delete method."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def record(
        self,
        entity_type: str,
        entity_id: Any,
        action: str,
        actor_id: uuid.UUID | None = None,
        before: dict | None = None,
        after: dict | None = None,
        reason: str | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            entity_type=entity_type,
            entity_id=str(entity_id),
            action=action,
            actor_id=actor_id,
            before=jsonable(before) if before is not None else None,
            after=jsonable(after) if after is not None else None,
            reason=reason,
        )
        self.session.add(entry)
        return entry

    async def history(self, entity_type: str, entity_id: str) -> list[dict]:
        rows = await self.session.scalars(
            select(AuditLog)
            .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
            .order_by(AuditLog.created_at)
        )
        return [
            {
                "id": str(r.id),
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "action": r.action,
                "actor_id": str(r.actor_id) if r.actor_id else None,
                "before": r.before,
                "after": r.after,
                "reason": r.reason,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
