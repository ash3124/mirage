"""FastAPI entry point for Mirage."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import MOCK_EXAMPLES_DIR, settings
from .errors import ERRORS, ApiError
from .mock_data import load_example
from .routers import certificate, cloak, config, files, health, jobs, sim, watermark
from .schemas import ErrorBody, ErrorCode, ErrorObj

logger = logging.getLogger(__name__)
API_PREFIX = "/api/v1"
ERROR_EXAMPLES = {
    ErrorCode.INVALID_IMAGE: "error.invalid_image.json",
    ErrorCode.TOO_LARGE: "error.too_large.json",
    ErrorCode.BAD_PARAMS: "error.bad_params.json",
    ErrorCode.JOB_NOT_FOUND: "error.job_not_found.json",
    ErrorCode.JOB_EXPIRED: "error.job_expired.json",
    ErrorCode.JOB_NOT_READY: "error.job_not_ready.json",
    ErrorCode.SIM_UNAVAILABLE: "error.sim_unavailable.json",
}

@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if not settings.mock:
        from .services.cloak import load_vae

        load_vae()
        if settings.simulator_enabled:
            from .services.simulate import load_pipeline

            load_pipeline()
    yield


app = FastAPI(title="Mirage API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for route_module in (
    health,
    config,
    cloak,
    jobs,
    sim,
    certificate,
    files,
    watermark,
):
    app.include_router(route_module.router, prefix=API_PREFIX)


def error_response(code: ErrorCode, message: str | None = None) -> JSONResponse:
    error_body = None
    example_name = ERROR_EXAMPLES.get(code)
    if settings.mock and example_name is not None:
        example_path = MOCK_EXAMPLES_DIR / example_name
        if example_path.is_file():
            error_body = ErrorBody.model_validate(load_example(example_name))
            if error_body.error.code != code:
                raise ValueError(
                    f"Mock error example has an incorrect code: {example_name}"
                )
        else:
            logger.warning("MOCK error example is missing: %s", example_path)
    if error_body is None:
        error_body = ErrorBody(
            error=ErrorObj(code=code, message=message or ERRORS[code][1])
        )
    return JSONResponse(
        status_code=ERRORS[code][0],
        content=error_body.model_dump(mode="json"),
    )


@app.exception_handler(ApiError)
async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return error_response(exc.code, exc.safe_message)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _request: Request, _exc: RequestValidationError
) -> JSONResponse:
    return error_response(ErrorCode.BAD_PARAMS)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(
    _request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code_by_status = {
        404: ErrorCode.JOB_NOT_FOUND,
        410: ErrorCode.JOB_EXPIRED,
        413: ErrorCode.TOO_LARGE,
        429: ErrorCode.BUSY,
        501: ErrorCode.NOT_IMPLEMENTED,
        503: ErrorCode.SIM_UNAVAILABLE,
    }
    code = code_by_status.get(exc.status_code, ErrorCode.BAD_PARAMS)
    return error_response(code)


@app.exception_handler(Exception)
async def unexpected_error_handler(
    _request: Request, exc: Exception
) -> JSONResponse:
    logger.exception("Unhandled Mirage API error", exc_info=exc)
    return error_response(ErrorCode.INTERNAL)
