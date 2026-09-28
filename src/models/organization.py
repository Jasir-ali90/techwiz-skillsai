import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin
from src.models.enums import ExperienceLevel, TrainingStatus, UserType


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(Text)
    user_type: Mapped[UserType] = mapped_column(SAEnum(UserType, name="user_type"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Department(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "departments"

    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    job_roles: Mapped[list["JobRole"]] = relationship(back_populates="department")


class JobRole(Base, UUIDMixin, TimestampMixin):
    """Admins must be able to add a brand-new role at runtime (SRS 1.8.3)."""
    __tablename__ = "job_roles"

    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    department_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("departments.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    department: Mapped["Department"] = relationship(back_populates="job_roles")


class OnboardingStage(Base, UUIDMixin, TimestampMixin):
    """Configurable stages (SRS Step 13). Duration changes are data edits."""
    __tablename__ = "onboarding_stages"

    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    sequence: Mapped[int] = mapped_column(Integer)
    offset_days: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Employee(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "employees"

    employee_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    job_role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_roles.id"))
    department_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("departments.id"))
    experience_level: Mapped[ExperienceLevel] = mapped_column(
        SAEnum(ExperienceLevel, name="experience_level")
    )
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    joining_date: Mapped[date] = mapped_column(Date)
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id"), nullable=True
    )
    required_competencies: Mapped[list] = mapped_column(JSONB, default=list)
    previous_experience: Mapped[str | None] = mapped_column(Text, nullable=True)
    training_status: Mapped[TrainingStatus] = mapped_column(
        SAEnum(TrainingStatus, name="training_status"),
        default=TrainingStatus.NOT_STARTED,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, unique=True
    )

    job_role: Mapped["JobRole"] = relationship()
    department: Mapped["Department"] = relationship()