"""V2-010D — read-only unwatermarked-variant reconstruction from the 010C
F2A raw capture (no generation, no URL invention)."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from dola_010c_session import dpapi_unprotect

C10C = ROOT / "projects/quality_v2_010c_dola_fullstack"
PKG = ROOT / "projects/quality_v2_010d_f2b_completion"


def main() -> int:
    raw_dpapi = sorted((C10C / "runtime/capture").glob("raw_f2a_*.jsonl.dpapi"))[-1]
    lines = dpapi_unprotect(raw_dpapi.read_text(encoding="ascii")).decode(
        "utf-8", "replace").splitlines()
    # find the completed F2A video creation object (id from 010C evidence)
    f2a = json.loads((C10C / "V2_010C_F2A_EVIDENCE.json")
                     .read_text(encoding="utf-8"))
    creation_ids = f2a["qc"]["TRANSPORT_QC"]["creation_ids"]
    target = creation_ids[0]

    video_obj = None
    for line in lines:
        entry = json.loads(line)
        blob = entry.get("body") or ""
        if isinstance(blob, str) and target in blob and '"download_url"' in blob:
            idx = blob.find(f'"id":"{target}"')
            if idx < 0:
                idx = blob.find(f'"id": "{target}"')
            if idx >= 0:
                window = blob[idx:idx + 6000]
                if '"video"' in window:
                    video_obj = window
                    break

    findings = {"url_field_names": [], "unwatermarked_hits": 0,
                "watermark_hits": 0, "creation_ids_seen": sorted(set())}
    if video_obj:
        findings["url_field_names"] = sorted(set(re.findall(
            r'"(\w*url\w*)"\s*:', video_obj)))[:20]
        findings["unwatermarked_hits"] = len(re.findall(
            r"unwatermarked", video_obj))
        findings["watermark_hits"] = len(re.findall(r"watermark", video_obj))
        findings["creation_ids_seen"] = sorted(set(re.findall(
            r'"id"\s*:\s*"(\d{15,})"', video_obj)))

    # capture-wide semantics: which fields carry the unwatermarked marker
    field_hits = {}
    for line in lines:
        if "unwatermarked" not in line:
            continue
        entry = json.loads(line)
        blob = entry.get("body") or ""
        if not isinstance(blob, str):
            continue
        for match in re.finditer(r'"(\w*unwatermarked\w*)"\s*:', blob):
            field_hits[match.group(1)] = field_hits.get(
                match.group(1), 0) + 1

    evidence = {
        "version": "v2-010d-unwatermarked-variant-v1",
        "checkpoint": "V2010D_P7_UNWATERMARKED_RECONSTRUCTION",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "source": raw_dpapi.name + " (010C F2A capture, decrypted read-only)",
        "status": "OBSERVED_NOT_AUTHORIZED",
        "findings": {
            "f2a_creation_id_probed": target,
            "video_object_url_fields": findings["url_field_names"],
            "unwatermarked_marker_hits_in_video_object":
                findings["unwatermarked_hits"],
            "watermark_marker_hits_in_video_object":
                findings["watermark_hits"],
            "capture_wide_unwatermarked_fields": field_hits,
            "interpretation": "the creation video object carries "
                              "unwatermarked-labeled URL variants alongside "
                              "the watermarked download_url; BOTH belong to "
                              "the SAME creation id (same object), i.e. the "
                              "variant is a delivery format of the same "
                              "generation, not a different asset"},
        "authority_assessment": {
            "canonical_for_download": "video.download_url (the field the "
                                      "qualified adapter used; "
                                      "010C M2/F2A lineage is bound to it)",
            "unwatermarked_use": "NOT AUTHORIZED by any current Owner "
                                 "decision — the product UI itself displays "
                                 "the watermarked player; using the "
                                 "unwatermarked variant is a product-terms "
                                 "decision reserved to the Owner",
            "disposition": "current downloaded assets remain the "
                           "watermarked download_url variants; watermark "
                           "handling for editorial use is an Owner decision "
                           "(recorded in F2A/F2B editorial flags)"},
    }
    (PKG / "V2_010D_UNWATERMARKED_VARIANT.json").write_text(
        json.dumps(evidence, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2010D_UNWATERMARKED_RECONSTRUCTED",
                      "status": evidence["status"],
                      "video_object_url_fields":
                          findings["url_field_names"][:10],
                      "unwatermarked_hits": findings["unwatermarked_hits"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
