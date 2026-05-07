from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from model_engine.contracts.artifacts import ArtifactDescriptor, ArtifactStatus, InMemoryArtifactRegistry
from model_engine.contracts.document_ir import DocumentIR, LayerIR, TextBlock
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

    def test_replace_text_blocks_overwrites_existing_blocks(self) -> None:
        document = DocumentIR(
            id="doc_2",
            name="page-2",
            width=100,
            height=200,
            text_blocks=[TextBlock(block_id="block-old", source_lang_text="old")],
        )

        apply_patches(
            document,
            [
                PatchOperation(
                    op=PatchOp.REPLACE_TEXT_BLOCKS,
                    payload={
                        "text_blocks": [
                            {
                                "block_id": "block-new-1",
                                "source_lang_text": "첫 줄",
                                "source_region_ref": "region_0001",
                            },
                            {
                                "block_id": "block-new-2",
                                "source_lang_text": "둘째 줄",
                                "translated_text": "",
                                "writing_mode": "vertical",
                                "source_region_ref": "region_0002",
                            },
                        ]
                    },
                )
            ],
        )

        self.assertEqual(["block-new-1", "block-new-2"], [block.block_id for block in document.text_blocks])
        self.assertEqual("첫 줄", document.text_blocks[0].source_lang_text)
        self.assertEqual("vertical", document.text_blocks[1].writing_mode)


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
