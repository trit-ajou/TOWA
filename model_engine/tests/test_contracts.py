from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from model_engine.contracts.artifacts import ArtifactDescriptor, ArtifactStatus, InMemoryArtifactRegistry
from model_engine.contracts.document_ir import DocumentIR, LayerIR
from model_engine.contracts.patches import PatchOp, PatchOperation, apply_patches


class PatchContractTests(unittest.TestCase):
    def test_apply_patch_sequence_updates_document_ir(self) -> None:
        document = DocumentIR(
            id="doc_1",
            name="page-1",
            width=100,
            height=200,
            layers=[
                LayerIR(
                    id="layer_base",
                    name="Base",
                    type="graphic",
                    left=0,
                    top=0,
                    width=100,
                    height=200,
                    source_ref="artifact://base-v1",
                )
            ],
        )

        patches = [
            PatchOperation(
                op=PatchOp.ADD_LAYER,
                payload={
                    "layer": {
                        "id": "layer_text",
                        "name": "Text",
                        "type": "text",
                        "left": 10,
                        "top": 20,
                        "width": 40,
                        "height": 30,
                    }
                },
            ),
            PatchOperation(
                op=PatchOp.REPLACE_SOURCE_REF,
                target={"layer_id": "layer_base"},
                payload={"source_ref": "artifact://base-v2"},
            ),
            PatchOperation(
                op=PatchOp.APPEND_TEXT_BLOCKS,
                payload={
                    "text_blocks": [
                        {
                            "block_id": "block-1",
                            "source_lang_text": "안녕",
                            "translated_text": "Hello",
                        }
                    ]
                },
            ),
            PatchOperation(
                op=PatchOp.SET_STAGE_META,
                payload={"key": "text_detection", "value": {"engine": "craft"}},
            ),
        ]

        apply_patches(document, patches)

        self.assertEqual("artifact://base-v2", document.require_layer("layer_base").source_ref)
        self.assertEqual(2, len(document.layers))
        self.assertEqual("block-1", document.text_blocks[0].block_id)
        self.assertEqual({"engine": "craft"}, document.stage_meta["text_detection"])


class ArtifactRegistryTests(unittest.TestCase):
    def test_register_verify_and_release_artifact(self) -> None:
        registry = InMemoryArtifactRegistry()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "artifact.bin"
            path.write_bytes(b"abc")
            checksum = hashlib.sha256(b"abc").hexdigest()
            descriptor = ArtifactDescriptor(
                artifact_ref="artifact://sample",
                kind="bitmap",
                media_type="application/octet-stream",
                uri=path.as_uri(),
                checksum=f"sha256:{checksum}",
            )

            registry.register_artifact(descriptor)

            self.assertTrue(registry.verify_artifact("artifact://sample"))
            updated = registry.release_artifact("artifact://sample", orphaned=True)
            self.assertEqual(ArtifactStatus.ORPHANED, updated.status)
            removed = registry.gc_artifacts(remove_files=False)
            self.assertEqual(["artifact://sample"], removed)


if __name__ == "__main__":
    unittest.main()
