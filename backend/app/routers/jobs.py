from fastapi import APIRouter
from pydantic import TypeAdapter

from ..config import settings
from ..errors import ApiError
from ..jobs import job_manager
from ..mock_data import (
    fixture_for_job,
    get_job,
    job_is_expired,
)
from ..schemas import CloakResult, ErrorCode, Job, SimResult

router = APIRouter()
job_adapter = TypeAdapter(Job[CloakResult] | Job[SimResult])


@router.get("/jobs/{job_id}", response_model=Job[CloakResult] | Job[SimResult])
def get_job_status(job_id: str) -> Job[CloakResult] | Job[SimResult]:
    if settings.mock:
        job = get_job(job_id)
        if job is None:
            raise ApiError(ErrorCode.JOB_NOT_FOUND)
        if job_is_expired(job):
            raise ApiError(ErrorCode.JOB_EXPIRED)
        return job_adapter.validate_python(fixture_for_job(job))
    job = job_manager.get(job_id)
    if job is None:
        if job_manager.was_expired(job_id):
            raise ApiError(ErrorCode.JOB_EXPIRED)
        raise ApiError(ErrorCode.JOB_NOT_FOUND)
    if job_manager.is_expired(job):
        raise ApiError(ErrorCode.JOB_EXPIRED)
    return job_adapter.validate_python(job.to_model().model_dump(mode="json"))
