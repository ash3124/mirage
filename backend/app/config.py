"""Application settings and contract-defined configuration values."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .schemas import AppConfig

DeviceMode = Literal["gpu", "cpu"]


def _read_flag(name: str, default: str = "0") -> bool:
    value = os.getenv(name, default)
    if value not in {"0", "1"}:
        raise ValueError(f"{name} must be 0 or 1.")
    return value == "1"


def _resolve_mode(device: str) -> DeviceMode:
    if device == "cpu":
        return "cpu"
    if device == "cuda":
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError(
                "DEVICE=cuda requires a CUDA-enabled PyTorch installation."
            ) from exc
        if not torch.cuda.is_available():
            raise RuntimeError(
                "DEVICE=cuda was requested, but CUDA is unavailable. Install a "
                "CUDA-enabled PyTorch build and verify the NVIDIA driver, or set "
                "DEVICE=auto or DEVICE=cpu."
            )
        return "gpu"

    try:
        import torch
    except ImportError:
        return "cpu"
    return "gpu" if torch.cuda.is_available() else "cpu"


@dataclass(frozen=True)
class Settings:
    device: str
    mode: DeviceMode
    mock: bool
    sd_repo: str
    disable_sim: bool
    ttl_seconds: int
    max_queue: int

    @property
    def simulator_enabled(self) -> bool:
        return self.mode == "gpu" and not self.disable_sim

    @property
    def max_side_px(self) -> int:
        return 768 if self.mode == "gpu" else 512


def load_settings() -> Settings:
    device = os.getenv("DEVICE", "auto").lower()
    if device not in {"auto", "cuda", "cpu"}:
        raise ValueError("DEVICE must be auto, cuda, or cpu.")

    ttl_seconds = int(os.getenv("TTL_SECONDS", "900"))
    max_queue = int(os.getenv("MAX_QUEUE", "3"))
    if ttl_seconds <= 0:
        raise ValueError("TTL_SECONDS must be greater than 0.")
    if max_queue <= 0:
        raise ValueError("MAX_QUEUE must be greater than 0.")

    return Settings(
        device=device,
        mode=_resolve_mode(device),
        mock=_read_flag("MOCK"),
        sd_repo=os.getenv(
            "SD_REPO", "stable-diffusion-v1-5/stable-diffusion-v1-5"
        ),
        disable_sim=_read_flag("DISABLE_SIM"),
        ttl_seconds=ttl_seconds,
        max_queue=max_queue,
    )


settings = load_settings()

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
PROJECT_ROOT = (
    REPOSITORY_ROOT
    if (REPOSITORY_ROOT / "API.md").is_file()
    or (REPOSITORY_ROOT / "shared" / "examples").is_dir()
    else BACKEND_ROOT
)
MOCK_EXAMPLES_DIR = PROJECT_ROOT / "shared" / "examples"
MOCK_ASSETS_DIR = BACKEND_ROOT / "assets" / "mock"

STRENGTHS = [
    {
        "id": "light",
        "label": "Light",
        "description": "Nearly invisible, lighter protection",
    },
    {
        "id": "standard",
        "label": "Standard",
        "description": "Balanced. Recommended",
    },
    {
        "id": "strong",
        "label": "Strong",
        "description": "Strongest protection, slight grain",
    },
]

SIM_PRESETS = [
    {"id": "background_snow", "label": "Snowy background"},
    {"id": "background_beach", "label": "Beach background"},
    {"id": "new_hairstyle", "label": "New hairstyle"},
    {"id": "vintage_style", "label": "Vintage style"},
]


def app_config() -> AppConfig:
    return AppConfig(
        version="1.0.0",
        mode=settings.mode,
        simulator_enabled=settings.simulator_enabled,
        features={
            "watermark": False,
            "face_focus": True,
            "robust_mode": True,
        },
        limits={
            "max_upload_mb": 10,
            "ttl_seconds": settings.ttl_seconds,
            "max_side_px": settings.max_side_px,
        },
        strengths=STRENGTHS,
        sim_presets=SIM_PRESETS,
    )
