import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.document_processing.embeddings import embed_one, embed_texts
from src.repositories.document import ChunkRepository, DocumentRepository

EMBED_BATCH = 64


class EmbeddingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.documents = DocumentRepository(session)
        self.chunks = ChunkRepository(session)

    async def embed_document(self, document_id: uuid.UUID, force: bool = False) -> dict:
        document = await self.documents.get(document_id)
        if document is None:
            raise NotFoundError("Document not found")
        chunks = await self.chunks.for_document(document_id, missing_embedding_only=not force)

        embedded = 0
        for start in range(0, len(chunks), EMBED_BATCH):
            batch = chunks[start:start + EMBED_BATCH]
            # sentence-transformers is synchronous; keep it off the event loop.
            vectors = await asyncio.to_thread(embed_texts, [c.content for c in batch])
            await self.chunks.set_embeddings([(c.id, v) for c, v in zip(batch, vectors)])
            embedded += len(batch)
        await self.session.commit()

        return {
            "document_id": str(document.id),
            "document_code": document.document_code,
            "version": document.version,
            "chunks_embedded": embedded,
            "forced": force,
        }

    async def embed_all(self, force: bool = False) -> dict:
        per_document = []
        for document_id in await self.documents.list_ids():
            per_document.append(await self.embed_document(document_id, force=force))
        return {
            "documents": len(per_document),
            "chunks_embedded": sum(d["chunks_embedded"] for d in per_document),
            "per_document": per_document,
            **await self.coverage(),
        }

    async def coverage(self) -> dict:
        total, embedded = await self.chunks.coverage()
        return {"total_chunks": total, "embedded": embedded, "pending": total - embedded}

    async def search(
        self,
        query: str,
        limit: int = 10,
        min_similarity: float = 0.0,
        active_only: bool = True,
        exclude_suspicious: bool = False,
    ) -> list[dict]:
        vector = await asyncio.to_thread(embed_one, query)
        rows = await self.chunks.nearest(
            vector, limit=limit, active_only=active_only, exclude_suspicious=exclude_suspicious
        )
        results = []
        for chunk, doc, distance in rows:
            similarity = round(1.0 - distance, 4)
            if similarity < min_similarity:
                continue
            results.append({
                "similarity": similarity,
                "chunk_id": str(chunk.id),
                "chunk_code": chunk.chunk_code,
                "content": chunk.content,
                "is_suspicious": chunk.is_suspicious,
                "location": {
                    "section_id": chunk.section_id,
                    "heading": chunk.heading,
                    "heading_path": chunk.heading_path,
                    "page_number": chunk.page_number,
                    "paragraph_index": chunk.paragraph_index,
                },
                "document": {
                    "id": str(doc.id),
                    "document_code": doc.document_code,
                    "title": doc.title,
                    "document_type": doc.document_type.value,
                    "version": doc.version,
                    "status": doc.status.value,
                    "precedence_rank": doc.precedence_rank,
                },
            })
        return results
