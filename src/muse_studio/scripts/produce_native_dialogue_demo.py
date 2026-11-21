"""
Produce 1-Minute Native Dialogue Film Demo
Quy trình sản xuất phim điện ảnh 1 phút tự động:
1. Đọc SRT & Phân vai Diarization (180-rule)
2. Chuẩn bị 6 first-frame images (1280x720 16:9)
3. Đóng gói BATCH_01_HANDOFF.zip theo chuẩn Codex
4. Sinh Native Dialogue video qua Muse AI
5. Chạy QA/QC 5 Gate (FFmpeg + Faster-Whisper ASR)
6. Hậu kỳ Sample-Accurate Concat + Auto-Ducking BGM + EBU R128 (-16 LUFS)
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Add project root
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from muse_studio.core.srt_diarizer import SRTDiarizer, CharacterProfile, parse_srt, SRTCue
from muse_studio.core.batch_packager import BatchPackager, ShotItem, compute_sha256
from muse_studio.core.film_qc_engine import FilmQCEngine

DEMO_DIR = Path(r"D:\Muse\BLACK_PILOT_DEMO_60S_20261117")
NATIVE_DIR = DEMO_DIR / "NATIVE_PRODUCTION"
NATIVE_DIR.mkdir(parents=True, exist_ok=True)

# 1. KỊCH BẢN ĐỐI THOẠI 6 SHOT (10S MỖI SHOT = 60S TỔNG CỘNG)
DIALOGUE_SPECS = [
    {
        "shot_id": "shot_01",
        "speaker": "Attendant",
        "character": "The flight attendant, a sharp-featured woman in navy cabin crew uniform and red scarf",
        "gaze": "looking screen-left",
        "framing": "medium close-up, screen-right",
        "tone": "in a sharp, confrontational voice",
        "dialogue": "What the hell are you doing up here? This is not a place for jokes.",
        "action": "glares aggressively in the galley, mouth moves naturally speaking English, lips close at end. Hands remain below frame.",
        "ref_source": DEMO_DIR / "FINAL" / "evidence_frames" / "shot_1_evidence.png"
    },
    {
        "shot_id": "shot_02",
        "speaker": "Brianna",
        "character": "Captain Brianna, a poised Black woman in a crisp airline pilot uniform with four gold stripes",
        "gaze": "looking screen-right",
        "framing": "medium close-up, screen-left",
        "tone": "in a calm, authoritative and measured voice",
        "dialogue": "I am Captain Brianna Vance, your pilot today.",
        "action": "stands composed in the galley facing screen-right, steady dignified eyes, clear view of lips. Hands remain below frame.",
        "ref_source": DEMO_DIR / "FINAL" / "evidence_frames" / "shot_2_evidence.png"
    },
    {
        "shot_id": "shot_03",
        "speaker": "Attendant",
        "character": "The flight attendant in navy cabin crew uniform",
        "gaze": "looking screen-left",
        "framing": "close-up, screen-right",
        "tone": "in a contemptuous and sneering voice",
        "dialogue": "It smells like garbage. People like you don't even deserve to sit in economy class.",
        "action": "sneers with lips curling in disdain, speaking with sharp emphasis, lips close at end. Hands remain below frame.",
        "ref_source": DEMO_DIR / "FINAL" / "evidence_frames" / "shot_3_evidence.png"
    },
    {
        "shot_id": "shot_04",
        "speaker": "Attendant",
        "character": "The flight attendant in cabin crew uniform",
        "gaze": "looking screen-left",
        "framing": "medium shot, screen-right",
        "tone": "in a harsh, demanding shout",
        "dialogue": "Get out before I have someone drag you off this plane!",
        "action": "gestures with a firm posture toward the galley exit door, lips moving with sharp intensity. Hands remain below frame.",
        "ref_source": DEMO_DIR / "FINAL" / "evidence_frames" / "shot_4_evidence.png"
    },
    {
        "shot_id": "shot_05",
        "speaker": "Attendant",
        "character": "The flight attendant",
        "gaze": "looking screen-left",
        "framing": "medium close-up on uniform lapel and badge",
        "tone": "yelling in an enraged voice",
        "dialogue": "Security, get this woman off my plane right now!",
        "action": "reaches to snatch the pilot identification badge off the lapel, intense aggressive expression, mouth speaking verbatim English.",
        "ref_source": DEMO_DIR / "FINAL" / "evidence_frames" / "shot_5_evidence.png"
    },
    {
        "shot_id": "shot_06",
        "speaker": "Brianna",
        "character": "Captain Brianna in four-stripe pilot uniform",
        "gaze": "looking screen-right",
        "framing": "medium shot, screen-left",
        "tone": "in a firm, calm and controlled voice",
        "dialogue": "Flight operations, this is Captain Vance on flight 142. We have a security breach in the forward galley.",
        "action": "holds a black smartphone firmly against her right ear, five distinct fingers holding the phone securely, no extra fingers, no finger tapping, jaw set in quiet resolve.",
        "ref_source": DEMO_DIR / "FINAL" / "evidence_frames" / "new_s6b" / "frame_52.0s.png"
    }
]

def step1_prepare_shot_items() -> list[ShotItem]:
    print("[*] STEP 1: Chuẩn bị 6 Shot Items cho Batch...")
    shots_dir = NATIVE_DIR / "shots_input"
    shots_dir.mkdir(parents=True, exist_ok=True)

    items = []
    for spec in DIALOGUE_SPECS:
        s_id = spec["shot_id"]
        img_dest = shots_dir / f"{s_id}_first_frame.png"

        # Copy reference image
        src = spec["ref_source"]
        if not src.exists():
            # Fallback
            src = DEMO_DIR / "FINAL" / "evidence_frames" / "frame_52s.png"
        shutil.copy2(src, img_dest)

        # Biên dịch prompt Native Dialogue theo chuẩn Codex
        prompt = (
            f"The given image is the first frame. A single unbroken 10s shot, no scene cuts, 16:9: "
            f"{spec['framing']} of {spec['character']} {spec['gaze']}. "
            f"[0-0.5s] {spec['framing']} in the established aircraft forward galley, eyes attentive, {spec['gaze']}. "
            f"Clear view of lips. "
            f"[0.5-9s] The speaker says the exact words once with a short, natural breath between sentences. "
            f"{spec['action']} "
            f"[9-10s] Mouth closes and gaze settles. Quiet galley tone. "
            f"No added gesture, lettering, or speech. "
            f"{spec['character']}, {spec['tone']}, says in English: {spec['dialogue']} "
            f"Sound design: quiet airplane cabin ventilation hum, no music. "
            f"Only this character in frame, same cast and wardrobe as the reference. "
            f"No new lettering. No on-screen text, subtitles or logos. Nobody looks into the lens."
        )

        item = ShotItem(
            shot_id=s_id,
            prompt=prompt,
            first_frame_path=img_dest,
            duration_s=10.0,
            aspect_ratio="16:9",
            dialogue=spec["dialogue"],
            speaker=spec["speaker"]
        )
        items.append(item)
        print(f"  [+] {s_id}: {spec['speaker']} -> \"{spec['dialogue'][:50]}...\"")

    return items

def step2_package_batch(items: list[ShotItem]) -> tuple[Path, str]:
    print("\n[*] STEP 2: Đóng gói Batch Handoff ZIP theo chuẩn Codex...")
    batch_zip, relay_msg = BatchPackager.create_batch_handoff(
        batch_id="BLACK_PILOT_NATIVE_BATCH_01",
        shots=items,
        output_dir=NATIVE_DIR
    )
    print(f"  [+] Đã tạo file ZIP: {batch_zip} ({batch_zip.stat().st_size} bytes)")
    print(f"  [+] Relay Message tạo tại: {NATIVE_DIR / 'BLACK_PILOT_NATIVE_BATCH_01_relay_message.txt'}")
    return batch_zip, relay_msg

if __name__ == "__main__":
    items = step1_prepare_shot_items()
    zip_path, msg = step2_package_batch(items)
    print("\n[+] Hoàn tất Step 1 & 2!")
