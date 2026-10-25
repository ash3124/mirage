from fastapi import APIRouter

from ..config import settings
from ..jobs import job_manager
from ..mock_data import load_example
from ..schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    if settings.mock:
        return HealthResponse.model_validate(load_example("health.ok.json"))
    return HealthResponse(
        status="ok",
        version="1.0.0",
        mode=settings.mode,
        queue_depth=job_manager.queue_depth,
        simulator_enabled=settings.simulator_enabled,
    )
