import uuid
from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document, DocumentChunk
from src.models.enums import DocumentStatus
from src.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    model = Document

    async def list_ids(self, active_only: bool = False) -> list[uuid.UUID]:
        stmt = select(Document.id).order_by(Document.document_code, Document.version)
        if active_only:
            stmt = stmt.where(Document.status == DocumentStatus.ACTIVE)
        return list(await self.session.scalars(stmt))

    async def list_all(self, active_only: bool = False) -> list[Document]:
        stmt = select(Document).order_by(Document.document_code, Document.version)
        if active_only:
            stmt = stmt.where(Document.status == DocumentStatus.ACTIVE)
        return list(await self.session.scalars(stmt))

    async def by_ids(self, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Document]:
        if not ids:
            return {}
        rows = await self.session.scalars(select(Document).where(Document.id.in_(ids)))
        return {d.id: d for d in rows}

    async def versions_of(self, document_code: str) -> list[Document]:
        stmt = (
            select(Document)
            .where(Document.document_code == document_code)
            .order_by(Document.version)
        )
        return list(await self.session.scalars(stmt))

    async def previous_version(self, document: Document) -> Document | None:
        if document.supersedes_id:
            return await self.get(document.supersedes_id)
        stmt = (
            select(Document)
            .where(
                Document.document_code == document.document_code,
                Document.version < document.version,
            )
            .order_by(Document.version.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)


class ChunkRepository(BaseRepository[DocumentChunk]):
    model = DocumentChunk

    async def for_document(
        self, document_id: uuid.UUID, missing_embedding_only: bool = False
    ) -> list[DocumentChunk]:
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.sequence)
        )
        if missing_embedding_only:
            stmt = stmt.where(DocumentChunk.embedding.is_(None))
        return list(await self.session.scalars(stmt))

    async def count_for_document(self, document_id: uuid.UUID) -> int:
        return await self.session.scalar(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document_id)
        ) or 0

    async def set_embeddings(self, pairs: list[tuple[uuid.UUID, list[float]]]) -> None:
        for chunk_id, vector in pairs:
            await self.session.execute(
                update(DocumentChunk).where(DocumentChunk.id == chunk_id).values(embedding=vector)
            )

    async def coverage(self) -> tuple[int, int]:
        total = await self.session.scalar(select(func.count(DocumentChunk.id))) or 0
        embedded = await self.session.scalar(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.embedding.is_not(None))
        ) or 0
        return total, embedded

    async def nearest(
        self,
        vector: list[float],
        limit: int,
        active_only: bool = True,
        exclude_suspicious: bool = False,
        document_ids: Sequence[uuid.UUID] | None = None,
    ) -> list[tuple[DocumentChunk, Document, float]]:
        """Cosine distance ranking. Obsolete documents are excluded by default so a
        superseded policy can never be cited as a live source."""
        distance = DocumentChunk.embedding.cosine_distance(vector).label("distance")
        stmt = (
            select(DocumentChunk, Document, distance)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.embedding.is_not(None))
            .order_by(distance)
            .limit(limit)
        )
        if active_only:
            stmt = stmt.where(Document.status == DocumentStatus.ACTIVE)
        if exclude_suspicious:
            stmt = stmt.where(DocumentChunk.is_suspicious.is_(False))
        if document_ids:
            stmt = stmt.where(Document.id.in_(document_ids))
        rows = await self.session.execute(stmt)
        return [(chunk, doc, float(dist)) for chunk, doc, dist in rows.all()]

    async def with_documents(
        self, active_only: bool = True, embedded_only: bool = False
    ) -> list[tuple[DocumentChunk, Document]]:
        stmt = (
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .order_by(Document.document_code, Document.version, DocumentChunk.sequence)
        )
        if active_only:
            stmt = stmt.where(Document.status == DocumentStatus.ACTIVE)
        if embedded_only:
            stmt = stmt.where(DocumentChunk.embedding.is_not(None))
        rows = await self.session.execute(stmt)
        return [(c, d) for c, d in rows.all()]

    async def by_codes(self, codes: Sequence[str]) -> list[DocumentChunk]:
        if not codes:
            return []
        return list(
            await self.session.scalars(select(DocumentChunk).where(DocumentChunk.chunk_code.in_(codes)))
        )

    async def by_ids(self, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, DocumentChunk]:
        if not ids:
            return {}
        rows = await self.session.scalars(select(DocumentChunk).where(DocumentChunk.id.in_(ids)))
        return {c.id: c for c in rows}
