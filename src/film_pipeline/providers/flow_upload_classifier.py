"""Structural classification of maseQ upload responses (Package-008 U2).

Frozen contract, offline-proven BEFORE any live qualification canary:

- QUALIFIED_COMPLETED — HTTP 200 + strict batchexecute parse + the direct
  identity envelope accepted by the existing transport (``payload[0][0]`` is
  a provider media UUID, no conflicting sibling identities).
- QUALIFIED_PENDING — HTTP 200 + strict parse + payload is a JSON list that
  claims NO media identity anywhere (no UUID string inside the payload).
  This is the historical response class observed on ALL four AI-Film maseQ
  uploads (2026-09-30 slice0011 qualification 647 B; 2026-10-02 Scene-003
  651 B; 2026-10-03 Package-007 F2 651 B and G2 651 B), each of which later
  resolved to exactly one catalog media with exact content readback. The
  classification authorizes ONLY bounded read-only reconciliation — never a
  second upload, never any other mutation.
- UNOBSERVABLE — the response was never observed after dispatch.
- TRUE_AMBIGUOUS — everything else (unparseable frames, non-200, non-list
  payloads, identity echoes, conflicting identities, unknown shapes).
  Fail-closed: it must NEVER become qualified pending merely because
  parsing failed.

This module is pure: no browser, no network, no secrets. Skeletons record
structure only — types, uuid-ness, list lengths, dict key names. String
values, string lengths, URLs and numeric values never enter a skeleton.
"""
from __future__ import annotations

from ..core import canonical_json, sha256
from .flow_reference_upload import OwnerAmbiguityGate
from .flow_rpc_contract import MAX_JSON_DEPTH, UUID_RE, _new_uuid

QUALIFIED_COMPLETED = "QUALIFIED_COMPLETED"
QUALIFIED_PENDING = "QUALIFIED_PENDING"
TRUE_AMBIGUOUS = "TRUE_AMBIGUOUS"
TRANSPORT_NO_EFFECT_PROVEN = "TRANSPORT_NO_EFFECT_PROVEN"
UNOBSERVABLE = "UNOBSERVABLE"
CLASSIFICATIONS = (QUALIFIED_COMPLETED, QUALIFIED_PENDING, TRUE_AMBIGUOUS,
                   TRANSPORT_NO_EFFECT_PROVEN, UNOBSERVABLE)

# The pre-registered qualified-pending envelope, CORRECTED at U4 (Canary 1):
# the initially derived "no UUID anywhere" predicate mis-predicted the real
# maseQ response class and fail-closed (latched) on live observation. The
# live response skeleton — HTTP 200, two sibling records, UUID-bearing
# primary slots, no adoptable identity — is now frozen as the ONLY
# qualified-pending class, by exact structural fingerprint. Values never
# enter the skeleton, so the fingerprint is stable across uploads of the
# same class. Any structural drift stays fail-closed TRUE_AMBIGUOUS.
HISTORICAL_PENDING_RESPONSE_CLASS = "maseQ-200-live-skeleton"
LIVE_PENDING_SKELETON_FINGERPRINT = (
    "ae90da3e8da5f4330d774bce43dc8c6e995f948d3f904149cf5857152373b9a1")
RESPONSE_CLASS_VERSION = "upload-response-class-2026-10-03.2"


class UploadResponseClassified(RuntimeError):
    """Typed upload response outcome carrying its sanitized classification."""

    def __init__(self, classification: str, reason: str, skeleton,
                 fingerprint: str):
        if classification not in CLASSIFICATIONS:
            raise ValueError("unknown upload response classification")
        self.classification = classification
        self.reason = reason
        self.skeleton = skeleton
        self.fingerprint = fingerprint
        super().__init__(
            f"{classification} ({reason}; skeleton {fingerprint[:12]}…)")


class QualifiedUploadPending(UploadResponseClassified):
    """The response matched the qualified pending class.

    NOT an OwnerAmbiguityGate: no ambiguity gate is raised. The scope
    enters SUSPENDED_QUALIFIED_UPLOAD_PENDING; only bounded read-only
    reconciliation is authorized until unique binding (UPLOAD_BOUND).
    """


class UploadResponseAmbiguous(UploadResponseClassified, OwnerAmbiguityGate):
    """The response is TRUE_AMBIGUOUS/UNOBSERVABLE.

    Subclasses OwnerAmbiguityGate so every existing fail-closed handler
    keeps its exact historical behavior (durable FAILED_AMBIGUOUS + latch).
    """


def _skeleton(value, depth=0):
    """Deterministic, value-free structural skeleton of a decoded payload."""
    if depth > MAX_JSON_DEPTH:
        return "depth_exceeded"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "uuid" if UUID_RE.fullmatch(value) else "str"
    if isinstance(value, list):
        children = [_skeleton(item, depth + 1) for item in value[:16]]
        if len(value) > 16:
            children.append({"truncated_more": len(value) - 16})
        return {"list": children}
    if isinstance(value, dict):
        return {"dict": {key: _skeleton(value[key], depth + 1)
                         for key in sorted(value)}}
    return "unrepresentable"


def skeleton_fingerprint(skeleton) -> str:
    return sha256(canonical_json(skeleton))


def _contains_uuid(value) -> bool:
    if isinstance(value, str):
        return bool(UUID_RE.fullmatch(value))
    if isinstance(value, list):
        return any(_contains_uuid(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_uuid(item) for item in value.values())
    return False


def linked_upload_asset_header(node, media, project_id):
    """Recognize only the bidirectionally linked library header seen 2026-11-04."""
    return (isinstance(media, list) and len(media) == 7
            and isinstance(node, list) and len(node) == 5
            and node[1:3] == [None, None] and node[4] == project_id
            and media[1] == project_id and node[0] == media[2]
            and isinstance(node[0], str) and UUID_RE.fullmatch(node[0]) is not None
            and isinstance(node[3], list) and len(node[3]) in {5, 7}
            and node[3][4] == media[0])


def classify_upload_response(status, payload, *, project_id: str,
                             request_id: str) -> UploadResponseClassified:
    """Classify one observed maseQ response. Deterministic; fail-closed.

    ``status`` may be None when no HTTP response was observed in-process
    (e.g. transport death after dispatch): then QUALIFIED_PENDING is never
    granted — the class requires a durably observed HTTP 200."""
    skeleton = _skeleton(payload)
    fingerprint = skeleton_fingerprint(skeleton)
    if status is not None and status != 200:
        return UploadResponseAmbiguous(
            TRUE_AMBIGUOUS, "http_status_not_qualified", skeleton, fingerprint)
    if not isinstance(payload, list) or not payload:
        return UploadResponseAmbiguous(
            TRUE_AMBIGUOUS, "payload_shape_unqualified", skeleton, fingerprint)
    # The ONLY qualified-pending class: exact structural match to the live
    # frozen fingerprint (U4). Nothing else — not a parse failure, not a
    # degenerate shape, not "HTTP 200" — may become qualified pending.
    if status == 200 and fingerprint == LIVE_PENDING_SKELETON_FINGERPRINT:
        return QualifiedUploadPending(
            QUALIFIED_PENDING, HISTORICAL_PENDING_RESPONSE_CLASS,
            skeleton, fingerprint)
    primary = payload[0][0] if isinstance(payload[0], list) and payload[0] \
        else None
    metadata_ids = {str(project_id).lower(), str(request_id).lower(),
                    str(_new_uuid(request_id, "upload-client")).lower(),
                    str(_new_uuid(request_id, "upload-session")).lower()}
    if isinstance(primary, str) and UUID_RE.fullmatch(primary):
        if primary.lower() in metadata_ids:
            return UploadResponseAmbiguous(
                TRUE_AMBIGUOUS, "primary_identity_is_correlation_metadata",
                skeleton, fingerprint)
        conflicting = [
            node[0] for node in payload[1:]
            if isinstance(node, list) and node
            and not linked_upload_asset_header(node, payload[0], project_id)
            and isinstance(node[0], str) and UUID_RE.fullmatch(node[0])
            and node[0].lower() not in metadata_ids
            and node[0].lower() != primary.lower()]
        if conflicting:
            return UploadResponseAmbiguous(
                TRUE_AMBIGUOUS, "conflicting_primary_identities",
                skeleton, fingerprint)
        return UploadResponseClassified(
            QUALIFIED_COMPLETED, "direct_media_identity", skeleton,
            fingerprint)
    if _contains_uuid(payload):
        return UploadResponseAmbiguous(
            TRUE_AMBIGUOUS, "unrecognized_identity_inside_payload",
            skeleton, fingerprint)
    return UploadResponseAmbiguous(
        TRUE_AMBIGUOUS, "no_qualified_pending_class_matched", skeleton,
        fingerprint)


def classify_parse_failure() -> UploadResponseClassified:
    """Strict parse did not yield a qualified maseQ frame: fail closed."""
    return UploadResponseAmbiguous(
        TRUE_AMBIGUOUS, "response_frames_unparseable", None,
        skeleton_fingerprint(None))


def classify_unobservable() -> UploadResponseClassified:
    """Dispatched but no response bytes were ever observed."""
    return UploadResponseAmbiguous(
        UNOBSERVABLE, "no_response_observed", None,
        skeleton_fingerprint(None))


def pending_fingerprint_matches(expected: str, observed: str) -> bool:
    """Qualification guard between independent canaries: a later live
    pending response must reproduce the fingerprint frozen by the first
    canary exactly; any drift is response-shape drift (requalification
    trigger), never silently accepted."""
    return isinstance(expected, str) and isinstance(observed, str) \
        and len(expected) == 64 and len(observed) == 64 \
        and expected == observed
