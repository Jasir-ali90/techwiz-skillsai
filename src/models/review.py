import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, event, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models.audit import AppendOnlyError
from src.models.base import Base, UUIDMixin


class ComparisonReport(Base, UUIDMixin):
    """GenAI result versus Python expected result, per Matrix requirement (Step 46)."""
    __tablename__ = "comparison_reports"

    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("onboarding_plans.id", ondelete="CASCADE"), index=True)
    validation_result_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("validation_results.id", ondelete="SET NULL"), nullable=True)
    rows: Mapped[list] = mapped_column(JSONB, default=list)
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConsistencyRun(Base, UUIDMixin):
    """Repeated generation under fixed parameters (Steps 44-45). Runs as a
    background job so the standard 30-second path is never slowed down."""
    __tablename__ = "consistency_runs"

    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("onboarding_plans.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    run_count: Mapped[int] = mapped_column(Integer)
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict)
    runs: Mapped[list] = mapped_column(JSONB, default=list)
    comparison: Mapped[dict] = mapped_column(JSONB, default=dict)
    consistency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    major_differences: Mapped[list] = mapped_column(JSONB, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReviewDecision(Base, UUIDMixin):
    """A reviewer's decision on a finding (Steps 48-49). Append-only: the
    original finding and item are snapshotted, and the row can never be
    changed or removed."""
    __tablename__ = "review_decisions"

    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("validation_findings.id", ondelete="RESTRICT"), index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("onboarding_plans.id", ondelete="RESTRICT"), index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    decision: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    original_finding: Mapped[dict] = mapped_column(JSONB)
    original_item: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    edited_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    outcome: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


@event.listens_for(ReviewDecision, "before_update")
def _refuse_update(mapper, connection, target):
    raise AppendOnlyError("Review decisions cannot be modified")


@event.listens_for(ReviewDecision, "before_delete")
def _refuse_delete(mapper, connection, target):
    raise AppendOnlyError("Review decisions cannot be deleted")
