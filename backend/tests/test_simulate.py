from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from app.errors import ApiError
from app.schemas import SimPreset
from app.services.simulate import SIM_PROMPTS, process_simulation


class FakePipeline:
    def __init__(self) -> None:
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return type(
            "PipelineOutput",
            (),
            {
                "images": [kwargs["image"].copy()],
                "nsfw_content_detected": [False],
            },
        )()


class SimulateTests(unittest.TestCase):
    def test_fixed_prompt_settings_seed_progress_and_artifacts(self) -> None:
        preset = SimPreset.background_snow
        pipeline = FakePipeline()
        callbacks = []
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            Image.new("RGB", (64, 48), "blue").save(root / "original.png")
            Image.new("RGB", (64, 48), "red").save(root / "cloaked.png")

            with patch("app.services.simulate.load_pipeline", return_value=pipeline), patch(
                "app.services.simulate.torch.Generator"
            ) as generator_factory:
                result = process_simulation(
                    file_id="a" * 32,
                    preset=preset,
                    output_dir=root,
                    callback=lambda stage, progress: callbacks.append((stage, progress)),
                )

            self.assertEqual(len(pipeline.calls), 2)
            self.assertEqual(
                [call["prompt"] for call in pipeline.calls],
                [SIM_PROMPTS[preset], SIM_PROMPTS[preset]],
            )
            self.assertEqual(
                [
                    (
                        call["strength"],
                        call["guidance_scale"],
                        call["num_inference_steps"],
                    )
                    for call in pipeline.calls
                ],
                [(0.6, 7.5, 25), (0.6, 7.5, 25)],
            )
            self.assertEqual(generator_factory.call_count, 2)
            for generator_call in generator_factory.return_value.manual_seed.call_args_list:
                self.assertEqual(generator_call.args, (1234,))
            self.assertEqual(result.preset, preset)
            self.assertEqual(result.seed, 1234)
            self.assertEqual(result.disruption_score, 66)
            self.assertTrue((root / "sim_background_snow_original.png").is_file())
            self.assertTrue((root / "sim_background_snow_cloaked.png").is_file())
            self.assertEqual(
                callbacks,
                [
                    ("editing_original", 0),
                    ("editing_original", 45),
                    ("editing_cloaked", 45),
                    ("editing_cloaked", 90),
                    ("scoring", 90),
                    ("scoring", 99),
                ],
            )

    def test_simulator_fails_when_safety_checker_flags_output(self) -> None:
        class BlockedPipeline(FakePipeline):
            def __call__(self, **kwargs):
                return type(
                    "PipelineOutput",
                    (),
                    {
                        "images": [kwargs["image"].copy()],
                        "nsfw_content_detected": [True],
                    },
                )()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            Image.new("RGB", (32, 32), "blue").save(root / "original.png")
            Image.new("RGB", (32, 32), "red").save(root / "cloaked.png")
            callbacks = []
            with patch(
                "app.services.simulate.load_pipeline",
                return_value=BlockedPipeline(),
            ), patch("app.services.simulate.torch.Generator"):
                with self.assertRaises(ApiError) as context:
                    process_simulation(
                        "a" * 32,
                        SimPreset.background_snow,
                        root,
                        lambda stage, progress: callbacks.append((stage, progress)),
                    )
            self.assertEqual(context.exception.code.value, "SIM_BLOCKED")


if __name__ == "__main__":
    unittest.main()
