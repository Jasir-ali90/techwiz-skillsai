import asyncio

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.core.deps import require_roles
from src.models.enums import UserType
from src.reports.export import MEDIA_TYPES, render
from src.services.report_service import PDF_COLUMNS, REPORTS, ReportService

STAFF = require_roles(UserType.ADMIN, UserType.TRAINING_MANAGER, UserType.MANAGER, UserType.REVIEWER)
FORMAT = Query("json", pattern="^(json|csv|xlsx|pdf)$", description="json, csv, xlsx or pdf")

router = APIRouter(tags=["reports, export, search"])


@router.get("/reports")
async def list_reports(_=Depends(STAFF)):
    return [{"name": k, "title": v, "formats": ["json", "csv", "xlsx", "pdf"], "path": f"/reports/{k}"}
            for k, v in REPORTS.items()]


async def _report(name: str, format: str, session: AsyncSession):
    rows, summary = await ReportService(session).build(name)
    if format == "json":
        return {"report": name, "title": REPORTS[name], "summary": summary, "rows": rows}
    # pandas / openpyxl / reportlab are CPU-bound; keep them off the event loop.
    content = await asyncio.to_thread(render, rows, format, REPORTS[name], summary, PDF_COLUMNS.get(name))
    return Response(content, media_type=MEDIA_TYPES[format],
                    headers={"Content-Disposition": f'attachment; filename="{name}.{format}"'})


def _register(name: str, title: str) -> None:
    """One endpoint per SRS Step 62 report, each exportable in every format."""
    async def endpoint(format: str = FORMAT, session: AsyncSession = Depends(get_session), _=Depends(STAFF)):
        return await _report(name, format, session)

    endpoint.__name__ = f"report_{name.replace('-', '_')}"
    router.add_api_route(f"/reports/{name}", endpoint, methods=["GET"], summary=f"{title} report",
                         description=f"{title}. Add ?format=csv, xlsx or pdf to export.")


for _name, _title in REPORTS.items():
    _register(_name, _title)


@router.get("/search/records")
async def search_records(
    employee: str | None = None,
    role: str | None = None,
    department: str | None = None,
    module: str | None = None,
    policy: str | None = Query(None, description="Document code the plan cites, e.g. POL-INFOSEC-001"),
    status: str | None = Query(None, description="Training status, e.g. BEHIND_SCHEDULE"),
    verification: str | None = Query(None, description="Plan verification status, e.g. VERIFIED"),
    progress_min: float | None = Query(None, ge=0, le=100),
    progress_max: float | None = Query(None, ge=0, le=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _=Depends(STAFF),
):
    """One filter endpoint across employee, role, department, module, policy,
    status, progress and verification result (SRS Step 61)."""
    return await ReportService(session).search(employee, role, department, module, policy, status, verification,
                                               progress_min, progress_max, page, page_size)
