"""ASGI entrypoint. Run: ``uvicorn main:app --reload`` (repo root, after ``pip install -e .``)."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from admin.api.v1.router import router as admin_router
from auth.api.v1.router import router as auth_router
from config import get_settings
from config.sentry import SentryUserMiddleware, init_sentry
from core.api.v1.router import router as core_router
from notifications.api.v1.router import router as notifications_router
from services.redis import get_redis_service
from services.storage import get_storage_service

init_sentry(component="api")
logger = logging.getLogger(__name__)

_PUBLIC_IMAGE_HEADERS = {
    "Cache-Control": "public, max-age=31536000, immutable",
    "Access-Control-Allow-Origin": "*",
    "Cross-Origin-Resource-Policy": "cross-origin",
}

_DEV_APP_ENVS = frozenset({"local", "development"})


def _openapi_enabled() -> bool:
    """OpenAPI/Swagger solo in locale e development (non staging/production)."""
    return get_settings().app_env in _DEV_APP_ENVS


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    if settings.uses_redis_refresh_store:
        get_redis_service().connect()
    yield
    if settings.uses_redis_refresh_store:
        get_redis_service().close()


def create_app() -> FastAPI:
    openapi = _openapi_enabled()
    app = FastAPI(
        title="tab-be",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if openapi else None,
        redoc_url="/redoc" if openapi else None,
        openapi_url="/openapi.json" if openapi else None,
        swagger_ui_parameters={"persistAuthorization": True} if openapi else None,
    )
    app.add_middleware(SentryUserMiddleware)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])
    app.include_router(core_router, prefix="/api/v1/core", tags=["core"])
    app.include_router(notifications_router, prefix="/api/v1/notifications", tags=["notifications"])

    @app.get("/media/{key:path}", include_in_schema=False)
    def get_media(key: str) -> Response:
        """Avatar/cover: disco in locale, proxy dal Bucket Railway in produzione."""
        try:
            payload = get_storage_service().read_bytes(key)
        except HTTPException:
            raise
        if payload is None:
            logger.warning("media.not_found key=%s", key)
            raise HTTPException(status_code=404, detail="Not found")
        data, content_type = payload
        return Response(
            content=data,
            media_type=content_type,
            headers=_PUBLIC_IMAGE_HEADERS,
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        settings = get_settings()
        payload: dict[str, str] = {"status": "ok"}
        if settings.uses_redis_refresh_store:
            payload["redis"] = "ok" if get_redis_service().ping() else "unavailable"
            if payload["redis"] != "ok":
                payload["status"] = "degraded"
        else:
            payload["redis"] = "skipped"
        return payload

    if get_settings().app_env in _DEV_APP_ENVS:

        @app.get("/sentry-debug", include_in_schema=False)
        async def sentry_debug() -> None:
            _ = 1 / 0

    return app


app = create_app()
