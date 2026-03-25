from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

import app.modules  # noqa: F401
from app.api.errors import APIError, handle_api_error, handle_http_exception, handle_validation_error
from app.api.routers.auth import router as auth_router
from app.api.routers.health import router as health_router
from app.api.routers.usage import router as usage_router
from app.core.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name)
    application.add_exception_handler(APIError, handle_api_error)
    application.add_exception_handler(RequestValidationError, handle_validation_error)
    application.add_exception_handler(StarletteHTTPException, handle_http_exception)
    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(usage_router)
    return application


app = create_app()
