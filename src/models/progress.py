import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDMixin


class QuizAttempt(Base, UUIDMixin):
    """One answer to one quiz question (SRS Step 53). Correctness is decided
    server-side against the stored answer."""
    __tablename__ = "quiz_attempts"

    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("onboarding_plans.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("quiz_questions.id", ondelete="SET NULL"), nullable=True, index=True)
    requirement_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    competency: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    answer: Mapped[list] = mapped_column(JSONB, default=list)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AssessmentResult(Base, UUIDMixin):
    __tablename__ = "assessment_results"

    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("onboarding_plans.id", ondelete="CASCADE"), index=True)
    assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assessments.id", ondelete="SET NULL"), nullable=True, index=True)
    competency: Mapped[str | None] = mapped_column(String(150), nullable=True)
    score: Mapped[float] = mapped_column(Float)
    passed: Mapped[bool] = mapped_column(Boolean)
    assessor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criteria_scores: Mapped[dict] = mapped_column(JSONB, default=dict)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
