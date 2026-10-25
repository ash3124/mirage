from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.main import app


class StartupTests(unittest.TestCase):
    def test_gpu_real_server_loads_models_during_startup(self) -> None:
        async def enter_lifespan() -> None:
            async with app.router.lifespan_context(app):
                pass

        with (
            patch(
                "app.main.settings",
                SimpleNamespace(mock=False, mode="gpu", simulator_enabled=True),
            ),
            patch("app.services.cloak.load_vae") as load_vae,
            patch("app.services.simulate.load_pipeline") as load_pipeline,
        ):
            asyncio.run(enter_lifespan())

        load_vae.assert_called_once_with()
        load_pipeline.assert_called_once_with()

    def test_mock_server_does_not_load_model_weights(self) -> None:
        async def enter_lifespan() -> None:
            async with app.router.lifespan_context(app):
                pass

        with (
            patch(
                "app.main.settings",
                SimpleNamespace(mock=True, mode="gpu", simulator_enabled=True),
            ),
            patch("app.services.cloak.load_vae") as load_vae,
            patch("app.services.simulate.load_pipeline") as load_pipeline,
        ):
            asyncio.run(enter_lifespan())

        load_vae.assert_not_called()
        load_pipeline.assert_not_called()

    def test_cpu_real_server_loads_vae_but_not_simulator(self) -> None:
        async def enter_lifespan() -> None:
            async with app.router.lifespan_context(app):
                pass

        with (
            patch(
                "app.main.settings",
                SimpleNamespace(mock=False, mode="cpu", simulator_enabled=False),
            ),
            patch("app.services.cloak.load_vae") as load_vae,
            patch("app.services.simulate.load_pipeline") as load_pipeline,
        ):
            asyncio.run(enter_lifespan())

        load_vae.assert_called_once_with()
        load_pipeline.assert_not_called()


if __name__ == "__main__":
    unittest.main()
