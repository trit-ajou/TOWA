from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CredentialSource(str, Enum):
    PLATFORM_MANAGED = "platform_managed"
    USER_PERSONAL_PERSISTED = "user_personal_persisted"
    USER_PERSONAL_SESSION = "user_personal_session"
    WORKER_IDENTITY = "worker_identity"
    NONE = "none"


class BillingMode(str, Enum):
    PLATFORM_CREDIT = "platform_credit"
    USER_DIRECT = "user_direct"
    NONE = "none"


@dataclass
class CredentialBinding:
    provider: str
    credential_source: CredentialSource
    credential_id: str
    credential_version: str
    billing_mode: BillingMode


@dataclass
class ResolvedCredential:
    binding: CredentialBinding
    secrets: dict[str, str] = field(default_factory=dict)

    def secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self.secrets.get(key, default)
