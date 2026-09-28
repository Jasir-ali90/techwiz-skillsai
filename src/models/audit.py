import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, event, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDMixin


class AppendOnlyError(RuntimeError):
    pass


class AuditLog(Base, UUIDMixin):
    """Append-only history of every change and decision (SRS Steps 48-49).

    There is no update or delete path: the ORM refuses both below, and the
    migration installs a database trigger that refuses them too.
    """

    __tablename__ = "audit_log"

    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(60))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    before: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


@event.listens_for(AuditLog, "before_update")
def _refuse_update(mapper, connection, target):
    raise AppendOnlyError("Audit log entries cannot be modified")


@event.listens_for(AuditLog, "before_delete")
def _refuse_delete(mapper, connection, target):
    raise AppendOnlyError("Audit log entries cannot be deleted")
