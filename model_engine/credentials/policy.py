"""Who pays for a SaaS job — interim operating policy (2026-09).

A signed-in web (SaaS) user runs AI in one of two credential modes:

- platform (default): the shared platform key, billed to their credits through
  a service_engine usage hold (which also enforces the optional cloud password).
- personal: their own provider key, sent per request as
  ``runtime_context.session_provider_secrets``. No usage hold, and never a
  fallback to the platform key.

The client only picks the mode and one of PERSONAL_PROVIDERS; endpoints and
models are decided server-side. See model_engine/docs/SESSION_AND_CREDENTIAL_IMPLEMENTATION.md §5.
"""
from __future__ import annotations

from ..contracts.stages import ExecutionMode, StageRuntimeContext

PERSONAL_PROVIDERS = ("factchat", "gemini")


def is_personal_saas(runtime_context: StageRuntimeContext) -> bool:
    return (
        runtime_context.mode is ExecutionMode.SAAS
        and runtime_context.metadata.get("credential_mode") == "personal"
    )


def personal_provider(runtime_context: StageRuntimeContext) -> str | None:
    """The chosen personal provider, or None when not in (valid) personal mode."""
    if not is_personal_saas(runtime_context):
        return None
    provider = runtime_context.metadata.get("personal_provider")
    return provider if provider in PERSONAL_PROVIDERS else None
