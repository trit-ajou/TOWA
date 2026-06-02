from __future__ import annotations

import json
from uuid import uuid4

from fastapi import Response, UploadFile
from pydantic import ValidationError

from app.api.schemas.projects import PageSnapshotMetadata
from app.api.thumbnail_images import normalize_thumbnail_payload
from app.core.settings import get_settings
from app.modules.projects.service import BinaryPayload, PageSnapshotWrite, SnapshotValidationError, StoredPageSnapshot

JSON_MEDIA_TYPE = "application/json"
OCTET_STREAM_MEDIA_TYPE = "application/octet-stream"
IMAGE_MEDIA_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


def _normalized_media_type(value: str | None) -> str:
    return (value or "").split(";", 1)[0].strip().lower()


async def _read_upload_bytes(
    upload: UploadFile,
    *,
    field_name: str,
    allowed_media_types: set[str],
    max_bytes: int,
) -> BinaryPayload:
    media_type = _normalized_media_type(upload.content_type)
    if media_type not in allowed_media_types:
        raise SnapshotValidationError(
            f"{field_name} must use one of: {', '.join(sorted(allowed_media_types))}.",
        )
    payload = await upload.read()
    if not payload:
        raise SnapshotValidationError(f"{field_name} must not be empty.")
    if len(payload) > max_bytes:
        raise SnapshotValidationError(
            f"{field_name} exceeds the maximum size of {max_bytes} bytes.",
        )
    return BinaryPayload(content=payload, media_type=media_type)


async def _parse_metadata_upload(metadata: UploadFile) -> PageSnapshotMetadata:
    media_type = _normalized_media_type(metadata.content_type)
    if media_type != JSON_MEDIA_TYPE:
        raise SnapshotValidationError("metadata must use application/json.")

    raw_payload = await metadata.read()
    if not raw_payload:
        raise SnapshotValidationError("metadata must not be empty.")

    try:
        decoded_payload = json.loads(raw_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SnapshotValidationError("metadata must be valid UTF-8 JSON.") from exc

    try:
        return PageSnapshotMetadata.model_validate(decoded_payload)
    except ValidationError as exc:
        raise SnapshotValidationError(f"metadata validation failed: {exc}") from exc


async def parse_snapshot_write(
    *,
    metadata: UploadFile,
    original_image: UploadFile,
    layer_blob: UploadFile,
    thumbnail: UploadFile,
) -> PageSnapshotWrite:
    settings = get_settings()
    metadata_payload = await _parse_metadata_upload(metadata)
    original_image_payload = await _read_upload_bytes(
        original_image,
        field_name="original_image",
        allowed_media_types=IMAGE_MEDIA_TYPES,
        max_bytes=settings.project_original_image_max_bytes,
    )
    layer_blob_payload = await _read_upload_bytes(
        layer_blob,
        field_name="layer_blob",
        allowed_media_types={OCTET_STREAM_MEDIA_TYPE},
        max_bytes=settings.project_layer_blob_max_bytes,
    )
    thumbnail_payload = await _read_upload_bytes(
        thumbnail,
        field_name="thumbnail",
        allowed_media_types=IMAGE_MEDIA_TYPES,
        max_bytes=settings.project_thumbnail_max_bytes,
    )
    thumbnail_payload = normalize_thumbnail_payload(
        thumbnail_payload,
        max_width=settings.project_thumbnail_max_width,
        quality=settings.project_thumbnail_webp_quality,
    )
    return PageSnapshotWrite(
        page_id=metadata_payload.page.id,
        project_id=metadata_payload.page.project_id,
        index=metadata_payload.page.index,
        status=metadata_payload.page.status,
        metadata=metadata_payload.model_dump(mode="json"),
        original_image=original_image_payload,
        layer_blob=layer_blob_payload,
        thumbnail=thumbnail_payload,
    )


def normalize_snapshot_thumbnail(snapshot: StoredPageSnapshot) -> StoredPageSnapshot:
    settings = get_settings()
    return StoredPageSnapshot(
        metadata=snapshot.metadata,
        original_image=snapshot.original_image,
        layer_blob=snapshot.layer_blob,
        thumbnail=normalize_thumbnail_payload(
            snapshot.thumbnail,
            max_width=settings.project_thumbnail_max_width,
            quality=settings.project_thumbnail_webp_quality,
        ),
    )


def build_snapshot_response(snapshot: StoredPageSnapshot) -> Response:
    boundary = f"towa-{uuid4().hex}"
    metadata_payload = json.dumps(snapshot.metadata, ensure_ascii=False).encode("utf-8")
    body = b"".join(
        [
            _encode_part(
                boundary,
                name="metadata",
                media_type=JSON_MEDIA_TYPE,
                filename="metadata.json",
                payload=metadata_payload,
            ),
            _encode_part(
                boundary,
                name="original_image",
                media_type=snapshot.original_image.media_type,
                filename="original-image.bin",
                payload=snapshot.original_image.content,
            ),
            _encode_part(
                boundary,
                name="layer_blob",
                media_type=snapshot.layer_blob.media_type,
                filename="layer-blob.bin",
                payload=snapshot.layer_blob.content,
            ),
            _encode_part(
                boundary,
                name="thumbnail",
                media_type=snapshot.thumbnail.media_type,
                filename="thumbnail.bin",
                payload=snapshot.thumbnail.content,
            ),
            f"--{boundary}--\r\n".encode("utf-8"),
        ],
    )
    return Response(
        content=body,
        media_type=f'multipart/mixed; boundary="{boundary}"',
    )


def _encode_part(
    boundary: str,
    *,
    name: str,
    media_type: str,
    filename: str,
    payload: bytes,
) -> bytes:
    return b"".join(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            f"Content-Type: {media_type}\r\n".encode("utf-8"),
            f'Content-Disposition: attachment; name="{name}"; filename="{filename}"\r\n'.encode("utf-8"),
            b"\r\n",
            payload,
            b"\r\n",
        ],
    )
