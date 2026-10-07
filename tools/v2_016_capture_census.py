"""V2-016 Phase 1 — concept census across Dola captures (draft / 2.5 / seedance)."""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from dola_010c_session import dpapi_unprotect  # noqa: E402

CAP = ROOT / "projects/quality_v2_010c_dola_fullstack/runtime/capture"
PKG = ROOT / "projects/quality_v2_016_seedance25_capability"

PATTERNS = {
    "draft": re.compile(r"draft", re.I),
    "seedance25": re.compile(r"seedance[^a-z0-9]{0,4}2[.]5", re.I),
    "seedance_version": re.compile(r"seedance[ a-z0-9._-]{0,24}", re.I),
    "finalize": re.compile(r"finaliz", re.I),
    "upscale": re.compile(r"upscale", re.I),
}


def load_capture(cap: Path) -> str:
    if cap.suffix == ".dpapi":
        return dpapi_unprotect(cap.read_text(encoding="ascii")).decode(
            "utf-8", "replace")
    return cap.read_text(encoding="utf-8", errors="replace")


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    PKG.mkdir(parents=True, exist_ok=True)
    counts = {}
    draft_contexts = {}
    seed25_contexts = {}
    for cap in sorted(CAP.glob("raw_f*.jsonl*")):
        try:
            text = load_capture(cap)
        except Exception as e:
            print(cap.name, "LOAD FAIL", type(e).__name__)
            continue
        c = {k: len(p.findall(text)) for k, p in PATTERNS.items()}
        counts[cap.name] = c
        print(cap.name, c)
        if c["draft"]:
            for m in list(PATTERNS["draft"].finditer(text))[:3]:
                ctx = text[max(0, m.start() - 140):m.end() + 140]
                draft_contexts.setdefault(cap.name, []).append(
                    ctx.replace("\n", " ")[:280])
        if c["seedance25"]:
            for m in list(PATTERNS["seedance25"].finditer(text))[:3]:
                ctx = text[max(0, m.start() - 140):m.end() + 140]
                seed25_contexts.setdefault(cap.name, []).append(
                    ctx.replace("\n", " ")[:280])
    # seedance version strings in the f3r_012 capture
    f3r = counts.get("raw_f3r_012_20261006T145913.jsonl")
    versions = sorted(set(m.group(0).strip() for m in
                          PATTERNS["seedance_version"].finditer(
                              load_capture(CAP /
                                           "raw_f3r_012_20261006T145913.jsonl"))))
    print("f3r_012 seedance version strings:", versions[:8])
    for cap, ctxs in draft_contexts.items():
        print("== draft context in", cap)
        for c in ctxs[:2]:
            print("  ...", c[:250])
    write_out = {
        "version": "v2-016-capture-concept-census-v1",
        "recorded_at": utcnow(),
        "counts": counts,
        "seedance_version_strings_f3r_012": versions[:8],
        "draft_contexts": draft_contexts,
        "seedance25_contexts": seed25_contexts,
    }
    (PKG / "V2_016_CAPTURE_CONCEPT_CENSUS.json").write_text(
        json.dumps(write_out, indent=1, ensure_ascii=False)[:300000],
        encoding="utf-8")
    print("wrote V2_016_CAPTURE_CONCEPT_CENSUS.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
