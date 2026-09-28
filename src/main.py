import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError

from src.api import (
    auth,
    config,
    document,
    genai,
    impact,
    matrix,
    organization,
    plans,
    progress,
    reports,
    review,
    search,
    validation,
)
from src.core.config import get_settings
from src.core.db import SessionLocal
from src.core.exceptions import AppError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("skillsprint")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the embedding model so the first real request is not slow.
    from src.document_processing.embeddings import warm

    try:
        await asyncio.to_thread(warm)
        logger.info("Embedding model loaded")
    except Exception as exc:  # the API still serves non-search routes
        logger.error("Embedding model failed to load: %s", exc)
    # Register prompt templates from disk so the prompt used is recorded.
    from src.services.generation_service import GenerationService

    try:
        async with SessionLocal() as session:
            registered = await GenerationService(session).register_templates()
        logger.info("Registered %d prompt template(s)", len(registered))
    except Exception as exc:
        logger.error("Prompt template registration failed: %s", exc)
    yield


app = FastAPI(title="SkillSprint AI", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    # Set CORS_ORIGINS to the frontend's URL in production.
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (auth, organization, document, config, search, matrix, plans, validation, review, progress, impact, reports, genai):
    app.include_router(module.router)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message, "details": exc.details},
    )


def _database_down(exc: BaseException) -> bool:
    """True when the error means PostgreSQL could not be reached at all."""
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, (ConnectionError, OSError, InterfaceError)):
            return True
        if isinstance(exc, (OperationalError, DBAPIError)) and exc.connection_invalidated:
            return True
        exc = exc.__cause__ or exc.__context__
    return False


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    # Always answer in the same JSON shape as AppError, so the frontend can show
    # a real message instead of "500 Internal Server Error"; never leak internals.
    if _database_down(exc):
        logger.error("Database unreachable during %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(status_code=503, content={
            "error": "database_unavailable",
            "message": "The database is not reachable. Start it with: docker start skillsprint_db",
            "details": {}})
    logger.exception("Unhandled error during %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={
        "error": "internal_error", "message": "Something went wrong on the server. The error has been logged.",
        "details": {}})


@app.get("/health")
async def health():
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
            vector = await session.scalar(
                text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector')")
            )
    except Exception as exc:  # report, don't crash: this is what the start script polls
        logger.warning("Health check: database unreachable: %s", exc)
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "unreachable",
                                                      "pgvector": None})
    return {"status": "ok", "database": "connected", "pgvector": bool(vector)}
