import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from src.models.enums import DocumentStatus, DocumentType


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_code: str
    title: str
    document_type: DocumentType
    version: int
    status: DocumentStatus
    effective_date: date
    expiry_date: date | None
    department_id: uuid.UUID | None
    precedence_rank: int
    file_name: str
    file_extension: str
    file_size_bytes: int
    content_hash: str
    supersedes_id: uuid.UUID | None
    notes: str | None
    created_at: datetime


class UploadResult(BaseModel):
    document: DocumentOut
    validation: list[dict]
    superseded_document_id: uuid.UUID | None = None
    message: str