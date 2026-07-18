"""Standard API error handling."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .schemas import ErrorDetail, ErrorResponse


@dataclass(frozen=True)
class ApiError(Exception):
    """Exception raised for contract-level API errors."""

    code: str
    message: str
    status_code: int
    retryable: bool = False

    def to_payload(self) -> ErrorResponse:
        return ErrorResponse(
            error=ErrorDetail(
                code=self.code,
                message=self.message,
                retryable=self.retryable,
            )
        )


async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    payload = exc.to_payload()
    return JSONResponse(
        status_code=exc.status_code,
        content=payload.model_dump(mode="json"),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, api_error_handler)

