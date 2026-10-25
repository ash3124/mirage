from __future__ import annotations

from io import BytesIO
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from app.jobs import JobManager, JobRecord
from app.main import app
from app.schemas import (
    CloakRequest,
    CloakMetrics,
    CloakResult,
    ErrorCode,
    Hashes,
    JobStatus,
    JobType,
    MetadataReport,
    Robustness,
    Stage,
    VisualQuality,
    WorkingSize,
)


def make_png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), "blue").save(buffer, format="PNG")
    return buffer.getvalue()


def make_cloak_result(file_id: str) -> CloakResult:
    return CloakResult(
        file_id=file_id,
        original_url=f"/api/v1/files/{file_id}/original.png",
        cloaked_url=f"/api/v1/files/{file_id}/cloaked.png",
        heatmap_url=f"/api/v1/files/{file_id}/heatmap.png",
        metrics=CloakMetrics(
            protection_score=50,
            robustness=Robustness(jpeg_q75=40, resize_50=35, social_like=30),
            visual_quality=VisualQuality(psnr_db=32, ssim=0.95),
            working_size=WorkingSize(w=32, h=32),
            elapsed_s=0.1,
        ),
        metadata_report=MetadataReport(had_gps=False, removed=[]),
        hashes=Hashes(sha256_cloaked="a" * 64, phash_original="a" * 16),
        watermark=None,
        face_found=False,
        expires_at="2026-10-25T10:30:00Z",
    )


class RealJobRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.manager = JobManager(
            ttl_seconds=60,
            max_queue=3,
            root=Path(self.temp_dir.name),
            cleanup_interval=60,
        )
        self.client = TestClient(app)
        self.patches = [
            patch(
                "app.main.settings",
                SimpleNamespace(mock=True),
            ),
            patch("app.routers.cloak.job_manager", self.manager),
            patch("app.routers.jobs.job_manager", self.manager),
            patch("app.routers.files.job_manager", self.manager),
            patch("app.routers.sim.job_manager", self.manager),
            patch("app.routers.certificate.job_manager", self.manager),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.manager.stop()
        self.client.close()
        self.temp_dir.cleanup()

    def test_real_cloak_job_poll_and_file_download(self) -> None:
        def processor(**kwargs):
            output_dir = Path(kwargs["output_dir"])
            output_dir.mkdir(parents=True, exist_ok=True)
            for name, color in (
                ("original.png", "blue"),
                ("cloaked.png", "red"),
                ("heatmap.png", "black"),
            ):
                Image.new("RGB", (32, 32), color).save(output_dir / name)
            file_id = kwargs["file_id"]
            return CloakResult(
                file_id=file_id,
                original_url=f"/api/v1/files/{file_id}/original.png",
                cloaked_url=f"/api/v1/files/{file_id}/cloaked.png",
                heatmap_url=f"/api/v1/files/{file_id}/heatmap.png",
                metrics=CloakMetrics(
                    protection_score=50,
                    robustness=Robustness(
                        jpeg_q75=40,
                        resize_50=35,
                        social_like=30,
                    ),
                    visual_quality=VisualQuality(psnr_db=32, ssim=0.95),
                    working_size=WorkingSize(w=32, h=32),
                    elapsed_s=0.1,
                ),
                metadata_report=MetadataReport(had_gps=False, removed=[]),
                hashes=Hashes(
                    sha256_cloaked="a" * 64,
                    phash_original="a" * 16,
                ),
                watermark=None,
                face_found=False,
                expires_at="2026-10-25T10:30:00Z",
            )

        with patch("app.services.cloak.process_cloak", side_effect=processor):
            response = self.client.post(
                "/api/v1/cloak",
                files={"image": ("portrait.png", make_png(), "image/png")},
                data={"face_focus": "false"},
            )
            self.assertEqual(response.status_code, 202)
            job_id = response.json()["job_id"]

            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                job_response = self.client.get(f"/api/v1/jobs/{job_id}")
                if job_response.json()["status"] in {"done", "error"}:
                    break
                time.sleep(0.01)

        self.assertEqual(job_response.status_code, 200)
        self.assertEqual(job_response.json()["status"], "done")
        file_id = job_response.json()["result"]["file_id"]
        file_response = self.client.get(
            f"/api/v1/files/{file_id}/cloaked.png?download=1"
        )
        self.assertEqual(file_response.status_code, 200)
        self.assertEqual(file_response.headers["content-type"], "image/png")
        self.assertIn("attachment", file_response.headers["content-disposition"])
        self.assertEqual(file_response.content[:8], b"\x89PNG\r\n\x1a\n")

    def test_invalid_image_returns_contract_error_before_queueing(self) -> None:
        response = self.client.post(
            "/api/v1/cloak",
            files={"image": ("portrait.png", b"not an image", "image/png")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "INVALID_IMAGE")

    def add_job(
        self,
        *,
        job_id: str,
        status: JobStatus,
        file_id: str = "b" * 32,
    ) -> JobRecord:
        result = make_cloak_result(file_id) if status == JobStatus.done else None
        record = JobRecord(
            job_id=job_id,
            job_type=JobType.cloak,
            created_at=time.monotonic(),
            created_at_utc=datetime.now(timezone.utc),
            file_id=file_id,
            strength=CloakRequest().strength,
            status=status,
            progress=100 if status == JobStatus.done else 5,
            stage=Stage.done
            if status == JobStatus.done
            else Stage.optimizing,
            result=result,
        )
        self.manager.root.mkdir(parents=True, exist_ok=True)
        (self.manager.root / file_id).mkdir(parents=True, exist_ok=True)
        with self.manager._lock:
            self.manager._jobs[job_id] = record
        return record

    def test_attack_sim_returns_job_not_ready_for_running_cloak(self) -> None:
        self.add_job(job_id="running-cloak", status=JobStatus.running)
        response = self.client.post(
            "/api/v1/attack-sim",
            json={"job_id": "running-cloak", "preset": "background_snow"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "JOB_NOT_READY")

    def test_attack_sim_returns_sim_unavailable_when_disabled(self) -> None:
        self.add_job(job_id="done-cloak", status=JobStatus.done)
        with patch(
            "app.routers.sim.settings",
            SimpleNamespace(mock=False, simulator_enabled=False),
        ):
            response = self.client.post(
                "/api/v1/attack-sim",
                json={"job_id": "done-cloak", "preset": "background_snow"},
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "SIM_UNAVAILABLE")

    def test_certificate_returns_reportlab_pdf_for_completed_cloak(self) -> None:
        record = self.add_job(job_id="done-cloak", status=JobStatus.done)
        root = self.manager.root / record.file_id
        Image.new("RGB", (32, 32), "blue").save(root / "original.png")
        Image.new("RGB", (32, 32), "red").save(root / "cloaked.png")
        with patch(
            "app.routers.certificate.settings",
            SimpleNamespace(mock=False),
        ):
            response = self.client.post(
                "/api/v1/certificate",
                json={"job_id": record.job_id, "owner_name": "Test Owner"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertEqual(
            response.headers["content-disposition"],
            'attachment; filename="mirage-protection-record.pdf"',
        )
        self.assertTrue(response.content.startswith(b"%PDF-"))

    def test_certificate_returns_job_not_ready_for_running_cloak(self) -> None:
        self.add_job(job_id="running-cloak", status=JobStatus.running)
        with patch(
            "app.routers.certificate.settings",
            SimpleNamespace(mock=False),
        ):
            response = self.client.post(
                "/api/v1/certificate",
                json={"job_id": "running-cloak"},
            )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "JOB_NOT_READY")


if __name__ == "__main__":
    unittest.main()
