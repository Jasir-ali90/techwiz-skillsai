import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    model: type[T]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, id_: uuid.UUID) -> T | None:
        return await self.session.get(self.model, id_)

    async def get_by(self, **filters: Any) -> T | None:
        stmt = select(self.model).filter_by(**filters)
        return await self.session.scalar(stmt)

    async def list(self, **filters: Any) -> list[T]:
        stmt = select(self.model).filter_by(**{k: v for k, v in filters.items() if v is not None})
        result = await self.session.scalars(stmt)
        return list(result)

    async def create(self, **data: Any) -> T:
        obj = self.model(**data)
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def update(self, obj: T, **data: Any) -> T:
        for key, value in data.items():
            if value is not None:
                setattr(obj, key, value)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj