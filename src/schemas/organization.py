import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from src.models.enums import ExperienceLevel, TrainingStatus


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DepartmentCreate(BaseModel):
    code: str = Field(max_length=30)
    name: str = Field(max_length=120)
    description: str | None = None


class DepartmentOut(Out):
    id: uuid.UUID
    code: str
    name: str
    description: str | None


class JobRoleCreate(BaseModel):
    code: str = Field(max_length=40)
    title: str = Field(max_length=150)
    description: str | None = None
    department_id: uuid.UUID


class JobRoleUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    department_id: uuid.UUID | None = None
    is_active: bool | None = None


class JobRoleOut(Out):
    id: uuid.UUID
    code: str
    title: str
    description: str | None
    department_id: uuid.UUID
    is_active: bool


class StageCreate(BaseModel):
    code: str = Field(max_length=30)
    name: str = Field(max_length=80)
    sequence: int
    offset_days: int


class StageUpdate(BaseModel):
    name: str | None = None
    sequence: int | None = None
    offset_days: int | None = None
    is_active: bool | None = None


class StageOut(Out):
    id: uuid.UUID
    code: str
    name: str
    sequence: int
    offset_days: int
    is_active: bool


class EmployeeCreate(BaseModel):
    employee_code: str = Field(max_length=40)
    full_name: str = Field(max_length=150)
    job_role_id: uuid.UUID
    department_id: uuid.UUID
    experience_level: ExperienceLevel
    joining_date: date
    location: str | None = None
    manager_id: uuid.UUID | None = None
    required_competencies: list[str] = []
    previous_experience: str | None = None


class EmployeeUpdate(BaseModel):
    full_name: str | None = None
    job_role_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    experience_level: ExperienceLevel | None = None
    location: str | None = None
    manager_id: uuid.UUID | None = None
    required_competencies: list[str] | None = None
    previous_experience: str | None = None
    training_status: TrainingStatus | None = None


class EmployeeOut(Out):
    id: uuid.UUID
    employee_code: str
    full_name: str
    job_role_id: uuid.UUID
    department_id: uuid.UUID
    experience_level: ExperienceLevel
    location: str | None
    joining_date: date
    manager_id: uuid.UUID | None
    required_competencies: list
    previous_experience: str | None
    training_status: TrainingStatus