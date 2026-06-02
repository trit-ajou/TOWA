from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_session_token
from app.api.errors import openapi_error_responses, raise_project_http_error
from app.api.http_cache import conditional_not_modified_response, etag_for_parts, latest_datetime, set_cache_headers
from app.api.schemas.projects import (
    FolderCreateRequest,
    FolderDeleteResponse,
    FolderListResponse,
    FolderPatchRequest,
    FolderResponse,
    TrashListResponse,
    TrashItemResponse,
)
from app.db import get_db_session
from app.modules.projects import folders as folder_service

router = APIRouter(prefix="/api/v1", tags=["folders"])


@router.get(
    "/folders",
    response_model=FolderListResponse,
    responses=openapi_error_responses(401),
)
def list_folders(
    request: Request,
    response: Response,
    search: str | None = None,
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> FolderListResponse | Response:
    try:
        folders = folder_service.list_folders(session, session_token=session_token, search=search)
    except Exception as exc:  # noqa: BLE001
        raise_project_http_error(exc)
    etag = etag_for_parts("folders-list", {"search": search, "items": folders})
    last_modified = latest_datetime(folder["updated_at"] for folder in folders)
    not_modified = conditional_not_modified_response(request, etag=etag, last_modified=last_modified)
    if not_modified is not None:
        return not_modified
    set_cache_headers(response, etag=etag, last_modified=last_modified)
    return FolderListResponse(items=[FolderResponse.model_validate(folder) for folder in folders])


@router.post(
    "/folders",
    response_model=FolderResponse,
    responses=openapi_error_responses(401, 404, 409, 422),
)
def create_folder(
    payload: FolderCreateRequest,
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> FolderResponse:
    try:
        folder = folder_service.create_folder(
            session,
            session_token=session_token,
            name=payload.name,
            parent_id=payload.parent_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise_project_http_error(exc)
    return FolderResponse.model_validate(folder)


@router.patch(
    "/folders/{folder_id}",
    response_model=FolderResponse,
    responses=openapi_error_responses(400, 401, 404, 409, 422),
)
def update_folder(
    folder_id: str,
    payload: FolderPatchRequest,
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> FolderResponse:
    try:
        folder = folder_service.update_folder(
            session,
            session_token=session_token,
            folder_id=folder_id,
            updates=payload.model_dump(exclude_unset=True),
        )
    except Exception as exc:  # noqa: BLE001
        raise_project_http_error(exc)
    return FolderResponse.model_validate(folder)


@router.delete(
    "/folders/{folder_id}",
    response_model=FolderResponse | FolderDeleteResponse,
    responses=openapi_error_responses(400, 401, 404, 409),
)
def delete_folder(
    folder_id: str,
    cascade: str | None = Query(default=None),
    reparent: bool = Query(default=False),
    permanent: bool = Query(default=False),
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> FolderResponse | FolderDeleteResponse:
    try:
        result = folder_service.delete_folder(
            session,
            session_token=session_token,
            folder_id=folder_id,
            cascade=cascade,
            reparent=reparent,
            permanent=permanent,
        )
    except Exception as exc:  # noqa: BLE001
        raise_project_http_error(exc)
    if isinstance(result, str):
        return FolderDeleteResponse(deleted=True, folder_id=result)
    return FolderResponse.model_validate(result)


@router.post(
    "/folders/{folder_id}/restore",
    response_model=FolderResponse,
    responses=openapi_error_responses(400, 401, 404, 409),
)
def restore_folder(
    folder_id: str,
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> FolderResponse:
    try:
        folder = folder_service.restore_folder(session, session_token=session_token, folder_id=folder_id)
    except Exception as exc:  # noqa: BLE001
        raise_project_http_error(exc)
    return FolderResponse.model_validate(folder)


@router.get(
    "/trash",
    response_model=TrashListResponse,
    responses=openapi_error_responses(401),
)
def list_trash(
    request: Request,
    response: Response,
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> TrashListResponse | Response:
    try:
        items = folder_service.list_trash(session, session_token=session_token)
    except Exception as exc:  # noqa: BLE001
        raise_project_http_error(exc)
    timestamps = []
    for item in items:
        payload = item["item"]
        timestamps.extend([payload["updated_at"], payload["deleted_at"]])
    etag = etag_for_parts("trash-list", items)
    last_modified = latest_datetime(timestamps)
    not_modified = conditional_not_modified_response(request, etag=etag, last_modified=last_modified)
    if not_modified is not None:
        return not_modified
    set_cache_headers(response, etag=etag, last_modified=last_modified)
    return TrashListResponse(items=[TrashItemResponse.model_validate(item) for item in items])
