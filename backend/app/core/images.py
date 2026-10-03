"""Validation and re-encoding of uploaded images."""

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.errors import UnprocessableError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
# Upper bound for decoded pixels, to keep memory use small on the shared server.
MAX_PIXELS = 60_000_000
JPEG_QUALITY = 85


def reencode_image(data: bytes, *, max_edge: int) -> tuple[bytes, str]:
    """Decode an upload and return it as a JPEG without metadata, scaled to `max_edge`.

    Re-encoding drops EXIF data (including GPS) and anything hidden in the file.
    """
    invalid = UnprocessableError("File is not a supported image", code="invalid_image")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in ALLOWED_FORMATS:
                raise invalid
            if image.width * image.height > MAX_PIXELS:
                raise UnprocessableError("Image has too many pixels", code="image_too_large")
            image = ImageOps.exif_transpose(image)
            if image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info:
                image = image.convert("RGBA")
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
            image.thumbnail((max_edge, max_edge))
            output = BytesIO()
            image.save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise invalid from exc
    return output.getvalue(), "image/jpeg"
