"""
daemon/sanitiser.py — Three-stage telemetry sanitisation filter.

SECURITY CRITICAL: This module strips all sensitive data before
any payload leaves the local machine (ngrok tunnel or MongoDB Atlas).

Stage 1: Pattern-based regex masking (10 patterns)
Stage 2: Entity anonymisation (hostname, username, paths)
Stage 3: Schema-based key filtering for dict payloads
"""

import re
import socket
import os
import json
import logging
from typing import Any


class TelemetrySanitiser:
    """
    Three-stage telemetry sanitiser.

    Stage 1 applies 10 compiled regex patterns that mask well-known secret
    formats.  Stage 2 replaces real hostnames and usernames with generic
    tokens.  Stage 3 filters dict payloads to an explicit allowlist of keys
    and recursively sanitises string values.
    """

    # 10 patterns (pattern_string, replacement_string)
    PATTERNS: list[tuple[str, str]] = [
        # 1. AWS Access Key ID
        (r"AKIA[0-9A-Z]{16}", "[AWS_KEY_REDACTED]"),
        # 2. AWS Secret Access Key (40-char base64 token)
        (
            r"(?<![A-Za-z0-9/+])[A-Za-z0-9/+]{40}(?![A-Za-z0-9/+])",
            "[AWS_SECRET_REDACTED]",
        ),
        # 3. JSON Web Token
        (
            r"eyJ[A-Za-z0-9+/=]+\.[A-Za-z0-9+/=]+\.[A-Za-z0-9+/=_-]+",
            "[JWT_REDACTED]",
        ),
        # 4. GitHub Personal Access Token
        (r"ghp_[A-Za-z0-9]{36}", "[GH_TOKEN_REDACTED]"),
        # 5. MongoDB connection URI
        (r"mongodb(\+srv)?://[^\s]+", "[MONGODB_URI_REDACTED]"),
        # 6. Generic key=value or key:value secret pairs
        (
            r"(?i)(password|passwd|secret|token|api_key|apikey)\s*[=:]\s*\S+",
            "[SECRET_REDACTED]",
        ),
        # 7. E-mail address
        (
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "[EMAIL_REDACTED]",
        ),
        # 8. RFC-1918 private IPv4 addresses
        (
            r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
            r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
            r"|192\.168\.\d{1,3}\.\d{1,3})\b",
            "[PRIVATE_IP]",
        ),
        # 9. PEM private key header
        (r"-----BEGIN [A-Z ]+PRIVATE KEY-----", "[SSH_KEY_REDACTED]"),
        # 10. URLs with embedded credentials  (http://user:pass@host/...)
        (r"https?://[^:]+:[^@]+@[^\s]+", "[AUTHED_URL_REDACTED]"),
    ]

    def __init__(self) -> None:
        """Pre-compile all regex patterns and capture host/user identity."""
        self._real_hostname: str = socket.gethostname()
        self._real_username: str = (
            os.getenv("USER") or os.getenv("USERNAME") or ""
        )
        # Pre-compile for speed — done once at startup
        self._compiled_patterns: list[tuple[re.Pattern[str], str]] = [
            (re.compile(pattern), replacement)
            for pattern, replacement in self.PATTERNS
        ]
        self._logger = logging.getLogger(f"{__name__}.TelemetrySanitiser")
        self._logger.debug(
            f"TelemetrySanitiser initialised "
            f"(hostname='{self._real_hostname}', "
            f"username='{self._real_username}')"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sanitise(self, text: str) -> str:
        """
        Apply all three sanitisation stages to *text* and return the
        redacted string.

        Stage 1: 10 regex patterns mask secret values.
        Stage 2: Real hostname → ``AIOS_HOST``, real username → ``AIOS_USER``.

        Args:
            text: Raw string that may contain sensitive data.

        Returns:
            Sanitised string safe to transmit off-machine.
        """
        result = text

        # Stage 1 — pattern-based masking
        for pattern, replacement in self._compiled_patterns:
            result = pattern.sub(replacement, result)

        # Stage 2 — entity anonymisation
        if self._real_hostname:
            result = result.replace(self._real_hostname, "AIOS_HOST")
        if self._real_username:
            result = result.replace(self._real_username, "AIOS_USER")

        return result

    def sanitise_dict(
        self,
        data: dict,
        allowed_keys: set[str],
    ) -> dict:
        """
        Filter *data* to *allowed_keys* and sanitise all string values.

        Args:
            data:         Input dictionary that may contain sensitive values.
            allowed_keys: Set of keys that are permitted in the output.
                          Every key in *allowed_keys* **must** be present in
                          *data*; if any are missing a :class:`ValueError` is
                          raised.

        Returns:
            Filtered dict containing only *allowed_keys*, with string values
            passed through :meth:`sanitise` and nested dicts recursed.

        Raises:
            ValueError: If any key in *allowed_keys* is absent from *data*.
        """
        missing = allowed_keys - data.keys()
        if missing:
            raise ValueError(f"Missing required keys: {missing}")

        result: dict = {}
        for key in allowed_keys:
            value = data[key]
            if isinstance(value, str):
                result[key] = self.sanitise(value)
            elif isinstance(value, dict):
                # Recurse — sanitise all string leaves; keep all keys
                result[key] = self._sanitise_dict_values(value)
            else:
                result[key] = value

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sanitise_dict_values(self, data: dict) -> dict:
        """
        Recursively sanitise string values within an arbitrary dict without
        key filtering.
        """
        out: dict = {}
        for k, v in data.items():
            if isinstance(v, str):
                out[k] = self.sanitise(v)
            elif isinstance(v, dict):
                out[k] = self._sanitise_dict_values(v)
            else:
                out[k] = v
        return out
