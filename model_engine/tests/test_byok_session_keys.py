from __future__ import annotations

import unittest

from model_engine.api.jobs import _translation_provider_config_from_runtime
from model_engine.contracts.credentials import BillingMode, CredentialSource
from model_engine.contracts.stages import ExecutionMode, StageRuntimeContext
from model_engine.credentials import DefaultCredentialResolver

# BYOK contract the UI relies on: a cloud (SaaS) user who registered their own
# key sends it as runtime_context.session_provider_secrets, and it must win over
# the shared platform key for both the translation and the inpaint provider.

USER_KEY = "user-own-key"
PLATFORM_ENV = {
    "TOWA_PLATFORM_PROVIDER_MINDLOGIC_API_KEY": "platform-mindlogic",
    "TOWA_PLATFORM_PROVIDER_OPENAI_COMPATIBLE_API_KEY": "platform-openai",
}


def _saas_context(secrets: dict[str, str] | None = None, **metadata: object) -> StageRuntimeContext:
    return StageRuntimeContext(
        mode=ExecutionMode.SAAS,
        workspace_uri="file:///tmp/towa/saas",
        session_provider_secrets=dict(secrets or {}),
        metadata=dict(metadata),
    )


class SessionKeyResolutionTests(unittest.TestCase):
    def _resolve(self, stage_name: str, provider: str, secrets: dict[str, str]):
        resolver = DefaultCredentialResolver(environ=dict(PLATFORM_ENV))
        bindings, resolved = resolver.resolve_for_stage(
            stage_name=stage_name,
            runtime_context=_saas_context(secrets),
            stage_config={"provider": provider},
        )
        return bindings["primary_provider"], resolved["primary_provider"]

    def test_user_key_wins_over_platform_key_for_inpaint(self) -> None:
        binding, resolved = self._resolve("inpaint", "mindlogic", {"mindlogic": USER_KEY})
        self.assertEqual(CredentialSource.USER_PERSONAL_SESSION, binding.credential_source)
        self.assertEqual(BillingMode.USER_DIRECT, binding.billing_mode)
        self.assertEqual(USER_KEY, resolved.secret("api_key"))

    def test_user_key_wins_over_platform_key_for_translation(self) -> None:
        binding, resolved = self._resolve("translation", "openai_compatible", {"openai_compatible": USER_KEY})
        self.assertEqual(CredentialSource.USER_PERSONAL_SESSION, binding.credential_source)
        self.assertEqual(USER_KEY, resolved.secret("api_key"))

    def test_without_user_key_saas_uses_platform_key(self) -> None:
        binding, resolved = self._resolve("inpaint", "mindlogic", {})
        self.assertEqual(CredentialSource.PLATFORM_MANAGED, binding.credential_source)
        self.assertEqual("platform-mindlogic", resolved.secret("api_key"))


class TranslationStageConfigTests(unittest.TestCase):
    def test_user_key_routes_translation_through_the_resolver(self) -> None:
        config = _translation_provider_config_from_runtime(
            _saas_context({"openai_compatible": USER_KEY}, translation_backend="openai_compatible")
        )
        self.assertEqual("openai_compatible", config.get("provider"))
        self.assertNotIn("skip_provider_resolution", config)

    def test_without_user_key_translation_skips_the_resolver(self) -> None:
        config = _translation_provider_config_from_runtime(
            _saas_context({}, translation_backend="openai_compatible")
        )
        self.assertTrue(config.get("skip_provider_resolution"))
        self.assertNotIn("provider", config)


if __name__ == "__main__":
    unittest.main()
