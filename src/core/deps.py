import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.core.exceptions import AuthError, PermissionDeniedError
from src.core.security import decode_access_token
from src.models.enums import UserType
from src.models.organization import User

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    if creds is None:
        raise AuthError("Missing authentication token")
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired")
    except jwt.PyJWTError:
        raise AuthError("Invalid token")

    user = await session.scalar(select(User).where(User.email == payload.get("sub")))
    if user is None or not user.is_active:
        raise AuthError("User not found or inactive")
    return user


def require_roles(*allowed: UserType):
    async def _guard(user: User = Depends(get_current_user)) -> User:
        if user.user_type not in allowed:
            raise PermissionDeniedError(
                f"Requires one of: {', '.join(r.value for r in allowed)}"
            )
        return user

    return _guard

# Everyone except EMPLOYEE. Employees see their own onboarding (via /dashboard/me
# and their own plan) and the shared company knowledge (documents, search,
# requirements), but not other people's data, review material or settings.
require_staff = require_roles(UserType.ADMIN, UserType.TRAINING_MANAGER, UserType.MANAGER, UserType.REVIEWER)
