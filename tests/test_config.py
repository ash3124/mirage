from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest.mock import patch

import torch

from app import config


class SettingsTests(unittest.TestCase):
    def test_explicit_cuda_requires_cuda_enabled_torch(self) -> None:
        with (
            patch.dict(os.environ, {"DEVICE": "cuda"}),
            patch.object(torch.cuda, "is_available", return_value=False),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "DEVICE=cuda was requested, but CUDA is unavailable",
            ):
                config.load_settings()

    def test_auto_mode_uses_cpu_when_cuda_is_unavailable(self) -> None:
        with (
            patch.dict(os.environ, {"DEVICE": "auto"}),
            patch.object(torch.cuda, "is_available", return_value=False),
        ):
            settings = config.load_settings()

        self.assertEqual(settings.mode, "cpu")
        self.assertFalse(settings.simulator_enabled)
        self.assertEqual(settings.max_side_px, 512)

    def test_asset_directory_is_relative_to_backend_package(self) -> None:
        expected_target = config.BACKEND_ROOT / "assets" / "target.png"
        self.assertTrue(expected_target.is_file())


if __name__ == "__main__":
    unittest.main()
