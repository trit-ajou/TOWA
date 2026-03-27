from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
import hashlib
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse


class ArtifactStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    RELEASED = "released"
    ORPHANED = "orphaned"


@dataclass
class ArtifactDescriptor:
    artifact_ref: str
    kind: str
    media_type: str
    uri: str
    width: Optional[int] = None
    height: Optional[int] = None
    byte_size: Optional[int] = None
    checksum: Optional[str] = None
    version: int = 1
    producer_stage: Optional[str] = None
    status: ArtifactStatus = ArtifactStatus.READY
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    metadata: dict[str, object] = field(default_factory=dict)

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        if self.expires_at is None:
            return False
        now = now or datetime.now(timezone.utc)
        return now >= self.expires_at


class ArtifactRegistry(ABC):
    @abstractmethod
    def register_artifact(self, descriptor: ArtifactDescriptor) -> ArtifactDescriptor:
        raise NotImplementedError

    @abstractmethod
    def resolve_artifact(self, artifact_ref: str) -> ArtifactDescriptor:
        raise NotImplementedError

    @abstractmethod
    def verify_artifact(self, artifact_ref: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def mark_artifact_failed(self, artifact_ref: str, *, reason: Optional[str] = None) -> ArtifactDescriptor:
        raise NotImplementedError

    @abstractmethod
    def release_artifact(self, artifact_ref: str, *, orphaned: bool = False) -> ArtifactDescriptor:
        raise NotImplementedError

    @abstractmethod
    def gc_artifacts(
        self,
        *,
        referenced_refs: Iterable[str] = (),
        remove_files: bool = False,
    ) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def snapshot(self) -> dict[str, ArtifactDescriptor]:
        raise NotImplementedError


class InMemoryArtifactRegistry(ArtifactRegistry):
    def __init__(self) -> None:
        self._items: dict[str, ArtifactDescriptor] = {}

    def register_artifact(self, descriptor: ArtifactDescriptor) -> ArtifactDescriptor:
        existing = self._items.get(descriptor.artifact_ref)
        if existing is not None:
            raise ValueError(f"artifact_ref already registered: {descriptor.artifact_ref}")
        self._items[descriptor.artifact_ref] = descriptor
        return descriptor

    def resolve_artifact(self, artifact_ref: str) -> ArtifactDescriptor:
        try:
            return self._items[artifact_ref]
        except KeyError as exc:
            raise KeyError(f"Unknown artifact_ref: {artifact_ref}") from exc

    def verify_artifact(self, artifact_ref: str) -> bool:
        descriptor = self.resolve_artifact(artifact_ref)
        if descriptor.status is not ArtifactStatus.READY:
            return False
        if descriptor.is_expired():
            return False

        path = _path_from_uri(descriptor.uri)
        if path is None:
            return True
        if not path.exists():
            return False
        if descriptor.checksum:
            actual = _sha256_for_file(path)
            return descriptor.checksum == f"sha256:{actual}"
        return True

    def mark_artifact_failed(self, artifact_ref: str, *, reason: Optional[str] = None) -> ArtifactDescriptor:
        descriptor = self.resolve_artifact(artifact_ref)
        updated = replace(
            descriptor,
            status=ArtifactStatus.FAILED,
            metadata={**descriptor.metadata, "failure_reason": reason} if reason else dict(descriptor.metadata),
        )
        self._items[artifact_ref] = updated
        return updated

    def release_artifact(self, artifact_ref: str, *, orphaned: bool = False) -> ArtifactDescriptor:
        descriptor = self.resolve_artifact(artifact_ref)
        updated = replace(
            descriptor,
            status=ArtifactStatus.ORPHANED if orphaned else ArtifactStatus.RELEASED,
        )
        self._items[artifact_ref] = updated
        return updated

    def gc_artifacts(
        self,
        *,
        referenced_refs: Iterable[str] = (),
        remove_files: bool = False,
    ) -> list[str]:
        referenced = set(referenced_refs)
        removed: list[str] = []
        for artifact_ref, descriptor in list(self._items.items()):
            should_remove = (
                descriptor.status in {ArtifactStatus.RELEASED, ArtifactStatus.ORPHANED, ArtifactStatus.FAILED}
                or descriptor.is_expired()
                or artifact_ref not in referenced and descriptor.status is ArtifactStatus.ORPHANED
            )
            if not should_remove:
                continue

            if remove_files:
                path = _path_from_uri(descriptor.uri)
                if path and path.exists():
                    path.unlink()
            removed.append(artifact_ref)
            del self._items[artifact_ref]
        return removed

    def snapshot(self) -> dict[str, ArtifactDescriptor]:
        return dict(self._items)


def _path_from_uri(uri: str) -> Optional[Path]:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    return Path(parsed.path)


def _sha256_for_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
