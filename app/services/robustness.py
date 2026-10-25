"""Cloak protection, robustness, visual-quality, and heatmap metrics."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from skimage.metrics import peak_signal_noise_ratio, structural_similarity

from ..schemas import Robustness, VisualQuality


@dataclass(frozen=True)
class RobustnessMetrics:
    protection_score: int
    robustness: Robustness
    visual_quality: VisualQuality
    heatmap_path: Path


def protection_score(
    image_latent: torch.Tensor,
    original_latent: torch.Tensor,
    target_latent: torch.Tensor,
) -> int:
    """Return target-latent protection score, clamped to the contract range."""
    original_distance = torch.linalg.vector_norm(original_latent - target_latent)
    if original_distance.item() == 0:
        raise ValueError("Original image latent equals the target latent.")
    image_distance = torch.linalg.vector_norm(image_latent - target_latent)
    score = 100.0 * (1.0 - image_distance / original_distance)
    return int(torch.clamp(score, min=0, max=100).round().item())


def _as_rgb(image: Image.Image) -> Image.Image:
    return image if image.mode == "RGB" else image.convert("RGB")


def _validate_pair(original: Image.Image, cloaked: Image.Image) -> tuple[Image.Image, Image.Image]:
    original_rgb = _as_rgb(original)
    cloaked_rgb = _as_rgb(cloaked)
    if original_rgb.size != cloaked_rgb.size:
        raise ValueError("Original and cloaked images must have identical dimensions.")
    if min(original_rgb.size) < 8:
        raise ValueError("Working images must be at least 8 pixels in each dimension.")
    return original_rgb, cloaked_rgb


def _resize_round_trip(image: Image.Image, scale: float) -> Image.Image:
    width, height = image.size
    reduced_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    reduced = image.resize(reduced_size, Image.Resampling.LANCZOS)
    return reduced.resize(image.size, Image.Resampling.LANCZOS)


def _jpeg_round_trip(image: Image.Image, quality: int) -> Image.Image:
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    with Image.open(buffer) as compressed:
        return compressed.convert("RGB")


def _social_like_round_trip(image: Image.Image) -> Image.Image:
    width, height = image.size
    reduced_size = (max(1, round(width * 0.75)), max(1, round(height * 0.75)))
    reduced = image.resize(reduced_size, Image.Resampling.LANCZOS)
    compressed = _jpeg_round_trip(reduced, quality=70)
    return compressed.resize(image.size, Image.Resampling.LANCZOS)


def _image_tensor(image: Image.Image, reference: torch.Tensor) -> torch.Tensor:
    array = np.asarray(_as_rgb(image), dtype=np.float32) / 255.0
    return (
        torch.from_numpy(array)
        .permute(2, 0, 1)
        .unsqueeze(0)
        .to(device=reference.device, dtype=reference.dtype)
    )


def _encode_image(
    vae: torch.nn.Module,
    image: Image.Image,
    target_latent: torch.Tensor,
) -> torch.Tensor:
    tensor = _image_tensor(image, target_latent)
    with torch.no_grad():
        return vae.encode(tensor * 2.0 - 1.0).latent_dist.mean


def _protection_after_processing(
    image: Image.Image,
    vae: torch.nn.Module,
    target_latent: torch.Tensor,
    original_latent: torch.Tensor,
) -> int:
    image_latent = _encode_image(vae, image, target_latent)
    return protection_score(image_latent, original_latent, target_latent)


def _visual_quality(
    original: Image.Image,
    cloaked: Image.Image,
) -> VisualQuality:
    original_array = np.asarray(original, dtype=np.uint8)
    cloaked_array = np.asarray(cloaked, dtype=np.uint8)
    psnr_db = float(
        peak_signal_noise_ratio(original_array, cloaked_array, data_range=255)
    )
    ssim = float(
        structural_similarity(
            original_array,
            cloaked_array,
            channel_axis=2,
            data_range=255,
        )
    )
    return VisualQuality(psnr_db=psnr_db, ssim=float(np.clip(ssim, 0.0, 1.0)))


def create_heatmap(
    original: Image.Image,
    cloaked: Image.Image,
    eps: float,
    output_path: str | Path,
) -> Path:
    """Save the epsilon-normalized mean-channel difference as an Inferno PNG."""
    original_rgb, cloaked_rgb = _validate_pair(original, cloaked)
    if not np.isfinite(eps) or eps <= 0:
        raise ValueError("eps must be a finite value greater than zero.")

    original_array = np.asarray(original_rgb, dtype=np.float32) / 255.0
    cloaked_array = np.asarray(cloaked_rgb, dtype=np.float32) / 255.0
    difference = np.abs(cloaked_array - original_array).mean(axis=2)
    normalized = np.clip(difference / eps, 0.0, 1.0)
    grayscale = np.round(normalized * 255).astype(np.uint8)
    heatmap_bgr = cv2.applyColorMap(grayscale, cv2.COLORMAP_INFERNO)
    heatmap_rgb = cv2.cvtColor(heatmap_bgr, cv2.COLOR_BGR2RGB)

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(heatmap_rgb, mode="RGB").save(destination, format="PNG")
    return destination


def compute_robustness_metrics(
    original: Image.Image,
    cloaked: Image.Image,
    vae: torch.nn.Module,
    original_latent: torch.Tensor,
    target_latent: torch.Tensor,
    eps: float,
    heatmap_path: str | Path,
) -> RobustnessMetrics:
    """Compute cloak scores, visual quality, and save the difference heatmap.

    ``original_latent`` and ``target_latent`` must come from the same VAE
    encoder at the working image size. ``eps`` is the perturbation bound in
    image-space units (for example, ``12 / 255``).
    """
    original_rgb, cloaked_rgb = _validate_pair(original, cloaked)
    if not np.isfinite(eps) or eps <= 0:
        raise ValueError("eps must be a finite value greater than zero.")

    cloaked_latent = _encode_image(vae, cloaked_rgb, target_latent)
    base_score = protection_score(cloaked_latent, original_latent, target_latent)

    jpeg_q75 = _protection_after_processing(
        _jpeg_round_trip(cloaked_rgb, quality=75),
        vae,
        target_latent,
        original_latent,
    )
    resize_50 = _protection_after_processing(
        _resize_round_trip(cloaked_rgb, scale=0.5),
        vae,
        target_latent,
        original_latent,
    )
    social_like = _protection_after_processing(
        _social_like_round_trip(cloaked_rgb),
        vae,
        target_latent,
        original_latent,
    )

    destination = create_heatmap(original_rgb, cloaked_rgb, eps, heatmap_path)
    return RobustnessMetrics(
        protection_score=base_score,
        robustness=Robustness(
            jpeg_q75=jpeg_q75,
            resize_50=resize_50,
            social_like=social_like,
        ),
        visual_quality=_visual_quality(original_rgb, cloaked_rgb),
        heatmap_path=destination,
    )
