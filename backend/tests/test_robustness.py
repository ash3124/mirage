from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

import numpy as np
import torch
from PIL import Image

from app.schemas import Robustness, VisualQuality
from app.services.robustness import (
    compute_robustness_metrics,
    create_heatmap,
    protection_score,
)


class MeanColorVae(torch.nn.Module):
    def encode(self, image: torch.Tensor) -> SimpleNamespace:
        latent = torch.nn.functional.avg_pool2d(
            image.mean(dim=1, keepdim=True),
            kernel_size=8,
            stride=8,
        )
        return SimpleNamespace(latent_dist=SimpleNamespace(mean=latent))


def solid_image(size: tuple[int, int], color: tuple[int, int, int]) -> Image.Image:
    return Image.new("RGB", size, color)


class RobustnessTests(unittest.TestCase):
    def test_protection_score_matches_target_latent_formula_and_clamps(self) -> None:
        original_latent = torch.tensor([[[[4.0]]]])
        target_latent = torch.tensor([[[[0.0]]]])

        self.assertEqual(
            protection_score(torch.tensor([[[[2.0]]]]), original_latent, target_latent),
            50,
        )
        self.assertEqual(
            protection_score(torch.tensor([[[[5.0]]]]), original_latent, target_latent),
            0,
        )
        self.assertEqual(
            protection_score(torch.tensor([[[[0.0]]]]), original_latent, target_latent),
            100,
        )

    def test_protection_score_rejects_zero_baseline_distance(self) -> None:
        latent = torch.tensor([[[[0.0]]]])
        with self.assertRaises(ValueError):
            protection_score(latent, latent, latent)

    def test_metrics_and_inferno_heatmap(self) -> None:
        original = solid_image((32, 32), (180, 180, 180))
        cloaked = solid_image((32, 32), (152, 152, 152))
        vae = MeanColorVae()
        original_tensor = torch.from_numpy(
            np.asarray(original, dtype=np.float32) / 255.0
        ).permute(2, 0, 1).unsqueeze(0)
        original_latent = vae.encode(original_tensor * 2 - 1).latent_dist.mean
        target_latent = torch.zeros_like(original_latent)

        with tempfile.TemporaryDirectory() as temp_dir:
            heatmap_path = Path(temp_dir) / "nested" / "heatmap.png"
            metrics = compute_robustness_metrics(
                original,
                cloaked,
                vae,
                original_latent,
                target_latent,
                eps=12 / 255,
                heatmap_path=heatmap_path,
            )

            self.assertTrue(heatmap_path.is_file())
            with Image.open(heatmap_path) as heatmap:
                self.assertEqual(heatmap.format, "PNG")
                self.assertEqual(heatmap.size, original.size)
                self.assertEqual(heatmap.mode, "RGB")

            self.assertEqual(metrics.heatmap_path, heatmap_path)
            self.assertEqual(metrics.protection_score, 53)
            Robustness.model_validate(metrics.robustness.model_dump())
            VisualQuality.model_validate(metrics.visual_quality.model_dump())
            self.assertGreater(metrics.visual_quality.psnr_db, 0)
            self.assertGreaterEqual(metrics.visual_quality.ssim, 0)
            self.assertLessEqual(metrics.visual_quality.ssim, 1)
            self.assertGreaterEqual(metrics.robustness.jpeg_q75, 0)
            self.assertLessEqual(metrics.robustness.jpeg_q75, 100)
            self.assertGreaterEqual(metrics.robustness.resize_50, 0)
            self.assertLessEqual(metrics.robustness.resize_50, 100)
            self.assertGreaterEqual(metrics.robustness.social_like, 0)
            self.assertLessEqual(metrics.robustness.social_like, 100)

    def test_create_heatmap_normalizes_by_epsilon_and_rejects_invalid_inputs(
        self,
    ) -> None:
        original = solid_image((8, 8), (0, 0, 0))
        cloaked = solid_image((8, 8), (255, 255, 255))

        with tempfile.TemporaryDirectory() as temp_dir:
            path = create_heatmap(original, cloaked, eps=1 / 255, output_path=Path(temp_dir) / "map.png")
            with Image.open(path) as heatmap:
                self.assertEqual(heatmap.size, (8, 8))

            with self.assertRaises(ValueError):
                create_heatmap(original, cloaked, eps=0, output_path=Path(temp_dir) / "bad.png")
            with self.assertRaises(ValueError):
                create_heatmap(original, solid_image((9, 8), (0, 0, 0)), 1 / 255, Path(temp_dir) / "bad.png")

    def test_metrics_reject_mismatched_image_sizes(self) -> None:
        original = solid_image((32, 32), (100, 100, 100))
        cloaked = solid_image((16, 16), (110, 110, 110))
        latent = torch.zeros((1, 1, 4, 4))
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                compute_robustness_metrics(
                    original,
                    cloaked,
                    MeanColorVae(),
                    latent,
                    latent - 1,
                    12 / 255,
                    Path(temp_dir) / "heatmap.png",
                )


if __name__ == "__main__":
    unittest.main()
