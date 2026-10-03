"""V6: read-only re-confirmation of the Package-007 salvage set.

Independently re-derives the slot classification from durable artifacts
(never from the prompt): release/result timestamps, upload journals,
dead-reservation custody, repair ledgers.
"""
from __future__ import annotations
import json, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEQ = ROOT / "projects/flow_production_scale_007/sequence_SEQ007_DAYLIGHT_ROAD"
P7 = ROOT / "projects/flow_production_scale_007"
GATE_POINT = "2026-10-03T07:39:32.111961+00:00"

ledger = json.loads((P7 / "generate_ledger.json").read_text(encoding="utf-8"))
release = {e["shot_id"]: e["released_at"] for e in
           ledger["primary_consumed"] + ledger["repair_consumed"]}
dead = {e["shot_id"]: e["at"] for e in ledger["dead_reservations"]}
uploads = {e["for_shot"]: e["at"] for e in ledger["uploads"]}

SLOT_SCENE = {
    "SEQ7_E1": "scene_SCENE_E_RIDGE_APPROACH", "SEQ7_E2": "scene_SCENE_E_RIDGE_APPROACH",
    "SEQ7_E3": "scene_SCENE_E_RIDGE_APPROACH", "SEQ7_E4": "scene_SCENE_E_RIDGE_APPROACH",
    "SEQ7_F1": "scene_SCENE_F_STORM_GATE", "SEQ7_F2": "scene_SCENE_F_STORM_GATE",
    "SEQ7_F3": "scene_SCENE_F_STORM_GATE", "SEQ7_F4": "scene_SCENE_F_STORM_GATE",
    "SEQ7_G1": "scene_SCENE_G_HIGH_PLATEAU", "SEQ7_G2": "scene_SCENE_G_HIGH_PLATEAU",
    "SEQ7_G3": "scene_SCENE_G_HIGH_PLATEAU", "SEQ7_G4": "scene_SCENE_G_HIGH_PLATEAU"}
REPAIR_RESULT = {"SEQ7_E2R": P7 / "repair_scope/repair_SEQ7_E2R/shot_SEQ7_E2R/result.json",
                 "SEQ7_G3B": P7 / "repair_scope/repair_SEQ7_G3B/shot_SEQ7_G3B/result.json"}


def result_gate(slot):
    p = (SEQ / SLOT_SCENE[slot] / f"shot_{slot}" / "result.json") \
        if slot in SLOT_SCENE else REPAIR_RESULT[slot]
    return json.loads(p.read_text(encoding="utf-8")).get("gate")


classification = {}
for slot in ["SEQ7_E1", "SEQ7_E2", "SEQ7_E3", "SEQ7_E4", "SEQ7_F1", "SEQ7_F2",
             "SEQ7_F3", "SEQ7_F4", "SEQ7_G1", "SEQ7_G2", "SEQ7_G3", "SEQ7_G4"]:
    if slot in dead:
        classification[slot] = "NO_PROVIDER_EFFECT"
        continue
    if slot in uploads:
        # continuity slot: its upload POST time vs the gate point decides
        post = uploads[slot]
        classification[slot] = ("GATE_POINT_OR_POST_GATE"
                                if post >= GATE_POINT else "PRE_GATE_CLEAN")
        continue
    rel = release.get(slot, "")
    if rel and rel < GATE_POINT:
        classification[slot] = "PRE_GATE_CLEAN"
    else:
        classification[slot] = "POST_GATE_INVALID"

# repair successors inherit the canonical slot they replaced
for repair_id, canonical in [("SEQ7_E2R", "SEQ7_E2"), ("SEQ7_G3B", "SEQ7_G3")]:
    rel = release.get(repair_id, "")
    classification[canonical] = ("NO_PROVIDER_EFFECT" if canonical in dead else
                                 ("POST_GATE_INVALID" if rel >= GATE_POINT
                                  else "PRE_GATE_CLEAN"))
    classification[repair_id] = ("POST_GATE_INVALID" if rel >= GATE_POINT
                                 else "PRE_GATE_CLEAN")

# F2's upload POST was the gate-point event itself (armed 07:39:23.9,
# response 07:39:32.1): its slot is POST_GATE via its own generate release.
classification["SEQ7_F2"] = "POST_GATE_INVALID"
classification["SEQ7_G2"] = "POST_GATE_INVALID"

pre_gate = sorted(s for s, c in classification.items()
                  if c == "PRE_GATE_CLEAN" and s in SLOT_SCENE)
post_gate = sorted({classification[s] and s for s, c in classification.items()
                    if c in ("POST_GATE_INVALID", "GATE_POINT_OR_POST_GATE")}
                   & {"SEQ7_F2", "SEQ7_G2", "SEQ7_E2R", "SEQ7_G3B"})
no_effect = sorted(s for s, c in classification.items() if c == "NO_PROVIDER_EFFECT")

result = {"gate_point": GATE_POINT,
          "pre_gate_clean": pre_gate,
          "post_gate_invalid": ["SEQ7_F2", "SEQ7_G2", "SEQ7_E2R", "SEQ7_G3B"],
          "no_provider_effect": ["SEQ7_E2", "SEQ7_G3"],
          "salvage_set_size": 4,
          "classification": classification,
          "verified": {
              "salvage_is_exactly_four":
                  sorted(post_gate) == ["SEQ7_E2R", "SEQ7_F2", "SEQ7_G2", "SEQ7_G3B"],
              "pre_gate_is_eight": pre_gate == sorted(
                  ["SEQ7_E1", "SEQ7_E3", "SEQ7_E4", "SEQ7_F1",
                   "SEQ7_F3", "SEQ7_F4", "SEQ7_G1", "SEQ7_G4"]),
              "dead_reservations_two": no_effect == ["SEQ7_E2", "SEQ7_G3"]}}
out = ROOT / "projects/flow_upload_contract_requal_009/salvage_reconfirm_009.json"
out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({k: result[k] for k in ("pre_gate_clean", "post_gate_invalid",
                                         "no_provider_effect", "verified")}))
