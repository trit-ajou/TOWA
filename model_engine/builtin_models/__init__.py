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
from .vertex_translation import (
    VERTEX_TRANSLATION_DEFAULT_MODEL,
    VERTEX_TRANSLATION_MODEL_ID,
    build_vertex_translation_adapter,
    build_vertex_translation_manifest,
    register_vertex_translation_model,
    run_vertex_translation,
    vertex_translation_handler,
)

__all__ = [
    "CRAFT_TEXT_DETECTION_MODEL_ID",
    "MANGA_OCR_MODEL_ID",
    "NANOBANANA_DEFAULT_PROMPT",
    "NANOBANANA_IMAGE_MODEL",
    "NANOBANANA_INPAINT_MODEL_ID",
    "VERTEX_TRANSLATION_DEFAULT_MODEL",
    "VERTEX_TRANSLATION_MODEL_ID",
    "build_craft_text_detection_adapter",
    "build_craft_text_detection_manifest",
    "build_manga_ocr_adapter",
    "build_manga_ocr_manifest",
    "build_nanobanana_inpaint_adapter",
    "build_nanobanana_inpaint_manifest",
    "build_vertex_translation_adapter",
    "build_vertex_translation_manifest",
    "craft_text_detection_handler",
    "manga_ocr_handler",
    "nanobanana_inpaint_handler",
    "register_vertex_translation_model",
    "register_craft_text_detection_model",
    "register_manga_ocr_model",
    "register_nanobanana_inpaint_model",
    "run_vertex_translation",
    "vertex_translation_handler",
]
