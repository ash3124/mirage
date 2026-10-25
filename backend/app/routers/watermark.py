from fastapi import APIRouter, File, UploadFile

from ..config import settings
from ..errors import ApiError
from ..mock_data import load_example
from ..schemas import AppConfig, ErrorCode, WatermarkVerifyResponse

router = APIRouter()


@router.post("/watermark/verify", response_model=WatermarkVerifyResponse)
async def verify_watermark(image: UploadFile = File(...)) -> WatermarkVerifyResponse:
    if settings.mock:
        config = AppConfig.model_validate(load_example("config.ok.json"))
        if not config.features.watermark:
            raise ApiError(ErrorCode.NOT_IMPLEMENTED)
        fixture = load_example("watermark.verify.found.json")
        return WatermarkVerifyResponse.model_validate(fixture)
    raise ApiError(ErrorCode.NOT_IMPLEMENTED)
