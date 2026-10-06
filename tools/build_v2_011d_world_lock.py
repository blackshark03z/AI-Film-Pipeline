"""V2-011D Phase 1 — SEQ7_WORLD_LOCK_FROM_F2.

Derives the world authority for F1R/F3R from the ACTUAL accepted locked F2
imagery (not from prose): copies the locked proof into 011D custody
(sha-verified), extracts start/end region reference frames, and measures the
palette targets the repairs must match. Read-only w.r.t. F2.
"""
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "projects/quality_v2_011b_editorial_assembly/outputs/F2_SEQUENCE_EDITORIAL_PROOF.mp4"
PKG = ROOT / "projects/quality_v2_011d_world_matched_context"
FR = PKG / "world_reference_frames"
EXPECT_SHA = "ada66463983636e505b181d5b81b10c6a7f4da8cdd1a80aff55880dd8fd820de"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def measure(video: Path, start_frame: int, end_frame: int) -> dict:
    """YAVG/Usat-VAVG luma+chroma means over a frame range."""
    vf = (f"trim=start_frame={start_frame}:end_frame={end_frame},"
          f"setpts=PTS-STARTPTS,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-")
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", vf,
                        "-an", "-f", "null", "-"], capture_output=True, text=True)
    lumas = [float(m) for m in re.findall(r"YAVG=([\d.]+)", r.stdout)]
    vf_u = (f"trim=start_frame={start_frame}:end_frame={end_frame},"
            f"setpts=PTS-STARTPTS,signalstats,metadata=print:key=lavfi.signalstats.UAVG:file=-")
    r_u = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", vf_u,
                          "-an", "-f", "null", "-"], capture_output=True, text=True)
    us = [float(m) for m in re.findall(r"UAVG=([\d.]+)", r_u.stdout)]
    vf_v = (f"trim=start_frame={start_frame}:end_frame={end_frame},"
            f"setpts=PTS-STARTPTS,signalstats,metadata=print:key=lavfi.signalstats.VAVG:file=-")
    r_v = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", vf_v,
                          "-an", "-f", "null", "-"], capture_output=True, text=True)
    vs = [float(m) for m in re.findall(r"VAVG=([\d.]+)", r_v.stdout)]
    n = len(lumas)
    return {"frames_measured": n,
            "luma_mean": round(sum(lumas) / n, 2) if n else None,
            "u_mean": round(sum(us) / n, 2) if us else None,
            "v_mean": round(sum(vs) / n, 2) if vs else None}


def main() -> None:
    PKG.mkdir(parents=True, exist_ok=True)
    (PKG / "assets").mkdir(exist_ok=True)
    (PKG / "outputs").mkdir(exist_ok=True)
    (PKG / "owner_review_011d").mkdir(exist_ok=True)
    FR.mkdir(exist_ok=True)

    locked = PKG / "inputs_F2_proof.mp4"
    shutil.copyfile(SRC, locked)
    got = sha256(locked)
    assert got == EXPECT_SHA, f"F2 proof custody mismatch: {got}"
    print("F2 proof copied, sha verified:", got[:16])

    # start region (F2A approach world — F1R target): frames 0..23
    # end region (F2B exit world — F3R target): frames 110..133
    regions = {}
    for name, lo, hi in (("f2_start_region", 0, 24), ("f2_end_region", 110, 134)):
        for n in range(lo, hi, 2):
            subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(locked),
                            "-vf", f"select=eq(n\\,{n})", "-vframes", "1", "-y",
                            str(FR / f"{name}_n{n:03d}.png")], check=True)
        regions[name] = measure(locked, lo, hi)
        print(name, regions[name])

    world = {
        "version": "v2-011d-world-lock-v1",
        "world_lock_id": "SEQ7_WORLD_LOCK_FROM_F2",
        "checkpoint": "V2011D_P1_WORLD_LOCK",
        "created_at": utcnow(),
        "derived_from": {
            "authority": "the ACTUAL accepted locked F2 imagery (F2_CREATIVE_LOCK GRANTED via Owner ruling; F2_EDITORIAL_LOCK GRANTED) + V2-011C junction findings + frozen V2-009 traversal geometry TG-eac7757544b0d950 / causal environment CE-88efa70391fb228e",
            "locked_f2_proof_sha256": got,
            "start_region_frames": [0, 23],
            "end_region_frames": [110, 133],
            "reference_frames_dir": "world_reference_frames/",
        },
        "palette_measurements": regions,
        "required": [
            "continuous natural dark rock ridge (rough natural stone, no built architecture)",
            "single narrow choke point (the only walkable gap)",
            "road funnels through the opening",
            "ridge extends beyond the opening on both lateral sides, closing every bypass",
            "cold blue-grey storm palette",
            "heavy overcast storm sky",
            "wind-exposed environment (wind funnels through the pass against travel)",
            "swordsman identity: flowing white robes with a black sash and a topknot (text identity, 0 uploads — the 011R proven route)",
        ],
        "forbidden": [
            "freestanding decorative gate",
            "standing-stone gate structure",
            "wooden lintel/crossbeam",
            "castle",
            "fortress",
            "cut masonry",
            "tan built wall",
            "parapet",
            "open-field bypass",
            "warm golden sunlight",
            "sword / scabbard / any visible weapon",
        ],
        "repair_application": {
            "F1R": "start region world (frames 0-23): dark ridge face left-of-frame character approach, cold blue-grey flat storm light",
            "F3R": "end region world (frames 110-133): natural dark jagged rock face beside the track, same storm state",
        },
        "f2_immutability": "F2_SEQUENCE_LOCKED_v1 untouched; this lock only governs NEW F1R/F3R renders",
    }
    out = PKG / "V2_011D_WORLD_LOCK.json"
    out.write_text(json.dumps(world, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
