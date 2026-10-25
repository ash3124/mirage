"""Fixed-prompt Stable Diffusion img2img simulator."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Callable

import numpy as np
import torch
from PIL import Image
from skimage.metrics import structural_similarity

from ..config import settings
from ..schemas import SimPreset, SimResult

ProgressCallback = Callable[[str, int], None]
SIM_PROMPTS = {
    SimPreset.background_snow: "a portrait photo of the same person standing in a snowy mountain landscape, realistic",
    SimPreset.background_beach: "a portrait photo of the same person on a sunny beach, realistic",
    SimPreset.new_hairstyle: "a portrait photo of the same person with a different hairstyle, realistic",
    SimPreset.vintage_style: "a vintage film photograph of the same person, 1970s style",
}
SIM_SEED = 1234


@lru_cache(maxsize=1)
def load_pipeline():
    from diffusers import StableDiffusionImg2ImgPipeline

    pipeline = StableDiffusionImg2ImgPipeline.from_pretrained(
        settings.sd_repo,
        torch_dtype=torch.float16,
    ).to("cuda")
    pipeline.set_progress_bar_config(disable=True)
    return pipeline


def _prepare_image(image: Image.Image) -> Image.Image:
    scale = min(1.0, 512 / max(image.size))
    width = max(8, int(image.width * scale) // 8 * 8)
    height = max(8, int(image.height * scale) // 8 * 8)
    return image.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)


def _check_output(image: Image.Image, safety_flags: list[bool] | None) -> None:
    if safety_flags is not None and len(safety_flags) > 0 and safety_flags[0]:
        from ..errors import ApiError
        from ..schemas import ErrorCode

        raise ApiError(ErrorCode.SIM_BLOCKED)
    if np.asarray(image.convert("RGB")).max() == 0:
        from ..errors import ApiError
        from ..schemas import ErrorCode

        raise ApiError(ErrorCode.SIM_BLOCKED)


def process_simulation(
    file_id: str,
    preset: SimPreset,
    output_dir: str | Path,
    callback: ProgressCallback,
) -> SimResult:
    root = Path(output_dir)
    with Image.open(root / "original.png") as source:
        original = _prepare_image(source)
    with Image.open(root / "cloaked.png") as source:
        cloaked = _prepare_image(source)
    if original.size != cloaked.size:
        raise ValueError("Original and cloaked simulator inputs have different sizes.")

    pipeline = load_pipeline()
    prompt = SIM_PROMPTS[preset]
    outputs = []
    for index, image in enumerate((original, cloaked)):
        stage = "editing_original" if index == 0 else "editing_cloaked"
        progress_start = index * 45
        callback(stage, progress_start)
        generator = torch.Generator(device="cuda").manual_seed(SIM_SEED)
        result = pipeline(
            prompt=prompt,
            image=image,
            strength=0.6,
            guidance_scale=7.5,
            num_inference_steps=25,
            generator=generator,
        )
        edited = result.images[0].convert("RGB")
        safety_flags = getattr(result, "nsfw_content_detected", None)
        _check_output(edited, safety_flags)
        outputs.append(edited)
        callback(stage, progress_start + 45)

    edited_original, edited_cloaked = outputs
    callback("scoring", 90)
    original_array = np.asarray(edited_original, dtype=np.uint8)
    cloaked_array = np.asarray(edited_cloaked, dtype=np.uint8)
    ssim = structural_similarity(
        original_array,
        cloaked_array,
        channel_axis=2,
        data_range=255,
    )
    score = int(np.clip(100 * (1 - ssim), 0, 100))

    original_name = f"sim_{preset.value}_original.png"
    cloaked_name = f"sim_{preset.value}_cloaked.png"
    edited_original.save(root / original_name, format="PNG")
    edited_cloaked.save(root / cloaked_name, format="PNG")
    callback("scoring", 99)
    return SimResult(
        preset=preset,
        edit_on_original_url=f"/api/v1/files/{file_id}/{original_name}",
        edit_on_cloaked_url=f"/api/v1/files/{file_id}/{cloaked_name}",
        disruption_score=score,
        seed=SIM_SEED,
    )
