from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.modules.projects.service import BinaryPayload, SnapshotValidationError

WEBP_MEDIA_TYPE = "image/webp"


def normalize_thumbnail_payload(
    payload: BinaryPayload,
    *,
    max_width: int,
    quality: int,
) -> BinaryPayload:
    try:
        with Image.open(BytesIO(payload.content)) as image:
            image = ImageOps.exif_transpose(image)
            image.load()
            normalized = _resize_for_thumbnail(image, max_width=max_width)
            if normalized.mode in {"RGBA", "LA"} or "transparency" in normalized.info:
                normalized = normalized.convert("RGBA")
            else:
                normalized = normalized.convert("RGB")
            output = BytesIO()
            normalized.save(
                output,
                format="WEBP",
                quality=quality,
                lossless=False,
                method=6,
            )
    except (OSError, UnidentifiedImageError) as exc:
        raise SnapshotValidationError("thumbnail must contain a valid image payload.") from exc

    content = output.getvalue()
    if not content:
        raise SnapshotValidationError("thumbnail WebP encoding produced an empty payload.")
    return BinaryPayload(content=content, media_type=WEBP_MEDIA_TYPE)


def _resize_for_thumbnail(image: Image.Image, *, max_width: int) -> Image.Image:
    if max_width <= 0:
        raise SnapshotValidationError("thumbnail max width must be positive.")
    if image.width <= max_width:
        return image.copy()
    target_height = max(1, round(image.height * (max_width / image.width)))
    return image.resize((max_width, target_height), Image.Resampling.LANCZOS)
