"""Prints how many documents are stored (used by start.ps1 to decide whether
the demo data still needs loading). Exits 1 if the database can't be read."""
import asyncio
import sys

from sqlalchemy import func, select

from src.core.db import SessionLocal
from src.models.document import Document


async def main() -> int:
    try:
        async with SessionLocal() as session:
            print(await session.scalar(select(func.count()).select_from(Document)))
        return 0
    except Exception as exc:  # noqa: BLE001 - reported to the caller
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
