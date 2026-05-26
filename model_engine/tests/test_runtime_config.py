from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from model_engine.config.runtime_config import load_runtime_config, runtime_config_value


class RuntimeConfigTests(unittest.TestCase):
    def test_load_runtime_config_reads_json_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "runtime_config.json"
            path.write_text('{"TOWA_TRANSLATION_BACKEND": "openai_compatible"}', encoding="utf-8")

            config = load_runtime_config(config_path=str(path))

            self.assertEqual("openai_compatible", config["TOWA_TRANSLATION_BACKEND"])

    def test_runtime_config_value_prefers_env_over_json(self) -> None:
        config = {
            "TOWA_TRANSLATION_BACKEND": "openai_compatible",
            "translation": {"model_name": "json-model"},
        }

        self.assertEqual(
            "vertex",
            runtime_config_value(
                config,
                "TOWA_TRANSLATION_BACKEND",
                environ={"TOWA_TRANSLATION_BACKEND": "vertex"},
            ),
        )
        self.assertEqual(
            "json-model",
            runtime_config_value(
                config,
                "TOWA_TRANSLATION_MODEL_NAME",
                aliases=("translation.model_name",),
                environ={},
            ),
        )


if __name__ == "__main__":
    unittest.main()
