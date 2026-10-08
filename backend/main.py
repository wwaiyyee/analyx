"""Analyx backend — FastAPI application factory."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.attestation import router as attestation_router
from backend.api.auth import router as auth_router
from backend.api.datasets import router as datasets_router
from backend.api.evidence import router as evidence_router
from backend.api.jobs import router as jobs_router
from backend.api.reports import router as reports_router
from backend.api.sessions import router as sessions_router
from backend.api.verify import router as verify_router
from backend.config import settings
from backend.core.errors import AnalyxError
from backend.db.session import init_db

__version__ = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle."""
    init_db()
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Analyx",
        description="Evidence-first AI data analyst",
        version=__version__,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global domain exception handler
    @app.exception_handler(AnalyxError)
    async def analyx_exception_handler(request: Request, exc: AnalyxError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    # Health check
    @app.get("/api/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "version": __version__,
            "git_commit": "HEAD",
            "backend": "local",
        }

    # Register API routers under /api
    app.include_router(auth_router, prefix="/api")
    app.include_router(datasets_router, prefix="/api")
    app.include_router(jobs_router, prefix="/api")
    app.include_router(sessions_router, prefix="/api")
    app.include_router(evidence_router, prefix="/api")
    app.include_router(reports_router, prefix="/api")
    app.include_router(attestation_router, prefix="/api")
    app.include_router(verify_router, prefix="/api")

    return app


app = create_app()

