from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_session_token
from app.api.errors import openapi_error_responses, raise_project_http_error
from app.api.http_cache import conditional_not_modified_response, etag_for_parts, latest_datetime, set_cache_headers
from app.api.page_snapshots import parse_snapshot_write
from app.api.schemas.projects import (
    PageListResponse,
    PageSummaryEnvelope,
    PageSummaryResponse,
    ProjectCreateRequest,
    ProjectDeleteResponse,
    ProjectListResponse,
    ProjectPatchRequest,
    ProjectResponse,
)
from app.db import get_db_session
from app.modules.projects.models import Page
from app.modules.projects import service as project_service

router = APIRouter(prefix="/api/v1", tags=["projects"])


def _page_summary_response(page: Page, request: Request) -> PageSummaryResponse:
    return PageSummaryResponse(
        id=page.id,
        project_id=page.project_id,
        index=page.index,
        status=page.status,
        thumbnail_url=str(request.url_for("get_page_thumbnail", page_id=page.id)),
        updated_at=page.updated_at,
    )


@router.post(
    "/projects",
    response_model=ProjectResponse,
    responses=openapi_error_responses(401, 409, 422),
)
def create_project(
    payload: ProjectCreateRequest,
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> ProjectResponse:
    try:
        project = project_service.create_project(
            session,
            session_token=session_token,
            project_id=payload.id,
            name=payload.name,
            thumbnail_url=payload.thumbnail_url,
            source_lang=payload.source_lang,
            target_lang=payload.target_lang,
            status=payload.status,
            folder_id=payload.folder_id,
            config=payload.config,
        )
    except Exception as exc:  # noqa: BLE001
        raise_project_http_error(exc)
    return ProjectResponse.model_validate(project)


@router.get(
    "/projects",
    response_model=ProjectListResponse,
    responses=openapi_error_responses(401),
)
def list_projects(
    request: Request,
    response: Response,
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> ProjectListResponse | Response:
    try:
        projects = project_service.list_projects(session, session_token=session_token)
    except Exception as exc:  # noqa: BLE001
        raise_project_http_error(exc)
    etag = etag_for_parts("projects-list", projects)
    last_modified = latest_datetime(project["updated_at"] for project in projects)
    not_modified = conditional_not_modified_response(request, etag=etag, last_modified=last_modified)
    if not_modified is not None:
        return not_modified
    set_cache_headers(response, etag=etag, last_modified=last_modified)
    return ProjectListResponse(items=[ProjectResponse.model_validate(project) for project in projects])


@router.get(
    "/projects/{project_id}",
    response_model=ProjectResponse,
    responses=openapi_error_responses(401, 404),
)
def get_project(
    project_id: str,
    request: Request,
    response: Response,
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> ProjectResponse | Response:
    try:
        project = project_service.get_project(
            session,
            session_token=session_token,
            project_id=project_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise_project_http_error(exc)
    etag = etag_for_parts("project-detail", project)
    last_modified = latest_datetime([project["updated_at"]])
    not_modified = conditional_not_modified_response(request, etag=etag, last_modified=last_modified)
    if not_modified is not None:
        return not_modified
    set_cache_headers(response, etag=etag, last_modified=last_modified)
    return ProjectResponse.model_validate(project)


@router.patch(
    "/projects/{project_id}",
    response_model=ProjectResponse,
    responses=openapi_error_responses(401, 404, 409, 422),
)
def update_project(
    project_id: str,
    payload: ProjectPatchRequest,
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> ProjectResponse:
    try:
        project = project_service.update_project(
            session,
            session_token=session_token,
            project_id=project_id,
            updates=payload.model_dump(exclude_unset=True),
        )
    except Exception as exc:  # noqa: BLE001
        raise_project_http_error(exc)
    return ProjectResponse.model_validate(project)


@router.delete(
    "/projects/{project_id}",
    response_model=ProjectResponse | ProjectDeleteResponse,
    responses=openapi_error_responses(400, 401, 404),
)
def delete_project(
    project_id: str,
    permanent: bool = Query(default=False),
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> ProjectResponse | ProjectDeleteResponse:
    try:
        result = project_service.delete_project(
            session,
            session_token=session_token,
            project_id=project_id,
            permanent=permanent,
        )
    except Exception as exc:  # noqa: BLE001
        raise_project_http_error(exc)
    if isinstance(result, str):
        return ProjectDeleteResponse(deleted=True, project_id=result)
    return ProjectResponse.model_validate(result)


@router.post(
    "/projects/{project_id}/restore",
    response_model=ProjectResponse,
    responses=openapi_error_responses(400, 401, 404, 409),
)
def restore_project(
    project_id: str,
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> ProjectResponse:
    try:
        project = project_service.restore_project(
            session,
            session_token=session_token,
            project_id=project_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise_project_http_error(exc)
    return ProjectResponse.model_validate(project)


@router.get(
    "/projects/{project_id}/pages",
    response_model=PageListResponse,
    responses=openapi_error_responses(401, 404),
)
def list_project_pages(
    project_id: str,
    request: Request,
    response: Response,
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> PageListResponse | Response:
    try:
        pages = project_service.list_pages(
            session,
            session_token=session_token,
            project_id=project_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise_project_http_error(exc)
    items = [_page_summary_response(page, request) for page in pages]
    etag = etag_for_parts("project-pages-list", [item.model_dump(mode="json") for item in items])
    last_modified = latest_datetime(page.updated_at for page in pages)
    not_modified = conditional_not_modified_response(request, etag=etag, last_modified=last_modified)
    if not_modified is not None:
        return not_modified
    set_cache_headers(response, etag=etag, last_modified=last_modified)
    return PageListResponse(items=items)


@router.post(
    "/projects/{project_id}/pages",
    response_model=PageSummaryEnvelope,
    responses=openapi_error_responses(401, 404, 409, 422),
)
async def create_project_page(
    project_id: str,
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
        if write.project_id.strip().upper() != project_id.strip().upper():
            raise ValueError("metadata.page.project_id must match the project_id path parameter.")
        page = project_service.create_page_snapshot(
            session,
            session_token=session_token,
            write=write,
        )
    except Exception as exc:  # noqa: BLE001
        raise_project_http_error(exc)
    return PageSummaryEnvelope(page=_page_summary_response(page, request))
