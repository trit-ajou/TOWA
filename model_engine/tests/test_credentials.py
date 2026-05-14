from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from model_engine.contracts.credentials import BillingMode, CredentialSource
from model_engine.contracts.stages import ExecutionMode, StageRuntimeContext
from model_engine.credentials import DefaultCredentialResolver


class DefaultCredentialResolverTests(unittest.TestCase):
    def test_resolves_local_persisted_credential_for_inpaint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            credentials_path = Path(tmpdir) / "credentials.json"
            credentials_path.write_text(
                json.dumps(
                    {
                        "providers": {
                            "nanobanana": {
                                "api_key": "local-secret",
                                "updated_at": "2026-03-27T00:00:00Z",
                            }
                        }
                    }
                )
            )
            resolver = DefaultCredentialResolver(credentials_file=str(credentials_path), environ={})
            runtime_context = StageRuntimeContext(
                mode=ExecutionMode.LOCAL,
                workspace_uri="file:///tmp/towa/local",
            )

            bindings, resolved = resolver.resolve_for_stage(
                stage_name="inpaint",
                runtime_context=runtime_context,
                stage_config={},
            )

            binding = bindings["primary_provider"]
            self.assertEqual("nanobanana", binding.provider)
            self.assertEqual(CredentialSource.USER_PERSONAL_PERSISTED, binding.credential_source)
            self.assertEqual(BillingMode.USER_DIRECT, binding.billing_mode)
            self.assertEqual("local-secret", resolved["primary_provider"].secret("api_key"))

    def test_resolves_platform_credential_for_saas(self) -> None:
        resolver = DefaultCredentialResolver(
            environ={
                "TOWA_PLATFORM_PROVIDER_NANOBANANA_API_KEY": "platform-secret",
                "TOWA_PLATFORM_PROVIDER_NANOBANANA_CREDENTIAL_VERSION": "2026-03-27",
            }
        )
        runtime_context = StageRuntimeContext(
            mode=ExecutionMode.SAAS,
            workspace_uri="file:///tmp/towa/saas",
        )

        bindings, resolved = resolver.resolve_for_stage(
            stage_name="inpaint",
            runtime_context=runtime_context,
            stage_config={},
        )

        binding = bindings["primary_provider"]
        self.assertEqual(CredentialSource.PLATFORM_MANAGED, binding.credential_source)
        self.assertEqual(BillingMode.PLATFORM_CREDIT, binding.billing_mode)
        self.assertEqual("platform-secret", resolved["primary_provider"].secret("api_key"))

    def test_resolves_platform_credential_from_runtime_config(self) -> None:
        resolver = DefaultCredentialResolver(
            environ={},
            runtime_config={
                "inpaint": {
                    "mindlogic_api_key": "runtime-secret",
                },
                "providers": {
                    "mindlogic": {
                        "credential_version": "runtime-version",
                    }
                },
            },
        )
        runtime_context = StageRuntimeContext(
            mode=ExecutionMode.SAAS,
            workspace_uri="file:///tmp/towa/saas",
        )

        bindings, resolved = resolver.resolve_for_stage(
            stage_name="inpaint",
            runtime_context=runtime_context,
            stage_config={"provider": "mindlogic"},
        )

        binding = bindings["primary_provider"]
        self.assertEqual("mindlogic", binding.provider)
        self.assertEqual("runtime-version", binding.credential_version)
        self.assertEqual(CredentialSource.PLATFORM_MANAGED, binding.credential_source)
        self.assertEqual("runtime-secret", resolved["primary_provider"].secret("api_key"))


if __name__ == "__main__":
    unittest.main()
