from fastapi import APIRouter, File, Form, UploadFile
from pydantic import ValidationError

from ..config import settings
from ..errors import ApiError
from ..jobs import job_manager
from ..mock_data import load_example, register_job
from ..schemas import CloakRequest, ErrorCode, JobAccepted, JobType, Strength
from ..services.privacy import MAX_UPLOAD_BYTES, validate_image_bytes

router = APIRouter()
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
SUPPORTED_MEDIA_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/octet-stream",
}


async def validate_upload(image: UploadFile) -> bytes:
    contents = await image.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise ApiError(ErrorCode.TOO_LARGE)

    filename = image.filename or ""
    extension = filename.rsplit(".", maxsplit=1)
    suffix = f".{extension[-1].lower()}" if len(extension) == 2 else ""
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ApiError(ErrorCode.INVALID_IMAGE)
    if image.content_type and image.content_type.lower() not in SUPPORTED_MEDIA_TYPES:
        raise ApiError(ErrorCode.INVALID_IMAGE)

    validate_image_bytes(contents)
    return contents


@router.post("/cloak", status_code=202, response_model=JobAccepted)
async def start_cloak(
    image: UploadFile = File(...),
    strength: Strength = Form(default=Strength.standard),
    face_focus: bool = Form(default=True),
    robust_mode: bool = Form(default=True),
    embed_watermark: bool = Form(default=False),
    owner_tag: str | None = Form(
        default=None, min_length=1, max_length=4, pattern=r"^[A-Z0-9]{1,4}$"
    ),
) -> JobAccepted:
    image_bytes = await validate_upload(image)
    try:
        request = CloakRequest(
            strength=strength,
            face_focus=face_focus,
            robust_mode=robust_mode,
            embed_watermark=embed_watermark,
            owner_tag=owner_tag,
        )
    except ValidationError as exc:
        raise ApiError(ErrorCode.BAD_PARAMS) from exc

    if settings.mock:
        from ..schemas import AppConfig

        config = AppConfig.model_validate(load_example("config.ok.json"))
        if request.embed_watermark and not config.features.watermark:
            raise ApiError(ErrorCode.NOT_IMPLEMENTED)
    elif request.embed_watermark:
        raise ApiError(ErrorCode.NOT_IMPLEMENTED)

    if settings.mock:
        if request.embed_watermark and request.owner_tag is None:
            raise ApiError(ErrorCode.BAD_PARAMS)
        fixture = load_example("cloak.accepted.json")
        fixture["job_id"] = register_job(JobType.cloak)
        return JobAccepted.model_validate(fixture)
    record = job_manager.submit_cloak(image_bytes, request)
    return JobAccepted(job_id=record.job_id, status="queued")
