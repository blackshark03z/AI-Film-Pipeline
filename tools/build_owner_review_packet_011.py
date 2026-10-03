"""S7: Owner Review Packet for the Package-009 replacements (F2C/G2C/E2C/G3C)
plus any semantic FAIL/INCONCLUSIVE slot (none — semantic not qualified).
Deterministic frames extracted via ffmpeg; no subjective self-approval.
"""
from __future__ import annotations
import json, subprocess, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M9 = ROOT / "projects/flow_upload_contract_requal_009/master_package_009"
M10 = ROOT / "projects/flow_editorial_runtime_scale_010/master_package_010"
REPROOF = ROOT / "projects/flow_upload_contract_requal_009/reproof"
OUT = ROOT / "projects/flow_semantic_delivery_011/review"
SCENE_OF = {"SEQ7_F2C": "scene_SCENE_F_STORM_GATE",
            "SEQ7_G2C": "scene_SCENE_G_HIGH_PLATEAU",
            "SEQ7_E2C": "scene_SCENE_E_RIDGE_APPROACH",
            "SEQ7_G3C": "scene_SCENE_G_HIGH_PLATEAU"}

summary = json.loads((M10 / "master_summary.json").read_text(encoding="utf-8"))
slots = {s["slot_id"]: s for s in summary["slots"]}
packet = {"version": "owner-review-packet-011-v1", "entries": []}

for successor in ("SEQ7_F2C", "SEQ7_G2C", "SEQ7_E2C", "SEQ7_G3C"):
    scene = SCENE_OF[successor]
    result = json.loads((REPROOF / scene / f"shot_{successor}" /
                         "result.json").read_text(encoding="utf-8"))
    slot = slots[{"SEQ7_F2C": "SEQ7_F2", "SEQ7_G2C": "SEQ7_G2",
                  "SEQ7_E2C": "SEQ7_E2", "SEQ7_G3C": "SEQ7_G3"}[successor]]
    asset_path = Path(result["asset"]["uri_or_path"])
    contact = OUT / f"{successor}_contact.png"
    contact.parent.mkdir(parents=True, exist_ok=True)
    if not contact.exists():
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(asset_path),
                        "-vf", "select='eq(n\,0)+eq(n\,96)+eq(n\,191)',scale=480:-1,tile=3x1",
                        "-frames:v", "1", str(contact)],
                       check=True, capture_output=True)
    packet["entries"].append({
        "canonical_shot_id": slot["slot_id"],
        "successor_id": successor,
        "source_spec": f"fixtures/requal009/{successor}.json",
        "selected_take": slot["selected_take_id"],
        "asset_sha256": result["asset"]["sha256"],
        "provider_output_identity": result.get("output_identity"),
        "editorial_range_file": f"ranges/[{[f for f in __import__('os').listdir(M10 / 'ranges') if slot['slot_id'] in f][0]}]",
        "editorial_range": json.loads(next(
            (M10 / "ranges" / f).read_text(encoding="utf-8")
            for f in sorted(__import__('os').listdir(M10 / "ranges"))
            if slot["slot_id"] in f)),
        "reference_lineage": {
            "kind": result.get("continuity", {}).get("kind"),
            "media_id": result.get("continuity", {}).get("media_id")},
        "contact_sheet": {"path": str(contact),
                          "sha256": hashlib.sha256(contact.read_bytes()).hexdigest()},
        "technical_qc": {"gate": result["gate"],
                         "decode": result.get("decode"),
                         "qc_eligibility": result.get("qc_eligibility")},
        "semantic_qc": "NOT_AVAILABLE (SEMANTIC_QC_NOT_QUALIFIED in 011)",
        "reason_for_review": ("post-gate-invalidated predecessor required a "
                              "fresh clean re-proof; subjective take quality "
                              "is an Owner judgment — not self-approved")})
packet["generated_at"] = "2026-10-03T18:20:00Z"
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "owner_review_packet_011.json").write_text(
    json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({"entries": len(packet["entries"]),
                  "hashes": [e["asset_sha256"][:12] for e in packet["entries"]]}))
