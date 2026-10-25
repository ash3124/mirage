"""Single-worker in-memory job queue with TTL-based file cleanup."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
import queue
import re
import shutil
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from .config import settings
from .errors import ApiError
from .schemas import (
    CloakRequest,
    CloakResult,
    ErrorCode,
    ErrorObj,
    Job,
    JobStatus,
    JobType,
    SimPreset,
    SimResult,
    Strength,
    Stage,
)

logger = logging.getLogger(__name__)
JOB_ROOT = Path(tempfile.gettempdir()) / "mirage"


@dataclass
class JobRecord:
    job_id: str
    job_type: JobType
    created_at: float
    created_at_utc: datetime
    file_id: str
    strength: Strength | None = None
    owner_tag: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    status: JobStatus = JobStatus.queued
    progress: int = 0
    stage: Stage = Stage.queued
    result: CloakResult | SimResult | None = None
    error: ErrorObj | None = None

    def to_model(self) -> Job:
        return Job(
            job_id=self.job_id,
            type=self.job_type,
            status=self.status,
            progress=self.progress,
            stage=self.stage,
            result=self.result,
            error=self.error,
        )


class JobContext:
    def __init__(self, manager: "JobManager", job_id: str) -> None:
        self._manager = manager
        self.job_id = job_id

    def update(self, stage: str, progress: int) -> None:
        self._manager.update_progress(self.job_id, stage, progress)


class JobManager:
    def __init__(
        self,
        ttl_seconds: int,
        max_queue: int,
        root: Path = JOB_ROOT,
        cleanup_interval: float = 60.0,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_queue = max_queue
        self.root = root
        self.cleanup_interval = cleanup_interval
        self._jobs: dict[str, JobRecord] = {}
        self._expired_job_ids: set[str] = set()
        self._expired_file_ids: set[str] = set()
        self._lock = threading.RLock()
        self._queue: queue.Queue[str] = queue.Queue()
        self._started = False
        self._worker: threading.Thread | None = None
        self._cleaner: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self.root.mkdir(parents=True, exist_ok=True)
            self._started = True
            self._worker = threading.Thread(
                target=self._worker_loop,
                name="mirage-job-worker",
                daemon=True,
            )
            self._cleaner = threading.Thread(
                target=self._cleaner_loop,
                name="mirage-job-cleaner",
                daemon=True,
            )
            self._worker.start()
            self._cleaner.start()

    def stop(self, timeout: float = 1.0) -> None:
        self._stop_event.set()
        self._queue.put("")
        if self._worker is not None:
            self._worker.join(timeout=timeout)
        if self._cleaner is not None:
            self._cleaner.join(timeout=timeout)

    def _ensure_started(self) -> None:
        if not self._started:
            self.start()

    @property
    def queue_depth(self) -> int:
        with self._lock:
            return sum(
                record.status in {JobStatus.queued, JobStatus.running}
                for record in self._jobs.values()
            )

    def submit_cloak(self, image_bytes: bytes, request: CloakRequest) -> JobRecord:
        self._ensure_started()
        with self._lock:
            if self.queue_depth >= self.max_queue:
                raise ApiError(ErrorCode.BUSY)
            job_id = str(uuid4())
            file_id = uuid4().hex
            directory = self.root / file_id
            directory.mkdir(parents=True, exist_ok=False)
            record = JobRecord(
                job_id=job_id,
                job_type=JobType.cloak,
                created_at=time.monotonic(),
                created_at_utc=datetime.now(timezone.utc),
                file_id=file_id,
                strength=request.strength,
                owner_tag=request.owner_tag if request.embed_watermark else None,
                payload={"image_bytes": image_bytes, "request": request},
            )
            self._jobs[job_id] = record
            self._queue.put(job_id)
            return record

    def submit_simulation(
        self,
        source_job_id: str,
        preset: SimPreset,
    ) -> JobRecord:
        self._ensure_started()
        with self._lock:
            source = self._jobs.get(source_job_id)
            if source is None:
                raise ApiError(ErrorCode.JOB_NOT_FOUND)
            if self.is_expired(source):
                raise ApiError(ErrorCode.JOB_EXPIRED)
            if source.job_type != JobType.cloak:
                raise ApiError(ErrorCode.BAD_PARAMS)
            if source.status != JobStatus.done:
                raise ApiError(ErrorCode.JOB_NOT_READY)
            if self.queue_depth >= self.max_queue:
                raise ApiError(ErrorCode.BUSY)
            record = JobRecord(
                job_id=str(uuid4()),
                job_type=JobType.attack_sim,
                created_at=time.monotonic(),
                created_at_utc=datetime.now(timezone.utc),
                file_id=source.file_id,
                payload={"source_job_id": source_job_id, "preset": preset},
            )
            self._jobs[record.job_id] = record
            self._queue.put(record.job_id)
            return record

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def get_cloak_record(self, job_id: str) -> JobRecord:
        record = self.get(job_id)
        if record is None:
            if self.was_expired(job_id):
                raise ApiError(ErrorCode.JOB_EXPIRED)
            raise ApiError(ErrorCode.JOB_NOT_FOUND)
        if self.is_expired(record):
            raise ApiError(ErrorCode.JOB_EXPIRED)
        if record.job_type != JobType.cloak:
            raise ApiError(ErrorCode.BAD_PARAMS)
        if record.status != JobStatus.done or not isinstance(record.result, CloakResult):
            raise ApiError(ErrorCode.JOB_NOT_READY)
        return record

    def was_expired(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._expired_job_ids

    def is_expired(self, record: JobRecord) -> bool:
        return time.monotonic() - record.created_at >= self.ttl_seconds

    def file_path(self, file_id: str, name: str) -> Path:
        if len(file_id) != 32 or any(char not in "0123456789abcdef" for char in file_id):
            raise ApiError(ErrorCode.JOB_NOT_FOUND)
        if not (
            name in {"original.png", "cloaked.png", "heatmap.png"}
            or re.fullmatch(
                r"sim_(background_snow|background_beach|new_hairstyle|vintage_style)_(original|cloaked)\.png",
                name,
            )
        ):
            raise ApiError(ErrorCode.JOB_NOT_FOUND)
        with self._lock:
            source = next(
                (
                    record
                    for record in self._jobs.values()
                    if record.job_type == JobType.cloak
                    and record.file_id == file_id
                ),
                None,
            )
            if source is None:
                if file_id in self._expired_file_ids:
                    raise ApiError(ErrorCode.JOB_EXPIRED)
                raise ApiError(ErrorCode.JOB_NOT_FOUND)
            if self.is_expired(source):
                raise ApiError(ErrorCode.JOB_EXPIRED)
            if source.status != JobStatus.done:
                raise ApiError(ErrorCode.JOB_NOT_FOUND)
            path = self.root / file_id / name
            if not path.is_file():
                raise ApiError(ErrorCode.JOB_NOT_FOUND)
            return path

    def update_progress(self, job_id: str, stage: str, progress: int) -> None:
        try:
            stage_value = Stage(stage)
        except ValueError as exc:
            raise ValueError(f"Unsupported job stage: {stage}") from exc
        if not 0 <= progress <= 100:
            raise ValueError("Job progress must be in the range 0..100.")
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return
            record.stage = stage_value
            record.progress = progress
            record.status = JobStatus.running

    def cleanup_expired(self, now: float | None = None) -> int:
        current = time.monotonic() if now is None else now
        removed_file_ids: set[str] = set()
        with self._lock:
            expired = [
                record
                for record in self._jobs.values()
                if current - record.created_at >= self.ttl_seconds
            ]
            for record in expired:
                self._expired_job_ids.add(record.job_id)
                if record.job_type == JobType.cloak:
                    removed_file_ids.add(record.file_id)
            self._expired_file_ids.update(removed_file_ids)
            for job_id, record in list(self._jobs.items()):
                if record.file_id in removed_file_ids or current - record.created_at >= self.ttl_seconds:
                    self._expired_job_ids.add(job_id)
                    del self._jobs[job_id]
        for file_id in removed_file_ids:
            try:
                shutil.rmtree(self.root / file_id)
            except FileNotFoundError:
                pass
            except OSError:
                logger.exception("Could not remove expired Mirage files (file_id=%s)", file_id)
        return len(expired)

    def _cleaner_loop(self) -> None:
        while not self._stop_event.wait(self.cleanup_interval):
            try:
                self.cleanup_expired()
            except Exception:
                logger.exception("Mirage job cleanup failed")

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            job_id = self._queue.get()
            try:
                if not job_id:
                    continue
                self._execute(job_id)
            finally:
                self._queue.task_done()

    def _execute(self, job_id: str) -> None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None or self.is_expired(record):
                return
            record.status = JobStatus.running
            record.progress = 0
            context = JobContext(self, job_id)
        try:
            if record.job_type == JobType.cloak:
                from .services.cloak import process_cloak

                result = process_cloak(
                    image_bytes=record.payload["image_bytes"],
                    request=record.payload["request"],
                    file_id=record.file_id,
                    output_dir=self.root / record.file_id,
                    max_side_px=settings.max_side_px,
                    callback=context.update,
                    expires_at=(
                        record.created_at_utc
                        + timedelta(seconds=self.ttl_seconds)
                    ).isoformat().replace("+00:00", "Z"),
                )
            else:
                from .services.simulate import process_simulation

                result = process_simulation(
                    file_id=record.file_id,
                    preset=record.payload["preset"],
                    output_dir=self.root / record.file_id,
                    callback=context.update,
                )
            with self._lock:
                current = self._jobs.get(job_id)
                if current is None:
                    file_is_owned = any(
                        entry.job_type == JobType.cloak
                        and entry.file_id == record.file_id
                        for entry in self._jobs.values()
                    )
                    remove_orphaned_files = not file_is_owned
                else:
                    remove_orphaned_files = False
                    current.result = result
                    current.error = None
                    current.status = JobStatus.done
                    current.progress = 100
                    current.stage = Stage.done
                    current.payload.clear()
            if remove_orphaned_files:
                try:
                    shutil.rmtree(self.root / record.file_id)
                except FileNotFoundError:
                    pass
                except OSError:
                    logger.exception(
                        "Could not remove orphaned Mirage files (file_id=%s)",
                        record.file_id,
                    )
                return
        except ApiError as exc:
            self._fail(record, exc.code, exc.safe_message)
        except Exception:
            logger.exception("Mirage job processing failed (job_id=%s)", job_id)
            self._fail(
                record,
                ErrorCode.INTERNAL,
                "Something went wrong while protecting your photo."
                if record.job_type == JobType.cloak
                else "Something went wrong while running the edit simulation.",
            )

    def _fail(self, record: JobRecord, code: ErrorCode, message: str) -> None:
        with self._lock:
            current = self._jobs.get(record.job_id)
            if current is None:
                return
            current.status = JobStatus.error
            current.result = None
            current.error = ErrorObj(code=code, message=message)
            current.payload.clear()


job_manager = JobManager(
    ttl_seconds=settings.ttl_seconds,
    max_queue=settings.max_queue,
)
