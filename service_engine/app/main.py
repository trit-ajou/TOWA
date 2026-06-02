from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette_compress import CompressMiddleware, remove_compress_type

import app.modules  # noqa: F401
from app.api.errors import APIError, handle_api_error, handle_http_exception, handle_validation_error
from app.api.routers.auth import router as auth_router
from app.api.routers.folders import router as folders_router
from app.api.routers.health import router as health_router
from app.api.routers.pages import router as pages_router
from app.api.routers.projects import router as projects_router
from app.api.routers.usage import router as usage_router
from app.core.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name)
    remove_compress_type("multipart/mixed")
    application.add_middleware(
        CompressMiddleware,
        minimum_size=settings.http_compression_minimum_size,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_exception_handler(APIError, handle_api_error)
    application.add_exception_handler(RequestValidationError, handle_validation_error)
    application.add_exception_handler(StarletteHTTPException, handle_http_exception)
    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(usage_router)
    application.include_router(folders_router)
    application.include_router(projects_router)
    application.include_router(pages_router)
    return application


app = create_app()
