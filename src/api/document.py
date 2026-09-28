import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.db import get_session
from src.core.deps import get_current_user, require_roles, require_staff
from src.core.exceptions import NotFoundError
from src.models.document import Document
from src.models.enums import DocumentStatus, DocumentType, UserType
from src.schemas.document import DocumentOut, UploadResult
from src.services.document_service import DocumentService
from src.models.document import DocumentChunk
from src.schemas.chunk import ChunkOut, ParseResult, SuspiciousChunkOut
from src.services.parse_service import ParseService


ADMIN_TM = require_roles(UserType.ADMIN, UserType.TRAINING_MANAGER)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=UploadResult, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    document_code: str = Form(...),
    title: str = Form(...),
    document_type: DocumentType = Form(...),
    version: int = Form(1),
    effective_date: date = Form(...),
    expiry_date: date | None = Form(None),
    department_id: uuid.UUID | None = Form(None),
    notes: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    user=Depends(ADMIN_TM),
):
    # Read at most one byte past the limit: enough for the size check to reject
    # an oversized file, without ever holding a huge upload in memory.
    content = await file.read(get_settings().max_upload_mb * 1024 * 1024 + 1)
    document, report, superseded = await DocumentService(session).upload(
        content=content,
        file_name=file.filename or "unnamed",
        document_code=document_code,
        title=title,
        document_type=document_type,
        version=version,
        effective_date=effective_date,
        expiry_date=expiry_date,
        department_id=department_id,
        notes=notes,
        uploaded_by_id=user.id,
    )
    message = (
        f"Stored version {document.version}. Version {version - 1} is now obsolete."
        if superseded
        else f"Stored version {document.version}."
    )
    return UploadResult(
        document=DocumentOut.model_validate(document),
        validation=report.checks,
        superseded_document_id=superseded,
        message=message,
    )


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    status_filter: DocumentStatus | None = None,
    document_type: DocumentType | None = None,
    department_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(get_current_user),
):
    stmt = select(Document).order_by(Document.document_code, Document.version.desc())
    if status_filter:
        stmt = stmt.where(Document.status == status_filter)
    if document_type:
        stmt = stmt.where(Document.document_type == document_type)
    if department_id:
        stmt = stmt.where(Document.department_id == department_id)
    return list(await session.scalars(stmt))


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _=Depends(get_current_user),
):
    document = await session.get(Document, document_id)
    if document is None:
        raise NotFoundError("Document not found")
    return document


@router.get("/{document_id}/versions", response_model=list[DocumentOut])
async def document_versions(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _=Depends(get_current_user),
):
    """Version history for the document's code, newest first."""
    document = await session.get(Document, document_id)
    if document is None:
        raise NotFoundError("Document not found")
    stmt = (
        select(Document)
        .where(Document.document_code == document.document_code)
        .order_by(Document.version.desc())
    )
    return list(await session.scalars(stmt))


@router.post("/{document_id}/parse", response_model=ParseResult)
async def parse_document(
    document_id: uuid.UUID,
    force: bool = False,
    session: AsyncSession = Depends(get_session),
    _=Depends(ADMIN_TM),
):
    """SRS Steps 6-7: extract text, split into traceable chunks, scan for
    adversarial instructions."""
    return await ParseService(session).parse(document_id, force=force)


@router.get("/{document_id}/chunks", response_model=list[ChunkOut])
async def list_chunks(
    document_id: uuid.UUID,
    section_id: str | None = None,
    suspicious_only: bool = False,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.sequence)
    )
    if user.user_type == UserType.EMPLOYEE:
        # Flagged (prompt-injection) text is for staff review only.
        stmt = stmt.where(DocumentChunk.is_suspicious.is_(False))
    if section_id:
        stmt = stmt.where(DocumentChunk.section_id == section_id)
    if suspicious_only:
        stmt = stmt.where(DocumentChunk.is_suspicious.is_(True))
    return list(await session.scalars(stmt))


@router.get("/chunks/suspicious", response_model=list[SuspiciousChunkOut])
async def suspicious_chunks(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_staff),
):
    """Every flagged chunk across all documents. SRS FR xlix."""
    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.is_suspicious.is_(True))
        .order_by(DocumentChunk.document_id, DocumentChunk.sequence)
    )
    return list(await session.scalars(stmt))


@router.get("/chunks/{chunk_code}/trace")
async def trace_chunk(
    chunk_code: str,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    """Source traceability lookup. SRS 1.8.7: given any cited chunk, return the
    document, version, section and page it came from."""
    chunk = await session.scalar(
        select(DocumentChunk).where(DocumentChunk.chunk_code == chunk_code)
    )
    if chunk is None or (chunk.is_suspicious and user.user_type == UserType.EMPLOYEE):
        raise NotFoundError(f"No chunk found with code '{chunk_code}'")
    document = await session.get(Document, chunk.document_id)
    return {
        "chunk_code": chunk.chunk_code,
        "source": {
            "document_id": str(document.id),
            "document_code": document.document_code,
            "title": document.title,
            "document_type": document.document_type.value,
            "version": document.version,
            "status": document.status.value,
            "effective_date": str(document.effective_date),
            "precedence_rank": document.precedence_rank,
        },
        "location": {
            "section_id": chunk.section_id,
            "heading": chunk.heading,
            "heading_path": chunk.heading_path,
            "page_number": chunk.page_number,
            "paragraph_index": chunk.paragraph_index,
        },
        "content": chunk.content,
        "is_suspicious": chunk.is_suspicious,
        "suspicion_reasons": chunk.suspicion_reasons,
    }