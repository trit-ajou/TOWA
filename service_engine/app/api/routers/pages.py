from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_session_token
from app.api.errors import openapi_error_responses, raise_project_http_error
from app.api.http_cache import conditional_not_modified_response, etag_for_parts, latest_datetime, set_cache_headers
from app.api.page_snapshots import build_snapshot_response, normalize_snapshot_thumbnail, parse_snapshot_write
from app.api.schemas.projects import PageDeleteResponse, PageSummaryEnvelope, PageSummaryResponse
from app.api.thumbnail_images import WEBP_MEDIA_TYPE, normalize_thumbnail_payload
from app.core.settings import get_settings
from app.db import get_db_session
from app.modules.projects.models import Page
from app.modules.projects import service as project_service

router = APIRouter(prefix="/api/v1", tags=["pages"])


def _page_summary_response(page: Page, request: Request) -> PageSummaryResponse:
    return PageSummaryResponse(
        id=page.id,
        project_id=page.project_id,
        index=page.index,
        status=page.status,
        thumbnail_url=str(request.url_for("get_page_thumbnail", page_id=page.id)),
        updated_at=page.updated_at,
    )


def _snapshot_etag_parts(state: project_service.PageSnapshotState) -> dict[str, object]:
    settings = get_settings()
    return {
        "page_id": state.page_id,
        "project_id": state.project_id,
        "page_status": state.page_status,
        "page_updated_at": state.page_updated_at,
        "snapshot_updated_at": state.snapshot_updated_at,
        "metadata": state.metadata,
        "original_image_media_type": state.original_image_media_type,
        "original_image_byte_size": state.original_image_byte_size,
        "layer_blob_media_type": state.layer_blob_media_type,
        "layer_blob_byte_size": state.layer_blob_byte_size,
        "thumbnail_media_type": state.thumbnail_media_type,
        "thumbnail_byte_size": state.thumbnail_byte_size,
        "thumbnail_target_media_type": WEBP_MEDIA_TYPE,
        "thumbnail_max_width": settings.project_thumbnail_max_width,
        "thumbnail_webp_quality": settings.project_thumbnail_webp_quality,
    }


def _thumbnail_etag_parts(state: project_service.PageSnapshotState) -> dict[str, object]:
    settings = get_settings()
    return {
        "page_id": state.page_id,
        "page_updated_at": state.page_updated_at,
        "snapshot_updated_at": state.snapshot_updated_at,
        "thumbnail_media_type": state.thumbnail_media_type,
        "thumbnail_byte_size": state.thumbnail_byte_size,
        "thumbnail_target_media_type": WEBP_MEDIA_TYPE,
        "thumbnail_max_width": settings.project_thumbnail_max_width,
        "thumbnail_webp_quality": settings.project_thumbnail_webp_quality,
    }


@router.get(
    "/pages/{page_id}/snapshot",
    response_class=Response,
    responses={
        200: {
            "content": {
                "multipart/mixed": {
                    "schema": {"type": "string", "format": "binary"},
                },
            },
        },
        **openapi_error_responses(401, 404, 409, 422),
    },
)
def get_page_snapshot(
    page_id: str,
    request: Request,
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> Response:
    try:
        state = project_service.get_page_snapshot_state(
            session,
            session_token=session_token,
            page_id=page_id,
        )
        last_modified = latest_datetime([state.page_updated_at, state.snapshot_updated_at])
        etag = etag_for_parts("page-snapshot", _snapshot_etag_parts(state))
        not_modified = conditional_not_modified_response(request, etag=etag, last_modified=last_modified)
        if not_modified is not None:
            return not_modified
        snapshot = project_service.get_page_snapshot(
            session,
            session_token=session_token,
            page_id=page_id,
        )
        snapshot = normalize_snapshot_thumbnail(snapshot)
    except Exception as exc:  # noqa: BLE001
        raise_project_http_error(exc)
    response = build_snapshot_response(snapshot)
    set_cache_headers(response, etag=etag, last_modified=last_modified)
    return response


@router.put(
    "/pages/{page_id}/snapshot",
    response_model=PageSummaryEnvelope,
    responses=openapi_error_responses(401, 404, 409, 422),
)
async def update_page_snapshot(
    page_id: str,
    request: Request,
    metadata: Annotated[UploadFile, File(...)],
    original_image: Annotated[UploadFile, File(...)],
    layer_blob: Annotated[UploadFile, File(...)],
    thumbnail: Annotated[UploadFile, File(...)],
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> PageSummaryEnvelope:
    try:
        write = await parse_snapshot_write(
            metadata=metadata,
            original_image=original_image,
            layer_blob=layer_blob,
            thumbnail=thumbnail,
        )
        if write.page_id.strip().upper() != page_id.strip().upper():
            raise ValueError("metadata.page.id must match the page_id path parameter.")
        page = project_service.update_page_snapshot(
            session,
            session_token=session_token,
            page_id=page_id,
            write=write,
        )
    except Exception as exc:  # noqa: BLE001
        raise_project_http_error(exc)
    return PageSummaryEnvelope(page=_page_summary_response(page, request))


@router.delete(
    "/pages/{page_id}",
    response_model=PageDeleteResponse,
    responses=openapi_error_responses(401, 404),
)
def delete_page(
    page_id: str,
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> PageDeleteResponse:
    try:
        deleted_page_id = project_service.delete_page(
            session,
            session_token=session_token,
            page_id=page_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise_project_http_error(exc)
    return PageDeleteResponse(deleted=True, page_id=deleted_page_id)


@router.get(
    "/pages/{page_id}/thumbnail",
    response_class=Response,
    responses={
        200: {
            "content": {
                "image/webp": {},
            },
        },
        **openapi_error_responses(401, 404, 409, 422),
    },
)
def get_page_thumbnail(
    page_id: str,
    request: Request,
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> Response:
    try:
        state = project_service.get_page_snapshot_state(
            session,
            session_token=session_token,
            page_id=page_id,
        )
        last_modified = latest_datetime([state.page_updated_at, state.snapshot_updated_at])
        etag = etag_for_parts("page-thumbnail", _thumbnail_etag_parts(state))
        not_modified = conditional_not_modified_response(request, etag=etag, last_modified=last_modified)
        if not_modified is not None:
            return not_modified
        thumbnail = project_service.get_page_thumbnail(
            session,
            session_token=session_token,
            page_id=page_id,
        )
        settings = get_settings()
        thumbnail = normalize_thumbnail_payload(
            thumbnail,
            max_width=settings.project_thumbnail_max_width,
            quality=settings.project_thumbnail_webp_quality,
        )
    except Exception as exc:  # noqa: BLE001
        raise_project_http_error(exc)
    response = Response(content=thumbnail.content, media_type=thumbnail.media_type)
    set_cache_headers(response, etag=etag, last_modified=last_modified)
    return response
