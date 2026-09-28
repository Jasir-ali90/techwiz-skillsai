import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.core.deps import get_current_user, require_roles, require_staff
from src.models.enums import UserType
from src.schemas.config import ConfigOut, PrecedenceConfig, ReindexResult
from src.services.config_service import ConfigService

ADMIN = require_roles(UserType.ADMIN)

router = APIRouter(prefix="/config", tags=["configuration"])


@router.get("/precedence", response_model=ConfigOut)
async def read_precedence(
    session: AsyncSession = Depends(get_session), _=Depends(require_staff)
):
    """The active precedence hierarchy. 'source' says whether it comes from the
    YAML default or from a runtime override stored in the database."""
    return await ConfigService(session).read("precedence")


@router.put("/precedence", response_model=ConfigOut)
async def update_precedence(
    payload: PrecedenceConfig,
    session: AsyncSession = Depends(get_session),
    _=Depends(ADMIN),
):
    """SRS 1.8.9: 'modify policy precedence' during evaluation, with no code change."""
    return await ConfigService(session).write_precedence(payload)


@router.post("/precedence/reapply", response_model=ReindexResult)
async def reapply_precedence(
    session: AsyncSession = Depends(get_session), _=Depends(ADMIN)
):
    """Re-rank stored documents against the current rules."""
    count, changes = await ConfigService(session).reapply_precedence()
    return ReindexResult(documents_updated=count, changes=changes)


@router.post("/precedence/resolve")
async def resolve_conflict(
    document_ids: list[uuid.UUID],
    session: AsyncSession = Depends(get_session),
    _=Depends(require_staff),
):
    """Which document wins a conflict, and why. Used by contradiction handling
    and demonstrable on its own during judging."""
    return await ConfigService(session).resolve_conflict(document_ids)

@router.get("")
async def list_config_keys(session: AsyncSession = Depends(get_session), _=Depends(require_staff)):
    """Every configurable key, and whether it currently comes from YAML or the database."""
    return await ConfigService(session).list_keys()


@router.get("/{key}", response_model=ConfigOut)
async def read_config(key: str, session: AsyncSession = Depends(get_session), _=Depends(require_staff)):
    return await ConfigService(session).read_known(key)


@router.put("/{key}", response_model=ConfigOut)
async def write_config(
    key: str,
    value: dict,
    session: AsyncSession = Depends(get_session),
    _=Depends(ADMIN),
):
    """Runtime override for any configuration file under config/. The YAML stays
    as the default; the stored value wins until it is reset."""
    return await ConfigService(session).write_generic(key, value)


@router.delete("/{key}")
async def reset_config(key: str, session: AsyncSession = Depends(get_session), _=Depends(ADMIN)):
    """Drop the runtime override so the YAML default applies again."""
    return await ConfigService(session).reset(key)
