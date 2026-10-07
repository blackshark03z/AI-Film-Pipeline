"""V2-019 Phase A/C — Dola capability registry.

Normalizes the provider-DELIVERED capability truth (composer selector
templates from /alice/slot/action_bar_v3/get_item_conf + model catalogs
from /samantha/skill/pack) into an immutable registry. The registry never
invents a capability: anything not delivered/declared by the provider stays
unknown, and TRUE draft->final support is False until a draft identity AND
a finalization operation referencing it are both observed (Phase F rule).
"""
from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field

from ...core import ContractModel

GateClass = Literal["FREE", "SUBSCRIPTION_GATED", "COMMERCE_GATED", "UNKNOWN"]

_SUBS_ONLY_TAGS = {"none": "FREE"}


def _peel_json_strings(node: Any, depth: int = 0) -> list[Any]:
    """Every dict reachable by recursively json.loads-ing JSON-string
    values (the anti-shallow-scan rule from V2-011W)."""
    out: list[Any] = []
    if depth > 12 or node is None:
        return out
    if isinstance(node, str):
        s = node.strip()
        if s[:1] in "{[":
            try:
                obj = json.loads(s)
            except Exception:
                return out
            out.append(obj)
            out.extend(_peel_json_strings(obj, depth + 1))
        return out
    if isinstance(node, dict):
        for value in node.values():
            out.extend(_peel_json_strings(value, depth + 1))
    elif isinstance(node, list):
        for value in node:
            out.extend(_peel_json_strings(value, depth + 1))
    return out


class DolaModelEntry(ContractModel):
    model_id: str
    display: str = ""
    sub_display: str = ""
    gate: GateClass = "UNKNOWN"
    gate_tag: str = ""
    credit_multiplier: int | None = None
    is_default: bool = False


class DolaModelCapability(ContractModel):
    supported_durations: list[str] = Field(default_factory=list)
    supported_resolutions: list[str] = Field(default_factory=list)
    support_video_ref: bool | None = None


class DolaModelCatalog(ContractModel):
    models: list[DolaModelEntry] = Field(default_factory=list)
    capabilities: dict[str, DolaModelCapability] = Field(default_factory=dict)
    duration_options: list[str] = Field(default_factory=list)
    ratio_options: list[str] = Field(default_factory=list)
    resolution_control_delivered: bool = False


def _gate_for(extra: dict | None, option_key: str) -> tuple[GateClass, str]:
    if not isinstance(extra, dict):
        return "UNKNOWN", ""
    tag = extra.get("subs_only_tag") or extra.get("subscription_tag")
    if isinstance(tag, str) and tag and tag != "none":
        return "SUBSCRIPTION_GATED", tag
    if tag == "none":
        return "FREE", "none"
    commerce = extra.get("actionbar_commerce_gate_id")
    if isinstance(commerce, str) and commerce:
        return "COMMERCE_GATED", commerce
    return "UNKNOWN", ""


def _multiplier(sub_display: str) -> int | None:
    # sub_display carries the cost line, e.g. "最高品質 • 5倍のクレジットを使用"
    import re

    match = re.search(r"(\d+)\s*(?:倍|x|X)", sub_display or "")
    return int(match.group(1)) if match else None


def parse_composer_template(action_bar_conf: dict) -> DolaModelCatalog:
    """Parse the provider-delivered composer templates into a catalog.

    Accepts the raw get_item_conf body (nested JSON strings included).
    """
    catalog = DolaModelCatalog()
    seen_models: set[str] = set()
    for candidate in _peel_json_strings(action_bar_conf) + \
            [action_bar_conf]:
        if not isinstance(candidate, dict):
            continue
        key = str(candidate.get("key") or "")
        options = candidate.get("option_list")
        if not isinstance(options, list) or not options:
            continue
        if key == "video-model":
            for option in options:
                model_id = str(option.get("option_key") or "")
                if not model_id or model_id in seen_models:
                    continue
                seen_models.add(model_id)
                extra = option.get("extra") if \
                    isinstance(option.get("extra"), dict) else {}
                gate, tag = _gate_for(extra, model_id)
                catalog.models.append(DolaModelEntry(
                    model_id=model_id,
                    display=str(option.get("display_text") or ""),
                    sub_display=str((extra or {}).get("sub_display") or ""),
                    gate=gate, gate_tag=tag,
                    credit_multiplier=_multiplier(
                        str((extra or {}).get("sub_display") or "")),
                    is_default=False))
        elif key.startswith("video") or key in ("model", "duration", "ratio"):
            values = [str(o.get("option_key") or o.get("display_text") or "")
                      for o in options]
            values = [v for v in values if v]
            if key == "video-duration":
                catalog.duration_options = values
            elif key in ("video-ratio", "image_creation_ratio", "ratio"):
                if key == "video-ratio":
                    catalog.ratio_options = values
            elif key == "video-resolution":
                catalog.resolution_control_delivered = True
    # default flags: provider default_selection_index/id wins
    return catalog


def parse_skill_pack(skill_pack_body: dict) -> DolaModelCatalog:
    """Parse /samantha/skill/pack data.video_generation (meta.option_list +
    model_capability)."""
    catalog = DolaModelCatalog()
    data = skill_pack_body.get("data") if \
        isinstance(skill_pack_body, dict) else None
    video = data.get("video_generation") if isinstance(data, dict) else None
    meta = video.get("meta") if isinstance(video, dict) else None
    if not isinstance(meta, dict):
        return catalog
    for group in meta.get("option_list") or []:
        if not isinstance(group, dict):
            continue
        value = str(group.get("value") or "")
        if value == "model":
            for option in group.get("options") or []:
                if not isinstance(option, dict):
                    continue
                model_id = str(option.get("value") or "")
                if not model_id:
                    continue
                gate, tag = _gate_for(option, model_id)
                if not any(m.model_id == model_id
                           for m in catalog.models):
                    catalog.models.append(DolaModelEntry(
                        model_id=model_id,
                        display=str(option.get("show_name") or ""),
                        sub_display=str(option.get("sub_display") or ""),
                        gate=gate, gate_tag=tag,
                        credit_multiplier=_multiplier(
                            str(option.get("sub_display") or "")),
                        is_default=bool(option.get("is_default"))))
        elif value == "duration":
            catalog.duration_options = [
                str(o.get("value") or "") for o in group.get("options") or []
                if isinstance(o, dict) and o.get("value")]
        elif value == "resolution":
            catalog.resolution_control_delivered = True
        elif value == "ratio":
            catalog.ratio_options = [
                str(o.get("value") or "") for o in group.get("options") or []
                if isinstance(o, dict) and o.get("value")]
    capability = meta.get("model_capability")
    if isinstance(capability, dict):
        for model_id, raw in capability.items():
            if not isinstance(raw, dict):
                continue
            catalog.capabilities[model_id] = DolaModelCapability(
                supported_durations=[str(d) for d in
                                     raw.get("supported_durations") or []],
                supported_resolutions=[
                    str(r) for r in raw.get("supported_resolutions") or []],
                support_video_ref=raw.get("support_video_ref"))
    return catalog


class DolaCapabilityRegistry:
    """Merged, immutable view of the provider-delivered capability truth."""

    def __init__(self, catalogs: list[DolaModelCatalog]) -> None:
        self._models: dict[str, DolaModelEntry] = {}
        self._capabilities: dict[str, DolaModelCapability] = {}
        self._durations: list[str] = []
        self._ratios: list[str] = []
        self._resolution_control = False
        for catalog in catalogs:
            for model in catalog.models:
                existing = self._models.get(model.model_id)
                if existing is None:
                    self._models[model.model_id] = model
                else:
                    # merge: a delivered non-UNKNOWN gate wins; keep default
                    gate = existing.gate if existing.gate != "UNKNOWN" \
                        else model.gate
                    tag = existing.gate_tag or model.gate_tag
                    self._models[model.model_id] = existing.model_copy(
                        update={"gate": gate, "gate_tag": tag,
                                "is_default": existing.is_default
                                or model.is_default})
            for model_id, capability in catalog.capabilities.items():
                self._capabilities.setdefault(model_id, capability)
            if catalog.duration_options and not self._durations:
                self._durations = catalog.duration_options
            if catalog.ratio_options and not self._ratios:
                self._ratios = catalog.ratio_options
            self._resolution_control = \
                self._resolution_control or catalog.resolution_control_delivered

    # -- queries -------------------------------------------------------------

    def models(self) -> list[DolaModelEntry]:
        return list(self._models.values())

    def model(self, model_id: str) -> DolaModelEntry | None:
        return self._models.get(model_id)

    def capability(self, model_id: str) -> DolaModelCapability | None:
        return self._capabilities.get(model_id)

    def duration_options(self) -> list[str]:
        return list(self._durations)

    def ratio_options(self) -> list[str]:
        return list(self._ratios)

    def resolution_control_delivered(self) -> bool:
        return self._resolution_control

    def supports_request(self, *, model_id: str, duration: str | None = None,
                         resolution: str | None = None) -> tuple[bool, str]:
        """Fail-closed eligibility: model registered, gate free of an
        unmet entitlement, duration/resolution declared."""
        model = self._models.get(model_id)
        if model is None:
            return False, "MODEL_NOT_IN_DELIVERED_REGISTRY"
        if model.gate == "COMMERCE_GATED":
            return False, "COMMERCE_GATED"
        if model.gate == "SUBSCRIPTION_GATED":
            return False, "SUBSCRIPTION_GATED"
        capability = self._capabilities.get(model_id)
        if capability is None:
            return False, "CAPABILITY_NOT_DECLARED"
        if duration is not None and \
                str(duration) not in capability.supported_durations:
            return False, "DURATION_NOT_DECLARED"
        if resolution is not None and \
                str(resolution) not in capability.supported_resolutions:
            return False, "RESOLUTION_NOT_DECLARED"
        return True, "OK"

    # -- Phase F rule --------------------------------------------------------

    @property
    def true_draft_final_supported(self) -> bool:
        """TRUE only when a draft identity AND a provider finalization op
        referencing it have both been observed. Dola: neither exists."""
        return False


def merge_registry(*bodies: dict) -> DolaCapabilityRegistry:
    """Build a registry from raw provider config bodies (any mix of
    get_item_conf / skill/pack shapes)."""
    catalogs: list[DolaModelCatalog] = []
    for body in bodies:
        if not isinstance(body, dict):
            continue
        text = json.dumps(body, ensure_ascii=False)
        if "model_capability" in text:
            catalogs.append(parse_skill_pack(body))
        if "video-model" in text or '"option_list"' in text:
            catalogs.append(parse_composer_template(body))
    return DolaCapabilityRegistry(catalogs)
