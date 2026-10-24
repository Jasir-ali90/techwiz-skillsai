import uuid
from typing import Any
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.core.deps import get_current_user
from src.services.certificate_service import CertificateService

router = APIRouter(prefix="/certificates", tags=["certificates"])


@router.get("/issue/{employee_id}")
async def issue_certificate(
    employee_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _=Depends(get_current_user),
) -> dict[str, Any]:
    """Issues a cryptographically signed onboarding certificate for an employee."""
    service = CertificateService(session)
    return await service.issue_certificate(employee_id)


@router.get("/verify/{certificate_id}")
async def verify_certificate(
    certificate_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Public verification endpoint for auditors and third parties."""
    service = CertificateService(session)
    return await service.verify(certificate_id)


@router.get("/download/{employee_id}")
async def download_certificate_pdf(
    employee_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _=Depends(get_current_user),
):
    """Generates and downloads a print-ready PDF certificate."""
    service = CertificateService(session)
    pdf_bytes = await service.generate_pdf(employee_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Nexora_Certificate_{employee_id}.pdf"},
    )
