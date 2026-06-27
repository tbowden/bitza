import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import (
    ConflictError,
    InvalidCredentialsError,
    InvalidTokenError,
    PermissionDeniedError,
    RevokedTokenError,
    SuperuserExistsError,
    UserNotFoundError,
    UserSuspendedError,
)
from app.db.session import SessionLocal, engine
from app.repositories.token_repository import TokenRepository
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Application lifespan — runs startup/shutdown logic
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Startup:
      • Log environment and DB path.
      • Run expired-token cleanup (cheap — keeps the whitelist table small).

    Shutdown:
      • Dispose the SQLAlchemy connection pool cleanly.
    """
    logger.info("Starting up [env=%s]", settings.APP_ENV)
    logger.info("Database: %s", settings.DATABASE_URL)

    # Clean up stale refresh tokens from previous sessions.
    try:
        db = SessionLocal()
        try:
            token_repo = TokenRepository(db)
            auth_svc = AuthService(db=db, user_repo=None, token_repo=token_repo)  # type: ignore[arg-type]
            count = auth_svc.cleanup_expired_tokens()
            if count:
                logger.info("Cleaned up %d expired refresh token(s)", count)
        finally:
            db.close()
    except Exception as exc:  # pragma: no cover
        logger.warning("Token cleanup on startup failed: %s", exc)

    yield  # application runs here

    logger.info("Shutting down — disposing connection pool")
    engine.dispose()


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # CORS — tighten origins for production in your .env.prod
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.APP_ENV != "prod" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # Mount versioned router
    # ------------------------------------------------------------------
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # ------------------------------------------------------------------
    # Global exception handlers
    # All our custom HTTPExceptions already serialise themselves, but we
    # add a catch-all so unexpected errors return JSON (not HTML).
    # ------------------------------------------------------------------

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected internal error occurred"},
        )

    # Health-check endpoint (no auth required — for Docker / reverse-proxy).
    @app.get("/health", tags=["health"], include_in_schema=True)
    def health_check() -> dict:
        return {"status": "ok", "env": settings.APP_ENV}

    return app


app = create_app()
