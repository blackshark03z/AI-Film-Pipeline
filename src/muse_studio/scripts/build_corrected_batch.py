"""
Build and Dispatch Corrected Native Dialogue Batch (Batch 02)
Khắc phục 100% lỗi đảo vai:
- Tiếp viên da trắng tóc vàng: Shots 1, 3, 4, 5
- Cơ trưởng Brianna da đen: Shots 2, 6
"""

import json
import shutil
import sys
from pathlib import Path

# Add project root
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from muse_studio.core.batch_packager import BatchPackager, ShotItem

DEMO_DIR = Path(r"D:\Muse\BLACK_PILOT_DEMO_60S_20261117")
NATIVE_DIR = DEMO_DIR / "NATIVE_PRODUCTION_V2"
NATIVE_DIR.mkdir(parents=True, exist_ok=True)
INPUTS_DIR = NATIVE_DIR / "shots_input"
INPUTS_DIR.mkdir(parents=True, exist_ok=True)

EVIDENCE_DIR = DEMO_DIR / "FINAL" / "evidence_frames"

CORRECTED_SPECS = [
    {
        "shot_id": "shot_01",
        "speaker": "Attendant",
        "actor_type": "Caucasian_Blonde",
        "character": "A 30-year-old blonde Caucasian flight attendant with sharp features, tight blonde hair in a neat bun, red lipstick, wearing a tailored navy blue flight attendant vest, light blue silk neck scarf",
        "gaze": "looking screen-left",
        "framing": "medium close-up, screen-right",
        "tone": "in a sharp, confrontational and aggressive voice",
        "dialogue": "What the hell are you doing up here? This is not a place for jokes.",
        "action": "glares aggressively in the galley, mouth moves naturally speaking English, lips close at end. Hands remain below frame.",
        "first_frame_src": EVIDENCE_DIR / "shot_2_evidence.png" # Blonde Caucasian attendant
    },
    {
        "shot_id": "shot_02",
        "speaker": "Brianna",
        "actor_type": "Black_Captain",
        "character": "Captain Brianna Vance, an elegant African American woman pilot in official commercial airline captain navy blue uniform blazer with four gold stripes on the cuffs and epaulets",
        "gaze": "looking screen-right",
        "framing": "medium close-up, screen-left",
        "tone": "in a calm, resonant and authoritative voice",
        "dialogue": "I am Captain Brianna Vance, your pilot today.",
        "action": "stands composed in the galley facing screen-right, steady dignified eyes, clear view of lips. Hands remain below frame.",
        "first_frame_src": EVIDENCE_DIR / "shot_1_evidence.png" # Black female pilot with 4 gold stripes
    },
    {
        "shot_id": "shot_03",
        "speaker": "Attendant",
        "actor_type": "Caucasian_Blonde",
        "character": "A 30-year-old blonde Caucasian flight attendant with tight blonde hair and red lipstick",
        "gaze": "looking screen-left",
        "framing": "close-up, screen-right",
        "tone": "in a contemptuous and sneering voice",
        "dialogue": "It smells like garbage. People like you don't even deserve to sit in economy class.",
        "action": "sneers with nose wrinkled in disgust, mouth articulating with sharp disdain, lips close at end. Hands remain below frame.",
        "first_frame_src": EVIDENCE_DIR / "shot_2_evidence.png" # Blonde Caucasian attendant sneering
    },
    {
        "shot_id": "shot_04",
        "speaker": "Attendant",
        "actor_type": "Caucasian_Blonde",
        "character": "A blonde Caucasian flight attendant with tight blonde hair and red lipstick in navy vest",
        "gaze": "looking screen-left",
        "framing": "medium shot, screen-right",
        "tone": "in a harsh, demanding shout",
        "dialogue": "Get out before I have someone drag you off this plane!",
        "action": "gestures with firm posture toward the aircraft exit door, lips moving with intense anger, lips close firmly. Hands remain below frame.",
        "first_frame_src": EVIDENCE_DIR / "shot_3_evidence.png" # Blonde Caucasian attendant pointing to exit
    },
    {
        "shot_id": "shot_05",
        "speaker": "Attendant",
        "actor_type": "Caucasian_Blonde",
        "character": "The flight attendant",
        "gaze": "looking screen-left",
        "framing": "medium close-up on uniform lapel and gold wings badge",
        "tone": "yelling in an enraged voice",
        "dialogue": "Security, get this woman off my plane right now!",
        "action": "reaches to snatch the pilot identification badge off the lapel, intense aggressive expression, mouth speaking verbatim English.",
        "first_frame_src": EVIDENCE_DIR / "shot_5_evidence.png" # Badge rip close-up
    },
    {
        "shot_id": "shot_06",
        "speaker": "Brianna",
        "actor_type": "Black_Captain",
        "character": "Captain Brianna Vance, an African American woman pilot in four-stripe uniform",
        "gaze": "looking screen-right",
        "framing": "medium shot, screen-left",
        "tone": "in a firm, calm and controlled voice",
        "dialogue": "Flight operations, this is Captain Vance on flight 142. We have a security breach in the forward galley.",
        "action": "holds a black smartphone firmly against her right ear, five distinct fingers holding the phone securely, no extra fingers, no finger tapping, jaw set in quiet resolve.",
        "first_frame_src": EVIDENCE_DIR / "new_s6b" / "frame_52.0s.png" # Black female pilot with phone (5 clean fingers)
    }
]

def build_corrected_batch():
    print("[*] STEP 1: Chuẩn bị 6 Shot Items đã gán đúng nhân vật...")
    items = []
    for spec in CORRECTED_SPECS:
        s_id = spec["shot_id"]
        img_dest = INPUTS_DIR / f"{s_id}_first_frame.png"
        shutil.copy2(spec["first_frame_src"], img_dest)

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
        print(f"  [+] {s_id} [{spec['actor_type']}]: {spec['speaker']} -> \"{spec['dialogue'][:50]}...\"")

    batch_zip, relay_msg = BatchPackager.create_batch_handoff(
        batch_id="BLACK_PILOT_NATIVE_BATCH_02",
        shots=items,
        output_dir=NATIVE_DIR
    )
    print(f"\n[+] ĐÃ ĐÓNG GÓI XONG: {batch_zip} ({batch_zip.stat().st_size} bytes)")
    print(f"[+] Relay message: {NATIVE_DIR / 'BLACK_PILOT_NATIVE_BATCH_02_relay_message.txt'}")
    return batch_zip, relay_msg

if __name__ == "__main__":
    build_corrected_batch()
