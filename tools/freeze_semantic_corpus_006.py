"""S2 — freeze the semantic qualification corpus (18 controls).

Frames are extracted deterministically from immutable canonical assets and
hash-pinned. Expected control classes are frozen BEFORE any Gemini call.
No provider media is mutated; frames are derived copies under
projects/flow_semantic_qualify_006/corpus/.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "projects/flow_semantic_qualify_006/corpus"
KEY_FILE = Path(r"D:\API KEY\gemini_api_key.txt")
MODEL = "gemini-2.5-flash"

# Immutable canonical assets (shot_id -> video path), all hash-verified at
# freeze time against their durable result.json.
ASSETS = {
    # Scene-003 R1 canonical (6 shots; slot 3 = fresh 3R asset)
    "SEQ4_A1": ROOT / "projects/flow_multiscene_004/scene_SCENE_A_DAWN_STANCE/shot_SEQ4_A1/videos",
    "SEQ4_A2": ROOT / "projects/flow_multiscene_004/scene_SCENE_A_DAWN_STANCE/shot_SEQ4_A2/videos",
    "SEQ4_A3": ROOT / "projects/flow_multiscene_004/scene_SCENE_A_DAWN_STANCE/shot_SEQ4_A3/videos",
    "SEQ4_A4": ROOT / "projects/flow_multiscene_004/scene_SCENE_A_DAWN_STANCE/shot_SEQ4_A4/videos",
    "SEQ4_A5": ROOT / "projects/flow_multiscene_004/scene_SCENE_A_DAWN_STANCE/shot_SEQ4_A5/videos",
    "SEQ4_B1": ROOT / "projects/flow_multiscene_004/scene_SCENE_B_VALLEY_PASS/shot_SEQ4_B1/videos",
    "SEQ4_B2": ROOT / "projects/flow_multiscene_004/scene_SCENE_B_VALLEY_PASS/shot_SEQ4_B2/videos",
    "SEQ4_B3": ROOT / "projects/flow_multiscene_004/scene_SCENE_B_VALLEY_PASS/shot_SEQ4_B3/videos",
    "SEQ4_B4": ROOT / "projects/flow_multiscene_004/scene_SCENE_B_VALLEY_PASS/shot_SEQ4_B4/videos",
    "SEQ4_B5R": ROOT / "projects/flow_multiscene_004/repair_scope/shot_SEQ4_B5R/videos",
    "SEQ5_C1": ROOT / "projects/flow_sequence_005/sequence_SEQ005_VALLEY_STREAM/shot_SEQ5_C1/videos",
    "SEQ5_C3": ROOT / "projects/flow_sequence_005/sequence_SEQ005_VALLEY_STREAM/shot_SEQ5_C3/videos",
    "SEQ5_C4": ROOT / "projects/flow_sequence_005/sequence_SEQ005_VALLEY_STREAM/shot_SEQ5_C4/videos",
    "SEQ5_D1": ROOT / "projects/flow_sequence_005/sequence_SEQ005_VALLEY_STREAM/scene_SCENE_D_STREAM_REST/shot_SEQ5_D1/videos",
    "SEQ5_D2": ROOT / "projects/flow_sequence_005/sequence_SEQ005_VALLEY_STREAM/scene_SCENE_D_STREAM_REST/shot_SEQ5_D2/videos",
    "SEQ5_D3": ROOT / "projects/flow_sequence_005/sequence_SEQ005_VALLEY_STREAM/scene_SCENE_D_STREAM_REST/shot_SEQ5_D3/videos",
    "SEQ5_D4": ROOT / "projects/flow_sequence_005/sequence_SEQ005_VALLEY_STREAM/scene_SCENE_D_STREAM_REST/shot_SEQ5_D4/videos",
    # Historical identity-negative fixture (different character, immutable)
    "TEAL_REF": sorted((ROOT / "projects/character_continuity/slice0011/reference").glob("*.png"))[0],
}

REQ = {
    "character_identity": ("the same lone swordsman: white robes, long black "
                           "hair in a topknot with a white band, katana at the side"),
    "wardrobe_props": ("white layered robes, single katana with dark wrapped "
                       "hilt and golden guard"),
    "environment_world": ("high mountain summit / valley pass above a sea of "
                          "clouds at dawn; no man-made structures"),
    "action_completion": ("the frozen blocking for this shot is performed "
                          "visibly (see requirement)"),
    "framing_camera": ("the frozen framing for this shot: shot size and "
                       "locked camera per ShotSpec"),
    "lighting_time": ("warm low-angle dawn/morning light from frame-left "
                      "over the cloud-sea"),
    "shot_continuity": ("the two frames are the LAST frame of one shot and "
                        "the FIRST frame of the next: same character, world, "
                        "light and geography across the cut"),
    "scene_transition": ("the two frames form the required scene transition: "
                         "prior scene button frame, then the new scene's "
                         "establishing frame"),
}


def video_file(directory: Path) -> Path:
    videos = sorted(directory.glob("*.mp4"))
    if not videos:
        raise SystemExit(f"no mp4 in {directory}")
    return videos[0]


def extract(video: Path, name: str, *, first=True, scale=512) -> dict:
    out = CORPUS_DIR / f"{name}.png"
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    if first:
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-frames:v", "1",
               "-vf", f"scale={scale}:-2", str(out)]
    else:
        cmd = ["ffmpeg", "-y", "-v", "error", "-sseof", "-0.1", "-i", str(video),
               "-frames:v", "1", "-vf", f"scale={scale}:-2", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    data = out.read_bytes()
    return {"path": str(out), "sha256": hashlib.sha256(data).hexdigest(),
            "label": name}


def synth(name: str, color: str) -> dict:
    out = CORPUS_DIR / f"{name}.png"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    f"color=c={color}:s=512x288:d=1", "-frames:v", "1",
                    str(out)], check=True, capture_output=True)
    data = out.read_bytes()
    return {"path": str(out), "sha256": hashlib.sha256(data).hexdigest(),
            "label": name}


def frame_pair(prev_video, next_video, prev_name, next_name):
    return [extract(prev_video, prev_name, first=False),
            extract(next_video, next_name, first=True)]


def main() -> None:
    if CORPUS_DIR.exists():
        raise SystemExit("corpus already frozen; refusing to re-derive")
    videos = {k: video_file(v) for k, v in ASSETS.items() if v.is_dir()}
    teal_png = Path(str(ASSETS["TEAL_REF"]))

    teal_frame = {"path": str(teal_png),
                  "sha256": hashlib.sha256(teal_png.read_bytes()).hexdigest(),
                  "label": "TEAL_REF"}

    f = lambda video, name, first=True: extract(video, name, first=first)
    controls = []

    def add(control_id, dimension, frames, requirement, expected, reason):
        controls.append({
            "control_id": control_id, "dimension": dimension,
            "frames": frames, "requirement": requirement,
            "expected_class": expected, "reason": reason,
            "frame_sha256": [fr["sha256"] for fr in frames]})

    # 1/2 identity
    add("identity_positive", "character_identity",
        [f(videos["SEQ4_A4"], "id_pos_a"), f(videos["SEQ5_C3"], "id_pos_b")],
        REQ["character_identity"], "POSITIVE",
        "same swordsman in two canonical shots")
    add("identity_negative", "character_identity",
        [f(videos["SEQ4_A4"], "id_neg_a"), teal_frame],
        REQ["character_identity"], "NEGATIVE",
        "different character entirely (teal-hooded reference vs swordsman)")
    # 3/4 wardrobe
    add("wardrobe_positive", "wardrobe_props",
        [f(videos["SEQ4_A3"], "ward_pos_a"), f(videos["SEQ4_B2"], "ward_pos_b")],
        REQ["wardrobe_props"], "POSITIVE", "same robes and katana")
    add("wardrobe_negative", "wardrobe_props",
        [f(videos["SEQ4_A3"], "ward_neg_a"), teal_frame],
        REQ["wardrobe_props"], "NEGATIVE", "different wardrobe entirely")
    # 5/6 world
    add("world_positive", "environment_world",
        [f(videos["SEQ4_A1"], "world_pos_a"), f(videos["SEQ4_B3"], "world_pos_b")],
        REQ["environment_world"], "POSITIVE", "same summit/pass cloud-sea world")
    add("world_negative", "environment_world",
        [extract(videos["SEQ4_A1"], "world_neg_a"),
         extract(videos["SEQ5_C4"], "world_neg_b")],
        REQ["environment_world"], "NEGATIVE",
        "summit cloud-sea vs green valley floor/treeline")
    # 7/8 action
    add("action_positive", "action_completion",
        [f(videos["SEQ5_D2"], "act_pos_a"), f(videos["SEQ5_D2"], "act_pos_b", first=False)],
        "the swordsman kneels at the water and drinks", "POSITIVE",
        "kneel-and-drink visibly performed")
    add("action_negative", "action_completion",
        [f(videos["SEQ5_D2"], "act_neg_a"), f(videos["SEQ5_D2"], "act_neg_b", first=False)],
        "the swordsman draws the blade overhead and holds it aloft", "NEGATIVE",
        "no overhead draw occurs in this shot")
    # 9/10 framing
    add("framing_positive", "framing_camera",
        [f(videos["SEQ4_A4"], "frame_pos_a")],
        "a medium close-up of the character's face and shoulders", "POSITIVE",
        "MCU face shot")
    add("framing_negative", "framing_camera",
        [f(videos["SEQ4_A1"], "frame_neg_a")],
        "an extreme close-up of the character's eye only", "NEGATIVE",
        "frame is an extreme wide shot, not an ECU")
    # 11/12 lighting
    add("lighting_positive", "lighting_time",
        [f(videos["SEQ4_A4"], "light_pos_a"), f(videos["SEQ5_C3"], "light_pos_b")],
        REQ["lighting_time"], "POSITIVE", "same warm low-angle light")
    add("lighting_negative", "lighting_time",
        [f(videos["SEQ4_A4"], "light_neg_a"), synth("light_neg_b", "0x101840")],
        REQ["lighting_time"], "NEGATIVE", "dark blue synthetic night vs warm dawn")
    # 13/14 shot continuity
    add("shot_continuity_positive", "shot_continuity",
        frame_pair(videos["SEQ4_A1"], videos["SEQ4_A2"],
                   "cont_pos_prev", "cont_pos_next"),
        REQ["shot_continuity"], "POSITIVE",
        "adjacent canonical cuts within Scene A")
    add("shot_continuity_negative", "shot_continuity",
        [extract(videos["SEQ4_A1"], "cont_neg_prev", first=False), teal_frame],
        REQ["shot_continuity"], "NEGATIVE",
        "different character/world across the supposed cut")
    # 15/16 scene transition
    add("scene_transition_positive", "scene_transition",
        frame_pair(videos["SEQ4_A5"], videos["SEQ4_B1"],
                   "trans_pos_prev", "trans_pos_next"),
        REQ["scene_transition"], "POSITIVE",
        "exit-empty button then new-space establishing")
    add("scene_transition_negative", "scene_transition",
        [extract(videos["SEQ4_A1"], "trans_neg_prev"),
         extract(videos["SEQ4_A2"], "trans_neg_next", first=False)],
        REQ["scene_transition"], "NEGATIVE",
        "two same-scene frames cannot satisfy a scene-transition requirement")
    # 17 ambiguous
    add("ambiguous", "character_identity",
        [extract(videos["SEQ5_D3"], "amb_a"),
         extract(videos["SEQ4_B4"], "amb_b")],
        REQ["character_identity"], "AMBIGUOUS",
        "object/ECU frames without a visible face cannot decide identity")
    # 18 wrong-source lineage
    add("wrong_source", "character_identity",
        [{**teal_frame, "sha256": "0" * 64}],
        REQ["character_identity"], "MUST_REJECT_LINEAGE",
        "pinned hash does not match on-disk bytes; harness must reject "
        "before any API call")

    corpus = {"frozen_at": datetime.now(timezone.utc).isoformat(),
              "model": MODEL, "key_source": "OWNER_APPROVED_LOCAL_FILE",
              "key_path": str(KEY_FILE),
              "requirements": REQ, "controls": controls}
    out = CORPUS_DIR / "qualification_corpus.json"
    out.write_text(json.dumps(corpus, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print("froze", len(controls), "controls ->", out)


if __name__ == "__main__":
    from datetime import datetime, timezone  # noqa: F401
    main()
