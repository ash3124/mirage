from fastapi import APIRouter
from fastapi.responses import FileResponse, Response

from ..config import settings
from ..errors import ApiError
from ..jobs import job_manager
from ..mock_data import (
    get_job,
    job_is_expired,
    job_is_ready,
    load_certificate_asset,
)
from ..schemas import CertificateRequest, ErrorCode, JobType
from ..services.certificate import create_certificate as generate_certificate

router = APIRouter()


@router.post("/certificate")
def create_certificate(request: CertificateRequest):
    if settings.mock:
        job = get_job(request.job_id)
        if job is None:
            raise ApiError(ErrorCode.JOB_NOT_FOUND)
        if job_is_expired(job):
            raise ApiError(ErrorCode.JOB_EXPIRED)
        if job.job_type != JobType.cloak:
            raise ApiError(ErrorCode.BAD_PARAMS)
        if not job_is_ready(job):
            raise ApiError(ErrorCode.JOB_NOT_READY)
        return FileResponse(
            load_certificate_asset(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    'attachment; filename="mirage-protection-record.pdf"'
                )
            },
        )
    record = job_manager.get_cloak_record(request.job_id)
    pdf = generate_certificate(
        record,
        image_directory=job_manager.root / record.file_id,
        owner_name=request.owner_name,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                'attachment; filename="mirage-protection-record.pdf"'
            )
        },
    )
