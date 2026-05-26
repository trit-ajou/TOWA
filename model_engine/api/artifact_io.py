from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import tempfile
from typing import Any, Optional
from urllib.parse import unquote, urlparse

from ..contracts.artifacts import ArtifactDescriptor, ArtifactStatus


@dataclass(frozen=True)
class UploadedBinaryPart:
    part_name: str
    filename: str
    media_type: str
    content: bytes


@dataclass(frozen=True)
class JobArtifactDownload:
    descriptor: ArtifactDescriptor
    path: Path


@dataclass(frozen=True)
class UnsupportedArtifactUriError(Exception):
    artifact_ref: str
    uri: str
    message: str


def artifact_descriptor_from_api_data(payload: dict[str, Any]) -> ArtifactDescriptor:
    return ArtifactDescriptor(
        artifact_ref=str(payload["artifact_ref"]),
        kind=str(payload["kind"]),
        media_type=str(payload["media_type"]),
        uri=str(payload["uri"]),
        width=payload.get("width"),
        height=payload.get("height"),
        byte_size=payload.get("byte_size"),
        checksum=payload.get("checksum"),
        version=int(payload.get("version", 1)),
        producer_stage=payload.get("producer_stage"),
        status=ArtifactStatus(payload.get("status", ArtifactStatus.READY.value)),
        expires_at=_parse_datetime(payload.get("expires_at")),
        metadata=dict(payload.get("metadata", {})),
    )


def artifact_descriptors_from_api_payload(
    artifacts_payload: dict[str, dict[str, Any]],
    *,
    primary_bitmap: UploadedBinaryPart | None = None,
    primary_bitmap_checksum: str | None = None,
) -> dict[str, ArtifactDescriptor]:
    normalized: dict[str, ArtifactDescriptor] = {}
    resolved_primary_uri: str | None = None
    referenced_primary_upload = False

    for artifact_ref, descriptor_payload in artifacts_payload.items():
        upload_uri = str(descriptor_payload.get("uri", ""))
        if upload_uri.startswith("upload://") and upload_uri != "upload://primary_bitmap":
            raise ValueError(f"Unsupported upload artifact uri: {upload_uri}")
        if upload_uri == "upload://primary_bitmap":
            referenced_primary_upload = True
            if primary_bitmap is None or primary_bitmap_checksum is None:
                raise ValueError("primary_bitmap upload is required when metadata references upload://primary_bitmap")
            if resolved_primary_uri is None:
                resolved_primary_uri = _persist_uploaded_binary(primary_bitmap)
            descriptor_payload = {
                **descriptor_payload,
                "uri": resolved_primary_uri,
                "media_type": primary_bitmap.media_type or descriptor_payload.get("media_type", "application/octet-stream"),
                "byte_size": len(primary_bitmap.content),
                "checksum": primary_bitmap_checksum,
                "metadata": {
                    **dict(descriptor_payload.get("metadata", {})),
                    "upload_part": primary_bitmap.part_name,
                    "upload_filename": primary_bitmap.filename,
                },
            }
        normalized[artifact_ref] = artifact_descriptor_from_api_data(descriptor_payload)

    if primary_bitmap is not None and not referenced_primary_upload:
        raise ValueError("primary_bitmap upload was provided but metadata does not reference upload://primary_bitmap")

    return normalized


def artifact_descriptor_to_api_data(descriptor: ArtifactDescriptor) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "artifact_ref": descriptor.artifact_ref,
        "kind": descriptor.kind,
        "media_type": descriptor.media_type,
        "uri": descriptor.uri,
        "version": descriptor.version,
        "status": descriptor.status.value,
        "metadata": dict(descriptor.metadata),
    }
    if descriptor.width is not None:
        payload["width"] = descriptor.width
    if descriptor.height is not None:
        payload["height"] = descriptor.height
    if descriptor.byte_size is not None:
        payload["byte_size"] = descriptor.byte_size
    if descriptor.checksum is not None:
        payload["checksum"] = descriptor.checksum
    if descriptor.producer_stage is not None:
        payload["producer_stage"] = descriptor.producer_stage
    if descriptor.expires_at is not None:
        payload["expires_at"] = descriptor.expires_at.isoformat()
    return payload


def file_artifact_path(descriptor: ArtifactDescriptor) -> Path:
    parsed = urlparse(descriptor.uri)
    if parsed.scheme != "file" or parsed.params or parsed.query or parsed.fragment:
        raise UnsupportedArtifactUriError(
            artifact_ref=descriptor.artifact_ref,
            uri=descriptor.uri,
            message=f"Unsupported artifact uri for binary download: {descriptor.uri}",
        )
    if parsed.netloc not in {"", "localhost"}:
        raise UnsupportedArtifactUriError(
            artifact_ref=descriptor.artifact_ref,
            uri=descriptor.uri,
            message=f"Unsupported artifact file host: {parsed.netloc}",
        )
    path = unquote(parsed.path)
    if not path:
        raise UnsupportedArtifactUriError(
            artifact_ref=descriptor.artifact_ref,
            uri=descriptor.uri,
            message=f"Unsupported artifact uri for binary download: {descriptor.uri}",
        )
    return Path(path)


def _persist_uploaded_binary(upload: UploadedBinaryPart) -> str:
    suffix = _upload_suffix(upload)
    upload_dir = Path(tempfile.mkdtemp(prefix="towa_model_job_upload_"))
    file_path = upload_dir / f"{upload.part_name}{suffix}"
    file_path.write_bytes(upload.content)
    return file_path.resolve().as_uri()


def _upload_suffix(upload: UploadedBinaryPart) -> str:
    candidate = Path(upload.filename or "").suffix.lower()
    if candidate:
        return candidate
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }.get(upload.media_type, ".bin")


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    return datetime.fromisoformat(str(value))
