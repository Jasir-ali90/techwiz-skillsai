import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDMixin


class ImpactRecord(Base, UUIDMixin):
    """What a new document version changed and everything it touches
    (SRS Steps 57-59)."""
    __tablename__ = "impact_records"

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    previous_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    document_code: Mapped[str] = mapped_column(String(60), index=True)
    previous_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_version: Mapped[int] = mapped_column(Integer)
    changed_sections: Mapped[dict] = mapped_column(JSONB, default=dict)
    affected_requirement_ids: Mapped[list] = mapped_column(JSONB, default=list)
    affected_requirement_codes: Mapped[list] = mapped_column(JSONB, default=list)
    affected_item_ids: Mapped[dict] = mapped_column(JSONB, default=dict)
    reference_only_item_ids: Mapped[dict] = mapped_column(JSONB, default=dict)
    affected_plan_ids: Mapped[list] = mapped_column(JSONB, default=list)
    affected_employee_ids: Mapped[list] = mapped_column(JSONB, default=list)
    regeneration_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    regeneration_result: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
