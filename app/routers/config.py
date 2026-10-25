from fastapi import APIRouter

from ..config import app_config, settings
from ..mock_data import load_example
from ..schemas import AppConfig

router = APIRouter()


@router.get("/config", response_model=AppConfig)
def get_config() -> AppConfig:
    if settings.mock:
        return AppConfig.model_validate(load_example("config.ok.json"))
    return app_config()
