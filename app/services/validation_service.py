"""
validation_service.py
---------------------
Input validation — Step 3

Validates the incoming DetectRequest before any Boce call is made.
FastAPI + Pydantic already cover most cases but we add extra rules here.
"""

from __future__ import annotations

import re
from typing import List, Optional

from app.utils.errors import ValidationError


# Basic URL pattern (Pydantic HttpUrl already validates, but this is used
# for any additional checks or standalone unit tests)
_URL_RE = re.compile(
    r"^https?://"              # must start with http or https
    r"[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+"  # allowed URL chars
    r"$",
    re.IGNORECASE,
)

# Simple IPv4 pattern
_IPV4_RE = re.compile(
    r"^\d{1,3}(\.\d{1,3}){3}$"
)


def validate_detect_request(url: str, ip_whitelist: Optional[List[str]]) -> None:
    """
    Validate the detect endpoint inputs.
    Raises ValidationError with a human-readable message on failure.
    """
    _validate_url(url)
    if ip_whitelist is not None:
        _validate_whitelist(ip_whitelist)


def _validate_url(url: str) -> None:
    url = str(url)  # Ensure AnyHttpUrl objects are converted to strings
    if not url or not url.strip():
        raise ValidationError("'url' field is required.", "MISSING_URL")
    if not _URL_RE.match(url.strip()):
        raise ValidationError(
            f"'{url}' is not a valid HTTP/HTTPS URL.",
            "INVALID_URL",
        )


def _validate_whitelist(ip_whitelist: List[str]) -> None:
    if not isinstance(ip_whitelist, list):
        raise ValidationError(
            "'ip_whitelist' must be an array of IP address strings.",
            "INVALID_WHITELIST_FORMAT",
        )
    for ip in ip_whitelist:
        if not isinstance(ip, str) or not ip.strip():
            raise ValidationError(
                f"Each entry in 'ip_whitelist' must be a non-empty string. Got: {ip!r}",
                "INVALID_WHITELIST_ENTRY",
            )
