"""Test configuration.

* The GenAI provider is the deterministic offline one, so the suite runs with
  no key and no cost. Provider failures are simulated with scripted clients.
* Unit tests need nothing but Python. Tests marked `db` use a throwaway
  database, skillsprint_test, created fresh for each session and skipped when
  PostgreSQL is not reachable.
"""
import asyncio
import hashlib
import os
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

BASE_URL = os.environ.get("TEST_DATABASE_URL",
                          "postgresql+asyncpg://skillsprint:skillsprint@localhost:5432/skillsprint_test")
os.environ["DATABASE_URL"] = BASE_URL
os.environ["GENAI_PROVIDER"] = "offline"
# Never reach a real provider from tests, even if a key sits in .env.
os.environ["GENAI_FALLBACK_PROVIDERS"] = "none"
for _key in ("GENAI_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
    os.environ[_key] = ""
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hs256"

WORD = re.compile(r"[a-z0-9]+")


class HashEmbedder:
    """Deterministic bag-of-words vectors, so validation rules can be unit
    tested without loading the sentence-transformer."""

    dim = 384

    def __call__(self, texts):
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in WORD.findall(text.lower()):
                if len(word) < 3:
                    continue
                index = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dim
                out[row, index] += 1.0
            norm = np.linalg.norm(out[row])
            if norm:
                out[row] /= norm
        return out


@pytest.fixture
def embedder():
    return HashEmbedder()


def _db_available() -> bool:
    import asyncpg

    async def probe():
        conn = await asyncpg.connect(BASE_URL.replace("postgresql+asyncpg", "postgresql").rsplit("/", 1)[0] + "/postgres",
                                     timeout=3)
        await conn.close()

    try:
        asyncio.run(probe())
        return True
    except Exception:
        return False


DB_AVAILABLE = _db_available()


def pytest_collection_modifyitems(config, items):
    if DB_AVAILABLE:
        return
    skip = pytest.mark.skip(reason="PostgreSQL test database not reachable")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)


def _recreate_database() -> None:
    import asyncpg

    admin_url = BASE_URL.replace("postgresql+asyncpg", "postgresql").rsplit("/", 1)[0] + "/postgres"
    name = BASE_URL.rsplit("/", 1)[1]

    async def run():
        conn = await asyncpg.connect(admin_url)
        await conn.execute(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{name}' "
                           "AND pid <> pg_backend_pid()")
        await conn.execute(f'DROP DATABASE IF EXISTS "{name}"')
        await conn.execute(f'CREATE DATABASE "{name}"')
        await conn.close()

    asyncio.run(run())
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")


@pytest.fixture(scope="session")
def database():
    if not DB_AVAILABLE:
        pytest.skip("PostgreSQL test database not reachable")
    _recreate_database()
    return BASE_URL


@pytest.fixture(scope="session")
async def loaded(database):
    """Seed data, the three v1 documents, the Matrix and one employee per role."""
    from scripts.bootstrap_demo import DOCUMENTS, build_matrix, employees, upload_all
    from src.database.seed import seed

    await seed()
    await upload_all(DOCUMENTS)
    await build_matrix()
    ids = await employees()
    return {"employee_ids": ids}


@pytest.fixture(scope="session")
async def client(loaded):
    import httpx

    from src.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _token(client, email, password):
    response = await client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="session")
async def admin(client):
    return await _token(client, "admin@nexoralabs.io", "Admin@123")


@pytest.fixture(scope="session")
async def employee_login(client):
    return await _token(client, "employee@nexoralabs.io", "Employ@123")


@pytest.fixture(scope="session")
async def reviewer(client):
    return await _token(client, "reviewer@nexoralabs.io", "Review@123")


@pytest.fixture(scope="session")
async def employees_by_code(client, admin):
    response = await client.get("/employees", headers=admin)
    return {e["employee_code"]: e for e in response.json()}


@pytest.fixture(scope="session")
async def backend_plan(client, admin, employees_by_code):
    response = await client.post("/plans/generate", headers=admin,
                                 json={"employee_id": employees_by_code["EMP-001"]["id"]})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture(scope="session")
async def seo_plan(client, admin, employees_by_code):
    response = await client.post("/plans/generate", headers=admin,
                                 json={"employee_id": employees_by_code["EMP-002"]["id"]})
    assert response.status_code == 200, response.text
    return response.json()
