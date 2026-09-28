import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.core.deps import get_current_user, require_roles, require_staff
from src.core.exceptions import ConflictError, NotFoundError
from src.models.enums import UserType
from src.repositories.organization import (
    DepartmentRepository,
    EmployeeRepository,
    JobRoleRepository,
    StageRepository,
)
from src.schemas.organization import (
    DepartmentCreate,
    DepartmentOut,
    EmployeeCreate,
    EmployeeOut,
    EmployeeUpdate,
    JobRoleCreate,
    JobRoleOut,
    JobRoleUpdate,
    StageCreate,
    StageOut,
    StageUpdate,
)

ADMIN = require_roles(UserType.ADMIN)
ADMIN_TM = require_roles(UserType.ADMIN, UserType.TRAINING_MANAGER)

router = APIRouter(tags=["organization"])


# ---------- departments ----------
@router.get("/departments", response_model=list[DepartmentOut])
async def list_departments(
    session: AsyncSession = Depends(get_session), _=Depends(get_current_user)
):
    return await DepartmentRepository(session).list()


@router.post("/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(ADMIN),
):
    repo = DepartmentRepository(session)
    if await repo.get_by(code=payload.code):
        raise ConflictError(f"Department code '{payload.code}' already exists")
    return await repo.create(**payload.model_dump())


# ---------- job roles ----------
@router.get("/roles", response_model=list[JobRoleOut])
async def list_roles(
    department_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(get_current_user),
):
    return await JobRoleRepository(session).list(department_id=department_id)


@router.post("/roles", response_model=JobRoleOut, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: JobRoleCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(ADMIN),
):
    """SRS 1.8.3: evaluators may add a brand-new role with no code change."""
    repo = JobRoleRepository(session)
    if await repo.get_by(code=payload.code):
        raise ConflictError(f"Role code '{payload.code}' already exists")
    if not await DepartmentRepository(session).get(payload.department_id):
        raise NotFoundError("Department not found")
    return await repo.create(**payload.model_dump())


@router.patch("/roles/{role_id}", response_model=JobRoleOut)
async def update_role(
    role_id: uuid.UUID,
    payload: JobRoleUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(ADMIN),
):
    repo = JobRoleRepository(session)
    role = await repo.get(role_id)
    if role is None:
        raise NotFoundError("Role not found")
    return await repo.update(role, **payload.model_dump(exclude_unset=True))


# ---------- onboarding stages ----------
@router.get("/stages", response_model=list[StageOut])
async def list_stages(
    session: AsyncSession = Depends(get_session), _=Depends(get_current_user)
):
    stages = await StageRepository(session).list()
    return sorted(stages, key=lambda s: s.sequence)


@router.post("/stages", response_model=StageOut, status_code=status.HTTP_201_CREATED)
async def create_stage(
    payload: StageCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(ADMIN),
):
    repo = StageRepository(session)
    if await repo.get_by(code=payload.code):
        raise ConflictError(f"Stage code '{payload.code}' already exists")
    return await repo.create(**payload.model_dump())


@router.patch("/stages/{stage_id}", response_model=StageOut)
async def update_stage(
    stage_id: uuid.UUID,
    payload: StageUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(ADMIN),
):
    """SRS 1.8.9: 'change onboarding duration' is a data edit, not a code edit."""
    repo = StageRepository(session)
    stage = await repo.get(stage_id)
    if stage is None:
        raise NotFoundError("Stage not found")
    return await repo.update(stage, **payload.model_dump(exclude_unset=True))


# ---------- employees ----------
@router.get("/employees", response_model=list[EmployeeOut])
async def list_employees(
    job_role_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_staff),
):
    return await EmployeeRepository(session).list(
        job_role_id=job_role_id, department_id=department_id
    )


@router.get("/employees/{employee_id}", response_model=EmployeeOut)
async def get_employee(
    employee_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_staff),
):
    employee = await EmployeeRepository(session).get(employee_id)
    if employee is None:
        raise NotFoundError("Employee not found")
    return employee


@router.post("/employees", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
async def create_employee(
    payload: EmployeeCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(ADMIN_TM),
):
    repo = EmployeeRepository(session)
    if await repo.get_by(employee_code=payload.employee_code):
        raise ConflictError(f"Employee code '{payload.employee_code}' already exists")
    role = await JobRoleRepository(session).get(payload.job_role_id)
    if role is None:
        raise NotFoundError("Job role not found")
    if not await DepartmentRepository(session).get(payload.department_id):
        raise NotFoundError("Department not found")
    return await repo.create(**payload.model_dump())


@router.patch("/employees/{employee_id}", response_model=EmployeeOut)
async def update_employee(
    employee_id: uuid.UUID,
    payload: EmployeeUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(ADMIN_TM),
):
    repo = EmployeeRepository(session)
    employee = await repo.get(employee_id)
    if employee is None:
        raise NotFoundError("Employee not found")
    return await repo.update(employee, **payload.model_dump(exclude_unset=True))