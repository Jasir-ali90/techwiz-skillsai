from src.models.organization import Department, Employee, JobRole, OnboardingStage
from src.repositories.base import BaseRepository


class DepartmentRepository(BaseRepository[Department]):
    model = Department


class JobRoleRepository(BaseRepository[JobRole]):
    model = JobRole


class StageRepository(BaseRepository[OnboardingStage]):
    model = OnboardingStage


class EmployeeRepository(BaseRepository[Employee]):
    model = Employee