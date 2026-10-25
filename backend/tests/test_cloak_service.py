from __future__ import annotations

import unittest

import torch

from app.services.cloak import PRESETS, _cloak_pgd


class MeanVae(torch.nn.Module):
    def encode(self, image: torch.Tensor):
        mean = image.mean(dim=1, keepdim=True)
        return type("Encoded", (), {"latent_dist": type("Distribution", (), {"mean": mean})()})()


class CloakServiceTests(unittest.TestCase):
    def test_strength_presets_limit_visible_perturbation(self) -> None:
        self.assertEqual(PRESETS, {"light": (4, 40), "standard": (8, 80), "strong": (12, 120)})

    def test_pgd_respects_masked_epsilon_and_reports_progress(self) -> None:
        image = torch.full((1, 3, 16, 16), 0.5)
        mask = torch.full((1, 1, 16, 16), 0.4)
        target_latent = torch.zeros((1, 1, 16, 16))
        updates: list[tuple[str, int]] = []

        result = _cloak_pgd(
            image,
            MeanVae(),
            target_latent,
            eps=12 / 255,
            steps=8,
            mask=mask,
            callback=lambda stage, progress: updates.append((stage, progress)),
            robust=False,
        )

        self.assertEqual(result.shape, image.shape)
        self.assertFalse(result.requires_grad)
        self.assertTrue(((result - image).abs() <= (12 / 255) * mask + 1e-6).all())
        self.assertEqual(updates[0], ("optimizing", 5))
        self.assertTrue(all(stage == "optimizing" for stage, _ in updates))
        self.assertTrue(all(5 <= progress <= 80 for _, progress in updates))


if __name__ == "__main__":
    unittest.main()
