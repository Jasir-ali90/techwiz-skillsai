import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    Index,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin
from src.models.enums import DocumentStatus, DocumentType
from pgvector.sqlalchemy import Vector


class Document(Base, UUIDMixin, TimestampMixin):
    """An uploaded company document. SRS Steps 5, 6, 8 and FR v-x."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("document_code", "version", name="uq_document_code_version"),
    )

    document_code: Mapped[str] = mapped_column(String(60), index=True)
    title: Mapped[str] = mapped_column(String(255))
    document_type: Mapped[DocumentType] = mapped_column(
        SAEnum(DocumentType, name="document_type")
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, name="document_status"),
        default=DocumentStatus.ACTIVE,
    )

    effective_date: Mapped[date] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id"), nullable=True
    )
    precedence_rank: Mapped[int] = mapped_column(Integer, default=50)

    file_name: Mapped[str] = mapped_column(String(255))
    file_extension: Mapped[str] = mapped_column(String(10))
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    storage_path: Mapped[str] = mapped_column(Text)

    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id"), nullable=True
    )
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    parse_meta: Mapped[dict] = mapped_column(JSONB, default=dict)

    department = relationship("Department")
    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentChunk.sequence",
    )


class DocumentChunk(Base, UUIDMixin, TimestampMixin):
    """A traceable slice of a document. SRS Steps 6-7 and FR viii-ix.

    Every chunk carries enough metadata that any generated sentence can be
    traced back to a document, a section and a physical location in the file.
    """

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_code", name="uq_chunk_per_document"),
        Index(
            "ix_document_chunks_embedding", "embedding",
            postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    chunk_code: Mapped[str] = mapped_column(String(60), index=True)
    sequence: Mapped[int] = mapped_column(Integer)

    section_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    heading: Mapped[str | None] = mapped_column(String(300), nullable=True)
    heading_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paragraph_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    content: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer)
    token_estimate: Mapped[int] = mapped_column(Integer)

    is_suspicious: Mapped[bool] = mapped_column(Boolean, default=False)
    suspicion_reasons: Mapped[list] = mapped_column(JSONB, default=list)

    document = relationship("Document", back_populates="chunks")