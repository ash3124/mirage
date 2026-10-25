"""Contract-standard API errors."""

from __future__ import annotations

from dataclasses import dataclass

from .schemas import ErrorCode


ERRORS: dict[ErrorCode, tuple[int, str]] = {
    ErrorCode.INVALID_IMAGE: (
        400,
        "That file does not look like a photo we can read.",
    ),
    ErrorCode.TOO_LARGE: (413, "That file is larger than the 10 MB limit."),
    ErrorCode.BAD_PARAMS: (422, "One or more request fields are invalid."),
    ErrorCode.JOB_NOT_FOUND: (404, "That job or file could not be found."),
    ErrorCode.JOB_EXPIRED: (410, "That job or file has expired."),
    ErrorCode.JOB_NOT_READY: (409, "That job is not finished yet."),
    ErrorCode.BUSY: (429, "The server is busy. Please try again shortly."),
    ErrorCode.SIM_UNAVAILABLE: (503, "The simulator is unavailable on this server."),
    ErrorCode.SIM_BLOCKED: (422, "The edit was blocked by the AI safety filter."),
    ErrorCode.NOT_IMPLEMENTED: (501, "This feature is turned off."),
    ErrorCode.INTERNAL: (
        500,
        "Something went wrong while processing your request.",
    ),
}


@dataclass
class ApiError(Exception):
    code: ErrorCode
    message: str | None = None

    @property
    def status_code(self) -> int:
        return ERRORS[self.code][0]

    @property
    def safe_message(self) -> str:
        return self.message or ERRORS[self.code][1]
