"""Pipeline 1 output, persisted. Source references are stored as the model
wrote them (plain strings, not foreign keys) so Pipeline 2 can catch a
fabricated or stale reference instead of the database silently rejecting it."""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class SourceRefMixin:
    requirement_code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    source_document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_section_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_chunk_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    mandatory: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    priority: Mapped[str | None] = mapped_column(String(12), nullable=True)
    due_stage: Mapped[str | None] = mapped_column(String(30), nullable=True)


class CompletionMixin:
    completion_status: Mapped[str] = mapped_column(String(20), default="NOT_STARTED")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_outdated: Mapped[bool] = mapped_column(Boolean, default=False)


class PromptTemplate(Base, UUIDMixin):
    __tablename__ = "prompt_templates"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_prompt_template_version"),)

    name: Mapped[str] = mapped_column(String(80))
    version: Mapped[str] = mapped_column(String(20))
    purpose: Mapped[str] = mapped_column(Text)
    file_path: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    output_schema: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OnboardingPlan(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "onboarding_plans"

    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), index=True)
    job_role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_roles.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Lifecycle: GENERATED, VALIDATED, APPROVED, REJECTED, SUPERSEDED
    status: Mapped[str] = mapped_column(String(30), default="GENERATED", index=True)
    # Plan-level verification (SRS Step 47), set by Pipeline 2 only.
    verification_status: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    prompt_template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("prompt_templates.id"), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(20))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source_document_versions: Mapped[list] = mapped_column(JSONB, default=list)
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    gaps: Mapped[list] = mapped_column(JSONB, default=list)
    excluded_chunks: Mapped[list] = mapped_column(JSONB, default=list)

    modules = relationship("PlanModule", back_populates="plan", cascade="all, delete-orphan",
                           order_by="PlanModule.sequence")


class PlanModule(Base, UUIDMixin, TimestampMixin, SourceRefMixin, CompletionMixin):
    """SRS Step 14."""
    __tablename__ = "plan_modules"

    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("onboarding_plans.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(150), nullable=True)
    competency: Mapped[str | None] = mapped_column(String(150), nullable=True)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    learning_objectives: Mapped[list] = mapped_column(JSONB, default=list)
    key_concepts: Mapped[list] = mapped_column(JSONB, default=list)
    required_source_documents: Mapped[list] = mapped_column(JSONB, default=list)
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    learning_activities: Mapped[list] = mapped_column(JSONB, default=list)
    assessment_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    completion_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirement_codes: Mapped[list] = mapped_column(JSONB, default=list)
    scenarios: Mapped[list] = mapped_column(JSONB, default=list)
    regeneration_count: Mapped[int] = mapped_column(Integer, default=0)

    plan = relationship("OnboardingPlan", back_populates="modules")
    checklist = relationship("ChecklistItem", cascade="all, delete-orphan", back_populates="module",
                         order_by="[ChecklistItem.position, ChecklistItem.id]")
    tasks = relationship("PlanTask", cascade="all, delete-orphan", back_populates="module",
                         order_by="[PlanTask.position, PlanTask.id]")
    quiz = relationship("QuizQuestion", cascade="all, delete-orphan", back_populates="module",
                         order_by="[QuizQuestion.position, QuizQuestion.id]")
    assessments = relationship("Assessment", cascade="all, delete-orphan", back_populates="module",
                         order_by="[Assessment.position, Assessment.id]")


class ChecklistItem(Base, UUIDMixin, TimestampMixin, SourceRefMixin, CompletionMixin):
    """SRS Step 17."""
    __tablename__ = "checklist_items"

    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("onboarding_plans.id", ondelete="CASCADE"), index=True)
    module_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plan_modules.id", ondelete="CASCADE"), index=True)
    # Order within the parent, as generated. Without it PostgreSQL may return rows in
    # any order, so a ticked task could jump to another place after a save.
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    activity: Mapped[str] = mapped_column(Text)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    responsible_person: Mapped[str | None] = mapped_column(String(80), nullable=True)

    module = relationship("PlanModule", back_populates="checklist")


class PlanTask(Base, UUIDMixin, TimestampMixin, SourceRefMixin, CompletionMixin):
    """SRS Step 18."""
    __tablename__ = "plan_tasks"

    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("onboarding_plans.id", ondelete="CASCADE"), index=True)
    module_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plan_modules.id", ondelete="CASCADE"), index=True)
    # Order within the parent, as generated. Without it PostgreSQL may return rows in
    # any order, so a ticked task could jump to another place after a save.
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    description: Mapped[str] = mapped_column(Text)
    expected_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    completion_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)

    module = relationship("PlanModule", back_populates="tasks")


class QuizQuestion(Base, UUIDMixin, TimestampMixin, SourceRefMixin):
    """SRS Steps 20-21."""
    __tablename__ = "quiz_questions"

    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("onboarding_plans.id", ondelete="CASCADE"), index=True)
    module_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plan_modules.id", ondelete="CASCADE"), index=True)
    # Order within the parent, as generated. Without it PostgreSQL may return rows in
    # any order, so a ticked task could jump to another place after a save.
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    question_type: Mapped[str] = mapped_column(String(40))
    question: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSONB, default=list)
    correct_answer: Mapped[list] = mapped_column(JSONB, default=list)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_outdated: Mapped[bool] = mapped_column(Boolean, default=False)

    module = relationship("PlanModule", back_populates="quiz")


class Assessment(Base, UUIDMixin, TimestampMixin, SourceRefMixin, CompletionMixin):
    """SRS Steps 23-24."""
    __tablename__ = "assessments"

    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("onboarding_plans.id", ondelete="CASCADE"), index=True)
    module_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plan_modules.id", ondelete="CASCADE"), index=True)
    # Order within the parent, as generated. Without it PostgreSQL may return rows in
    # any order, so a ticked task could jump to another place after a save.
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    title: Mapped[str] = mapped_column(String(255))
    assessment_type: Mapped[str] = mapped_column(String(40))
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    passing_score: Mapped[float] = mapped_column(Float, default=70.0)

    module = relationship("PlanModule", back_populates="assessments")
    rubric = relationship("AssessmentRubricCriterion", cascade="all, delete-orphan", back_populates="assessment",
                          order_by="[AssessmentRubricCriterion.position, AssessmentRubricCriterion.id]")


class AssessmentRubricCriterion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "assessment_rubric_criteria"

    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    # Order within the parent, as generated. Without it PostgreSQL may return rows in
    # any order, so a ticked task could jump to another place after a save.
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    criterion: Mapped[str] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float)
    expected_performance: Mapped[str] = mapped_column(Text)
    pass_condition: Mapped[str] = mapped_column(Text)
    requirement_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    assessment = relationship("Assessment", back_populates="rubric")


class GenerationRun(Base, UUIDMixin):
    """Evidence for every generation (SRS Step 41, FR lxv)."""
    __tablename__ = "generation_runs"

    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("onboarding_plans.id", ondelete="SET NULL"), nullable=True, index=True
    )
    employee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    purpose: Mapped[str] = mapped_column(String(40), default="PLAN")
    prompt_template_version: Mapped[str] = mapped_column(String(60))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[list] = mapped_column(JSONB, default=list)
    source_documents: Mapped[list] = mapped_column(JSONB, default=list)
    token_usage: Mapped[dict] = mapped_column(JSONB, default=dict)
    raw_request: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
