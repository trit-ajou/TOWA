"""Built-in model registration helpers."""

from .craft_text_detection import (
    CRAFT_TEXT_DETECTION_MODEL_ID,
    build_craft_text_detection_adapter,
    build_craft_text_detection_manifest,
    craft_text_detection_handler,
    register_craft_text_detection_model,
)
from .manga_ocr import (
    MANGA_OCR_MODEL_ID,
    build_manga_ocr_adapter,
    build_manga_ocr_manifest,
    manga_ocr_handler,
    register_manga_ocr_model,
)
from .nanobanana_inpaint import (
    NANOBANANA_DEFAULT_PROMPT,
    NANOBANANA_IMAGE_MODEL,
    NANOBANANA_INPAINT_MODEL_ID,
    build_nanobanana_inpaint_adapter,
    build_nanobanana_inpaint_manifest,
    nanobanana_inpaint_handler,
    register_nanobanana_inpaint_model,
)

__all__ = [
    "CRAFT_TEXT_DETECTION_MODEL_ID",
    "MANGA_OCR_MODEL_ID",
    "NANOBANANA_DEFAULT_PROMPT",
    "NANOBANANA_IMAGE_MODEL",
    "NANOBANANA_INPAINT_MODEL_ID",
    "build_craft_text_detection_adapter",
    "build_craft_text_detection_manifest",
    "build_manga_ocr_adapter",
    "build_manga_ocr_manifest",
    "build_nanobanana_inpaint_adapter",
    "build_nanobanana_inpaint_manifest",
    "craft_text_detection_handler",
    "manga_ocr_handler",
    "nanobanana_inpaint_handler",
    "register_craft_text_detection_model",
    "register_manga_ocr_model",
    "register_nanobanana_inpaint_model",
]
