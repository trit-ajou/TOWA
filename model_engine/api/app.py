from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import FastAPI, Header, status
from fastapi.responses import JSONResponse

from .schemas import UsageJobCaptureRequest, UsageJobCreateRequest, UsageJobReleaseRequest
from .service_bridge import (
    ServiceEngineBridgeClient,
    ServiceEngineHTTPError,
    ServiceEngineUnavailableError,
)
from .settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name)

    @application.get("/healthz", tags=["infra"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/bridge/service/healthz", tags=["bridge"])
    def bridge_service_healthz() -> JSONResponse | dict[str, Any]:
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
    ) -> JSONResponse | dict[str, Any]:
        client = _service_bridge_client()
        return _bridge_response(lambda: client.get("/auth/me", authorization=authorization))

    @application.post("/bridge/service/usage/jobs", tags=["bridge"])
    def bridge_usage_job_create(
        payload: UsageJobCreateRequest,
        authorization: Annotated[str | None, Header()] = None,
    ) -> JSONResponse | dict[str, Any]:
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
    ) -> JSONResponse | dict[str, Any]:
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
    ) -> JSONResponse | dict[str, Any]:
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
    ) -> JSONResponse | dict[str, Any]:
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


def _bridge_response(call: Callable[[], dict[str, Any]]) -> JSONResponse | dict[str, Any]:
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


app = create_app()
