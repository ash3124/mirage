from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from PIL import Image

from app.errors import ApiError
from app.jobs import JobManager, JobRecord
from app.schemas import (
    CloakMetrics,
    CloakRequest,
    CloakResult,
    ErrorCode,
    Hashes,
    Job,
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


def cloak_result(file_id: str) -> CloakResult:
    return CloakResult(
        file_id=file_id,
        original_url=f"/api/v1/files/{file_id}/original.png",
        cloaked_url=f"/api/v1/files/{file_id}/cloaked.png",
        heatmap_url=f"/api/v1/files/{file_id}/heatmap.png",
        metrics=CloakMetrics(
            protection_score=50,
            robustness=Robustness(jpeg_q75=45, resize_50=40, social_like=35),
            visual_quality=VisualQuality(psnr_db=32.0, ssim=0.95),
            working_size=WorkingSize(w=64, h=64),
            elapsed_s=0.1,
        ),
        metadata_report=MetadataReport(had_gps=False, removed=[]),
        hashes=Hashes(sha256_cloaked="a" * 64, phash_original="a" * 16),
        watermark=None,
        face_found=False,
        expires_at="2026-10-25T10:30:00Z",
    )


class JobManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.manager = JobManager(
            ttl_seconds=60,
            max_queue=3,
            root=Path(self.temp_dir.name),
            cleanup_interval=60,
        )

    def tearDown(self) -> None:
        self.manager.stop()
        self.temp_dir.cleanup()

    def wait_for_status(self, job_id: str, status: JobStatus) -> JobRecord:
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            record = self.manager.get(job_id)
            if record is not None and record.status == status:
                return record
            time.sleep(0.01)
        self.fail(f"Job {job_id} did not reach {status.value}.")

    def test_cloak_worker_updates_progress_and_finishes_contract_job(self) -> None:
        def processor(**kwargs):
            kwargs["callback"]("detecting_face", 5)
            kwargs["callback"]("optimizing", 42)
            return cloak_result(kwargs["file_id"])

        with patch("app.services.cloak.process_cloak", side_effect=processor):
            accepted = self.manager.submit_cloak(b"image bytes", CloakRequest())
            finished = self.wait_for_status(accepted.job_id, JobStatus.done)

        model = finished.to_model()
        Job[CloakResult].model_validate(model.model_dump(mode="json"))
        self.assertEqual(model.progress, 100)
        self.assertEqual(model.stage, Stage.done)
        self.assertEqual(model.type, JobType.cloak)
        self.assertIsInstance(model.result, CloakResult)
        self.assertEqual(model.result.file_id, accepted.file_id)
        self.assertEqual(finished.payload, {})

    def test_worker_converts_unexpected_errors_to_safe_internal_job_error(self) -> None:
        with patch(
            "app.services.cloak.process_cloak",
            side_effect=RuntimeError("private implementation detail"),
        ):
            accepted = self.manager.submit_cloak(b"image bytes", CloakRequest())
            failed = self.wait_for_status(accepted.job_id, JobStatus.error)

        self.assertEqual(failed.error.code, ErrorCode.INTERNAL)
        self.assertNotIn("private implementation detail", failed.error.message)
        Job[CloakResult].model_validate(failed.to_model().model_dump(mode="json"))

    def test_simulator_api_error_is_preserved_in_terminal_job(self) -> None:
        from app.errors import ApiError

        def cloak_processor(**kwargs):
            return cloak_result(kwargs["file_id"])

        with patch("app.services.cloak.process_cloak", side_effect=cloak_processor):
            source = self.manager.submit_cloak(b"image bytes", CloakRequest())
            self.wait_for_status(source.job_id, JobStatus.done)

        with patch(
            "app.services.simulate.process_simulation",
            side_effect=ApiError(ErrorCode.SIM_BLOCKED),
        ):
            accepted = self.manager.submit_simulation(
                source.job_id,
                SimPreset.background_snow,
            )
            failed = self.wait_for_status(accepted.job_id, JobStatus.error)

        self.assertEqual(failed.error.code, ErrorCode.SIM_BLOCKED)
        failed_model = Job[SimResult].model_validate(
            failed.to_model().model_dump(mode="json")
        )
        self.assertEqual(failed_model.type, JobType.attack_sim)

    def test_simulation_worker_uses_parent_file_id_and_finishes(self) -> None:
        def cloak_processor(**kwargs):
            root = Path(kwargs["output_dir"])
            root.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (16, 16), "white").save(root / "original.png")
            Image.new("RGB", (16, 16), "gray").save(root / "cloaked.png")
            return cloak_result(kwargs["file_id"])

        sim_result = SimResult(
            preset=SimPreset.background_snow,
            edit_on_original_url="/api/v1/files/file/sim_background_snow_original.png",
            edit_on_cloaked_url="/api/v1/files/file/sim_background_snow_cloaked.png",
            disruption_score=65,
            seed=1234,
        )

        with patch("app.services.cloak.process_cloak", side_effect=cloak_processor):
            source = self.manager.submit_cloak(b"image bytes", CloakRequest())
            self.wait_for_status(source.job_id, JobStatus.done)
        with patch("app.services.simulate.process_simulation") as processor:
            processor.side_effect = lambda **kwargs: (
                kwargs["callback"]("editing_original", 45),
                kwargs["callback"]("editing_cloaked", 90),
                kwargs["callback"]("scoring", 99),
                sim_result.model_copy(
                    update={
                        "edit_on_original_url": (
                            f"/api/v1/files/{kwargs['file_id']}/"
                            "sim_background_snow_original.png"
                        ),
                        "edit_on_cloaked_url": (
                            f"/api/v1/files/{kwargs['file_id']}/"
                            "sim_background_snow_cloaked.png"
                        ),
                    }
                ),
            )[-1]
            accepted = self.manager.submit_simulation(
                source.job_id,
                SimPreset.background_snow,
            )
            finished = self.wait_for_status(accepted.job_id, JobStatus.done)

        self.assertEqual(accepted.file_id, source.file_id)
        self.assertEqual(finished.stage, Stage.done)
        self.assertIsInstance(finished.result, SimResult)
        self.assertIn(source.file_id, finished.result.edit_on_original_url)
        Job[SimResult].model_validate(finished.to_model().model_dump(mode="json"))
        processor.assert_called_once()

    def test_simulation_requires_a_completed_cloak_job(self) -> None:
        queued = self.manager.submit_cloak(b"image bytes", CloakRequest())
        try:
            with self.assertRaises(ApiError) as context:
                self.manager.submit_simulation(
                    queued.job_id,
                    SimPreset.background_snow,
                )
            self.assertEqual(context.exception.code, ErrorCode.JOB_NOT_READY)
        finally:
            self.manager.stop()

    def test_file_path_requires_completed_job_and_safe_id(self) -> None:
        accepted = self.manager.submit_cloak(b"image bytes", CloakRequest())
        with self.assertRaises(ApiError) as context:
            self.manager.file_path(accepted.file_id, "original.png")
        self.assertEqual(context.exception.code, ErrorCode.JOB_NOT_FOUND)

        with self.assertRaises(ApiError) as context:
            self.manager.file_path("../outside", "original.png")
        self.assertEqual(context.exception.code, ErrorCode.JOB_NOT_FOUND)

    def test_cleanup_removes_expired_cloak_job_and_files(self) -> None:
        self.manager.root.mkdir(parents=True, exist_ok=True)
        file_id = "a" * 32
        directory = self.manager.root / file_id
        directory.mkdir()
        artifact = directory / "original.png"
        artifact.write_bytes(b"image")
        record = JobRecord(
            job_id="expired-job",
            job_type=JobType.cloak,
            created_at=100.0,
            created_at_utc=datetime.now(timezone.utc),
            file_id=file_id,
        )
        self.manager._jobs[record.job_id] = record

        removed = self.manager.cleanup_expired(now=161.0)

        self.assertEqual(removed, 1)
        self.assertIsNone(self.manager.get(record.job_id))
        self.assertFalse(directory.exists())
        with self.assertRaises(ApiError) as context:
            self.manager.file_path(file_id, "original.png")
        self.assertEqual(context.exception.code, ErrorCode.JOB_EXPIRED)


if __name__ == "__main__":
    unittest.main()
