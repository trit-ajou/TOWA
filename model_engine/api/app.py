from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import FastAPI, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .jobs import ModelJobError, ModelJobManager, submission_from_api_payload
from .schemas import (
    ModelJobCreateRequest,
    UsageJobCaptureRequest,
    UsageJobCreateRequest,
    UsageJobReleaseRequest,
)
from .service_bridge import (
    ServiceEngineBridgeClient,
    ServiceEngineHTTPError,
    ServiceEngineUnavailableError,
)
from .settings import get_settings


def create_app(
    *,
    job_manager: ModelJobManager | None = None,
) -> FastAPI:
    settings = get_settings()
    service_client_factory = lambda: _service_bridge_client()
    job_manager = job_manager or ModelJobManager(service_client_factory=service_client_factory)
    application = FastAPI(title=settings.app_name)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/healthz", tags=["infra"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @application.post("/v1/jobs", tags=["jobs"])
    def create_job(
        payload: ModelJobCreateRequest,
        authorization: Annotated[str | None, Header()] = None,
    ) -> JSONResponse:
        try:
            submission = submission_from_api_payload(payload)
            status_code, response = job_manager.create_job(
                submission,
                authorization=authorization,
            )
            return JSONResponse(status_code=status_code, content=response)
        except ModelJobError as exc:
            return _error_response(
                status_code=exc.status_code,
                code=exc.code,
                message=exc.message,
                retryable=exc.retryable,
                details=exc.details,
            )
        except ServiceEngineHTTPError as exc:
            return JSONResponse(status_code=exc.status_code, content=exc.payload)
        except ServiceEngineUnavailableError as exc:
            return _error_response(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="service_engine_unreachable",
                message=str(exc),
                retryable=True,
            )
        except (KeyError, TypeError, ValueError) as exc:
            return _error_response(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="model_validation_error",
                message=str(exc),
            )

    @application.get("/v1/jobs/{job_id}", tags=["jobs"])
    def get_job(job_id: str) -> JSONResponse:
        try:
            return JSONResponse(status_code=status.HTTP_200_OK, content=job_manager.get_job(job_id))
        except ModelJobError as exc:
            return _error_response(
                status_code=exc.status_code,
                code=exc.code,
                message=exc.message,
                retryable=exc.retryable,
                details=exc.details,
            )

    @application.get("/bridge/service/healthz", tags=["bridge"])
    def bridge_service_healthz() -> Any:
        client = _service_bridge_client()
        return _bridge_response(
            lambda: {
                "status": "ok",
                "service_engine_url": settings.service_engine_url,
                "service": client.get("/healthz"),
            }
        )

    @application.get("/bridge/service/auth/me", tags=["bridge"])
    def bridge_auth_me(
        authorization: Annotated[str | None, Header()] = None,
    ) -> Any:
        client = _service_bridge_client()
        return _bridge_response(lambda: client.get("/auth/me", authorization=authorization))

    @application.post("/bridge/service/usage/jobs", tags=["bridge"])
    def bridge_usage_job_create(
        payload: UsageJobCreateRequest,
        authorization: Annotated[str | None, Header()] = None,
    ) -> Any:
        client = _service_bridge_client()
        return _bridge_response(
            lambda: client.post(
                "/usage/jobs",
                body=payload.model_dump(),
                authorization=authorization,
            )
        )

    @application.post("/bridge/service/usage/jobs/{job_id}/capture", tags=["bridge"])
    def bridge_usage_job_capture(
        job_id: str,
        payload: UsageJobCaptureRequest,
        authorization: Annotated[str | None, Header()] = None,
    ) -> Any:
        client = _service_bridge_client()
        return _bridge_response(
            lambda: client.post(
                f"/usage/jobs/{job_id}/capture",
                body=payload.model_dump(),
                authorization=authorization,
            )
        )

    @application.post("/bridge/service/usage/jobs/{job_id}/release", tags=["bridge"])
    def bridge_usage_job_release(
        job_id: str,
        payload: UsageJobReleaseRequest,
        authorization: Annotated[str | None, Header()] = None,
    ) -> Any:
        client = _service_bridge_client()
        return _bridge_response(
            lambda: client.post(
                f"/usage/jobs/{job_id}/release",
                body=payload.model_dump(exclude_none=True),
                authorization=authorization,
            )
        )

    @application.get("/bridge/service/usage/jobs/{job_id}", tags=["bridge"])
    def bridge_usage_job_get(
        job_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> Any:
        client = _service_bridge_client()
        return _bridge_response(
            lambda: client.get(
                f"/usage/jobs/{job_id}",
                authorization=authorization,
            )
        )

    return application


def _service_bridge_client() -> ServiceEngineBridgeClient:
    settings = get_settings()
    return ServiceEngineBridgeClient(
        base_url=settings.service_engine_url,
        timeout_seconds=settings.service_engine_timeout_seconds,
    )


def _bridge_response(call: Callable[[], dict[str, Any]]) -> Any:
    try:
        return call()
    except ServiceEngineHTTPError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.payload)
    except ServiceEngineUnavailableError as exc:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "error": {
                    "code": "service_engine_unreachable",
                    "message": str(exc),
                    "retryable": True,
                    "details": None,
                }
            },
        )


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "retryable": retryable,
                "details": details,
            }
        },
    )


app = create_app()
