import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, UUIDMixin


class ValidationResult(Base, UUIDMixin):
    """One run of Pipeline 2 over one plan (SRS Steps 29-38)."""
    __tablename__ = "validation_results"

    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("onboarding_plans.id", ondelete="CASCADE"), index=True)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    rule_set_version: Mapped[str] = mapped_column(String(60))
    rule_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    enabled_rules: Mapped[list] = mapped_column(JSONB, default=list)

    # The six SRS metrics.
    mandatory_requirement_coverage_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_traceability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    requirement_consistency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    missing_requirement_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unsupported_requirement_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contradiction_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    extra_metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    counts_by_severity: Mapped[dict] = mapped_column(JSONB, default=dict)
    rule_summaries: Mapped[dict] = mapped_column(JSONB, default=dict)
    verification_status: Mapped[str] = mapped_column(String(40))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    status_reasons: Mapped[list] = mapped_column(JSONB, default=list)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    findings = relationship("ValidationFinding", back_populates="result", cascade="all, delete-orphan")


class ValidationFinding(Base, UUIDMixin):
    __tablename__ = "validation_findings"

    result_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("validation_results.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("onboarding_plans.id", ondelete="CASCADE"), index=True)
    rule_name: Mapped[str] = mapped_column(String(60), index=True)
    severity: Mapped[str] = mapped_column(String(12), index=True)
    item_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    item_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    requirement_code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    item_status: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    # OPEN until a reviewer decides. The original finding is never altered
    # beyond this marker; the decision itself lives in review_decisions.
    review_status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    result = relationship("ValidationResult", back_populates="findings")
