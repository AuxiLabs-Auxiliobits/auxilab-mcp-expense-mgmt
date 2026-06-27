"""HEIC → JPEG conversion for receipt uploads (SCOPING §6.1 — "HEIC needing conversion").

iPhones produce HEIC images that browsers and most OCR engines (incl. older Azure Document
Intelligence paths) can't render. We transcode HEIC to JPEG at upload so the stored receipt
previews in the portal and reconciles downstream like any other image.

The transcode needs `pillow` + `pillow-heif` (the `[images]` extra). When they aren't
installed the original bytes are stored unchanged and a warning is logged — the upload still
succeeds (graceful degradation), it just won't render in browsers that lack HEIC support.
"""

from __future__ import annotations

import io
import logging
from pathlib import PurePosixPath

logger = logging.getLogger(__name__)

_HEIC_EXTENSIONS = {".heic", ".heif"}
_JPEG_TYPE = "image/jpeg"


def is_heic(filename: str, file_type: str | None = None) -> bool:
    ext = PurePosixPath(filename).suffix.lower()
    return ext in _HEIC_EXTENSIONS or (file_type or "").lower() in {"image/heic", "image/heif"}


def convert_heic_to_jpeg(filename: str, data: bytes, file_type: str) -> tuple[str, bytes, str]:
    """Return `(filename, data, file_type)`, transcoding HEIC → JPEG when possible.

    Non-HEIC inputs pass through untouched. HEIC is decoded and re-encoded as JPEG with the
    extension swapped to `.jpg`; if the imaging libraries are missing or the bytes don't
    decode, the original input is returned unchanged (the caller still gets a valid upload).
    """
    if not is_heic(filename, file_type):
        return filename, data, file_type

    try:
        import pillow_heif  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415

        pillow_heif.register_heif_opener()
        image = Image.open(io.BytesIO(data))
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=90)
    except ImportError:
        logger.warning(
            "HEIC upload %s stored as-is: install the [images] extra (pillow + pillow-heif) "
            "to enable conversion",
            filename,
        )
        return filename, data, file_type
    except Exception as exc:  # noqa: BLE001 — corrupt/unsupported HEIC: keep original bytes
        logger.warning("HEIC conversion failed for %s (%s); storing original", filename, exc)
        return filename, data, file_type

    new_name = PurePosixPath(filename).with_suffix(".jpg").name
    logger.debug("converted HEIC %s → JPEG %s", filename, new_name)
    return new_name, buffer.getvalue(), _JPEG_TYPE
