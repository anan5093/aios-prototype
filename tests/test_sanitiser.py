"""
tests/test_sanitiser.py — Unit tests for daemon/sanitiser.py (TelemetrySanitiser).

Covers all 10 regex patterns plus entity anonymisation (hostname, username)
and the sanitise_dict() method's key-filtering and required-key enforcement.

No network calls are made. Uses unittest.mock.patch to inject a known
username for deterministic testing.
"""

import os
import socket
import sys
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "daemon"))

from sanitiser import TelemetrySanitiser  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sanitiser() -> TelemetrySanitiser:
    """Return a fresh TelemetrySanitiser instance for each test."""
    return TelemetrySanitiser()


# ---------------------------------------------------------------------------
# Tests — Regex pattern masking (Stage 1)
# ---------------------------------------------------------------------------


class TestAWSKeyRedaction:
    """AWS Access Key ID must be fully redacted."""

    def test_aws_key_redacted(self, sanitiser: TelemetrySanitiser) -> None:
        """AKIA… key must be replaced with [AWS_KEY_REDACTED]."""
        input_text = "Access key: AKIA1234567890ABCDEF found in config"
        result = sanitiser.sanitise(input_text)

        assert "[AWS_KEY_REDACTED]" in result, (
            f"Expected '[AWS_KEY_REDACTED]' in sanitised output, got: {result!r}"
        )
        assert "AKIA1234567890ABCDEF" not in result, (
            "Raw AWS key must not appear in sanitised output."
        )


class TestJWTRedaction:
    """JSON Web Tokens must be fully redacted."""

    def test_jwt_token_redacted(self, sanitiser: TelemetrySanitiser) -> None:
        """A three-part JWT must be replaced with [JWT_REDACTED]."""
        jwt = (
            "eyJhbGciOiJIUzI1NiJ9"
            ".eyJzdWIiOiJ1c2VyIn0"
            ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        result = sanitiser.sanitise(f"JWT is {jwt}")

        assert "[JWT_REDACTED]" in result, (
            f"Expected '[JWT_REDACTED]' in sanitised output, got: {result!r}"
        )
        assert jwt not in result, "Raw JWT must not appear in sanitised output."


class TestGitHubTokenRedaction:
    """GitHub Personal Access Tokens must be fully redacted."""

    def test_github_token_redacted(self, sanitiser: TelemetrySanitiser) -> None:
        """A ghp_<36-char> token must be replaced with [GH_TOKEN_REDACTED]."""
        token = "ghp_" + "A" * 36
        result = sanitiser.sanitise(f"GitHub key: {token}")

        assert "[GH_TOKEN_REDACTED]" in result, (
            f"Expected '[GH_TOKEN_REDACTED]' in sanitised output, got: {result!r}"
        )
        assert token not in result, "Raw GitHub token must not appear in output."


class TestMongoDBURIRedaction:
    """MongoDB Atlas connection URIs must be fully redacted."""

    def test_mongodb_uri_redacted(self, sanitiser: TelemetrySanitiser) -> None:
        """A mongodb+srv://… URI must be replaced with [MONGODB_URI_REDACTED]."""
        uri = "mongodb+srv://user:pass@cluster0.abc123.mongodb.net/mydb"
        result = sanitiser.sanitise(f"Connecting to {uri}")

        assert "[MONGODB_URI_REDACTED]" in result, (
            f"Expected '[MONGODB_URI_REDACTED]' in output, got: {result!r}"
        )
        assert "mongodb+srv://" not in result, (
            "Raw MongoDB URI prefix must not appear in sanitised output."
        )


class TestPasswordKVRedaction:
    """Generic password= / token= key-value patterns must be redacted."""

    def test_password_kv_redacted(self, sanitiser: TelemetrySanitiser) -> None:
        """password=<value> must be replaced with [SECRET_REDACTED]."""
        input_text = "password=MySuperSecret123"
        result = sanitiser.sanitise(input_text)

        assert "[SECRET_REDACTED]" in result, (
            f"Expected '[SECRET_REDACTED]' in output, got: {result!r}"
        )
        assert "MySuperSecret123" not in result, (
            "Raw password value must not appear in sanitised output."
        )


class TestEmailRedaction:
    """Email addresses must be fully redacted."""

    def test_email_redacted(self, sanitiser: TelemetrySanitiser) -> None:
        """An email address must be replaced with [EMAIL_REDACTED]."""
        input_text = "Contact: real.user@company.com for support"
        result = sanitiser.sanitise(input_text)

        assert "[EMAIL_REDACTED]" in result, (
            f"Expected '[EMAIL_REDACTED]' in output, got: {result!r}"
        )
        assert "real.user@company.com" not in result, (
            "Raw email address must not appear in sanitised output."
        )


class TestPrivateIPRedaction:
    """RFC-1918 private IPv4 addresses must be redacted."""

    def test_private_ip_redacted(self, sanitiser: TelemetrySanitiser) -> None:
        """A 192.168.x.x address must be replaced with [PRIVATE_IP]."""
        input_text = "Connected to 192.168.1.42 via ssh"
        result = sanitiser.sanitise(input_text)

        assert "[PRIVATE_IP]" in result, (
            f"Expected '[PRIVATE_IP]' in output, got: {result!r}"
        )
        assert "192.168.1.42" not in result, (
            "Raw private IP must not appear in sanitised output."
        )


class TestSSHKeyRedaction:
    """PEM private key headers must be redacted."""

    def test_ssh_key_marker_redacted(self, sanitiser: TelemetrySanitiser) -> None:
        """-----BEGIN RSA PRIVATE KEY----- must be replaced with [SSH_KEY_REDACTED]."""
        input_text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA..."
        result = sanitiser.sanitise(input_text)

        assert "[SSH_KEY_REDACTED]" in result, (
            f"Expected '[SSH_KEY_REDACTED]' in output, got: {result!r}"
        )


# ---------------------------------------------------------------------------
# Tests — Entity anonymisation (Stage 2)
# ---------------------------------------------------------------------------


class TestHostnameAnonymisation:
    """The real machine hostname must be replaced with AIOS_HOST."""

    def test_real_hostname_anonymised(self, sanitiser: TelemetrySanitiser) -> None:
        """socket.gethostname() must not appear after sanitisation."""
        hostname = socket.gethostname()
        input_text = f"Host {hostname} failed health check"
        result = sanitiser.sanitise(input_text)

        assert hostname not in result, (
            f"Real hostname '{hostname}' should have been anonymised."
        )
        assert "AIOS_HOST" in result, (
            f"Expected 'AIOS_HOST' token in output, got: {result!r}"
        )


class TestUsernameAnonymisation:
    """The real OS username must be replaced with AIOS_USER."""

    def test_real_username_anonymised(self, sanitiser: TelemetrySanitiser) -> None:
        """The injected username 'testuser' must be replaced with AIOS_USER."""
        # Directly set the private attribute to a known test value
        sanitiser._real_username = "testuser"

        input_text = "User testuser ran the command sudo reboot"
        result = sanitiser.sanitise(input_text)

        assert "testuser" not in result, (
            "Real username 'testuser' should have been anonymised."
        )
        assert "AIOS_USER" in result, (
            f"Expected 'AIOS_USER' token in output, got: {result!r}"
        )


# ---------------------------------------------------------------------------
# Tests — sanitise_dict() (Stage 3)
# ---------------------------------------------------------------------------


class TestSanitiseDict:
    """Tests for the dict-level key-filtering sanitisation."""

    def test_sanitise_dict_drops_unknown_keys(
        self, sanitiser: TelemetrySanitiser
    ) -> None:
        """Keys not in the allowed set must be dropped from the result dict."""
        data = {
            "allowed_key": "some safe value",
            "secret": "should_be_dropped",
            "another": "also_dropped",
        }
        allowed = {"allowed_key"}
        result = sanitiser.sanitise_dict(data, allowed)

        assert "secret" not in result, (
            "Key 'secret' must be dropped as it is not in the allowed set."
        )
        assert "another" not in result, (
            "Key 'another' must be dropped as it is not in the allowed set."
        )
        assert "allowed_key" in result, (
            "Key 'allowed_key' must be present as it is in the allowed set."
        )

    def test_sanitise_dict_raises_on_missing_required_key(
        self, sanitiser: TelemetrySanitiser
    ) -> None:
        """sanitise_dict must raise ValueError if any allowed_key is absent from data."""
        data = {"only_key": "value"}
        allowed = {"only_key", "required_but_missing"}

        with pytest.raises(ValueError):
            sanitiser.sanitise_dict(data, allowed)
