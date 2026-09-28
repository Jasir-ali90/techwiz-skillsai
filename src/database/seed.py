import asyncio
import os

from sqlalchemy import select

from src.core.db import SessionLocal
from src.core.security import hash_password
from src.models.enums import UserType
from src.models.organization import Department, JobRole, OnboardingStage, User

DEPARTMENTS = [
    ("ENG", "Engineering"),
    ("INFRA", "Infrastructure"),
    ("QA", "Quality Assurance"),
    ("DELIVERY", "Delivery"),
    ("MKT", "Marketing"),
    ("DESIGN", "Design"),
    ("DATA", "Data"),
    ("SUPPORT", "Support"),
]

ROLES = [
    ("SW_INTERN", "Software Intern", "ENG"),
    ("BACKEND_DEV", "Backend Developer", "ENG"),
    ("FRONTEND_DEV", "Frontend Developer", "ENG"),
    ("DEVOPS_ENG", "DevOps Engineer", "INFRA"),
    ("QA_ENG", "QA Engineer", "QA"),
    ("PROJECT_MGR", "Project Manager", "DELIVERY"),
    ("SEO_SPEC", "SEO Specialist", "MKT"),
    ("UIUX_DESIGNER", "UI/UX Designer", "DESIGN"),
    ("DATA_ANALYST", "Data Analyst", "DATA"),
    ("SUPPORT_ENG", "Technical Support Engineer", "SUPPORT"),
]

STAGES = [
    ("DAY_1", "Day 1", 1, 1),
    ("WEEK_1", "Week 1", 2, 7),
    ("WEEK_2", "Week 2", 3, 14),
    ("DAY_30", "First 30 Days", 4, 30),
    ("DAY_60", "First 60 Days", 5, 60),
    ("DAY_90", "First 90 Days", 6, 90),
]

# Passwords can be overridden per deployment with SEED_<NAME>_PASSWORD.
USERS = [
    ("admin@nexoralabs.io", "Aarav Admin", UserType.ADMIN, os.environ.get("SEED_ADMIN_PASSWORD", "Admin@123")),
    ("evaluator@nexoralabs.io", "Evan Evaluator", UserType.ADMIN,
     os.environ.get("SEED_EVALUATOR_PASSWORD", "Evaluate@123")),
    ("training@nexoralabs.io", "Tara Trainer", UserType.TRAINING_MANAGER, "Train@123"),
    ("reviewer@nexoralabs.io", "Raza Reviewer", UserType.REVIEWER, "Review@123"),
    ("manager@nexoralabs.io", "Maya Manager", UserType.MANAGER, "Manage@123"),
    ("employee@nexoralabs.io", "Emaan Employee", UserType.EMPLOYEE, "Employ@123"),
]


async def seed() -> None:
    async with SessionLocal() as session:
        dept_map = {}
        for code, name in DEPARTMENTS:
            dept = await session.scalar(select(Department).where(Department.code == code))
            if dept is None:
                dept = Department(code=code, name=name)
                session.add(dept)
                await session.flush()
            dept_map[code] = dept.id

        for code, title, dept_code in ROLES:
            exists = await session.scalar(select(JobRole).where(JobRole.code == code))
            if exists is None:
                session.add(
                    JobRole(code=code, title=title, department_id=dept_map[dept_code])
                )

        for code, name, seq, offset in STAGES:
            exists = await session.scalar(
                select(OnboardingStage).where(OnboardingStage.code == code)
            )
            if exists is None:
                session.add(
                    OnboardingStage(
                        code=code, name=name, sequence=seq, offset_days=offset
                    )
                )

        for email, name, utype, password in USERS:
            exists = await session.scalar(select(User).where(User.email == email))
            if exists is None:
                session.add(
                    User(
                        email=email,
                        full_name=name,
                        password_hash=hash_password(password),
                        user_type=utype,
                    )
                )

        await session.commit()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())