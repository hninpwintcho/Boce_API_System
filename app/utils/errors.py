"""
errors.py
---------
Custom exception classes and error response helpers — Step 6

Three tiers:
  400  ValidationError       — bad input from the caller
  502  BoceInvalidResponseError — upstream gave garbage
  503  BoceUnavailableError  — upstream is down
  504  BoceTimeoutError      — upstream timed out
  500  InternalError         — unexpected server-side bug
"""

from __future__ import annotations


class AppBaseError(Exception):
    """Base for all application errors."""

    http_status: int = 500
    default_error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, error_code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.default_error_code


class ValidationError(AppBaseError):
    """Raised when the caller sends invalid input."""

    http_status = 400
    default_error_code = "VALIDATION_ERROR"


class BoceTimeoutError(AppBaseError):
    """Raised when Boce API does not respond within the configured timeout."""

    http_status = 504
    default_error_code = "BOCE_TIMEOUT"


class BoceUnavailableError(AppBaseError):
    """Raised when Boce API returns a server error or is unreachable."""

    http_status = 503
    default_error_code = "BOCE_UNAVAILABLE"


class BoceInvalidResponseError(AppBaseError):
    """Raised when Boce API returns a response that cannot be parsed."""

    http_status = 502
    default_error_code = "BOCE_INVALID_RESPONSE"


class InternalError(AppBaseError):
    """Unexpected server-side error."""

    http_status = 500
    default_error_code = "INTERNAL_ERROR"
