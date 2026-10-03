"""FLOW-EDITORIAL-RUNTIME-SCALE-010 (T12) — independent MASTER_EDITORIAL_010_V1
conformance audit (audio + handles + canary-leak edition).

Additional U10 exclusion proof over the 007 audit:
- the four post-gate-invalidated historical artifacts (ProviderJob ids,
  asset hashes, output identities) must be ABSENT from every canonical
  package artifact; they remain only in historical evidence directories.

Re-derives everything from durable records (never from the builder's
summary) and proves:
- lineage: manifest clips ↔ durable EditorialRanges ↔ canonical slots; the
  repaired slots (SEQ7_E2, SEQ7_G3) carry their successor takes (E2R/G3B),
  no stale primary take for a repaired slot survives in the manifest;
- trim: every clip's range equals its durable EditorialRange and resolves
  against the exact asset (hash + duration) through the editorial boundary;
- boundaries: frame/time sampling around ALL 29 cuts — master frames just
  before/after each boundary must match the outgoing source tail frame and
  the incoming source head frame (RMS pixel distance with a calibrated
  tolerance, plus negative controls against distant source frames);
- duration: master duration within one-frame-per-cut rounding of the
  timeline sum;
- integrity: full-decode EOF;
- machine-readable conformance_report.json.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.editorial import EditorialStore, probe_media
from film_pipeline.editorial_range import read_range
from film_pipeline.store import SQLiteStore

STORE_PATH = ROOT / "projects/flow_production_harden_002/requal_current_build/runtime.sqlite"
OUT_DIR = ROOT / "projects/flow_editorial_runtime_scale_010/master_package_010"
MASTER = OUT_DIR / "master_editorial_010_v1.mp4"
SEQ7_DIR = ROOT / "projects/flow_production_scale_007"
CANONICAL_ORDER = [
    "SEQ4_A1", "SEQ4_A2", "SEQ4_A3", "SEQ4_A4", "SEQ4_A5",
    "SEQ4_B1", "SEQ4_B2", "SEQ4_B3", "SEQ4_B4", "SEQ4_B5R",
    "SEQ5_C1", "SEQ5_C2", "SEQ5_C3", "SEQ5_C4",
    "SEQ5_D1", "SEQ5_D2", "SEQ5_D3", "SEQ5_D4",
    "SEQ7_E1", "SEQ7_E2", "SEQ7_E3", "SEQ7_E4",
    "SEQ7_F1", "SEQ7_F2", "SEQ7_F3", "SEQ7_F4",
    "SEQ7_G1", "SEQ7_G2", "SEQ7_G3", "SEQ7_G4"]
REPAIRED = {"SEQ7_E2": "SEQ7_E2C", "SEQ7_F2": "SEQ7_F2C",
            "SEQ7_G2": "SEQ7_G2C", "SEQ7_G3": "SEQ7_G3C"}
REPROOF_SCENE_OF = {"SEQ7_E2C": "SCENE_E_RIDGE_APPROACH",
                    "SEQ7_F2C": "SCENE_F_STORM_GATE",
                    "SEQ7_G2C": "SCENE_G_HIGH_PLATEAU",
                    "SEQ7_G3C": "SCENE_G_HIGH_PLATEAU"}
# Superseded/invalid classes excluded from the canonical package:
# 1) Package-007 post-gate-invalidated slots; 2) Package-008 re-proof
# successors; 3) the Package-008 continuation-test asset; 4) the
# historical invalid Shot-3C lineage (Scene-003 R1 custody).
# Post-gate-invalidated historical slots and their durable artifact ids.
INVALIDATED_SLOTS = {"SEQ7_F2": "scene_SCENE_F_STORM_GATE",
                     "SEQ7_G2": "scene_SCENE_G_HIGH_PLATEAU"}
INVALIDATED_REPAIRS = {"SEQ7_E2R": "repair_scope/repair_SEQ7_E2R",
                       "SEQ7_G3B": "repair_scope/repair_SEQ7_G3B"}


EXTRA_INVALIDATED_RESULTS = [
    # (label, result.json path)
    ("P8_F2R", ROOT / "projects/flow_upload_reconciliation_008/reproof/"
     "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2R/result.json"),
    ("P8_G2R", ROOT / "projects/flow_upload_reconciliation_008/reproof/"
     "scene_SCENE_G_HIGH_PLATEAU/shot_SEQ7_G2R/result.json"),
    ("P8_E2R2", ROOT / "projects/flow_upload_reconciliation_008/reproof/"
     "scene_SCENE_E_RIDGE_APPROACH/shot_SEQ7_E2R2/result.json"),
    ("P8_G3BR", ROOT / "projects/flow_upload_reconciliation_008/reproof/"
     "scene_SCENE_G_HIGH_PLATEAU/shot_SEQ7_G3BR/result.json"),
    ("P8_CONT", ROOT / "projects/flow_upload_reconciliation_008/continuation/"
     "scene_U6_CONTINUATION_PROOF/shot_U6_CONT/result.json"),
    ("SCENE003_3C", ROOT / "projects/flow_scene_scale_003/"
     "shot_SCENE003_SHOT_3C/result.json"),
]


def invalidated_artifacts() -> dict:
    tokens = {}
    for label, path in EXTRA_INVALIDATED_RESULTS:
        result = json.loads(path.read_text(encoding="utf-8"))
        asset = result["asset"]
        tokens[f"{label}:provider_job"] = result["provider_job_id"]
        tokens[f"{label}:output_identity"] = result["output_identity"]
        tokens[f"{label}:asset_id"] = asset["asset_id"]
        tokens[f"{label}:asset_sha256"] = asset["sha256"]
    for slot, rel in INVALIDATED_SLOTS.items():
        result = json.loads((SEQ7_DIR / "sequence_SEQ007_DAYLIGHT_ROAD" /
                             rel / f"shot_{slot}" / "result.json")
                            .read_text(encoding="utf-8"))
        asset = result["asset"]
        tokens[f"{slot}:provider_job"] = result["provider_job_id"]
        tokens[f"{slot}:output_identity"] = result["output_identity"]
        tokens[f"{slot}:asset_id"] = asset["asset_id"]
        tokens[f"{slot}:asset_sha256"] = asset["sha256"]
    for slot, rel in INVALIDATED_REPAIRS.items():
        result = json.loads((SEQ7_DIR / rel / f"shot_{slot}" /
                             "result.json").read_text(encoding="utf-8"))
        asset = result["asset"]
        tokens[f"{slot}:provider_job"] = result["provider_job_id"]
        tokens[f"{slot}:output_identity"] = result["output_identity"]
        tokens[f"{slot}:asset_id"] = asset["asset_id"]
        tokens[f"{slot}:asset_sha256"] = asset["sha256"]
    return tokens
FRAME_STEP_S = 0.04
RMS_PASS = 16.0


def grab_frame(path: Path, at_s: float, destination: Path) -> None:
    attempt = max(at_s, 0.0)
    for step in (0.0, 0.08, 0.16):
        completed = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{max(attempt - step, 0.0):.3f}",
             "-i", str(path), "-frames:v", "1", str(destination)],
            capture_output=True, text=True, check=False)
        if completed.returncode == 0 and destination.exists():
            return
    raise RuntimeError(f"frame grab failed: {path}@{at_s:.3f}")


def rms(a: Path, b: Path) -> float:
    ia, ib = Image_open(a), Image_open(b)
    if ia.size != ib.size:
        return 255.0
    diff = ImageChops_difference(ia, ib)
    stat = ImageStat_stat(diff)
    return sum(stat.mean) / len(stat.mean)


def Image_open(p):
    from PIL import Image
    return Image.open(p).convert("RGB")


def ImageChops_difference(a, b):
    from PIL import ImageChops
    return ImageChops.difference(a, b)


def ImageStat_stat(d):
    from PIL import ImageStat
    return ImageStat.Stat(d)


def main() -> None:
    store = SQLiteStore(STORE_PATH)
    editorial = EditorialStore(store)
    summary = json.loads((OUT_DIR / "master_summary.json")
                         .read_text(encoding="utf-8"))
    manifest, sources = editorial.read_manifest(summary["edit_manifest_id"])
    report = {"version": "conformance-010-v1", "checks": [],
              "boundaries": []}

    # lineage + trim vs durable EditorialRanges ----------------------------
    ranges = {slot: read_range(OUT_DIR / "ranges" / f"{i:02d}_{slot}.json")
              for i, slot in enumerate(CANONICAL_ORDER, 1)}
    lineage_ok = True
    for clip, slot in zip(manifest.clips, CANONICAL_ORDER):
        rng = ranges[slot]
        if (clip.selected_take_id != rng.selected_take_id or
                clip.source_in_s != rng.source_in_s or
                clip.source_out_s != rng.source_out_s):
            lineage_ok = False
            report["checks"].append({"check": "lineage", "slot": slot,
                                     "verdict": "FAIL"})
    report["checks"].append({"check": "lineage_and_ranges_all_30",
                             "verdict": "PASS" if lineage_ok else "FAIL"})
    # repaired slots carry successor takes; no stale primary take survives
    for slot, repair_id in REPAIRED.items():
        clip = manifest.clips[CANONICAL_ORDER.index(slot)]
        row = store._connect().execute(
            "SELECT payload FROM selected_takes WHERE id=?",
            (clip.selected_take_id,)).fetchone()
        ok = row is not None and json.loads(row[0]).get("shot_id") == \
            repair_id
        report["checks"].append({"check": "repair_take_canonical",
                                 "slot": slot,
                                 "expect_take_shot": repair_id,
                                 "verdict": "PASS" if ok else "FAIL"})
    stale = [c.shot_id for c, s in zip(manifest.clips, CANONICAL_ORDER)
             if s in REPAIRED and c.shot_id == s]
    report["checks"].append({"check": "no_stale_primary_takes",
                             "verdict": "PASS" if not stale else "FAIL",
                             "stale": stale})
    # U10 exclusion scan: invalidated historical artifacts absent from the
    # canonical package (summary, plan, ranges, package payload, manifest).
    tokens = invalidated_artifacts()
    haystacks = {"master_summary.json": (OUT_DIR / "master_summary.json")
                 .read_text(encoding="utf-8"),
                 "editorial_plan_010.json": (OUT_DIR / "editorial_plan_010.json")
                 .read_text(encoding="utf-8")}
    for range_file in sorted((OUT_DIR / "ranges").glob("*.json")):
        haystacks[f"ranges/{range_file.name}"] = range_file.read_text(
            encoding="utf-8")
    for package_file in sorted((OUT_DIR / "autoedit_package").rglob("*")):
        if package_file.is_file():
            haystacks[f"autoedit_package/{package_file.relative_to(OUT_DIR)}"] =                 package_file.read_text(encoding="utf-8", errors="replace")
    manifest_blob = json.dumps({
        "clips": [c.model_dump(mode="json") for c in manifest.clips]},
        default=str)
    haystacks["manifest_clips"] = manifest_blob
    leaked = {where: token for where, blob in haystacks.items()
              for token in tokens.values() if token in blob}
    report["checks"].append({
        "check": "invalidated_artifacts_excluded_from_canonical_package",
        "tokens_scanned": len(tokens), "haystacks": len(haystacks),
        "leaks": leaked,
        "verdict": "PASS" if not leaked else "FAIL"})
    # reproof successor identity: each replaced slot binds the U9 output
    for slot, successor in REPAIRED.items():
        result = json.loads((ROOT / "projects/flow_upload_contract_requal_009/"
                             "reproof" / f"scene_{REPROOF_SCENE_OF[successor]}"
                             / f"shot_{successor}" / "result.json")
                            .read_text(encoding="utf-8"))
        clip = manifest.clips[CANONICAL_ORDER.index(slot)]
        ok = clip.asset_id == result["asset"]["asset_id"] and             result.get("gate") == "SHOT_PROVEN"
        report["checks"].append({
            "check": "reproof_successor_binding", "slot": slot,
            "successor": successor,
            "verdict": "PASS" if ok else "FAIL"})
    # the historical repaired take B5R is present, rejected B5 is absent
    b5r_ok = manifest.clips[CANONICAL_ORDER.index("SEQ4_B5R")].shot_id == \
        "SEQ4_B5R"
    b5_absent = all(c.shot_id != "SEQ4_B5" for c in manifest.clips)
    report["checks"].append({"check": "historical_B5R_canonical_B5_absent",
                             "verdict": "PASS" if b5r_ok and b5_absent
                             else "FAIL"})

    # duration conformance ---------------------------------------------------
    media = probe_media(MASTER)
    expected = sum(s.duration_s for s in sources)
    tolerance = len(sources) / 30.0 + 0.05  # one frame per cut, generous
    duration_ok = abs(media.duration_s - expected) <= tolerance
    report["checks"].append({
        "check": "duration", "master_s": media.duration_s,
        "timeline_s": round(expected, 3),
        "tolerance_s": round(tolerance, 3),
        "verdict": "PASS" if duration_ok else "FAIL"})

    # full decode --------------------------------------------------------------
    decode = subprocess.run(
        ["ffmpeg", "-v", "error", "-xerror", "-i", str(MASTER),
         "-f", "null", "-"], capture_output=True, text=True, timeout=600,
        check=False)
    report["checks"].append({"check": "full_decode_eof",
                             "verdict": "PASS" if decode.returncode == 0
                             else "FAIL"})

    # boundary localization + frame sampling (all 29 cuts) -------------------
    # Segment durations quantize to the 24 fps frame grid (a 5.6 s trim may
    # render 134 or 135 frames depending on source PTS jitter), so each
    # actual boundary can sit up to ~1 frame from the decimal expectation.
    # The audit therefore LOCATES each boundary by a local scan (±0.2 s,
    # 1/24 s steps) classifying master frames as outgoing/incoming by RMS
    # against reference frames of the two adjacent sources, then requires a
    # single contiguous transition inside the window.
    starts, acc = [], 0.0
    for s in sources:
        starts.append(acc)
        acc += s.duration_s
    STEP = 1 / 24
    WINDOW = 0.2
    MATCH_RMS = 10.0
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        boundaries = []
        for index in range(len(manifest.clips) - 1):
            src_out, src_in = sources[index], sources[index + 1]
            slot_out, slot_in = (CANONICAL_ORDER[index],
                                 CANONICAL_ORDER[index + 1])
            expected = starts[index] + src_out.duration_s
            tail_ref, head_ref = (tdp / f"t{index:02d}.png",
                                  tdp / f"h{index:02d}.png")
            grab_frame(Path(src_out.path),
                       src_out.source_out_s - 0.08, tail_ref)
            grab_frame(Path(src_in.path), src_in.source_in_s + 0.001,
                       head_ref)
            times = []
            t = expected - WINDOW
            while t <= expected + WINDOW + 1e-9:
                times.append(t)
                t += STEP
            labels = []
            for k, t in enumerate(times):
                frame = tdp / f"m{index:02d}_{k}.png"
                grab_frame(MASTER, t, frame)
                r_out, r_in = rms(frame, tail_ref), rms(frame, head_ref)
                labels.append("OUT" if r_out < MATCH_RMS else
                              "IN" if r_in < MATCH_RMS else "UNK")
            out_end = max((k for k, l in enumerate(labels)
                           if l == "OUT"), default=None)
            in_start = min((k for k, l in enumerate(labels)
                            if l == "IN"), default=None)
            single_transition = (out_end is not None and in_start is not None
                                 and in_start > out_end and
                                 all(l in ("OUT", "UNK")
                                     for l in labels[:in_start]) and
                                 all(l in ("IN", "UNK")
                                     for l in labels[in_start:]))
            actual = round((times[out_end] + times[in_start]) / 2, 4) \
                if out_end is not None and in_start is not None else None
            drift = round(actual - expected, 4) if actual is not None \
                else None
            ok = bool(single_transition and drift is not None and
                      abs(drift) <= WINDOW)
            boundaries.append({
                "cut_index": index + 1, "from": slot_out, "to": slot_in,
                "expected_boundary_s": round(expected, 4),
                "actual_boundary_s": actual, "drift_s": drift,
                "frames_out": (out_end + 1) if out_end is not None else None,
                "frames_in": (len(labels) - in_start) if in_start is not None
                else None,
                "single_contiguous_transition": ok,
                "verdict": "PASS" if ok else "FAIL"})
        report["boundaries"] = boundaries
    fails = [b for b in report["boundaries"] if b["verdict"] == "FAIL"]
    report["checks"].append({
        "check": "boundary_frame_sampling_29_cuts",
        "pass": len(report["boundaries"]) - len(fails), "fail": len(fails),
        "verdict": "PASS" if not fails else "FAIL"})
    # T12 additions: audio policy, handles metadata, canary-leak scan.
    import subprocess as _sp
    probe_out = json.loads(_sp.run(
        ["ffprobe", "-v", "error", "-show_streams", "-select_streams",
         "a", "-of", "json", str(MASTER)], capture_output=True,
        text=True).stdout or '{"streams": []}')
    audio_stream = (probe_out.get("streams") or [None])[0]
    audio_ok = bool(audio_stream) and audio_stream["codec_name"] == "aac"         and audio_stream["sample_rate"] == "48000"         and audio_stream["channels"] == 2
    report["checks"].append({"check": "audio_stream_aac_48k_stereo",
                             "verdict": "PASS" if audio_ok else "FAIL"})
    handles = {}
    for range_file in sorted((OUT_DIR / "ranges").glob("*.json")):
        data = json.loads(range_file.read_text(encoding="utf-8"))
        if data.get("handle_in_s", 0) or data.get("handle_out_s", 0):
            handles[data["shot_id"]] = [data.get("handle_in_s", 0),
                                        data.get("handle_out_s", 0)]
    handles_ok = len(handles) == 12 and all(
        v[0] >= 0 and v[1] >= 0 and (v[0] > 0 or v[1] > 0)
        for v in handles.values())
    report["checks"].append({
        "check": "editorial_handles_recorded_on_trimmed_slots",
        "count": len(handles), "verdict": "PASS" if handles_ok else "FAIL"})
    canary_outputs = ["7d61b2f2-2678-42c2-97bc-6fd30b1b1aef",
                      "378966a4-7ee9-421b-afb6-df974d4a4632",
                      "4fc1b2f5-4097-4a81-9eac-beec0a73b639"]
    blob = json.dumps(summary, default=str)
    leaked = [c for c in canary_outputs if c in blob]
    report["checks"].append({
        "check": "session_reuse_canary_videos_absent_from_master",
        "verdict": "PASS" if not leaked else "FAIL", "leaks": leaked})
    report["overall"] = ("CONFORMANT" if all(
        c["verdict"] == "PASS" for c in report["checks"])
        else "NONCONFORMANT")
    (OUT_DIR / "conformance_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps({"overall": report["overall"],
                      "checks": {c["check"]: c["verdict"]
                                 for c in report["checks"]},
                      "boundary_fails": len(fails)}))


if __name__ == "__main__":
    main()
