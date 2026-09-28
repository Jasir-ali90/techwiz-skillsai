from typing import Any
from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base, TimestampMixin, UUIDMixin


class AppConfig(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "app_config"
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)