"""Loads the Nexora Labs demo end to end: seed data, documents, parsing,
embeddings, the Role Requirement Matrix, one employee per role, and
(optionally) a generated and validated plan for each.

Run:  python -m scripts.bootstrap_demo [--plans] [--with-v2]

It is idempotent: documents already stored are reused, not duplicated.
InfoSec v2 is left out by default so the policy-update flow (Step 9) can be
demonstrated live with POST /documents and POST /impact/analyse.
"""
import argparse
import asyncio
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select

from src.core.db import SessionLocal
from src.database.seed import seed
from src.models.document import Document
from src.models.enums import DocumentType, ExperienceLevel
from src.models.organization import Department, Employee, JobRole, User
from src.services.document_service import DocumentService
from src.services.matrix_service import MatrixService
from src.services.parse_service import ParseService

SAMPLES = Path("sample_documents")

# (file, code, title, type, version, effective date, department code or None)
DOCUMENTS = [
    ("POL-INFOSEC-001_v1.pdf", "POL-INFOSEC-001", "Information Security Policy", "INFOSEC_POLICY", 1, "2026-01-15", None),
    ("SOP-DEPLOY-007_v1.pdf", "SOP-DEPLOY-007", "Deployment and Release Procedure", "DEPARTMENT_SOP", 1, "2026-02-01", "INFRA"),
    ("FAQ-ENG-002_v1.pdf", "FAQ-ENG-002", "Engineering Onboarding FAQ", "FAQ", 1, "2026-03-10", "ENG"),
]
V2 = ("POL-INFOSEC-001_v2.pdf", "POL-INFOSEC-001", "Information Security Policy", "INFOSEC_POLICY", 2, "2026-07-01", None)
EXTENDED_MANIFEST = SAMPLES / "manifest.csv"

EMPLOYEES = [
    ("EMP-001", "Ayesha Khan", "BACKEND_DEV", ExperienceLevel.INTERMEDIATE, 5, "employee@nexoralabs.io"),
    ("EMP-002", "Bilal Ahmed", "SEO_SPEC", ExperienceLevel.BEGINNER, 12, None),
    ("EMP-003", "Chen Wei", "DEVOPS_ENG", ExperienceLevel.ADVANCED, 20, None),
    ("EMP-004", "Dana Iqbal", "SW_INTERN", ExperienceLevel.BEGINNER, 3, None),
    ("EMP-005", "Elif Demir", "FRONTEND_DEV", ExperienceLevel.INTERMEDIATE, 40, None),
    ("EMP-006", "Farhan Ali", "QA_ENG", ExperienceLevel.INTERMEDIATE, 8, None),
    ("EMP-007", "Grace Otieno", "PROJECT_MGR", ExperienceLevel.ADVANCED, 15, None),
    ("EMP-008", "Hira Siddiqui", "UIUX_DESIGNER", ExperienceLevel.INTERMEDIATE, 25, None),
    ("EMP-009", "Imran Shah", "DATA_ANALYST", ExperienceLevel.BEGINNER, 30, None),
    ("EMP-010", "Julia Novak", "SUPPORT_ENG", ExperienceLevel.INTERMEDIATE, 2, None),
]


def _extended() -> list[tuple]:
    if not EXTENDED_MANIFEST.exists():
        return []
    rows = []
    for line in EXTENDED_MANIFEST.read_text(encoding="utf-8").splitlines()[1:]:
        if line.strip():
            f, code, title, dtype, version, eff, dept = line.split(",")
            rows.append((f, code, title, dtype, int(version), eff, dept or None))
    return rows


async def upload_all(docs: list[tuple]) -> None:
    async with SessionLocal() as session:
        admin = await session.scalar(select(User).where(User.email == "admin@nexoralabs.io"))
        depts = {d.code: d.id for d in await session.scalars(select(Department))}
        for file, code, title, dtype, version, eff, dept in docs:
            existing = await session.scalar(
                select(Document).where(Document.document_code == code, Document.version == version))
            if existing is None:
                content = (SAMPLES / file).read_bytes()
                document, _, _ = await DocumentService(session).upload(
                    content=content, file_name=file, document_code=code, title=title,
                    document_type=DocumentType(dtype), version=version, effective_date=date.fromisoformat(eff),
                    expiry_date=None, department_id=depts.get(dept) if dept else None, notes="demo corpus",
                    uploaded_by_id=admin.id,
                )
                print(f"uploaded {code} v{version}")
            else:
                document = existing
                if dept and existing.department_id != depts.get(dept):
                    existing.department_id = depts.get(dept)
                    await session.commit()
            result = await ParseService(session).parse(document.id, force=True)
            print(f"  parsed {code} v{version}: {result['chunks_created']} chunks, "
                  f"{result['chunks_embedded']} embedded, {result['suspicious_chunks']} suspicious")


async def build_matrix() -> None:
    async with SessionLocal() as session:
        service = MatrixService(session)
        extracted = await service.extract()
        print("extract:", {k: extracted[k] for k in ("requirements_found", "created", "by_type", "rejected_sentences")})
        mapped = await service.map_roles()
        print("map-roles:", mapped["per_method"])
        prereq = await service.build_prerequisites()
        print(f"prerequisites: {prereq['edge_count']} edges, {len(prereq['cycles_rejected'])} cycle(s) rejected")
        precedence = await service.apply_precedence()
        print(f"precedence: {precedence['overridden_count']} requirement(s) overridden by a higher-ranked source")


async def employees() -> list:
    async with SessionLocal() as session:
        roles = {r.code: r for r in await session.scalars(select(JobRole))}
        ids = []
        for code, name, role_code, level, days_ago, email in EMPLOYEES:
            emp = await session.scalar(select(Employee).where(Employee.employee_code == code))
            if emp is None:
                role = roles[role_code]
                user = await session.scalar(select(User).where(User.email == email)) if email else None
                emp = Employee(employee_code=code, full_name=name, job_role_id=role.id,
                               department_id=role.department_id, experience_level=level,
                               joining_date=date.today() - timedelta(days=days_ago), location="Karachi",
                               required_competencies=[], user_id=user.id if user else None)
                session.add(emp)
                await session.commit()
                print(f"employee {code} {name} ({role_code})")
            ids.append(emp.id)
        return ids


async def plans(employee_ids) -> None:
    from src.services.generation_service import GenerationService
    from src.services.validation_service import ValidationService

    async with SessionLocal() as session:
        await GenerationService(session).register_templates()
    for eid in employee_ids:
        async with SessionLocal() as session:
            plan = await GenerationService(session).generate_plan(eid)
            report = await ValidationService(session).run(plan["id"] if isinstance(plan["id"], str) else plan["id"])
            print(f"plan {plan['title'][:50]:50} modules={plan['counts']['modules']:2} "
                  f"status={report['verification_status']} coverage={report['metrics']['mandatory_requirement_coverage_score']}")


async def main(args) -> None:
    await seed()
    docs = DOCUMENTS + _extended() + ([V2] if args.with_v2 else [])
    await upload_all(docs)
    await build_matrix()
    ids = await employees()
    if args.plans:
        import uuid

        await plans([uuid.UUID(str(i)) for i in ids])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plans", action="store_true", help="generate and validate a plan per employee")
    parser.add_argument("--with-v2", action="store_true", help="also upload InfoSec policy v2")
    asyncio.run(main(parser.parse_args()))
