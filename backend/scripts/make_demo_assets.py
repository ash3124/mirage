"""Generate the static Demo Mode assets from exactly three real portrait photos."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from uuid import uuid4
import warnings

from PIL import Image
import torch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import PROJECT_ROOT, settings
from app.jobs import JobRecord
from app.schemas import (
    CloakRequest,
    CloakResult,
    JobType,
    SimPreset,
    SimResult,
    Strength,
)
from app.services.certificate import create_certificate
from app.services.cloak import process_cloak
from app.services.privacy import MAX_UPLOAD_BYTES, SUPPORTED_FORMATS
from app.services.simulate import process_simulation

OUTPUT_DIR = PROJECT_ROOT / "demo-assets"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
SIM_PRESETS = tuple(SimPreset)
MANIFEST_VERSION = "1.0.0"


def _supported_inputs(input_directory: Path) -> list[Path]:
    if not input_directory.is_dir():
        raise NotADirectoryError(f"Input photo folder does not exist: {input_directory}")

    images = sorted(
        (
            path
            for path in input_directory.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        ),
        key=lambda path: path.name.casefold(),
    )
    if len(images) != 3:
        raise ValueError(
            f"Expected exactly 3 supported photos in {input_directory}; found {len(images)}."
        )
    return images


def _validate_photo(path: Path) -> bytes:
    image_bytes = path.read_bytes()
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError(f"{path.name} exceeds the 10 MiB upload limit.")
    if not image_bytes:
        raise ValueError(f"{path.name} is empty.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                if image.format not in SUPPORTED_FORMATS:
                    raise ValueError(
                        f"{path.name} is not a supported JPEG, PNG, or WebP."
                    )
                image.verify()
    except (OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError(f"{path.name} is not a valid supported image.") from exc
    return image_bytes


def _progress(sample_label: str, phase: str):
    def report(stage: str, percent: int) -> None:
        print(f"{sample_label}: {phase} — {stage} {percent}%")

    return report


def _atomic_write(destination: Path, content: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)
        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _publish_file(source: Path, destination: Path) -> None:
    _atomic_write(destination, source.read_bytes())


def _cloak_result_for_demo(
    result: CloakResult,
    sample_id: str,
) -> CloakResult:
    return CloakResult.model_validate(
        {
            **result.model_dump(mode="json"),
            "file_id": sample_id,
            "original_url": f"/demo/{sample_id}/original.png",
            "cloaked_url": f"/demo/{sample_id}/cloaked.png",
            "heatmap_url": f"/demo/{sample_id}/heatmap.png",
        }
    )


def _sim_result_for_demo(result: SimResult, sample_id: str) -> SimResult:
    preset = result.preset.value
    return SimResult.model_validate(
        {
            **result.model_dump(mode="json"),
            "edit_on_original_url": (
                f"/demo/{sample_id}/sim_{preset}_original.png"
            ),
            "edit_on_cloaked_url": (
                f"/demo/{sample_id}/sim_{preset}_cloaked.png"
            ),
        }
    )


def generate_demo_assets(
    input_directory: str | Path,
    output_directory: str | Path = OUTPUT_DIR,
) -> dict[str, object]:
    """Run real cloak/simulator inference and publish the API.md §5 manifest."""
    if settings.mock:
        raise RuntimeError("Set MOCK=0 to generate demo assets from the real pipeline.")
    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is unavailable in this Python environment. Run this script in a "
            "Colab T4 GPU runtime or install a CUDA-enabled PyTorch build with a "
            "compatible NVIDIA GPU driver."
        )
    if settings.mode != "gpu" or not settings.simulator_enabled:
        raise RuntimeError(
            "Demo asset generation requires a CUDA GPU and an enabled simulator."
        )

    input_path = Path(input_directory).expanduser().resolve()
    output_path = Path(output_directory).expanduser().resolve()
    photos = _supported_inputs(input_path)
    photo_bytes = [(photo, _validate_photo(photo)) for photo in photos]
    output_path.mkdir(parents=True, exist_ok=True)

    samples: list[dict[str, object]] = []
    publish_operations: list[tuple[Path, Path]] = []
    certificate_bytes: bytes | None = None
    build_parent = output_path.parent
    with tempfile.TemporaryDirectory(
        prefix=".mirage-demo-build-",
        dir=build_parent,
    ) as temporary_directory:
        build_path = Path(temporary_directory)

        for index, (photo_path, image_bytes) in enumerate(photo_bytes, start=1):
            sample_id = f"sample-{index}"
            sample_label = f"Portrait {index}"
            sample_work = build_path / sample_id
            sample_work.mkdir(parents=True)
            file_id = str(uuid4())
            expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=settings.ttl_seconds)
            ).isoformat().replace("+00:00", "Z")

            cloak_result = process_cloak(
                image_bytes=image_bytes,
                request=CloakRequest(
                    strength=Strength.standard,
                    face_focus=True,
                    robust_mode=True,
                    embed_watermark=False,
                ),
                file_id=file_id,
                output_dir=sample_work,
                max_side_px=settings.max_side_px,
                callback=_progress(sample_label, "cloak"),
                expires_at=expires_at,
            )
            cloak_result = _cloak_result_for_demo(cloak_result, sample_id)

            expected_cloak_files = (
                "original.png",
                "cloaked.png",
                "heatmap.png",
            )
            for filename in expected_cloak_files:
                source = sample_work / filename
                if not source.is_file():
                    raise FileNotFoundError(
                        f"Cloak pipeline did not produce {source}."
                    )
                publish_operations.append(
                    (source, output_path / sample_id / filename)
                )

            sim_results: dict[str, dict[str, object]] = {}
            for preset in SIM_PRESETS:
                sim_result = process_simulation(
                    file_id=sample_id,
                    preset=preset,
                    output_dir=sample_work,
                    callback=_progress(sample_label, preset.value),
                )
                sim_result = _sim_result_for_demo(sim_result, sample_id)
                sim_results[preset.value] = sim_result.model_dump(mode="json")
                for suffix in ("original", "cloaked"):
                    filename = f"sim_{preset.value}_{suffix}.png"
                    source = sample_work / filename
                    if not source.is_file():
                        raise FileNotFoundError(
                            f"Simulator did not produce {source}."
                        )
                    publish_operations.append(
                        (source, output_path / sample_id / filename)
                    )

            if index == 1:
                record = JobRecord(
                    job_id=str(uuid4()),
                    job_type=JobType.cloak,
                    created_at=time.monotonic(),
                    created_at_utc=datetime.now(timezone.utc),
                    file_id=sample_id,
                    strength=Strength.standard,
                    result=cloak_result,
                )
                certificate_bytes = create_certificate(
                    record,
                    image_directory=sample_work,
                )

            samples.append(
                {
                    "id": sample_id,
                    "label": sample_label,
                    "thumb_url": f"/demo/{sample_id}/original.png",
                    "cloak": cloak_result.model_dump(mode="json"),
                    "sims": sim_results,
                }
            )
            print(f"Completed {sample_label} from {photo_path.name}.")

        if certificate_bytes is None:
            raise RuntimeError("The sample certificate was not generated.")
        manifest: dict[str, object] = {
            "version": MANIFEST_VERSION,
            "sample_certificate_url": "/demo/sample_certificate.pdf",
            "samples": samples,
        }
        manifest_bytes = (
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        ).encode("utf-8")

        for source, destination in publish_operations:
            _publish_file(source, destination)
        _atomic_write(output_path / "sample_certificate.pdf", certificate_bytes)
        _atomic_write(output_path / "manifest.json", manifest_bytes)

    print(f"Demo assets and manifest written to: {output_path}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Demo Mode files from exactly three photos using the real "
            "Mirage cloak and simulator pipelines."
        )
    )
    parser.add_argument(
        "input_directory",
        type=Path,
        help="Folder containing exactly three JPEG, PNG, or WebP portrait photos.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR}).",
    )
    arguments = parser.parse_args()
    generate_demo_assets(arguments.input_directory, arguments.output)


if __name__ == "__main__":
    main()
