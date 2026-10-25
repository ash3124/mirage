"""Common image, hashing, and file-ID helpers."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from PIL import Image


def load_rgb_image(path: str | Path) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGB").copy()


def sha256_hex(content: bytes) -> str:
    return sha256(content).hexdigest()


def create_file_id() -> str:
    return uuid4().hex
