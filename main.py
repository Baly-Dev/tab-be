"""ASGI entrypoint. Run: ``uvicorn main:app --reload`` (repo root, after ``pip install -e .``)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from auth.api.v1.router import router as auth_router
from config import get_settings
from config.sentry import SentryUserMiddleware, init_sentry
from services.redis import get_redis_service

init_sentry(component="api")

_DEV_APP_ENVS = frozenset({"local", "development"})


def _openapi_enabled() -> bool:
    """OpenAPI/Swagger only in local and development."""
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
        title="tab-intranet",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if openapi else None,
        redoc_url="/redoc" if openapi else None,
        openapi_url="/openapi.json" if openapi else None,
        swagger_ui_parameters={"persistAuthorization": True} if openapi else None,
    )
    app.add_middleware(SentryUserMiddleware)
    app.include_router(auth_router, prefix="/api/v1")

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
