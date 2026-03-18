"""
test_whitelist.py
-----------------
Unit tests for whitelist validation logic
(via validation_service and via detect_service normalizer)
"""

import pytest
from app.services.validation_service import validate_detect_request
from app.utils.errors import ValidationError


class TestValidateDetectRequest:
    def test_valid_url_no_whitelist(self):
        # Should not raise
        validate_detect_request("https://example.com", None)

    def test_valid_url_with_whitelist(self):
        validate_detect_request("https://example.com", ["1.2.3.4", "5.6.7.8"])

    def test_missing_url_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_detect_request("", None)
        assert exc_info.value.error_code == "MISSING_URL"

    def test_invalid_url_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_detect_request("not-a-url", None)
        assert exc_info.value.error_code == "INVALID_URL"

    def test_ftp_url_raises(self):
        with pytest.raises(ValidationError):
            validate_detect_request("ftp://example.com", None)

    def test_empty_whitelist_entry_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_detect_request("https://example.com", ["1.2.3.4", ""])
        assert exc_info.value.error_code == "INVALID_WHITELIST_ENTRY"

    def test_whitelist_match(self):
        """Whitelist validation logic — correct IPs should not raise."""
        validate_detect_request("https://example.com", ["192.168.1.1"])

    def test_https_with_path_accepted(self):
        validate_detect_request("https://example.com/api/v1/server/get_time", ["1.2.3.4"])
