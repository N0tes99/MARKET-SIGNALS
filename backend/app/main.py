"""Signal Engine FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings
from app.core.basic_auth import BasicAuthMiddleware
from app.core.site_gate import AccessGateMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle."""
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    is_prod = settings.app_env.lower() == "production"
    app = FastAPI(
        title=settings.app_name,
        description="AI-powered Market Intelligence Platform",
        version="0.1.0",
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Auth after CORS so preflight succeeds without credentials dance issues.
    # Last added runs first: SiteGate (human TOTP) then BasicAuth (machine).
    app.add_middleware(BasicAuthMiddleware)
    app.add_middleware(AccessGateMiddleware)

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
