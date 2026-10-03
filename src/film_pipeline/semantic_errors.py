"""Sanitized semantic-API error observability (Package-011 S1).

The historical adapter mapped EVERY external failure to the umbrella
`SEMANTIC_API_UNAVAILABLE`. This module preserves that umbrella string for
backward-compatible fail-closed handling while attaching a PRECISE,
evidence-based internal classification and the raw sanitized provider
classification. No error is forced into a class without evidence.

Never persisted: API keys, Authorization headers, cookies, signed URLs,
request bodies. Details are truncated and token-redacted.
"""
from __future__ import annotations

import json
import re

SEMANTIC_RATE_OR_QUOTA_LIMIT = "SEMANTIC_RATE_OR_QUOTA_LIMIT"
SEMANTIC_AUTH_FAILURE = "SEMANTIC_AUTH_FAILURE"
SEMANTIC_PERMISSION_DENIED = "SEMANTIC_PERMISSION_DENIED"
SEMANTIC_MODEL_UNAVAILABLE = "SEMANTIC_MODEL_UNAVAILABLE"
SEMANTIC_SERVICE_UNAVAILABLE = "SEMANTIC_SERVICE_UNAVAILABLE"
SEMANTIC_RESPONSE_MALFORMED = "SEMANTIC_RESPONSE_MALFORMED"
SEMANTIC_LINEAGE_FAILURE = "SEMANTIC_LINEAGE_FAILURE"
SEMANTIC_UNKNOWN_EXTERNAL_ERROR = "SEMANTIC_UNKNOWN_EXTERNAL_ERROR"
INTERNAL_CLASSES = (
    SEMANTIC_RATE_OR_QUOTA_LIMIT, SEMANTIC_AUTH_FAILURE,
    SEMANTIC_PERMISSION_DENIED, SEMANTIC_MODEL_UNAVAILABLE,
    SEMANTIC_SERVICE_UNAVAILABLE, SEMANTIC_RESPONSE_MALFORMED,
    SEMANTIC_LINEAGE_FAILURE, SEMANTIC_UNKNOWN_EXTERNAL_ERROR)

UMBRELLA = "SEMANTIC_API_UNAVAILABLE"
MAX_DETAIL = 240


def sanitize_detail(text: str) -> str:
    """Truncate and redact key-shaped material from any provider detail."""
    if not isinstance(text, str):
        text = str(text)
    redacted = re.sub(r"A[Iy]za[0-9A-Za-z_\-]{10,}", "<redacted-key>", text)
    redacted = re.sub(r"sk-[A-Za-z0-9_\-]{6,}", "<redacted-key>", redacted)
    redacted = re.sub(r"(?i)(authorization|api[_-]?key|x-goog-api-key)"
                      r"(\s*[:=]\s*)\S+", r"\1\2<redacted>", redacted)
    redacted = re.sub(r"[0-9A-Za-z_\-]{32,}", "<redacted-token>", redacted)
    return redacted.replace("\n", " ")[:MAX_DETAIL]


class SemanticExternalError(RuntimeError):
    """Fail-closed external semantic failure with sanitized classification.

    The message keeps the historical SEMANTIC_API_UNAVAILABLE umbrella so
    existing fail-closed handlers keep working; the precise class lives in
    ``internal_class`` and the raw sanitized provider classification in
    ``provider_class``.
    """

    def __init__(self, internal_class: str, provider_class: str,
                 *, http_status: int | None = None,
                 retry_after: str | None = None, detail: str = ""):
        if internal_class not in INTERNAL_CLASSES:
            raise ValueError("unknown semantic error class")
        self.internal_class = internal_class
        self.provider_class = sanitize_detail(provider_class)
        self.http_status = http_status
        self.retry_after = (retry_after or None) if \
            isinstance(retry_after, str) else None
        self.detail = sanitize_detail(detail)
        parts = [UMBRELLA, internal_class, f"provider={self.provider_class}"]
        if http_status is not None:
            parts.append(f"http={http_status}")
        if self.retry_after:
            parts.append(f"retry_after={self.retry_after}")
        if self.detail:
            parts.append(f"detail={self.detail}")
        super().__init__(" | ".join(parts))


def _provider_error_fields(body_text: str) -> tuple[str, str]:
    """Extract (provider_class, message) from a Google error body."""
    try:
        payload = json.loads(body_text)
        error = payload.get("error") or {}
        status = str(error.get("status") or "")
        message = str(error.get("message") or "")
        return status, message
    except (json.JSONDecodeError, AttributeError, TypeError):
        return "", sanitize_detail(body_text[:MAX_DETAIL])


def classify_http_failure(status: int, body_text: str,
                          retry_after: str | None = None
                          ) -> SemanticExternalError:
    """Map one HTTP failure to its evidence-based internal class."""
    provider_class, message = _provider_error_fields(body_text)
    combined = f"{provider_class} {message}".upper()
    if status == 429:
        marker = "RESOURCE_EXHAUSTED" in combined or \
            "QUOTA" in combined or "RATE" in combined
        cls = SEMANTIC_RATE_OR_QUOTA_LIMIT
        provider_class = (provider_class or
                          ("RESOURCE_EXHAUSTED" if marker else "THROTTLED"))
        return SemanticExternalError(
            cls, provider_class or "THROTTLED", http_status=status,
            retry_after=retry_after, detail=message)
    if status == 401:
        return SemanticExternalError(
            SEMANTIC_AUTH_FAILURE, provider_class or "UNAUTHENTICATED",
            http_status=status, detail=message)
    if status == 403:
        return SemanticExternalError(
            SEMANTIC_PERMISSION_DENIED, provider_class or "PERMISSION_DENIED",
            http_status=status, detail=message)
    if status == 404 and ("MODEL" in combined or "models/" in message):
        return SemanticExternalError(
            SEMANTIC_MODEL_UNAVAILABLE, provider_class or "NOT_FOUND",
            http_status=status, detail=message)
    if status in (408, 504) or "TIMEOUT" in combined or "DEADLINE" in combined:
        return SemanticExternalError(
            SEMANTIC_SERVICE_UNAVAILABLE, provider_class or "TIMEOUT",
            http_status=status, retry_after=retry_after, detail=message)
    if 500 <= status < 600:
        return SemanticExternalError(
            SEMANTIC_SERVICE_UNAVAILABLE, provider_class or "INTERNAL",
            http_status=status, detail=message)
    if 400 <= status < 500:
        # Known request rejection with an evidence-free provider class.
        return SemanticExternalError(
            SEMANTIC_UNKNOWN_EXTERNAL_ERROR, provider_class or f"HTTP_{status}",
            http_status=status, detail=message)
    return SemanticExternalError(
        SEMANTIC_UNKNOWN_EXTERNAL_ERROR, provider_class or f"HTTP_{status}",
        http_status=status, detail=message)


def classify_transport_exception(exc: Exception) -> SemanticExternalError:
    """Map a transport-level exception (no HTTP status available)."""
    reason = str(getattr(exc, "reason", "") or exc)
    if "timed out" in reason.lower() or "timeout" in reason.lower():
        return SemanticExternalError(
            SEMANTIC_SERVICE_UNAVAILABLE, "TRANSPORT_TIMEOUT", detail=reason)
    return SemanticExternalError(
        SEMANTIC_UNKNOWN_EXTERNAL_ERROR, "TRANSPORT_FAILURE", detail=reason)
