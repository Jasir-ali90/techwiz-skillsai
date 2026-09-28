import re
import uuid
from datetime import date
from pathlib import Path

import aiofiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.app_config import get_config, resolve_precedence_rank
from src.core.config import get_settings
from src.core.exceptions import ConflictError, ValidationFailedError
from src.document_validation.validators import (
    ValidationReport,
    check_dates,
    check_file_size,
    check_file_type,
    check_not_empty,
    check_version,
    compute_hash,
)
from src.models.document import Document
from src.models.enums import DocumentStatus, DocumentType
from src.models.organization import Department

UPLOAD_DIR = Path("uploads")
# Document codes become part of the stored file name, so only these characters
# are allowed: no dots, slashes or drive letters that could escape UPLOAD_DIR.
DOCUMENT_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,59}$")


class DocumentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def _latest(self, document_code: str) -> Document | None:
        stmt = (
            select(Document)
            .where(Document.document_code == document_code)
            .order_by(Document.version.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def upload(
        self,
        *,
        content: bytes,
        file_name: str,
        document_code: str,
        title: str,
        document_type: DocumentType,
        version: int,
        effective_date: date,
        expiry_date: date | None,
        department_id: uuid.UUID | None,
        notes: str | None,
        uploaded_by_id: uuid.UUID,
    ) -> tuple[Document, ValidationReport, uuid.UUID | None]:
        report = ValidationReport()
        if DOCUMENT_CODE.match(document_code or ""):
            report.add("document_code", True, document_code)
        else:
            report.add("document_code", False, "Use only letters, digits, '-' and '_' (up to 60), e.g. POL-HR-003")

        ext = check_file_type(file_name, content, report)
        check_file_size(content, self.settings.max_upload_mb, report)
        check_not_empty(content, report)
        check_dates(effective_date, expiry_date, report)

        content_hash = compute_hash(content)
        duplicate = await self.session.scalar(
            select(Document).where(Document.content_hash == content_hash)
        )
        if duplicate is not None:
            report.add(
                "duplicate_document", False,
                f"Identical content already stored as {duplicate.document_code} "
                f"v{duplicate.version}",
            )
        else:
            report.add("duplicate_document", True, "No identical document found")

        latest = await self._latest(document_code)
        check_version(version, latest.version if latest else None, report)

        if department_id is not None:
            dept = await self.session.get(Department, department_id)
            if dept is None:
                report.add("department", False, "The selected department does not exist")
            else:
                report.add("department", True, f"Department {dept.code}")
        else:
            report.add("department", True, "Company-wide document, no department set")

        if isinstance(document_type, DocumentType):
            report.add("document_category", True, document_type.value)
        else:
            report.add("document_category", False, "Unknown document category")

        if not report.ok:
            raise ValidationFailedError(
                "The document did not pass validation",
                details={"checks": report.checks},
            )

        precedence_config = await get_config(self.session, "precedence")
        rank = resolve_precedence_rank(precedence_config, document_type.value)

        UPLOAD_DIR.mkdir(exist_ok=True)
        stored_name = f"{document_code}_v{version}_{content_hash[:12]}{ext}"
        storage_path = UPLOAD_DIR / stored_name
        # Belt and braces: whatever the name, the file must land inside UPLOAD_DIR.
        if storage_path.resolve().parent != UPLOAD_DIR.resolve():
            raise ValidationFailedError("Invalid document code for storage", details={"checks": report.checks})
        async with aiofiles.open(storage_path, "wb") as fh:
            await fh.write(content)

        superseded_id: uuid.UUID | None = None
        if latest is not None and latest.status == DocumentStatus.ACTIVE:
            latest.status = DocumentStatus.OBSOLETE
            superseded_id = latest.id

        document = Document(
            document_code=document_code,
            title=title,
            document_type=document_type,
            version=version,
            status=DocumentStatus.ACTIVE,
            effective_date=effective_date,
            expiry_date=expiry_date,
            department_id=department_id,
            precedence_rank=rank,
            file_name=file_name,
            file_extension=ext,
            file_size_bytes=len(content),
            content_hash=content_hash,
            storage_path=str(storage_path),
            supersedes_id=superseded_id,
            uploaded_by_id=uploaded_by_id,
            notes=notes,
        )
        self.session.add(document)
        await self.session.commit()
        await self.session.refresh(document)
        return document, report, superseded_id