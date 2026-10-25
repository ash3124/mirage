from fastapi import APIRouter

from ..config import settings
from ..errors import ApiError
from ..jobs import job_manager
from ..mock_data import (
    get_job,
    job_is_expired,
    job_is_ready,
    load_example,
    register_job,
)
from ..schemas import (
    AppConfig,
    AttackSimRequest,
    ErrorCode,
    JobAccepted,
    JobType,
)

router = APIRouter()


@router.post("/attack-sim", status_code=202, response_model=JobAccepted)
def start_simulation(request: AttackSimRequest) -> JobAccepted:
    if settings.mock:
        source_job = get_job(request.job_id)
        if source_job is None:
            raise ApiError(ErrorCode.JOB_NOT_FOUND)
        if job_is_expired(source_job):
            raise ApiError(ErrorCode.JOB_EXPIRED)
        if source_job.job_type != JobType.cloak:
            raise ApiError(ErrorCode.BAD_PARAMS)
        if not job_is_ready(source_job):
            raise ApiError(ErrorCode.JOB_NOT_READY)
        config = AppConfig.model_validate(load_example("config.ok.json"))
        if not config.simulator_enabled:
            raise ApiError(ErrorCode.SIM_UNAVAILABLE)
        fixture = load_example("attack_sim.accepted.json")
        fixture["job_id"] = register_job(JobType.attack_sim, request.preset)
        return JobAccepted.model_validate(fixture)

    job_manager.get_cloak_record(request.job_id)
    if not settings.simulator_enabled:
        raise ApiError(ErrorCode.SIM_UNAVAILABLE)
    record = job_manager.submit_simulation(request.job_id, request.preset)
    return JobAccepted(job_id=record.job_id, status="queued")
