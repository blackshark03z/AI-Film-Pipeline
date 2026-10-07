"""V2-019 Phase H — DolaAssetVariantResolver.

Resolves provider-issued asset variants for a creation:
    creation.video.video_model (JSON string) -> video_list -> renditions
    -> base64-decoded main_url/backup_url_* (provider-encoded; decoding is
    reading, not construction) -> lr classification.

Selection policy (Owner-authorized, V2-011X precedent):
    PREFER_UNWATERMARKED -> the provider-issued lr=unwatermarked sibling of
    the SAME creation (class B PROVIDER_ISSUED_UNWATERMARKED).
No URL construction, no lr mutation, no CDN guessing, no host outside the
allowlist. Ambiguity fails closed.
"""
from __future__ import annotations

from typing import Any, Literal
from urllib.parse import parse_qsl, urlparse

from pydantic import Field

from ...core import ContractModel
from .observability import decode_media_url, deep_json_strings, redact_url

VariantAuthority = Literal[
    "PROVIDER_ISSUED_UNWATERMARKED",
    "PROVIDER_ISSUED_WATERMARKED",
    "NOT_FOUND",
]

_ALLOWED_HOST_SUFFIXES = (
    "dola.com", "byteimg.com", "ibyteimg.com", "volces.com",
    "bytepluses.com", "byteplus.com", "ibytedtos.com", "bytecdn.cn",
    "byteintlapi.com", "ttwstatic.com",
)


def _host_allowed(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == s or host.endswith("." + s)
               for s in _ALLOWED_HOST_SUFFIXES)


class VideoVariant(ContractModel):
    list_key: str
    definition: str | None = None
    quality: str | None = None
    bitrate: int | None = None
    width: int | None = None
    height: int | None = None
    variant_lr: str | None = None
    url_host: str | None = None
    main_url_redacted: dict | str = Field(default_factory=dict)
    field: str = "main_url"


class VariantSelection(ContractModel):
    authority: VariantAuthority
    variant: VideoVariant | None = None
    candidates_considered: int = 0
    reason: str = ""


def extract_renditions(creation: dict) -> list[dict]:
    """Every rendition dict visible on a creation object, via the deep
    JSON-string walker (video.video_model is a JSON string)."""
    video = creation.get("video") if isinstance(creation.get("video"),
                                                dict) else {}
    renditions: list[dict] = []
    seen: set[int] = set()
    for obj in [video, *deep_json_strings(video)]:
        video_list = obj.get("video_list") if isinstance(obj, dict) else None
        if not isinstance(video_list, dict):
            continue
        for name, rendition in video_list.items():
            if isinstance(rendition, dict) and id(rendition) not in seen:
                seen.add(id(rendition))
                rendition = dict(rendition)
                rendition["_list_key"] = str(name)
                renditions.append(rendition)
    return renditions


def _classify(rendition: dict, field: str) -> tuple[str, str]:
    url = decode_media_url(rendition.get(field))
    if not url or not _host_allowed(url):
        return "", ""
    try:
        query = dict(parse_qsl(urlparse(url).query, keep_blank_values=True))
    except Exception:
        return "", ""
    return query.get("lr", ""), url


class DolaAssetVariantResolver:
    """Resolve + select the provider-issued variant for one creation."""

    def __init__(self, *, prefer: str = "PREFER_UNWATERMARKED") -> None:
        self._prefer = prefer

    def resolve(self, creation: dict) -> list[VideoVariant]:
        variants: list[VideoVariant] = []
        for rendition in extract_renditions(creation):
            for field in ("main_url", "backup_url_1", "backup_url_2"):
                lr, url = _classify(rendition, field)
                if not url:
                    continue
                variants.append(VideoVariant(
                    list_key=str(rendition.get("_list_key") or ""),
                    definition=rendition.get("definition"),
                    quality=rendition.get("quality"),
                    bitrate=rendition.get("bitrate"),
                    width=rendition.get("vwidth"),
                    height=rendition.get("vheight"),
                    variant_lr=lr or None,
                    url_host=urlparse(url).hostname,
                    main_url_redacted=redact_url(url),
                    field=field))
        return variants

    def select(self, creation: dict) -> VariantSelection:
        variants = self.resolve(creation)
        if not variants:
            return VariantSelection(
                authority="NOT_FOUND", candidates_considered=0,
                reason="no provider-issued rendition with an allowed host")
        if self._prefer != "PREFER_UNWATERMARKED":
            raise ValueError("unsupported selection policy: "
                             + str(self._prefer))
        clean = [v for v in variants
                 if v.variant_lr == "unwatermarked"]
        if len(clean) == 1:
            return VariantSelection(
                authority="PROVIDER_ISSUED_UNWATERMARKED", variant=clean[0],
                candidates_considered=len(variants), reason="single clean "
                "provider-issued sibling")
        if len(clean) > 1:
            # same-rendition main/backup duplicates are one logical asset;
            # require identical (list_key, definition, bitrate) otherwise
            # fail closed.
            signatures = {(v.list_key, v.definition, v.bitrate)
                          for v in clean}
            if len(signatures) == 1:
                best = max(clean, key=lambda v: v.field != "main_url")
                return VariantSelection(
                    authority="PROVIDER_ISSUED_UNWATERMARKED",
                    variant=best, candidates_considered=len(variants),
                    reason="identical rendition across mirror fields")
            return VariantSelection(
                authority="NOT_FOUND", candidates_considered=len(variants),
                reason="ambiguous: multiple distinct clean renditions")
        watermarked = [v for v in variants if v.variant_lr == "cici_ai"]
        if watermarked:
            best = max(watermarked, key=lambda v: v.bitrate or 0)
            return VariantSelection(
                authority="PROVIDER_ISSUED_WATERMARKED", variant=best,
                candidates_considered=len(variants),
                reason="no unwatermarked sibling delivered")
        return VariantSelection(
            authority="NOT_FOUND", candidates_considered=len(variants),
            reason="renditions without a classifiable lr parameter")
