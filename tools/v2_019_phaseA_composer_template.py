"""V2-019 Phase A — clean extraction of the provider-delivered composer
template (model/ratio/duration/resolution control groups) from the raw
capture, decoding nested JSON strings properly (unicode-safe).

Read-only. Output: V2_019_PHASEA_COMPOSER_TEMPLATE.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_019_dola_productionization"
CAP = ROOT / ("projects/quality_v2_010c_dola_fullstack/runtime/capture/"
              "raw_f3r_012_20261006T145913.jsonl")


def try_json(s: str):
    try:
        return json.loads(s)
    except Exception:
        return None


def deep_json_strings(node, depth: int = 0):
    """Yield every dict reachable by recursively json.loads-ing string
    values that look like JSON objects/arrays."""
    if depth > 6 or node is None:
        return
    if isinstance(node, str):
        s = node.strip()
        if s[:1] in "{[" :
            obj = try_json(s)
            if obj is not None:
                yield obj
                yield from deep_json_strings(obj, depth + 1)
        return
    if isinstance(node, dict):
        for v in node.values():
            yield from deep_json_strings(v, depth + 1)
    elif isinstance(node, list):
        for v in node:
            yield from deep_json_strings(v, depth + 1)


def main() -> int:
    raw = CAP.read_text(encoding="utf-8", errors="replace")
    # capture lines are JSONL of CDP events; scan every string field
    selector_objects = []
    seen = set()
    for line in raw.splitlines():
        ev = try_json(line)
        if ev is None:
            continue
        for obj in deep_json_strings(ev):
            if isinstance(obj, dict) and "option_list" in obj and \
                    ("template" in obj or "key" in obj or "label" in obj):
                key = json.dumps(obj, sort_keys=True, ensure_ascii=False)
                h = hash(key)
                if h in seen:
                    continue
                seen.add(h)
                selector_objects.append(obj)

    groups = []
    for obj in selector_objects:
        groups.append({
            "id": obj.get("id"),
            "label": obj.get("label"),
            "key": obj.get("key"),
            "can_be_empty": obj.get("can_be_empty"),
            "default_selection_index": obj.get("default_selection_index"),
            "default_selection_id": obj.get("default_selection_id"),
            "options": [
                {
                    "id": o.get("id"),
                    "display_text": o.get("display_text"),
                    "option_key": o.get("option_key"),
                    "extra": o.get("extra"),
                    "selected_display_text": o.get("selected_display_text"),
                }
                for o in (obj.get("option_list") or [])
            ],
        })

    out = {
        "version": "v2-019-phaseA-composer-template-v1",
        "source_capture": CAP.name,
        "control_groups": groups,
    }
    dst = PKG / "V2_019_PHASEA_COMPOSER_TEMPLATE.json"
    dst.write_text(json.dumps(out, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(json.dumps({"groups": [
        {"key": g.get("key"), "label": g.get("label"),
         "n_options": len(g["options"])} for g in groups]},
        ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
