"""Built-in model registration helpers."""

from .craft_text_detection import (
    CRAFT_TEXT_DETECTION_MODEL_ID,
    build_craft_text_detection_adapter,
    build_craft_text_detection_manifest,
    craft_text_detection_handler,
    register_craft_text_detection_model,
)

__all__ = [
    "CRAFT_TEXT_DETECTION_MODEL_ID",
    "build_craft_text_detection_adapter",
    "build_craft_text_detection_manifest",
    "craft_text_detection_handler",
    "register_craft_text_detection_model",
]
