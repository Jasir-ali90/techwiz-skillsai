import asyncio
import uuid
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError, ValidationFailedError
from src.document_processing.chunker import chunk_document
from src.document_processing.docx_parser import parse_docx
from src.document_processing.pdf_parser import parse_pdf
from src.models.document import Document, DocumentChunk
from src.security.adversarial import scan_text
from src.services.embedding_service import EmbeddingService


class ParseService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def parse(self, document_id: uuid.UUID, force: bool = False) -> dict:
        document = await self.session.get(Document, document_id)
        if document is None:
            raise NotFoundError("Document not found")

        existing = await self.session.scalar(
            select(func.count(DocumentChunk.id)).where(
                DocumentChunk.document_id == document_id
            )
        )
        if existing and not force:
            raise ValidationFailedError(
                f"This document already has {existing} chunks. "
                "Send force=true to parse it again.",
                details={"existing_chunks": existing},
            )
        if existing:
            await self.session.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
            )

        path = Path(document.storage_path)
        if not path.exists():
            raise ValidationFailedError(
                f"The stored file is missing at {path}. Upload the document again."
            )

        parsers = {".pdf": parse_pdf, ".docx": parse_docx}
        if document.file_extension not in parsers:
            raise ValidationFailedError(
                f"No parser available for '{document.file_extension}' files"
            )
        extension = document.file_extension
        try:
            # PDF/DOCX parsing is CPU-bound; run it off the event loop so other requests keep flowing.
            parsed = await asyncio.to_thread(parsers[extension], str(path))
        except Exception as exc:  # a corrupt or crafted file must never surface as a 500
            await self.session.rollback()
            raise ValidationFailedError(
                f"The file could not be read as a {extension[1:].upper()}. "
                "It may be corrupt or not what its extension claims.",
                details={"parser_error": f"{type(exc).__name__}: {str(exc)[:200]}"},
            ) from exc

        if not parsed.blocks:
            raise ValidationFailedError(
                "No text could be extracted from this document",
                details={"warnings": parsed.warnings},
            )

        chunk_rows = chunk_document(parsed, document.document_code)
        suspicious_count = 0

        for row in chunk_rows:
            findings = scan_text(row["content"])
            if findings:
                suspicious_count += 1
            self.session.add(
                DocumentChunk(
                    document_id=document.id,
                    is_suspicious=bool(findings),
                    suspicion_reasons=findings,
                    **row,
                )
            )

        sections = {r["section_id"] for r in chunk_rows if r["section_id"]}
        document.parse_meta = {
            "parser": parsed.parser,
            "page_count": parsed.page_count,
            "blocks_extracted": len(parsed.blocks),
            "chunks_created": len(chunk_rows),
            "sections_found": sorted(sections),
            "suspicious_chunks": suspicious_count,
            "warnings": parsed.warnings,
        }

        await self.session.commit()

        # Embed now, at parse time, so no request ever pays for it later.
        embedded = (await EmbeddingService(self.session).embed_document(document.id))["chunks_embedded"]

        message = f"Created {len(chunk_rows)} chunks across {len(sections)} sections."
        if suspicious_count:
            message += (
                f" {suspicious_count} chunk(s) carry suspicious instructions and are "
                "flagged. They are stored as data and will never be executed."
            )

        return {
            "document_id": document.id,
            "document_code": document.document_code,
            "parser": parsed.parser,
            "page_count": parsed.page_count,
            "blocks_extracted": len(parsed.blocks),
            "chunks_created": len(chunk_rows),
            "sections_found": len(sections),
            "suspicious_chunks": suspicious_count,
            "warnings": parsed.warnings,
            "chunks_embedded": embedded,
            "message": message,
        }