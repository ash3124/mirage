"""Stable Diffusion VAE-based PGD cloak processing."""

from __future__ import annotations

from functools import lru_cache
import hashlib
import importlib
import logging
from pathlib import Path
import random
import time
from typing import Callable

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw, ImageFilter

from ..config import BACKEND_ROOT, settings
from ..schemas import (
    CloakMetrics,
    CloakRequest,
    CloakResult,
    Hashes,
    WorkingSize,
)
from .privacy import ProcessedImage, process_image
from .robustness import compute_robustness_metrics

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[str, int], None]
TARGET_PATH = BACKEND_ROOT / "assets" / "target.png"
FACE_MASK_BLUR_SIGMA_PX = 12
PRESETS = {
    "light": (6, 40),
    "standard": (12, 80),
    "strong": (16, 120),
}


@lru_cache(maxsize=1)
def load_vae() -> torch.nn.Module:
    from diffusers import AutoencoderKL

    device = settings.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    vae = AutoencoderKL.from_pretrained(
        settings.sd_repo,
        subfolder="vae",
        torch_dtype=torch.float32,
    ).to(device)
    vae.eval()
    for parameter in vae.parameters():
        parameter.requires_grad_(False)
    return vae


def _to_tensor(image: Image.Image, device: torch.device) -> torch.Tensor:
    array = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0).to(device)


def _mediapipe_face_boxes(image: Image.Image) -> list[tuple[int, int, int, int]]:
    import mediapipe as mp

    detection_api = getattr(getattr(mp, "solutions", None), "face_detection", None)
    if detection_api is None:
        detection_api = importlib.import_module(
            "mediapipe.python.solutions.face_detection"
        )

    rgb = np.asarray(image.convert("RGB"))
    with detection_api.FaceDetection(
        model_selection=1,
        min_detection_confidence=0.5,
    ) as detector:
        result = detector.process(rgb)

    boxes = []
    for detection in result.detections or []:
        bounds = detection.location_data.relative_bounding_box
        boxes.append(
            (
                round(bounds.xmin * image.width),
                round(bounds.ymin * image.height),
                round((bounds.xmin + bounds.width) * image.width),
                round((bounds.ymin + bounds.height) * image.height),
            )
        )
    return boxes


def _haar_face_boxes(image: Image.Image) -> list[tuple[int, int, int, int]]:
    import cv2

    if not hasattr(cv2, "CascadeClassifier") or not hasattr(cv2, "data"):
        raise RuntimeError("OpenCV Haar-cascade support is unavailable.")
    rgb = np.asarray(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(cascade_path)
    if detector.empty():
        raise RuntimeError("OpenCV Haar face detector could not be loaded.")
    return [
        (x, y, x + width, y + height)
        for x, y, width, height in detector.detectMultiScale(gray)
    ]


def _detect_faces(image: Image.Image) -> list[tuple[int, int, int, int]]:
    try:
        return _mediapipe_face_boxes(image)
    except (ImportError, AttributeError, RuntimeError, ValueError) as exc:
        logger.warning("MediaPipe face detection unavailable; trying Haar fallback: %s", exc)
    try:
        return _haar_face_boxes(image)
    except (ImportError, AttributeError, RuntimeError, ValueError) as exc:
        logger.warning("OpenCV Haar face detection unavailable: %s", exc)
        return []


def _build_mask(
    image: Image.Image,
    face_focus: bool,
    device: torch.device,
) -> tuple[torch.Tensor, bool]:
    width, height = image.size
    mask = torch.ones((1, 1, height, width), dtype=torch.float32, device=device)
    if not face_focus:
        return mask, False

    boxes = _detect_faces(image)
    if not boxes:
        return mask, False

    face_mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(face_mask)
    for left, top, right, bottom in boxes:
        center_x = (left + right) / 2
        center_y = (top + bottom) / 2
        expanded_width = (right - left) * 1.8
        expanded_height = (bottom - top) * 1.8
        draw.rectangle(
            (
                max(0, round(center_x - expanded_width / 2)),
                max(0, round(center_y - expanded_height / 2)),
                min(width, round(center_x + expanded_width / 2)),
                min(height, round(center_y + expanded_height / 2)),
            ),
            fill=255,
        )
    face_mask = face_mask.filter(
        ImageFilter.GaussianBlur(radius=FACE_MASK_BLUR_SIGMA_PX)
    )
    face_tensor = torch.from_numpy(
        np.asarray(face_mask, dtype=np.float32) / 255.0
    ).to(device=device)[None, None]
    return 0.4 + 0.6 * face_tensor, True


def _gaussian_blur(image: torch.Tensor, sigma: float) -> torch.Tensor:
    if sigma <= 1e-6:
        return image
    radius = max(1, round(3 * sigma))
    coordinates = torch.arange(
        -radius,
        radius + 1,
        device=image.device,
        dtype=image.dtype,
    )
    kernel_1d = torch.exp(-(coordinates**2) / (2 * sigma**2))
    kernel_1d /= kernel_1d.sum()
    kernel_2d = kernel_1d[:, None] * kernel_1d[None, :]
    channels = image.shape[1]
    kernel = kernel_2d.expand(channels, 1, -1, -1).contiguous()
    padded = F.pad(image, (radius, radius, radius, radius), mode="reflect")
    return F.conv2d(padded, kernel, groups=channels)


def _augment(image: torch.Tensor) -> torch.Tensor:
    augmented = _gaussian_blur(image, random.uniform(0.0, 1.0))
    noise_sigma = random.uniform(0.0, 0.02)
    if noise_sigma > 0:
        augmented = augmented + torch.randn_like(augmented) * noise_sigma
    augmented = augmented.clamp(0.0, 1.0)
    height, width = augmented.shape[-2:]
    scale = random.uniform(0.75, 1.0)
    if scale < 1.0:
        small_size = (max(1, round(height * scale)), max(1, round(width * scale)))
        augmented = F.interpolate(
            augmented,
            size=small_size,
            mode="bilinear",
            align_corners=False,
        )
        augmented = F.interpolate(
            augmented,
            size=(height, width),
            mode="bilinear",
            align_corners=False,
        )
    return augmented


def _cloak_pgd(
    x: torch.Tensor,
    vae: torch.nn.Module,
    target_latent: torch.Tensor,
    eps: float,
    steps: int,
    mask: torch.Tensor,
    callback: ProgressCallback,
    robust: bool,
) -> torch.Tensor:
    alpha = 2.5 * eps / steps
    delta = ((torch.rand_like(x) * 2 - 1) * eps * 0.1) * mask
    for index in range(steps):
        delta.requires_grad_(True)
        x_adv = torch.clamp(x + delta, 0, 1)
        input_image = _augment(x_adv) if robust else x_adv
        latent = vae.encode(input_image * 2 - 1).latent_dist.mean
        loss = F.mse_loss(latent, target_latent)
        (gradient,) = torch.autograd.grad(loss, delta)
        delta = (delta - alpha * gradient.sign()).detach()
        delta = torch.maximum(torch.minimum(delta, eps * mask), -eps * mask)
        if index % 4 == 0:
            callback("optimizing", 5 + round(75 * index / steps))
    return torch.clamp(x + delta, 0, 1).detach()


def process_cloak(
    image_bytes: bytes,
    request: CloakRequest,
    file_id: str,
    output_dir: str | Path,
    max_side_px: int,
    callback: ProgressCallback,
    expires_at: str,
) -> "CloakResult":
    """Run image intake, PGD, robustness metrics, and write cloak artifacts."""
    from ..schemas import CloakResult

    started = time.perf_counter()

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    processed: ProcessedImage = process_image(
        image_bytes,
        root / "original.png",
        max_side_px,
    )
    with Image.open(processed.original_path) as source:
        original_image = source.convert("RGB")
    vae = load_vae()
    device = next(vae.parameters()).device
    callback("detecting_face", 0)
    mask, face_found = _build_mask(original_image, request.face_focus, device)

    eps_255, gpu_steps = PRESETS[request.strength.value]
    eps = eps_255 / 255.0
    steps = int(gpu_steps * (0.4 if device.type == "cpu" else 1.0))
    x = _to_tensor(original_image, device)
    target_path = TARGET_PATH
    if not target_path.is_file():
        raise FileNotFoundError(f"Required cloak target asset is missing: {target_path}")
    with Image.open(target_path) as target_source:
        target_image = target_source.convert("RGB").resize(
            original_image.size,
            Image.Resampling.BICUBIC,
        )
    target = _to_tensor(target_image, device)
    with torch.no_grad():
        original_latent = vae.encode(x * 2 - 1).latent_dist.mean
        target_latent = vae.encode(target * 2 - 1).latent_dist.mean

    cloaked_tensor = _cloak_pgd(
        x,
        vae,
        target_latent,
        eps,
        steps,
        mask,
        callback,
        request.robust_mode,
    )
    cloaked_array = (
        cloaked_tensor[0].permute(1, 2, 0).cpu().numpy().clip(0, 1) * 255
    ).round().astype(np.uint8)
    cloaked_image = Image.fromarray(cloaked_array, mode="RGB")
    cloaked_path = root / "cloaked.png"
    cloaked_image.save(cloaked_path, format="PNG")

    callback("robustness_check", 80)
    metrics = compute_robustness_metrics(
        original_image,
        cloaked_image,
        vae,
        original_latent,
        target_latent,
        eps,
        root / "heatmap.png",
    )
    callback("finalizing", 92)

    png_bytes = cloaked_path.read_bytes()
    digest = hashlib.sha256(png_bytes).hexdigest()
    elapsed_s = time.perf_counter() - started

    callback("finalizing", 99)
    return CloakResult(
        file_id=file_id,
        original_url=f"/api/v1/files/{file_id}/original.png",
        cloaked_url=f"/api/v1/files/{file_id}/cloaked.png",
        heatmap_url=f"/api/v1/files/{file_id}/heatmap.png",
        metrics=CloakMetrics(
            protection_score=metrics.protection_score,
            robustness=metrics.robustness,
            visual_quality=metrics.visual_quality,
            working_size=WorkingSize(w=processed.width, h=processed.height),
            elapsed_s=elapsed_s,
        ),
        metadata_report=processed.metadata_report,
        hashes=Hashes(
            sha256_cloaked=digest,
            phash_original=processed.phash_original,
        ),
        watermark=None,
        face_found=face_found,
        expires_at=expires_at,
    )
