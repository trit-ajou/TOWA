from __future__ import annotations

from types import SimpleNamespace
import unittest

from model_engine.api.jobs import (
    FACTCHAT_GATEWAY_BASE_URL,
    ModelJobError,
    ModelJobManager,
    _inpaint_model_id_from_runtime,
    _inpaint_provider_config_from_runtime,
    _translation_model_id_from_runtime,
    _translation_provider_config_from_runtime,
)
from model_engine.builtin_models import (
    MINDLOGIC_INPAINT_MODEL_ID,
    NANOBANANA_INPAINT_MODEL_ID,
    OPENAI_COMPATIBLE_TRANSLATION_MODEL_ID,
    VERTEX_TRANSLATION_MODEL_ID,
)
from model_engine.contracts.credentials import BillingMode, CredentialSource
from model_engine.contracts.stages import ExecutionMode, StageRuntimeContext
from model_engine.credentials import DefaultCredentialResolver
from model_engine.credentials.resolver import CredentialResolutionError

# Interim policy (2026-09): a SaaS user runs AI either on the platform key
# (billed to credits) or, in personal mode, on their own key for a provider
# picked from a fixed list. See model_engine/credentials/policy.py.

USER_KEY = "user-own-key"
PLATFORM_ENV = {
    "TOWA_PLATFORM_PROVIDER_MINDLOGIC_API_KEY": "platform-mindlogic",
    "TOWA_PLATFORM_PROVIDER_OPENAI_COMPATIBLE_API_KEY": "platform-openai",
}


def _ctx(mode=ExecutionMode.SAAS, secrets=None, **metadata) -> StageRuntimeContext:
    return StageRuntimeContext(
        mode=mode,
        workspace_uri="file:///tmp/towa",
        session_provider_secrets=dict(secrets or {}),
        metadata=dict(metadata),
    )


def _personal(provider: str, secrets=None) -> StageRuntimeContext:
    return _ctx(secrets=secrets, credential_mode="personal", personal_provider=provider)


def _resolve(ctx: StageRuntimeContext, stage: str, provider: str):
    resolver = DefaultCredentialResolver(environ=dict(PLATFORM_ENV))
    bindings, resolved = resolver.resolve_for_stage(stage_name=stage, runtime_context=ctx, stage_config={"provider": provider})
    return bindings["primary_provider"], resolved["primary_provider"]


class CredentialModeTests(unittest.TestCase):
    def test_platform_mode_uses_platform_key_even_if_a_user_key_is_sent(self) -> None:
        binding, resolved = _resolve(_ctx(secrets={"mindlogic": USER_KEY}), "inpaint", "mindlogic")
        self.assertEqual(CredentialSource.PLATFORM_MANAGED, binding.credential_source)
        self.assertEqual(BillingMode.PLATFORM_CREDIT, binding.billing_mode)
        self.assertEqual("platform-mindlogic", resolved.secret("api_key"))

    def test_personal_mode_uses_the_user_key(self) -> None:
        binding, resolved = _resolve(_personal("factchat", {"mindlogic": USER_KEY}), "inpaint", "mindlogic")
        self.assertEqual(CredentialSource.USER_PERSONAL_SESSION, binding.credential_source)
        self.assertEqual(BillingMode.USER_DIRECT, binding.billing_mode)
        self.assertEqual(USER_KEY, resolved.secret("api_key"))

    def test_personal_mode_never_falls_back_to_the_platform_key(self) -> None:
        with self.assertRaises(CredentialResolutionError):
            _resolve(_personal("factchat", {}), "inpaint", "mindlogic")

    def test_local_mode_keeps_per_request_keys(self) -> None:
        binding, resolved = _resolve(_ctx(mode=ExecutionMode.LOCAL, secrets={"mindlogic": USER_KEY}), "inpaint", "mindlogic")
        self.assertEqual(CredentialSource.USER_PERSONAL_SESSION, binding.credential_source)
        self.assertEqual(USER_KEY, resolved.secret("api_key"))


class SaasRoutingIsServerDecidedTests(unittest.TestCase):
    """Security: in SaaS the client must not redirect the platform key."""

    def test_saas_ignores_a_client_supplied_translation_endpoint_and_key(self) -> None:
        config = _translation_provider_config_from_runtime(
            _ctx(
                translation_backend="openai_compatible",
                openai_compatible_base_url="https://attacker.example/v1",
                openai_compatible_api_key="attacker-key",
                translation_model_name="attacker-model",
            )
        )
        self.assertNotEqual("https://attacker.example/v1", config.get("base_url"))
        self.assertNotEqual("attacker-key", config.get("api_key"))
        self.assertNotEqual("attacker-model", config.get("model_name"))

    def test_saas_ignores_a_client_supplied_inpaint_provider(self) -> None:
        ctx = _ctx(inpaint_provider="attacker-provider", inpaint_model_name="attacker-model")
        self.assertNotEqual("attacker-provider", _inpaint_provider_config_from_runtime(ctx).get("provider"))
        self.assertNotEqual("attacker-model", _inpaint_provider_config_from_runtime(ctx).get("model_name"))

    def test_local_keeps_client_overrides(self) -> None:
        config = _translation_provider_config_from_runtime(
            _ctx(mode=ExecutionMode.LOCAL, translation_backend="openai_compatible", openai_compatible_base_url="http://127.0.0.1:9/v1")
        )
        self.assertEqual("http://127.0.0.1:9/v1", config["base_url"])


class PersonalProviderRoutingTests(unittest.TestCase):
    def test_factchat_routes_to_the_gateway_without_the_platform_key(self) -> None:
        ctx = _personal("factchat", {"openai_compatible": USER_KEY, "mindlogic": USER_KEY})
        config = _translation_provider_config_from_runtime(ctx)
        self.assertEqual(OPENAI_COMPATIBLE_TRANSLATION_MODEL_ID, _translation_model_id_from_runtime(ctx))
        self.assertEqual("openai_compatible", config["provider"])
        self.assertEqual(FACTCHAT_GATEWAY_BASE_URL, config["base_url"])
        self.assertNotIn("api_key", config)
        self.assertEqual(MINDLOGIC_INPAINT_MODEL_ID, _inpaint_model_id_from_runtime(ctx))
        self.assertEqual("mindlogic", _inpaint_provider_config_from_runtime(ctx)["provider"])

    def test_gemini_routes_to_the_gemini_developer_api(self) -> None:
        ctx = _personal("gemini", {"translation_provider": USER_KEY, "nanobanana": USER_KEY})
        config = _translation_provider_config_from_runtime(ctx)
        self.assertEqual(VERTEX_TRANSLATION_MODEL_ID, _translation_model_id_from_runtime(ctx))
        self.assertEqual("translation_provider", config["provider"])
        self.assertIs(False, config["gemini_vertexai"])
        self.assertEqual(NANOBANANA_INPAINT_MODEL_ID, _inpaint_model_id_from_runtime(ctx))
        self.assertEqual("nanobanana", _inpaint_provider_config_from_runtime(ctx)["provider"])


class PersonalModeJobTests(unittest.TestCase):
    def _manager(self) -> ModelJobManager:
        def no_service_calls():
            raise AssertionError("personal-key jobs must not call service_engine for a usage hold")

        return ModelJobManager(service_client_factory=no_service_calls)

    def test_personal_mode_skips_the_platform_credit_hold(self) -> None:
        submission = SimpleNamespace(runtime_context=_personal("factchat", {"mindlogic": USER_KEY}))
        self.assertIsNone(self._manager()._authorize_usage_hold(submission))

    def test_unknown_personal_provider_is_rejected(self) -> None:
        submission = SimpleNamespace(runtime_context=_personal("openrouter"))
        with self.assertRaises(ModelJobError) as caught:
            self._manager()._normalized_submission(submission, authorization="Bearer s")
        self.assertEqual("invalid_personal_provider", caught.exception.code)
        self.assertEqual(422, caught.exception.status_code)


if __name__ == "__main__":
    unittest.main()
