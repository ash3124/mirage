import re

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from ..config import settings
from ..errors import ApiError
from ..jobs import job_manager
from ..mock_data import (
    all_jobs,
    job_is_expired,
    job_is_ready,
    load_example,
    load_example_asset,
)
from ..schemas import ErrorCode, JobType

router = APIRouter()
SIM_FILE_PATTERN = re.compile(
    r"^sim_(background_snow|background_beach|new_hairstyle|vintage_style)_(original|cloaked)\.png$"
)


def allowed_file_name(name: str) -> bool:
    return name in {"original.png", "cloaked.png", "heatmap.png"} or bool(
        SIM_FILE_PATTERN.fullmatch(name)
    )


@router.get("/files/{file_id}/{name}")
def get_file(
    file_id: str,
    name: str,
    download: int = Query(default=0, ge=0, le=1),
):
    if not allowed_file_name(name):
        raise ApiError(ErrorCode.JOB_NOT_FOUND)

    if not settings.mock:
        path = job_manager.file_path(file_id, name)
        headers = (
            {"Content-Disposition": f'attachment; filename="{name}"'}
            if download
            else None
        )
        return FileResponse(path, media_type="image/png", headers=headers)

    cloak_job = load_example("job.cloak.done.json")
    if file_id != cloak_job["result"]["file_id"]:
        raise ApiError(ErrorCode.JOB_NOT_FOUND)
    if not any(
        job.job_type == JobType.cloak
        and not job_is_expired(job)
        and job_is_ready(job)
        for job in all_jobs()
    ):
        raise ApiError(ErrorCode.JOB_NOT_FOUND)

    asset = load_example_asset(name)
    headers = (
        {"Content-Disposition": f'attachment; filename="{name}"'}
        if download
        else None
    )
    return FileResponse(
        asset,
        media_type="image/png",
        headers=headers,
    )
