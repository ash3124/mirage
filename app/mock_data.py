"""Load shared contract examples and track short-lived mock jobs."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .config import MOCK_ASSETS_DIR, MOCK_EXAMPLES_DIR, settings
from .schemas import JobType, SimPreset


@dataclass(frozen=True)
class MockJob:
    job_id: str
    job_type: JobType
    created_at: float
    preset: SimPreset | None = None


_jobs: dict[str, MockJob] = {}
_jobs_lock = threading.Lock()


def load_example(filename: str) -> dict:
    if Path(filename).name != filename:
        raise ValueError("Mock example names must be file names.")
    path = MOCK_EXAMPLES_DIR / filename
    if not path.is_file():
        raise RuntimeError(
            f"Required MOCK fixture is missing: shared/examples/{filename}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_example_asset(filename: str) -> Path:
    if Path(filename).name != filename:
        raise ValueError("Mock asset names must be file names.")
    path = MOCK_ASSETS_DIR / filename
    if not path.is_file():
        raise RuntimeError(
            f"Required MOCK asset is missing: shared/examples/assets/{filename}"
        )
    return path


def load_certificate_asset() -> Path:
    if not MOCK_ASSETS_DIR.is_dir():
        raise RuntimeError("Required MOCK assets directory is missing.")
    pdf_files = sorted(MOCK_ASSETS_DIR.glob("*.pdf"))
    if len(pdf_files) != 1:
        raise RuntimeError(
            "MOCK requires exactly one PDF in shared/examples/assets/."
        )
    return pdf_files[0]


def register_job(job_type: JobType, preset: SimPreset | None = None) -> str:
    job_id = str(uuid4())
    with _jobs_lock:
        _jobs[job_id] = MockJob(job_id, job_type, time.monotonic(), preset)
    return job_id


def get_job(job_id: str) -> MockJob | None:
    with _jobs_lock:
        return _jobs.get(job_id)


def all_jobs() -> list[MockJob]:
    with _jobs_lock:
        return list(_jobs.values())


def job_fixture_name(job: MockJob) -> str:
    elapsed = time.monotonic() - job.created_at
    if job.job_type == JobType.cloak:
        if elapsed < 0.5:
            return "job.cloak.queued.json"
        if elapsed < min(6, settings.ttl_seconds):
            return "job.cloak.running.json"
        return "job.cloak.done.json"
    if elapsed < min(6, settings.ttl_seconds):
        return "job.sim.running.json"
    return "job.sim.done.json"


def job_is_expired(job: MockJob) -> bool:
    return time.monotonic() - job.created_at >= settings.ttl_seconds


def job_is_ready(job: MockJob) -> bool:
    return time.monotonic() - job.created_at >= 6


def fixture_for_job(job: MockJob) -> dict:
    fixture = load_example(job_fixture_name(job))
    fixture["job_id"] = job.job_id
    if job.job_type == JobType.attack_sim and job.preset is not None:
        result = fixture.get("result")
        if result is not None:
            result["preset"] = job.preset.value
            result["edit_on_original_url"] = result[
                "edit_on_original_url"
            ].replace("sim_background_snow_", f"sim_{job.preset.value}_")
            result["edit_on_cloaked_url"] = result[
                "edit_on_cloaked_url"
            ].replace("sim_background_snow_", f"sim_{job.preset.value}_")
    return fixture
