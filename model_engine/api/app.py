from __future__ import annotations

from collections.abc import Callable
import json
import logging
from typing import Annotated, Any

from fastapi import FastAPI, Header, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.datastructures import UploadFile as StarletteUploadFile

from .jobs import (
    ModelJobError,
    ModelJobManager,
    UploadedBinaryPart,
    submission_from_api_payload,
    submission_from_multipart_payload,
)
from ..logging_utils import log_event
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

logger = logging.getLogger(__name__)


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
    async def create_job(
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
    ) -> JSONResponse:
        try:
            submission = await _submission_from_http_request(request)
            status_code, response = job_manager.create_job(
                submission,
                authorization=authorization,
            )
            return JSONResponse(status_code=status_code, content=response)
        except ModelJobError as exc:
            _log_api_error(
                "model_job_create_rejected",
                status_code=exc.status_code,
                code=exc.code,
                retryable=exc.retryable,
                details=exc.details,
            )
            return _error_response(
                status_code=exc.status_code,
                code=exc.code,
                message=exc.message,
                retryable=exc.retryable,
                details=exc.details,
            )
        except ServiceEngineHTTPError as exc:
            _log_api_error(
                "model_job_create_service_error",
                status_code=exc.status_code,
                code=_error_code_from_payload(exc.payload),
            )
            return JSONResponse(status_code=exc.status_code, content=exc.payload)
        except ServiceEngineUnavailableError as exc:
            _log_api_error(
                "model_job_create_service_unavailable",
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="service_engine_unreachable",
            )
            return _error_response(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="service_engine_unreachable",
                message=str(exc),
                retryable=True,
            )
        except (KeyError, TypeError, ValueError) as exc:
            _log_api_error(
                "model_job_create_validation_error",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="model_validation_error",
                message=str(exc),
            )
            return _error_response(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="model_validation_error",
                message=str(exc),
            )

    @application.get("/v1/jobs/{job_id}", tags=["jobs"])
    def get_job(
        job_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> JSONResponse:
        try:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=job_manager.get_job(job_id, authorization=authorization),
            )
        except ModelJobError as exc:
            return _error_response(
                status_code=exc.status_code,
                code=exc.code,
                message=exc.message,
                retryable=exc.retryable,
                details=exc.details,
            )

    @application.get("/v1/jobs/{job_id}/artifacts", tags=["jobs"], response_model=None)
    def get_job_artifact(
        job_id: str,
        artifact_ref: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> Any:
        try:
            download = job_manager.get_artifact(
                job_id,
                artifact_ref=artifact_ref,
                authorization=authorization,
            )
            return FileResponse(
                download.path,
                media_type=download.descriptor.media_type,
            )
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
        _log_api_error(
            "model_bridge_service_error",
            status_code=exc.status_code,
            code=_error_code_from_payload(exc.payload),
        )
        return JSONResponse(status_code=exc.status_code, content=exc.payload)
    except ServiceEngineUnavailableError as exc:
        _log_api_error(
            "model_bridge_service_unavailable",
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="service_engine_unreachable",
        )
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


def _log_api_error(event: str, **fields: Any) -> None:
    log_event(logger, logging.WARNING, event, **fields)


def _error_code_from_payload(payload: dict[str, Any]) -> str | None:
    error = payload.get("error")
    if isinstance(error, dict):
        code = error.get("code")
        return str(code) if code is not None else None
    return None


async def _submission_from_http_request(request: Request):
    content_type = request.headers.get("content-type", "").lower()

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        extra_fields = set(form.keys()) - {"metadata", "primary_bitmap"}
        if extra_fields:
            raise ModelJobError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="model_validation_error",
                message=f"Unsupported multipart fields: {', '.join(sorted(extra_fields))}",
            )

        metadata_part = form.get("metadata")
        metadata = await _metadata_text_from_form_part(metadata_part)
        if metadata is None:
            raise ModelJobError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="model_validation_error",
                message="multipart metadata field is required",
            )

        try:
            metadata_payload = json.loads(metadata)
        except json.JSONDecodeError as exc:
            raise ModelJobError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="model_validation_error",
                message=f"Invalid metadata JSON: {exc.msg}",
            ) from exc

        payload = ModelJobCreateRequest.model_validate(metadata_payload)
        primary_bitmap = _upload_from_form_part(form.get("primary_bitmap"))
        if primary_bitmap is None:
            if payload.operation_kind == "translate":
                return submission_from_api_payload(payload)
            raise ModelJobError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="model_validation_error",
                message="multipart primary_bitmap field is required",
            )

        try:
            upload = UploadedBinaryPart(
                part_name="primary_bitmap",
                filename=primary_bitmap.filename or "primary_bitmap",
                media_type=primary_bitmap.content_type or "application/octet-stream",
                content=await primary_bitmap.read(),
            )
        finally:
            await primary_bitmap.close()
        return submission_from_multipart_payload(payload, primary_bitmap=upload)

    if content_type.startswith("application/json") or not content_type:
        payload = ModelJobCreateRequest.model_validate(await request.json())
        return submission_from_api_payload(payload)

    raise ModelJobError(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        code="model_validation_error",
        message=f"Unsupported Content-Type: {request.headers.get('content-type', '')}",
    )


async def _metadata_text_from_form_part(part: Any) -> str | None:
    if isinstance(part, str):
        return part
    upload = _upload_from_form_part(part)
    if upload is not None:
        try:
            return (await upload.read()).decode("utf-8")
        finally:
            await upload.close()
    return None


def _upload_from_form_part(part: Any) -> UploadFile | StarletteUploadFile | None:
    if isinstance(part, (UploadFile, StarletteUploadFile)):
        return part
    if all(hasattr(part, attr) for attr in ("read", "close", "filename")):
        return part
    return None


app = create_app()
