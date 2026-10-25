from __future__ import annotations

from contextlib import ExitStack
from io import BytesIO
from pathlib import Path
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from app.config import MOCK_ASSETS_DIR
from app.jobs import JobManager
from app.mock_data import load_example
from app.main import app
from app.schemas import (
    AppConfig,
    CloakMetrics,
    CloakResult,
    ErrorBody,
    Hashes,
    HealthResponse,
    Job,
    JobAccepted,
    JobStatus,
    JobType,
    MetadataReport,
    Robustness,
    SimPreset,
    SimResult,
    Stage,
    VisualQuality,
    WorkingSize,
)


def png_bytes(color: str = "blue") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), color).save(buffer, format="PNG")
    return buffer.getvalue()


def cloak_result(file_id: str, expires_at: str) -> CloakResult:
    return CloakResult(
        file_id=file_id,
        original_url=f"/api/v1/files/{file_id}/original.png",
        cloaked_url=f"/api/v1/files/{file_id}/cloaked.png",
        heatmap_url=f"/api/v1/files/{file_id}/heatmap.png",
        metrics=CloakMetrics(
            protection_score=50,
            robustness=Robustness(jpeg_q75=40, resize_50=35, social_like=30),
            visual_quality=VisualQuality(psnr_db=32.0, ssim=0.95),
            working_size=WorkingSize(w=32, h=32),
            elapsed_s=0.1,
        ),
        metadata_report=MetadataReport(had_gps=False, removed=[]),
        hashes=Hashes(sha256_cloaked="a" * 64, phash_original="b" * 16),
        watermark=None,
        face_found=False,
        expires_at=expires_at,
    )


class ApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.manager = JobManager(
            ttl_seconds=900,
            max_queue=3,
            root=Path(self.temp_dir.name),
            cleanup_interval=60,
        )
        self.client = TestClient(app)
        self.patches = [
            patch(
                "app.main.settings",
                type("Settings", (), {"mock": True})(),
            ),
            patch("app.routers.cloak.job_manager", self.manager),
            patch("app.routers.jobs.job_manager", self.manager),
            patch("app.routers.files.job_manager", self.manager),
            patch("app.routers.sim.job_manager", self.manager),
            patch("app.routers.certificate.job_manager", self.manager),
            patch(
                "app.routers.cloak.settings",
                type("Settings", (), {"mock": False})(),
            ),
            patch(
                "app.routers.sim.settings",
                type(
                    "Settings",
                    (),
                    {"mock": False, "simulator_enabled": True},
                )(),
            ),
            patch(
                "app.routers.certificate.settings",
                type("Settings", (), {"mock": False})(),
            ),
            patch(
                "app.routers.watermark.settings",
                type("Settings", (), {"mock": False})(),
            ),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.manager.stop()
        self.client.close()
        self.temp_dir.cleanup()

    def _process_cloak(self, **kwargs) -> CloakResult:
        output_dir = Path(kwargs["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        for filename, color in (
            ("original.png", "blue"),
            ("cloaked.png", "red"),
            ("heatmap.png", "black"),
        ):
            Image.new("RGB", (32, 32), color).save(output_dir / filename)
        return cloak_result(kwargs["file_id"], kwargs["expires_at"])

    @staticmethod
    def _process_simulation(**kwargs) -> SimResult:
        output_dir = Path(kwargs["output_dir"])
        preset = kwargs["preset"]
        for suffix, color in (("original", "green"), ("cloaked", "yellow")):
            Image.new("RGB", (32, 32), color).save(
                output_dir / f"sim_{preset.value}_{suffix}.png"
            )
        file_id = kwargs["file_id"]
        return SimResult(
            preset=preset,
            edit_on_original_url=(
                f"/api/v1/files/{file_id}/sim_{preset.value}_original.png"
            ),
            edit_on_cloaked_url=(
                f"/api/v1/files/{file_id}/sim_{preset.value}_cloaked.png"
            ),
            disruption_score=55,
            seed=1234,
        )

    def _wait_for_job(self, job_id: str) -> dict:
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            response = self.client.get(f"/api/v1/jobs/{job_id}")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            if data["status"] in {"done", "error"}:
                return data
            time.sleep(0.01)
        self.fail(f"Job {job_id} did not finish before the test timeout.")

    def test_health_and_config_responses_match_models(self) -> None:
        health_response = self.client.get("/api/v1/health")
        self.assertEqual(health_response.status_code, 200)
        HealthResponse.model_validate(health_response.json())

        config_response = self.client.get("/api/v1/config")
        self.assertEqual(config_response.status_code, 200)
        AppConfig.model_validate(config_response.json())

    def test_cloak_jobs_simulator_and_file_responses_match_contract(self) -> None:
        with (
            patch("app.services.cloak.process_cloak", side_effect=self._process_cloak),
            patch(
                "app.services.simulate.process_simulation",
                side_effect=self._process_simulation,
            ),
        ):
            accepted_response = self.client.post(
                "/api/v1/cloak",
                files={"image": ("portrait.png", png_bytes(), "image/png")},
                data={"strength": "standard"},
            )
            self.assertEqual(accepted_response.status_code, 202)
            accepted_cloak = JobAccepted.model_validate(accepted_response.json())
            self.assertEqual(accepted_cloak.status, "queued")

            cloak_job_data = self._wait_for_job(accepted_cloak.job_id)
            cloak_job = Job[CloakResult].model_validate(cloak_job_data)
            self.assertEqual(cloak_job.type, JobType.cloak)
            self.assertEqual(cloak_job.status, JobStatus.done)
            self.assertEqual(cloak_job.stage, Stage.done)
            cloak = cloak_job.result
            self.assertIsNotNone(cloak)

            image_response = self.client.get(cloak.cloaked_url)
            self.assertEqual(image_response.status_code, 200)
            self.assertEqual(image_response.headers["content-type"], "image/png")
            Image.open(BytesIO(image_response.content)).verify()

            sim_accepted_response = self.client.post(
                "/api/v1/attack-sim",
                json={
                    "job_id": accepted_cloak.job_id,
                    "preset": SimPreset.background_snow.value,
                },
            )
            self.assertEqual(sim_accepted_response.status_code, 202)
            accepted_sim = JobAccepted.model_validate(sim_accepted_response.json())
            sim_job = Job[SimResult].model_validate(
                self._wait_for_job(accepted_sim.job_id)
            )
            self.assertEqual(sim_job.type, JobType.attack_sim)
            self.assertEqual(sim_job.status, JobStatus.done)
            self.assertEqual(sim_job.result.preset, SimPreset.background_snow)

            certificate_response = self.client.post(
                "/api/v1/certificate",
                json={"job_id": accepted_cloak.job_id},
            )
            self.assertEqual(certificate_response.status_code, 200)
            self.assertEqual(
                certificate_response.headers["content-type"],
                "application/pdf",
            )
            self.assertEqual(
                certificate_response.headers["content-disposition"],
                'attachment; filename="mirage-protection-record.pdf"',
            )
            self.assertTrue(certificate_response.content.startswith(b"%PDF-"))

    def test_watermark_verify_disabled_uses_contract_error_body(self) -> None:
        response = self.client.post(
            "/api/v1/watermark/verify",
            files={"image": ("portrait.png", png_bytes(), "image/png")},
        )
        self.assertEqual(response.status_code, 501)
        error = ErrorBody.model_validate(response.json())
        self.assertEqual(error.error.code.value, "NOT_IMPLEMENTED")

    def test_all_mock_fixtures_and_assets_are_present_and_schema_valid(self) -> None:
        fixtures = {
            "health.ok.json": HealthResponse,
            "config.ok.json": AppConfig,
            "cloak.accepted.json": JobAccepted,
            "job.cloak.queued.json": Job[CloakResult],
            "job.cloak.running.json": Job[CloakResult],
            "job.cloak.done.json": Job[CloakResult],
            "job.cloak.error.json": Job[CloakResult],
            "attack_sim.accepted.json": JobAccepted,
            "job.sim.running.json": Job[SimResult],
            "job.sim.done.json": Job[SimResult],
            "error.invalid_image.json": ErrorBody,
            "error.too_large.json": ErrorBody,
            "error.bad_params.json": ErrorBody,
            "error.job_not_found.json": ErrorBody,
            "error.job_expired.json": ErrorBody,
            "error.job_not_ready.json": ErrorBody,
            "error.sim_unavailable.json": ErrorBody,
        }
        for filename, model in fixtures.items():
            with self.subTest(fixture=filename):
                model.model_validate(load_example(filename))

        for filename in (
            "original.png",
            "cloaked.png",
            "heatmap.png",
            *(
                f"sim_{preset.value}_{suffix}.png"
                for preset in SimPreset
                for suffix in ("original", "cloaked")
            ),
        ):
            with self.subTest(asset=filename):
                image = Image.open(
                    MOCK_ASSETS_DIR / filename
                )
                self.assertEqual(image.format, "PNG")
                image.verify()

        self.assertTrue(
            (MOCK_ASSETS_DIR / "sample_certificate.pdf").is_file()
        )

    def test_mock_mode_endpoint_responses_match_contract(self) -> None:
        mock_settings = type("Settings", (), {"mock": True})()
        patchers = [
            patch("app.routers.health.settings", mock_settings),
            patch("app.routers.config.settings", mock_settings),
            patch("app.routers.cloak.settings", mock_settings),
            patch("app.routers.jobs.settings", mock_settings),
            patch(
                "app.routers.sim.settings",
                type("Settings", (), {"mock": True, "simulator_enabled": True})(),
            ),
            patch("app.routers.certificate.settings", mock_settings),
            patch("app.routers.files.settings", mock_settings),
            patch("app.routers.watermark.settings", mock_settings),
            patch("app.routers.sim.job_is_ready", return_value=True),
            patch("app.routers.certificate.job_is_ready", return_value=True),
            patch("app.routers.files.job_is_ready", return_value=True),
        ]
        with ExitStack() as stack:
            for patcher in patchers:
                stack.enter_context(patcher)

            HealthResponse.model_validate(
                self.client.get("/api/v1/health").json()
            )
            AppConfig.model_validate(self.client.get("/api/v1/config").json())

            cloak_response = self.client.post(
                "/api/v1/cloak",
                files={"image": ("portrait.png", png_bytes(), "image/png")},
            )
            self.assertEqual(cloak_response.status_code, 202)
            accepted_cloak = JobAccepted.model_validate(cloak_response.json())
            cloak_job = Job[CloakResult].model_validate(
                self.client.get(
                    f"/api/v1/jobs/{accepted_cloak.job_id}"
                ).json()
            )
            self.assertEqual(cloak_job.type, JobType.cloak)

            sim_response = self.client.post(
                "/api/v1/attack-sim",
                json={
                    "job_id": accepted_cloak.job_id,
                    "preset": SimPreset.background_snow.value,
                },
            )
            self.assertEqual(sim_response.status_code, 202)
            accepted_sim = JobAccepted.model_validate(sim_response.json())
            sim_job = Job[SimResult].model_validate(
                self.client.get(
                    f"/api/v1/jobs/{accepted_sim.job_id}"
                ).json()
            )
            self.assertEqual(sim_job.type, JobType.attack_sim)

            file_response = self.client.get(
                "/api/v1/files/"
                "a91d3f0e5b7c4d2e8f10a6b3c4d5e6f7/original.png"
            )
            self.assertEqual(file_response.status_code, 200)
            self.assertEqual(file_response.headers["content-type"], "image/png")

            certificate_response = self.client.post(
                "/api/v1/certificate",
                json={"job_id": accepted_cloak.job_id},
            )
            self.assertEqual(certificate_response.status_code, 200)
            self.assertTrue(certificate_response.content.startswith(b"%PDF-"))

            watermark_response = self.client.post(
                "/api/v1/watermark/verify",
                files={"image": ("portrait.png", png_bytes(), "image/png")},
            )
            self.assertEqual(watermark_response.status_code, 501)
            self.assertEqual(
                ErrorBody.model_validate(watermark_response.json())
                .error.code.value,
                "NOT_IMPLEMENTED",
            )

    def test_invalid_cloak_and_invalid_requests_use_contract_error_body(self) -> None:
        invalid_image = self.client.post(
            "/api/v1/cloak",
            files={"image": ("portrait.png", b"not an image", "image/png")},
        )
        self.assertEqual(invalid_image.status_code, 400)
        self.assertEqual(
            ErrorBody.model_validate(invalid_image.json()).error.code.value,
            "INVALID_IMAGE",
        )

        invalid_sim = self.client.post(
            "/api/v1/attack-sim",
            json={"prompt": "free text"},
        )
        self.assertEqual(invalid_sim.status_code, 422)
        self.assertEqual(
            ErrorBody.model_validate(invalid_sim.json()).error.code.value,
            "BAD_PARAMS",
        )

    def test_oversized_upload_precedes_unsupported_file_type(self) -> None:
        response = self.client.post(
            "/api/v1/cloak",
            files={
                "image": (
                    "portrait.heic",
                    b"x" * (10 * 1024 * 1024 + 1),
                    "image/heic",
                )
            },
        )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(
            ErrorBody.model_validate(response.json()).error.code.value,
            "TOO_LARGE",
        )

    def test_unknown_job_and_file_errors_use_contract_error_body(self) -> None:
        job_response = self.client.get("/api/v1/jobs/not-a-known-job")
        self.assertEqual(job_response.status_code, 404)
        self.assertEqual(
            ErrorBody.model_validate(job_response.json()).error.code.value,
            "JOB_NOT_FOUND",
        )

        file_response = self.client.get(
            "/api/v1/files/not-a-known-file/original.png"
        )
        self.assertEqual(file_response.status_code, 404)
        self.assertEqual(
            ErrorBody.model_validate(file_response.json()).error.code.value,
            "JOB_NOT_FOUND",
        )

    def test_expired_mock_file_uses_job_expired_error(self) -> None:
        file_id = "a91d3f0e5b7c4d2e8f10a6b3c4d5e6f7"
        expired_job = SimpleNamespace(job_type=JobType.cloak)
        with (
            patch("app.routers.files.all_jobs", return_value=[expired_job]),
            patch("app.routers.files.job_is_expired", return_value=True),
            patch("app.routers.files.job_is_ready", return_value=False),
            patch(
                "app.routers.files.settings",
                SimpleNamespace(mock=True),
            ),
        ):
            response = self.client.get(
                f"/api/v1/files/{file_id}/original.png"
            )
        self.assertEqual(response.status_code, 410)
        self.assertEqual(
            ErrorBody.model_validate(response.json()).error.code.value,
            "JOB_EXPIRED",
        )

    def test_all_contract_endpoints_are_registered(self) -> None:
        expected_paths = {
            "/api/v1/health",
            "/api/v1/config",
            "/api/v1/cloak",
            "/api/v1/jobs/{job_id}",
            "/api/v1/attack-sim",
            "/api/v1/certificate",
            "/api/v1/files/{file_id}/{name}",
            "/api/v1/watermark/verify",
        }
        self.assertTrue(expected_paths.issubset(app.openapi()["paths"]))

    def test_job_models_are_generic_for_both_result_types(self) -> None:
        self.assertIsNotNone(Job[CloakResult])
        self.assertIsNotNone(Job[SimResult])


if __name__ == "__main__":
    unittest.main()
