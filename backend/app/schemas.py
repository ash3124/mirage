"""Pydantic models matching the public API contract."""

from __future__ import annotations

from enum import Enum
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Strength(str, Enum):
    light = "light"
    standard = "standard"
    strong = "strong"


class SimPreset(str, Enum):
    background_snow = "background_snow"
    background_beach = "background_beach"
    new_hairstyle = "new_hairstyle"
    vintage_style = "vintage_style"


class JobType(str, Enum):
    cloak = "cloak"
    attack_sim = "attack_sim"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    error = "error"


class Mode(str, Enum):
    gpu = "gpu"
    cpu = "cpu"


class Stage(str, Enum):
    queued = "queued"
    detecting_face = "detecting_face"
    optimizing = "optimizing"
    robustness_check = "robustness_check"
    finalizing = "finalizing"
    editing_original = "editing_original"
    editing_cloaked = "editing_cloaked"
    scoring = "scoring"
    done = "done"


class ErrorCode(str, Enum):
    INVALID_IMAGE = "INVALID_IMAGE"
    TOO_LARGE = "TOO_LARGE"
    BAD_PARAMS = "BAD_PARAMS"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    JOB_EXPIRED = "JOB_EXPIRED"
    JOB_NOT_READY = "JOB_NOT_READY"
    BUSY = "BUSY"
    SIM_UNAVAILABLE = "SIM_UNAVAILABLE"
    SIM_BLOCKED = "SIM_BLOCKED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    INTERNAL = "INTERNAL"


class ErrorObj(ContractModel):
    code: ErrorCode
    message: str


class ErrorBody(ContractModel):
    error: ErrorObj


class HealthResponse(ContractModel):
    status: Literal["ok"]
    version: str
    mode: Mode
    queue_depth: int = Field(ge=0)
    simulator_enabled: bool


class StrengthOption(ContractModel):
    id: Strength
    label: str
    description: str


class SimPresetOption(ContractModel):
    id: SimPreset
    label: str


class Features(ContractModel):
    watermark: bool
    face_focus: bool
    robust_mode: bool


class Limits(ContractModel):
    max_upload_mb: int
    ttl_seconds: int
    max_side_px: int


class AppConfig(ContractModel):
    version: str
    mode: Mode
    simulator_enabled: bool
    features: Features
    limits: Limits
    strengths: list[StrengthOption]
    sim_presets: list[SimPresetOption]


class Robustness(ContractModel):
    jpeg_q75: int = Field(ge=0, le=100)
    resize_50: int = Field(ge=0, le=100)
    social_like: int = Field(ge=0, le=100)


class VisualQuality(ContractModel):
    psnr_db: float
    ssim: float = Field(ge=0, le=1)


class WorkingSize(ContractModel):
    w: int
    h: int


class CloakMetrics(ContractModel):
    protection_score: int = Field(ge=0, le=100)
    robustness: Robustness
    visual_quality: VisualQuality
    working_size: WorkingSize
    elapsed_s: float


class MetadataReport(ContractModel):
    had_gps: bool
    removed: list[str]


class Hashes(ContractModel):
    sha256_cloaked: str
    phash_original: str


class Watermark(ContractModel):
    embedded: bool
    tag: str


class CloakResult(ContractModel):
    file_id: str
    original_url: str
    cloaked_url: str
    heatmap_url: str
    metrics: CloakMetrics
    metadata_report: MetadataReport
    hashes: Hashes
    watermark: Watermark | None
    face_found: bool
    expires_at: str


class SimResult(ContractModel):
    preset: SimPreset
    edit_on_original_url: str
    edit_on_cloaked_url: str
    disruption_score: int = Field(ge=0, le=100)
    seed: int


ResultT = TypeVar("ResultT", CloakResult, SimResult)


class Job(ContractModel, Generic[ResultT]):
    job_id: str
    type: JobType
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    stage: Stage
    result: ResultT | None
    error: ErrorObj | None

    @model_validator(mode="after")
    def validate_terminal_fields(self) -> "Job[ResultT]":
        if self.status == JobStatus.done:
            if self.result is None or self.error is not None:
                raise ValueError("A done job must have a result and no error.")
            if self.progress != 100 or self.stage != Stage.done:
                raise ValueError("A done job must have 100 progress and stage done.")
            if self.type == JobType.cloak and not isinstance(self.result, CloakResult):
                raise ValueError("A cloak job must have a CloakResult.")
            if self.type == JobType.attack_sim and not isinstance(
                self.result, SimResult
            ):
                raise ValueError("An attack_sim job must have a SimResult.")
        elif self.status == JobStatus.error:
            if self.error is None or self.result is not None:
                raise ValueError("An error job must have an error and no result.")
        elif self.result is not None or self.error is not None:
            raise ValueError("A non-terminal job cannot have a result or error.")
        return self


class JobAccepted(ContractModel):
    job_id: str
    status: Literal["queued"]


class CloakRequest(ContractModel):
    strength: Strength = Strength.standard
    face_focus: bool = True
    robust_mode: bool = True
    embed_watermark: bool = False
    owner_tag: str | None = Field(
        default=None,
        min_length=1,
        max_length=4,
        pattern=r"^[A-Z0-9]{1,4}$",
    )


class AttackSimRequest(ContractModel):
    job_id: str
    preset: SimPreset


class CertificateRequest(ContractModel):
    job_id: str
    owner_name: str | None = Field(default=None, max_length=60)


class WatermarkVerifyResponse(ContractModel):
    found: bool
    tag: str | None
