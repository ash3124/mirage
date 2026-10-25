from __future__ import annotations

import unittest

import torch

from app.services.cloak import _cloak_pgd


class MeanVae(torch.nn.Module):
    def encode(self, image: torch.Tensor):
        mean = image.mean(dim=1, keepdim=True)
        distribution = type("Distribution", (), {"mean": mean})()
        return type("Encoded", (), {"latent_dist": distribution})()


class CloakShapeTests(unittest.TestCase):
    def test_pgd_preserves_supported_image_shapes_and_bounds(self) -> None:
        torch.manual_seed(12)
        vae = MeanVae()
        eps = 12 / 255

        for height, width in ((16, 24), (32, 16), (24, 32)):
            with self.subTest(height=height, width=width):
                image = torch.full((1, 3, height, width), 0.5)
                mask = torch.ones((1, 1, height, width))
                target_latent = torch.zeros((1, 1, height, width))
                result = _cloak_pgd(
                    image,
                    vae,
                    target_latent,
                    eps,
                    steps=4,
                    mask=mask,
                    callback=lambda _stage, _progress: None,
                    robust=False,
                )

                self.assertEqual(result.shape, image.shape)
                self.assertEqual(result.dtype, image.dtype)
                self.assertFalse(result.requires_grad)
                self.assertTrue(torch.isfinite(result).all())
                self.assertGreaterEqual(result.min().item(), 0.0)
                self.assertLessEqual(result.max().item(), 1.0)
                self.assertTrue(((result - image).abs() <= eps + 1e-6).all())

    def test_pgd_supports_single_channel_spatial_mask_for_rgb_image(self) -> None:
        image = torch.full((1, 3, 16, 16), 0.5)
        mask = torch.full((1, 1, 16, 16), 0.25)
        target_latent = torch.zeros((1, 1, 16, 16))
        eps = 12 / 255

        result = _cloak_pgd(
            image,
            MeanVae(),
            target_latent,
            eps,
            steps=4,
            mask=mask,
            callback=lambda _stage, _progress: None,
            robust=False,
        )

        self.assertEqual(result.shape, image.shape)
        self.assertTrue(
            ((result - image).abs() <= eps * mask + 1e-6).all()
        )


if __name__ == "__main__":
    unittest.main()
