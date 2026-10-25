"""Optional DWT-DCT watermark encoding and verification."""

from __future__ import annotations

import re

import cv2
import numpy as np
from PIL import Image

from ..schemas import WatermarkVerifyResponse

_TAG_PATTERN = re.compile(r"^[A-Z0-9]{1,4}$")
_WATERMARK_PATTERN = re.compile(rb"^[A-Z0-9_]{4}$")
_MINIMUM_SIDE_PX = 256


def embed_watermark(image: Image.Image, tag: str) -> Image.Image:
    if not _TAG_PATTERN.fullmatch(tag):
        raise ValueError("Watermark tags must be 1 to 4 uppercase letters or digits.")
    if min(image.size) < _MINIMUM_SIDE_PX:
        raise ValueError("Watermark images must be at least 256 pixels per side.")

    from imwatermark import WatermarkEncoder

    encoder = WatermarkEncoder()
    encoder.set_watermark("bytes", tag.ljust(4, "_").encode("ascii"))
    image_bgr = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    encoded_bgr = encoder.encode(image_bgr, "dwtDct")
    encoded_rgb = cv2.cvtColor(encoded_bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(encoded_rgb)


def verify_watermark(image: Image.Image) -> WatermarkVerifyResponse:
    if min(image.size) < _MINIMUM_SIDE_PX:
        return WatermarkVerifyResponse(found=False, tag=None)

    from imwatermark import WatermarkDecoder

    decoder = WatermarkDecoder("bytes", 32)
    image_bgr = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    decoded = decoder.decode(image_bgr, "dwtDct")
    if isinstance(decoded, str):
        decoded_bytes = decoded.encode("ascii", errors="ignore")
    else:
        decoded_bytes = bytes(decoded)
    if not _WATERMARK_PATTERN.fullmatch(decoded_bytes):
        return WatermarkVerifyResponse(found=False, tag=None)
    tag = decoded_bytes.decode("ascii").rstrip("_")
    if not tag:
        return WatermarkVerifyResponse(found=False, tag=None)
    return WatermarkVerifyResponse(found=True, tag=tag)
