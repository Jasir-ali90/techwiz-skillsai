import uuid

from pydantic import BaseModel, ConfigDict


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    chunk_code: str
    sequence: int
    section_id: str | None
    heading: str | None
    heading_path: str | None
    page_number: int | None
    paragraph_index: int | None
    content: str
    char_count: int
    token_estimate: int
    is_suspicious: bool
    suspicion_reasons: list


class ParseResult(BaseModel):
    document_id: uuid.UUID
    document_code: str
    parser: str
    page_count: int
    blocks_extracted: int
    chunks_created: int
    sections_found: int
    suspicious_chunks: int
    warnings: list[str]
    chunks_embedded: int = 0
    message: str


class SuspiciousChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    chunk_code: str
    section_id: str | None
    heading: str | None
    page_number: int | None
    content: str
    suspicion_reasons: list