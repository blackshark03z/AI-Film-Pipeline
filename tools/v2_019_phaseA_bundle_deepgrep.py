"""V2-019 Phase A — deep bundle grep with contexts (read-only static RE)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_019_dola_productionization"
CHAT = (PKG / "bundles/chat.js").read_text(encoding="utf-8",
                                           errors="replace")

CONCEPTS = {
    # wire construction
    "ability_param": r"ability_param",
    "ability_type": r"ability_type",
    "seedance": r"seedance",
    "subs_only": r"subs_only",
    "enhanced": r"\"enhanced\"",
    "video_config": r"video_?[Cc]onfig",
    "resolution_tokens": r"(480p|720p|1080p)",
    "ratio_keys": r"(?:ratio|aspect_?ratio)",
    # draft->final semantic candidates (Phase B oracle terms)
    "draft": r"[Dd]raft",
    "preview": r"[Pp]review",
    "rough": r"[Rr]ough",
    "quick": r"[Qq]uick",
    "low_quality": r"low_?[Qq]uality",
    "source_task": r"source_?[Tt]ask",
    "parent_task": r"parent_?[Tt]ask",
    "derive": r"[Dd]erive",
    "render_final": r"render_?[Ff]inal",
    "quality_upgrade": r"quality_?[Uu]pgrade",
    "upscale": r"[Uu]pscale",
    "refine": r"[Rr]efine",
    "regenerate": r"[Rr]egenerate",
    "hd": r"\\bHD\\b|_hd_|hd_|\"hd\"",
    "superres": r"super_?[Rr]es",
    # entitlement / gating
    "subscribe": r"[Ss]ubscri",
    "vip": r"\\bvip\\b|Vip",
    "entitle": r"entitle",
    "paywall": r"paywall|upsell|upgrade_?to",
    "credit": r"[Cc]redit",
}


def contexts(text: str, pattern: str, span: int = 220, limit: int = 8) -> list[str]:
    out = []
    for m in list(re.finditer(pattern, text))[:limit]:
        s = max(0, m.start() - span)
        out.append(text[s:m.start() + span].replace("\\n", " "))
    return out


def main() -> int:
    report = {}
    for label, pattern in CONCEPTS.items():
        hits = list(re.finditer(pattern, CHAT))
        entry = {"count": len(hits)}
        if hits and label in (
                "ability_param", "ability_type", "seedance", "subs_only",
                "video_config", "enhanced", "ratio_keys", "upscale",
                "quality_upgrade", "source_task", "parent_task",
                "render_final", "superres", "low_quality", "derive"):
            entry["contexts"] = contexts(CHAT, pattern, span=260, limit=6)
        report[label] = entry
    out = PKG / "V2_019_PHASEA_BUNDLE_DEEPGREP.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    summary = {k: v["count"] for k, v in report.items()}
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
