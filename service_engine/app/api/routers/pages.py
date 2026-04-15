from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_session_token
from app.api.errors import openapi_error_responses, raise_project_http_error
from app.api.page_snapshots import build_snapshot_response, parse_snapshot_write
from app.api.schemas.projects import PageDeleteResponse, PageSummaryEnvelope, PageSummaryResponse
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


@router.get(
    "/pages/{page_id}/snapshot",
    responses={
        200: {
            "content": {
                "multipart/mixed": {
                    "schema": {"type": "string", "format": "binary"},
                },
            },
        },
        **openapi_error_responses(401, 404, 409),
    },
)
def get_page_snapshot(
    page_id: str,
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> Response:
    try:
        snapshot = project_service.get_page_snapshot(
            session,
            session_token=session_token,
            page_id=page_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise_project_http_error(exc)
    return build_snapshot_response(snapshot)


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
    responses={
        200: {
            "content": {
                "image/jpeg": {},
                "image/png": {},
                "image/webp": {},
            },
        },
        **openapi_error_responses(401, 404, 409),
    },
)
def get_page_thumbnail(
    page_id: str,
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> Response:
    try:
        thumbnail = project_service.get_page_thumbnail(
            session,
            session_token=session_token,
            page_id=page_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise_project_http_error(exc)
    return Response(content=thumbnail.content, media_type=thumbnail.media_type)
