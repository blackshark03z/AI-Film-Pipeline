"""V2-011D — F1R hard QC record + knowledge reconciliation (read-only writes)."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_011d_world_matched_context"
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
from mutation_authority import MutationAuthority  # noqa: E402


def utcnow():
    return datetime.now(timezone.utc).isoformat()


recon = json.loads((PKG / "V2_011D_F1R_CREATION_DUMP.json").read_text(encoding="utf-8"))
creation = recon["type2_creations"][0]
c = creation["creation"]
v = c["video"]
asset = PKG / "assets" / "f1r.mp4"
sha = hashlib.sha256(asset.read_bytes()).hexdigest()
frames = len(list((PKG / "frames_f1r").glob("F1R_*.png")))

qc = {
    "version": "v2-011d-f1r-qc-v1",
    "checkpoint": "V2011D_P2B_F1R_HARD_QC",
    "recorded_at": utcnow(),
    "shot_id": "SEQ7_F1_R",
    "asset": {
        "path": "assets/f1r.mp4",
        "sha256": sha,
        "provider_duration_s": v.get("duration"),
        "probe": {"frames": frames, "fps": "24/1", "codec": "hevc",
                  "audio": "aac", "width": 1280, "height": 720,
                  "duration_s": 5.088005},
    },
    "provider_lineage": {
        "conversation_id": recon["f1r_conversation_id"],
        "creation_id": c.get("id"),
        "vid": v.get("vid"),
        "model_statement": "Seedance 2.0 (provider message: 動画はSeedance 2.0モデルを使用して)",
        "provider_credit_ack": "本日の残りは0動画クレジットです (provider statement in-conversation — mutation billed; ACCOUNT_A now 0)",
        "download_filehash": v.get("download_filehash"),
        "acquisition": "READ-ONLY reconcile: one-shot full creation-object dump located the signed download_url (the limit-20 conversation poll used by the live runner returns the creation WITHOUT the url field — recorded as a delivery-shape variance; the limit-10 poll returns it); direct HTTP acquisition, no dispatch",
    },
    "hard_qc": {
        "natural_ridge": {"verdict": "PASS", "evidence": "towering continuous dark natural rock wall, rough stone, fills frame both sides (contact sheet + end zooms)"},
        "single_opening": {"verdict": "PASS", "evidence": "one narrow glowing mist slot; the road leads into it"},
        "no_decorative_gate": {"verdict": "PASS", "evidence": "no freestanding stones, no wooden lintel/crossbeam, no architecture anywhere in frame"},
        "no_open_field_bypass": {"verdict": "PASS", "evidence": "ridge extends beyond both lateral sides of the opening; no bypass or open horizon behind the gap"},
        "cold_storm_palette": {"verdict": "PASS", "evidence": "measured luma 67.80 (F2 start target 83.63 — same dark storm family; old F1 was 102.07 warm), U 139.04 vs target 139.85, V 114.94 vs 114.52 — chroma near-exact match; heavy overcast/mist; zero warm light"},
        "frame_left": {"verdict": "PASS", "evidence": "character enters frame-right, travels and faces frame-left across all 121 frames"},
        "identity": {"verdict": "PASS", "evidence": "white robes + black sash + topknot with streaming headband; suspected long object on the back resolved at full-res zoom as the wind-whipped headband ribbon — NO sword, scabbard or weapon in any frame"},
    },
    "editorial_observations": {
        "scale_step": "very wide establishing shot; the locked F2 starts closer — WS->closer cut-in is standard grammar",
        "end_state": "shot ends mid-approach, close to the gap, leaning into the gust — matches the F1 fixture end beat ('close to the pass, leaning')",
        "gap_interior": "F1R gap reads as a bright mist slot at distance; locked F2 gap interior is darker at entry — atmospheric distance difference, landmark identity (single gap in continuous dark ridge) unambiguous",
        "trim_window_effective": "asset has 121 frames (0..120): base OUT exclusive 115 (F1-slot parity 4.791667s); +/-12 window clips to exclusive end 103..121 (max +6 beyond base)",
    },
    "verdict": "F1R_ACCEPTED",
    "critical_failures": [],
}
(PKG / "V2_011D_F1R_QC.json").write_text(json.dumps(qc, indent=1, ensure_ascii=False), encoding="utf-8")
print("wrote V2_011D_F1R_QC.json — verdict:", qc["verdict"])

auth = MutationAuthority(PKG / "slot_f1r", "QUALITY-V2-011D-WORLD-MATCHED-CONTEXT/F1R")
auth.record_knowledge(
    "RESOLVED_EFFECT_IDENTIFIED",
    f"released F1R completed (Seedance 2.0); acquired sha256 {sha[:16]}…; "
    f"hard QC F1R_ACCEPTED; provider billed the mutation (remaining 0)")
print("knowledge resolved: RESOLVED_EFFECT_IDENTIFIED")
