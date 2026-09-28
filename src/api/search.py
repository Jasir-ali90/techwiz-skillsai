import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.core.deps import get_current_user, require_roles
from src.models.enums import UserType
from src.services.embedding_service import EmbeddingService

ADMIN_TM = require_roles(UserType.ADMIN, UserType.TRAINING_MANAGER)

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/embed-all")
async def embed_all(
    force: bool = False,
    session: AsyncSession = Depends(get_session),
    _=Depends(ADMIN_TM),
):
    return await EmbeddingService(session).embed_all(force=force)


@router.post("/embed/{document_id}")
async def embed_document(
    document_id: uuid.UUID,
    force: bool = False,
    session: AsyncSession = Depends(get_session),
    _=Depends(ADMIN_TM),
):
    return await EmbeddingService(session).embed_document(document_id, force=force)


@router.get("/coverage")
async def coverage(session: AsyncSession = Depends(get_session), _=Depends(get_current_user)):
    return await EmbeddingService(session).coverage()


@router.get("")
async def semantic_search(
    q: str = Query(min_length=2, max_length=500),
    limit: int = Query(10, ge=1, le=50),
    min_similarity: float = Query(0.0, ge=0.0, le=1.0),
    active_only: bool = True,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    """Returning nothing is a correct answer when no document covers the topic."""
    results = await EmbeddingService(session).search(
        q, limit=limit, min_similarity=min_similarity, active_only=active_only
    )
    if user.user_type == UserType.EMPLOYEE:
        # Flagged (prompt-injection) text is for staff review only.
        results = [r for r in results if not r.get("is_suspicious")]
    return {"query": q, "count": len(results), "grounded": bool(results), "results": results}
