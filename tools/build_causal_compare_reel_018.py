"""FLOW-ACTION-INTENT-CAUSALITY-018 (Phases 15-16): the Owner causal
compare reel (blind section first, then an intent section) + the Owner
decision template.

Section 1 (BLIND): F2C BASELINE -> 017 BEST (C) -> 018 A -> 018 B; G3C
BASELINE -> 017 BEST (D) -> 018 C — minimal labels only, no intent
revealed. Section 2 (INTENT): short neutral authoritative-intent cards
per family so the Owner can judge execution against intent. Canonical
master untouched; nothing promoted.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D17 = ROOT / "projects/flow_performance_motion_canary_017"
D18 = ROOT / "projects/flow_action_intent_causality_018"
REEL = D18 / "OWNER_ACTION_CAUSALITY_COMPARE_018.mp4"
FONT = "C\\:/Windows/Fonts/arial.ttf"

custody = {r["candidate_id"]: r for r in json.loads(
    (D18 / "candidate_custody_018.json").read_text(encoding="utf-8"))}

BLIND_SEGMENTS = [
    {"label": "F2C 1", "video": ROOT / "projects/"
     "flow_upload_contract_requal_009/reproof/scene_SCENE_F_STORM_GATE/"
     "shot_SEQ7_F2C/videos/c1a69047933565230870ad22.mp4",
     "surface": "F2C canonical", "trim": (0.0, 5.6)},
    {"label": "F2C 2", "video": D17 /
     "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C_P017_C/videos/"
     "b104f61c4424cf3e0e564323.mp4",
     "surface": "F2C-P017-C (017 best)", "trim": (0.0, 5.6)},
    {"label": "F2C 3", "video": ROOT / custody["F2C-P018-A"]["video"],
     "surface": "F2C-P018-A", "trim": (0.0, 5.6)},
    {"label": "F2C 4", "video": ROOT / custody["F2C-P018-B"]["video"],
     "surface": "F2C-P018-B", "trim": (0.0, 5.6)},
    {"label": "G3C 1", "video": ROOT / "projects/"
     "flow_upload_contract_requal_009/reproof/"
     "scene_SCENE_G_HIGH_PLATEAU/shot_SEQ7_G3C/videos/"
     "6013b45645fdffa4fa702278.mp4",
     "surface": "G3C canonical", "trim": (0.0, 3.2)},
    {"label": "G3C 2", "video": D17 /
     "scene_SCENE_G_HIGH_PLATEAU/shot_SEQ7_G3C_P017_D/videos/"
     "23eadf3f247614c52d4cb5a6.mp4",
     "surface": "G3C-P017-D (017 best)", "trim": (0.0, 3.2)},
    {"label": "G3C 3", "video": ROOT / custody["G3C-P018-C"]["video"],
     "surface": "G3C-P018-C", "trim": (0.0, 3.2)},
]

INTENT_CARDS = [
    {"label": "F2 INTENT", "seconds": 5.0,
     "text": "AUTHORITATIVE INTENT (F2): a hard gust funnels through "
             "the rock gate; he drives a step through; he breaks past "
             "the worst gust - road onward"},
    {"label": "G3 INTENT", "seconds": 5.0,
     "text": "AUTHORITATIVE INTENT (G3): the arc of the draw is "
             "complete; the effort leaves him - one long exhale, "
             "shoulders settle, eyes ease forward"}]


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main() -> None:
    inputs, filters = [], []
    stream = 0
    seg_rows = []
    t = 0.0
    for seg in BLIND_SEGMENTS:
        inputs += ["-i", str(seg["video"])]
        start, end = seg["trim"]
        filters.append(
            f"[{stream}:v]trim=start={start:.3f}:end={end:.3f},"
            f"setpts=PTS-STARTPTS,fps=24,scale=1280:720,setsar=1,"
            f"drawtext=fontfile='{FONT}':text='{seg['label']}':"
            f"fontcolor=white:fontsize=40:box=1:boxcolor=black@0.55:"
            f"boxborderw=12:x=24:y=24[v{stream}]")
        dur = round(end - start, 3)
        seg_rows.append({"reel_start_s": round(t, 3),
                         "reel_end_s": round(t + dur, 3),
                         "section": "BLIND", "label": seg["label"],
                         "surface": seg["surface"],
                         "asset_sha256": sha(seg["video"]),
                         "provider_job_id": custody.get(
                             seg["surface"], {}).get("provider_job_id")})
        t += dur
        stream += 1
    for card in INTENT_CARDS:
        card_png = D18 / "intent_cards" / \
            f"{card['label'].replace(' ', '_')}.png"
        inputs += ["-loop", "1", "-t", str(card["seconds"]),
                   "-i", str(card_png)]
        filters.append(
            f"[{stream}:v]fps=24,scale=1280:720,setsar=1,"
            f"trim=duration={card['seconds']},setpts=PTS-STARTPTS"
            f"[v{stream}]")
        seg_rows.append({"reel_start_s": round(t, 3),
                         "reel_end_s": round(t + card["seconds"], 3),
                         "section": "INTENT", "label": card["label"],
                         "surface": "intent card",
                         "asset_sha256": None,
                         "provider_job_id": None})
        t += card["seconds"]
        stream += 1
    concat = "".join(f"[v{i}]" for i in range(stream))
    filters.append(f"{concat}concat=n={stream}:v=1:a=0[vout]")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error"] + inputs +
        ["-filter_complex", ";".join(filters), "-map", "[vout]", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-pix_fmt", "yuv420p", "-r", "24", str(REEL)], check=True)

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(REEL)], capture_output=True, text=True,
        check=True)
    duration = float(json.loads(probe.stdout)["format"]["duration"])
    decode = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(REEL), "-f", "null", "-"],
        capture_output=True, text=True)
    manifest = {
        "version": "owner-action-causality-compare-018-v1",
        "reel": {"path": "OWNER_ACTION_CAUSALITY_COMPARE_018.mp4",
                 "sha256": sha(REEL), "duration_s": duration,
                 "audio": "none",
                 "full_decode": decode.returncode == 0 and
                 not decode.stderr.strip()},
        "blind_section_rule": "the BLIND section carries only neutral "
                              "clip numbers; no intent, no worker "
                              "verdicts; the intent cards come ONLY in "
                              "the second section",
        "segments": seg_rows,
        "surfaces_note": "F2C/G3C canonical = authoritative baselines; "
                         "017 best = motion-only candidates; 018 = "
                         "causal candidates; nothing promoted"}
    (D18 / "owner_action_causality_compare_018.json").write_text(
        json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps({"reel_sha256": manifest["reel"]["sha256"][:16],
                      "duration_s": duration,
                      "full_decode": manifest["reel"]["full_decode"]}))

    # Phase 16: decision template
    template = {
        "version": "owner-action-decisions-template-018-v1",
        "status": "UNPOPULATED - no decision exists; nothing is "
                  "auto-promoted",
        "how_to_review": "watch OWNER_ACTION_CAUSALITY_COMPARE_018.mp4: "
                         "blind section first (clip numbers only), then "
                         "the intent cards; then pick ONE option per "
                         "family",
        "canonical_master_sha256":
            "976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda1786"
            "595",
        "decisions": {
            "F2": {"options": {
                "KEEP_CANONICAL": {"selected": False,
                    "asset_sha256": seg_rows[0]["asset_sha256"]},
                "SELECT_017_C": {"selected": False,
                    "asset_sha256": seg_rows[1]["asset_sha256"]},
                "SELECT_018_A": {"selected": False,
                    "asset_sha256": seg_rows[2]["asset_sha256"],
                    "worker_note_advisory": "trigger+outcome visibly "
                    "rendered; best causal read"},
                "SELECT_018_B": {"selected": False,
                    "asset_sha256": seg_rows[3]["asset_sha256"],
                    "worker_note_advisory": "strong reaction cue; "
                    "through-state less clear than A"},
                "REQUIRES_REDESIGN": {"selected": False},
                "DEFER": {"selected": False}},
                "decision": None, "note": ""},
            "G3": {"options": {
                "KEEP_CANONICAL": {"selected": False,
                    "asset_sha256": seg_rows[4]["asset_sha256"]},
                "SELECT_017_D": {"selected": False,
                    "asset_sha256": seg_rows[5]["asset_sha256"]},
                "SELECT_018_C": {"selected": False,
                    "asset_sha256": seg_rows[6]["asset_sha256"],
                    "worker_note_advisory": "release reads as effort "
                    "leaving the body; minor hair-pin drift flagged; "
                    "arc context comes from G2 in the cut"},
                "REQUIRES_REDESIGN": {"selected": False},
                "DEFER": {"selected": False}},
                "decision": None, "note": ""}},
        "rules": ["no candidate becomes canonical without an explicit "
                  "Owner decision bound to the exact asset SHA",
                  "worker notes are ADVISORY, not truth",
                  "improved meaning does not compensate identity "
                  "regression"]}
    (D18 / "owner_action_decisions_018.template.json").write_text(
        json.dumps(template, indent=1), encoding="utf-8")
    print("decision template written")


if __name__ == "__main__":
    main()
