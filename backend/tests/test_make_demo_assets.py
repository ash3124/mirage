from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from app.schemas import CloakResult, SimPreset, SimResult
from scripts import make_demo_assets


class MakeDemoAssetsTests(unittest.TestCase):
    def test_generates_contract_shaped_manifest_and_assets(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            inputs = root / "photos"
            output = root / "demo-assets"
            inputs.mkdir()
            for index in range(1, 4):
                Image.new("RGB", (32, 32), (index * 20, 50, 80)).save(
                    inputs / f"portrait-{index}.png"
                )

            def process_cloak(**kwargs):
                sample_output = Path(kwargs["output_dir"])
                for name in ("original.png", "cloaked.png", "heatmap.png"):
                    Image.new("RGB", (32, 32), (10, 20, 30)).save(
                        sample_output / name
                    )
                return CloakResult.model_validate(
                    {
                        "file_id": kwargs["file_id"],
                        "original_url": f"/api/v1/files/{kwargs['file_id']}/original.png",
                        "cloaked_url": f"/api/v1/files/{kwargs['file_id']}/cloaked.png",
                        "heatmap_url": f"/api/v1/files/{kwargs['file_id']}/heatmap.png",
                        "metrics": {
                            "protection_score": 50,
                            "robustness": {
                                "jpeg_q75": 40,
                                "resize_50": 30,
                                "social_like": 20,
                            },
                            "visual_quality": {"psnr_db": 30.0, "ssim": 0.9},
                            "working_size": {"w": 32, "h": 32},
                            "elapsed_s": 1.0,
                        },
                        "metadata_report": {"had_gps": False, "removed": []},
                        "hashes": {
                            "sha256_cloaked": "a" * 64,
                            "phash_original": "b" * 16,
                        },
                        "watermark": None,
                        "face_found": False,
                        "expires_at": kwargs["expires_at"],
                    }
                )

            def process_simulation(**kwargs):
                sample_output = Path(kwargs["output_dir"])
                preset = kwargs["preset"]
                for suffix in ("original", "cloaked"):
                    Image.new("RGB", (32, 32), (40, 50, 60)).save(
                        sample_output / f"sim_{preset.value}_{suffix}.png"
                    )
                return SimResult(
                    preset=preset,
                    edit_on_original_url=f"/original/{preset.value}.png",
                    edit_on_cloaked_url=f"/cloaked/{preset.value}.png",
                    disruption_score=25,
                    seed=1234,
                )

            fake_settings = SimpleNamespace(
                mock=False,
                mode="gpu",
                simulator_enabled=True,
                ttl_seconds=900,
                max_side_px=768,
            )
            with (
                patch.object(make_demo_assets, "settings", fake_settings),
                patch.object(make_demo_assets, "process_cloak", side_effect=process_cloak),
                patch.object(
                    make_demo_assets,
                    "process_simulation",
                    side_effect=process_simulation,
                ),
                patch.object(
                    make_demo_assets,
                    "create_certificate",
                    return_value=b"%PDF-test",
                ),
                patch.object(
                    make_demo_assets.torch.cuda,
                    "is_available",
                    return_value=True,
                ),
            ):
                manifest = make_demo_assets.generate_demo_assets(inputs, output)

            self.assertEqual(
                set(manifest),
                {"version", "sample_certificate_url", "samples"},
            )
            self.assertEqual(manifest["version"], "1.0.0")
            self.assertEqual(
                manifest["sample_certificate_url"],
                "/demo/sample_certificate.pdf",
            )
            samples = manifest["samples"]
            self.assertEqual(len(samples), 3)

            for index, sample in enumerate(samples, start=1):
                sample_id = f"sample-{index}"
                self.assertEqual(
                    set(sample),
                    {"id", "label", "thumb_url", "cloak", "sims"},
                )
                self.assertEqual(sample["id"], sample_id)
                cloak = CloakResult.model_validate(sample["cloak"])
                self.assertEqual(cloak.file_id, sample_id)
                for url in (
                    cloak.original_url,
                    cloak.cloaked_url,
                    cloak.heatmap_url,
                ):
                    self.assertTrue(url.startswith(f"/demo/{sample_id}/"))
                self.assertEqual(set(sample["sims"]), {preset.value for preset in SimPreset})
                for preset_name, sim_data in sample["sims"].items():
                    sim = SimResult.model_validate(sim_data)
                    self.assertEqual(sim.preset.value, preset_name)
                    self.assertTrue(
                        sim.edit_on_original_url.startswith(f"/demo/{sample_id}/")
                    )
                    self.assertTrue(
                        sim.edit_on_cloaked_url.startswith(f"/demo/{sample_id}/")
                    )
                for name in (
                    "original.png",
                    "cloaked.png",
                    "heatmap.png",
                    *(
                        f"sim_{preset.value}_{suffix}.png"
                        for preset in SimPreset
                        for suffix in ("original", "cloaked")
                    ),
                ):
                    self.assertTrue((output / sample_id / name).is_file())

            saved_manifest = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(saved_manifest, manifest)
            self.assertEqual(
                (output / "sample_certificate.pdf").read_bytes(),
                b"%PDF-test",
            )

    def test_default_output_directory_is_the_public_demo_directory(self) -> None:
        self.assertEqual(make_demo_assets.OUTPUT_DIR.name, "demo-assets")

    def test_requires_actual_cuda_before_checking_input_folder(self) -> None:
        with (
            patch.object(
                make_demo_assets,
                "settings",
                SimpleNamespace(
                    mock=False,
                    mode="gpu",
                    simulator_enabled=True,
                ),
            ),
            patch.object(
                make_demo_assets.torch.cuda,
                "is_available",
                return_value=False,
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CUDA is unavailable in this Python environment",
            ):
                make_demo_assets.generate_demo_assets("missing-photo-folder")


if __name__ == "__main__":
    unittest.main()
