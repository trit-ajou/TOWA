from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Optional

from ..config.runtime_config import load_runtime_config, runtime_config_value
from ..contracts.credentials import BillingMode, CredentialBinding, CredentialSource, ResolvedCredential
from ..contracts.stages import ExecutionMode, StageRuntimeContext


class CredentialResolutionError(RuntimeError):
    """Raised when a stage credential cannot be resolved safely."""


class CredentialResolver(ABC):
    @abstractmethod
    def resolve_for_stage(
        self,
        *,
        stage_name: str,
        runtime_context: StageRuntimeContext,
        stage_config: dict[str, object],
    ) -> tuple[dict[str, CredentialBinding], dict[str, ResolvedCredential]]:
        raise NotImplementedError


class DefaultCredentialResolver(CredentialResolver):
    """Resolve credential bindings from the documented defaults."""

    def __init__(
        self,
        *,
        environ: Optional[dict[str, str]] = None,
        credentials_file: Optional[str] = None,
        runtime_config: Optional[dict[str, object]] = None,
    ) -> None:
        self._environ = environ if environ is not None else dict(os.environ)
        self._runtime_config = (
            runtime_config
            if runtime_config is not None
            else load_runtime_config(environ=self._environ)
        )
        self._credentials_file = credentials_file or self._environ.get(
            "TOWA_CREDENTIALS_FILE",
            str(Path.home() / ".config" / "towa" / "model_engine" / "credentials.json"),
        )

    def resolve_for_stage(
        self,
        *,
        stage_name: str,
        runtime_context: StageRuntimeContext,
        stage_config: dict[str, object],
    ) -> tuple[dict[str, CredentialBinding], dict[str, ResolvedCredential]]:
        provider = self._provider_for_stage(stage_name, stage_config)
        if provider is None:
            return {}, {}

        if runtime_context.mode is ExecutionMode.SAAS:
            return self._resolve_platform_binding(provider)
        return self._resolve_local_binding(provider, runtime_context)

    def _provider_for_stage(self, stage_name: str, stage_config: dict[str, object]) -> Optional[str]:
        if bool(stage_config.get("skip_provider_resolution")):
            return None

        explicit_provider = stage_config.get("provider")
        if isinstance(explicit_provider, str) and explicit_provider:
            return explicit_provider

        if stage_name == "inpaint":
            return "nanobanana"
        if stage_name == "translation":
            return "translation_provider"
        return None

    def _resolve_platform_binding(
        self,
        provider: str,
    ) -> tuple[dict[str, CredentialBinding], dict[str, ResolvedCredential]]:
        env_key = _platform_api_key_env(provider)
        secret = runtime_config_value(
            self._runtime_config,
            env_key,
            aliases=_provider_api_key_aliases(provider),
            environ=self._environ,
        )
        if not secret:
            raise CredentialResolutionError(
                f"Missing platform credential for provider={provider} env={env_key}"
            )

        version = runtime_config_value(
            self._runtime_config,
            _platform_version_env(provider),
            default=_today_version(),
            aliases=_provider_version_aliases(provider),
            environ=self._environ,
        )
        binding = CredentialBinding(
            provider=provider,
            credential_source=CredentialSource.PLATFORM_MANAGED,
            credential_id=f"platform/{provider}/default",
            credential_version=version,
            billing_mode=BillingMode.PLATFORM_CREDIT,
        )
        resolved = ResolvedCredential(binding=binding, secrets={"api_key": secret})
        return {"primary_provider": binding}, {"primary_provider": resolved}

    def _resolve_local_binding(
        self,
        provider: str,
        runtime_context: StageRuntimeContext,
    ) -> tuple[dict[str, CredentialBinding], dict[str, ResolvedCredential]]:
        session_secret = runtime_context.session_provider_secrets.get(provider)
        if session_secret:
            binding = CredentialBinding(
                provider=provider,
                credential_source=CredentialSource.USER_PERSONAL_SESSION,
                credential_id=f"session/{provider}/active",
                credential_version="session",
                billing_mode=BillingMode.USER_DIRECT,
            )
            resolved = ResolvedCredential(binding=binding, secrets={"api_key": session_secret})
            return {"primary_provider": binding}, {"primary_provider": resolved}

        persisted = self._read_persisted_provider(provider)
        if not persisted:
            raise CredentialResolutionError(
                f"Missing local credential for provider={provider} file={self._credentials_file}"
            )

        binding = CredentialBinding(
            provider=provider,
            credential_source=CredentialSource.USER_PERSONAL_PERSISTED,
            credential_id=f"user/local/{provider}",
            credential_version=str(persisted.get("updated_at") or "persisted"),
            billing_mode=BillingMode.USER_DIRECT,
        )
        resolved = ResolvedCredential(binding=binding, secrets={"api_key": str(persisted["api_key"])})
        return {"primary_provider": binding}, {"primary_provider": resolved}

    def _read_persisted_provider(self, provider: str) -> Optional[dict[str, object]]:
        path = Path(self._credentials_file)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        providers = data.get("providers", {})
        entry = providers.get(provider)
        if not isinstance(entry, dict):
            return None
        if not entry.get("api_key"):
            return None
        return entry


def _platform_api_key_env(provider: str) -> str:
    normalized = provider.upper().replace("-", "_")
    return f"TOWA_PLATFORM_PROVIDER_{normalized}_API_KEY"


def _platform_version_env(provider: str) -> str:
    normalized = provider.upper().replace("-", "_")
    return f"TOWA_PLATFORM_PROVIDER_{normalized}_CREDENTIAL_VERSION"


def _provider_api_key_aliases(provider: str) -> tuple[str, ...]:
    normalized = provider.upper().replace("-", "_")
    return (
        f"TOWA_{normalized}_API_KEY",
        f"{provider}_api_key",
        f"inpaint.{provider}_api_key",
        f"providers.{provider}.api_key",
    )


def _provider_version_aliases(provider: str) -> tuple[str, ...]:
    return (
        f"{provider}_credential_version",
        f"providers.{provider}.credential_version",
    )


def _today_version() -> str:
    return datetime.now(timezone.utc).date().isoformat()
