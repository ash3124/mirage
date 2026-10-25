"""Image intake, EXIF reporting, metadata stripping, and working-copy hashing."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import warnings

import imagehash
from PIL import ExifTags, Image, ImageOps, UnidentifiedImageError

from ..errors import ApiError
from ..schemas import ErrorCode, MetadataReport
from .utils import load_rgb_image

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP"}
GPS_INFO_IFD = 0x8825
EXIF_IFD = 0x8769


@dataclass(frozen=True)
class ProcessedImage:
    """Sanitized working image and contract-facing intake metadata."""

    original_path: Path
    width: int
    height: int
    phash_original: str
    metadata_report: MetadataReport


def _read_exif_report(image: Image.Image) -> MetadataReport:
    exif = image.getexif()
    root_tags = {
        ExifTags.TAGS.get(tag_id): value
        for tag_id, value in exif.items()
    }

    try:
        exif_ifd = exif.get_ifd(EXIF_IFD)
    except (KeyError, TypeError):
        exif_ifd = {}
    exif_tags = {
        ExifTags.TAGS.get(tag_id): value
        for tag_id, value in exif_ifd.items()
    }

    try:
        gps_ifd = exif.get_ifd(GPS_INFO_IFD)
    except (KeyError, TypeError):
        gps_ifd = {}
    had_gps = bool(gps_ifd)

    removed: list[str] = []
    if had_gps:
        removed.append("GPS location")
    if root_tags.get("Make") or root_tags.get("Model"):
        removed.append("Camera model")
    if any(
        root_tags.get(tag) or exif_tags.get(tag)
        for tag in ("DateTime", "DateTimeOriginal", "DateTimeDigitized")
    ):
        removed.append("Capture date")
    if root_tags.get("Software"):
        removed.append("Editing software")
    if root_tags.get("Artist") or root_tags.get("Copyright"):
        removed.append("Creator/copyright")

    return MetadataReport(had_gps=had_gps, removed=removed)


def _working_dimensions(width: int, height: int, max_side_px: int) -> tuple[int, int]:
    scale = min(1.0, max_side_px / max(width, height))
    working_width = int(width * scale) // 8 * 8
    working_height = int(height * scale) // 8 * 8
    if working_width < 8 or working_height < 8:
        raise ApiError(ErrorCode.INVALID_IMAGE)
    return working_width, working_height


def process_image(
    image_bytes: bytes,
    output_path: str | Path,
    max_side_px: int,
) -> ProcessedImage:
    """Decode and sanitize an upload into a metadata-free PNG working copy.

    Args:
        image_bytes: Raw uploaded image contents.
        output_path: Destination path for the sanitized ``original.png``.
        max_side_px: Maximum allowed working-image side (768 GPU, 512 CPU).

    Raises:
        ApiError: If the upload exceeds the byte limit or is not a supported,
            decodable image with valid working dimensions.
        ValueError: If ``max_side_px`` is not positive.
    """
    if max_side_px <= 0:
        raise ValueError("max_side_px must be greater than zero.")
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise ApiError(ErrorCode.TOO_LARGE)
    if not image_bytes:
        raise ApiError(ErrorCode.INVALID_IMAGE)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(image_bytes)) as source:
                if source.format not in SUPPORTED_FORMATS:
                    raise ApiError(ErrorCode.INVALID_IMAGE)
                source.load()
                metadata_report = _read_exif_report(source)
                oriented = ImageOps.exif_transpose(source).convert("RGB")
    except ApiError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as exc:
        raise ApiError(ErrorCode.INVALID_IMAGE) from exc

    width, height = _working_dimensions(*oriented.size, max_side_px)
    working = oriented.resize(
        (width, height),
        resample=Image.Resampling.LANCZOS,
    )

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    clean_rgb = Image.new("RGB", working.size)
    clean_rgb.paste(working)
    clean_rgb.save(destination, format="PNG")

    phash_original = str(imagehash.phash(load_rgb_image(destination)))

    return ProcessedImage(
        original_path=destination,
        width=width,
        height=height,
        phash_original=phash_original,
        metadata_report=metadata_report,
    )


def validate_image_bytes(image_bytes: bytes) -> None:
    """Validate upload byte size and decodeability before accepting a job."""
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise ApiError(ErrorCode.TOO_LARGE)
    if not image_bytes:
        raise ApiError(ErrorCode.INVALID_IMAGE)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(image_bytes)) as image:
                if image.format not in SUPPORTED_FORMATS:
                    raise ApiError(ErrorCode.INVALID_IMAGE)
                image.verify()
    except ApiError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as exc:
        raise ApiError(ErrorCode.INVALID_IMAGE) from exc
