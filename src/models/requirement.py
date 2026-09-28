import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin
from src.models.enums import MappingMethod, Priority, RequirementType


class Requirement(Base, UUIDMixin, TimestampMixin):
    """One row of the Role Requirement Matrix answer key. SRS Step 10.

    Built by deterministic Python only; the AI that writes plans never writes
    its own answer key.
    """

    __tablename__ = "requirements"

    requirement_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    # document_code:section:sentence. Version independent, so the same clause
    # keeps its code when a new document version is uploaded.
    source_key: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    statement: Mapped[str] = mapped_column(Text)
    requirement_type: Mapped[RequirementType] = mapped_column(
        SAEnum(RequirementType, name="requirement_type")
    )
    competency: Mapped[str] = mapped_column(String(150))
    policy_requirement: Mapped[str | None] = mapped_column(Text, nullable=True)
    process_requirement: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[Priority] = mapped_column(SAEnum(Priority, name="priority"))
    is_compliance: Mapped[bool] = mapped_column(Boolean, default=False)
    deadline_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    source_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    source_document_code: Mapped[str] = mapped_column(String(60), index=True)
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True
    )
    source_chunk_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    source_section_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)

    assessment_required: Mapped[bool] = mapped_column(Boolean, default=False)
    assessment_topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    applies_to_all_roles: Mapped[bool] = mapped_column(Boolean, default=False)
    conditions: Mapped[dict] = mapped_column(JSONB, default=dict)

    extraction_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    extraction_method: Mapped[str] = mapped_column(String(200))
    manually_overridden: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    # Set when a higher-precedence document states the same obligation
    # differently. An overridden requirement stays on record but leaves the
    # Matrix, so plans follow the authoritative source.
    overridden_by: Mapped[str | None] = mapped_column(String(20), nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    role_mappings = relationship(
        "RoleRequirement", back_populates="requirement", cascade="all, delete-orphan"
    )


class RoleRequirement(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "role_requirements"
    __table_args__ = (
        UniqueConstraint("job_role_id", "requirement_id", name="uq_role_requirement"),
    )

    job_role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_roles.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requirements.id", ondelete="CASCADE"), index=True
    )
    is_mandatory_for_role: Mapped[bool] = mapped_column(Boolean)
    priority_for_role: Mapped[Priority] = mapped_column(SAEnum(Priority, name="priority"))
    mapping_reason: Mapped[str] = mapped_column(Text)
    mapping_method: Mapped[MappingMethod] = mapped_column(
        SAEnum(MappingMethod, name="mapping_method")
    )

    requirement = relationship("Requirement", back_populates="role_mappings")
    job_role = relationship("JobRole")


class Prerequisite(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "prerequisites"
    __table_args__ = (
        UniqueConstraint("requirement_id", "depends_on_requirement_id", name="uq_prerequisite"),
        CheckConstraint("requirement_id <> depends_on_requirement_id", name="ck_no_self_prerequisite"),
    )

    requirement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requirements.id", ondelete="CASCADE"), index=True
    )
    depends_on_requirement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requirements.id", ondelete="CASCADE"), index=True
    )
    reason: Mapped[str] = mapped_column(Text)
    method: Mapped[str] = mapped_column(String(60), default="EXPLICIT_MARKER")
