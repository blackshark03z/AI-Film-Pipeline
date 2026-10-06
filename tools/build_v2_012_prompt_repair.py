"""V2-012 Phase 0/1 — prompt audit, repaired spec, and prompt diff.

Fail-closed: verifies the frozen 011D F3R prompt SHA before writing anything.
The exact provider-policy trigger stays UNKNOWN (no hypothesis promoted).
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P11D = ROOT / "projects/quality_v2_011d_world_matched_context"
PKG = ROOT / "projects/quality_v2_012_f3r_policy_repair"
FROZEN_SHA = "4066ab6f755475cd5d2797e4a8d3edc9282205e06fcbccfad38b4a7e73625405"


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def write(name, payload):
    (PKG / name).write_text(json.dumps(payload, indent=1,
                                       ensure_ascii=False), encoding="utf-8")
    print("wrote", name)


def main():
    PKG.mkdir(parents=True, exist_ok=True)
    (PKG / "outputs").mkdir(exist_ok=True)
    (PKG / "owner_review_012").mkdir(exist_ok=True)
    (PKG / "assets").mkdir(exist_ok=True)

    old_spec = json.loads(
        (P11D / "V2_011D_F3R_SPEC.json").read_text(encoding="utf-8"))
    old_prompt = old_spec["prompt"]
    got = hashlib.sha256(old_prompt.encode()).hexdigest()
    assert got == FROZEN_SHA, f"frozen prompt mismatch: {got}"
    print("frozen 011D F3R prompt verified:", got[:16])

    # ------------------------------------------------------------- audit
    write("V2_012_F3R_PROMPT_AUDIT.json", {
        "version": "v2-012-f3r-prompt-audit-v1",
        "checkpoint": "V2012_P0_PROMPT_AUDIT",
        "recorded_at": utcnow(),
        "audited_prompt_sha256": got,
        "proven": {
            "provider_refused_the_exact_prior_prompt": True,
            "release_was_accepted_and_billed": True,
            "refusal_text": "当社のポリシーに違反する可能性がある内容が入力されているため、動画を生成できません。",
        },
        "unknown": {
            "exact_policy_trigger": "UNKNOWN — which token, phrase, or "
                "semantic relation tripped the filter is not proven. Filter "
                "neutrality IS proven for several components by the accepted "
                "F2A-R/F2B-R prompts (which contained 'swordsman', 'No "
                "sword', storm/wind language, and passed the same filter "
                "family). The F3R-specific differences (face close-up "
                "framing, hair-whip wording, abstract 'cost' phrasing) are "
                "RECORDED as audit observations only — no hypothesis is "
                "promoted to canonical truth.",
        },
        "components": {
            "A_required_cinematic_intent": [
                "medium close-up of the protagonist pausing beside the rock "
                "face after the crossing",
                "the settle/resolve beat ('the cost, held') — narrative "
                "authority; the literal phrase need not appear in the prompt",
            ],
            "B_world_continuity": [
                "natural dark jagged rock face — rough natural stone, part "
                "of the continuous mountain ridge",
                "cold storm-blue light, heavy overcast sky",
                "negative block: no brick / cut stone / masonry / built wall "
                "/ architecture",
            ],
            "C_character_continuity": [
                "flowing white robes, black sash, topknot (text identity, "
                "0 uploads — the 011R/011D proven route)",
            ],
            "D_camera_composition": [
                "5-second, 16:9, locked camera",
                "medium close-up, face and shoulders, three-quarter profile",
                "facing the LEFT of the frame; eyeline down the road ahead",
            ],
            "E_performance": [
                "jaw sets, one slow breath, still, holding against the wind",
                "headband and loose robe ends stream leeward to the right",
                "strands of hair whip across his face",
                "storm gust keeps pulling",
            ],
            "F_optional_wording": [
                "'portrait'", "'the same swordsman'", "'pressed close "
                "against'", "'Generate a 5-second cinematic video'",
            ],
            "G_possibly_ambiguous_wording": [
                "audit observations only — trigger UNKNOWN:",
                "'strands of hair whip across his face' (whip + face "
                "proximity)",
                "'the cost held' (abstract harm-adjacent noun 'cost')",
                "'eyes narrowed' (aggression/pain adjacency)",
                "'swordsman' + 'No sword' (weapon token family — PROVEN "
                "filter-neutral by the accepted F2A-R/F2B-R prompts)",
                "'pressed close against' (proximity phrasing)",
            ],
            "H_unnecessary_language": [
                "'portrait' (redundant with 'medium close-up')",
                "'pressed' (the composition survives with 'stands safely "
                "beside')",
                "'whip' (the wind-in-hair visual survives with neutral "
                "wording)",
                "'the cost held' as literal prompt text (the beat is fully "
                "expressed by concrete observable language)",
            ],
        },
    })

    # ------------------------------------------------------- repaired prompt
    repaired_prompt = (
        "Generate a 5-second cinematic video, 16:9, locked camera. "
        "Medium close-up: the same adult traveler in flowing white robes "
        "with a black sash and a topknot stands safely beside a natural "
        "dark jagged rock face — rough natural stone, part of the "
        "continuous mountain ridge. His face and shoulders are in "
        "three-quarter profile facing the LEFT of the frame, with a steady "
        "gaze down the road ahead to the left. After crossing the mountain "
        "pass, his breathing settles; his expression becomes calm, "
        "determined, and reflective, and he stands still and steady against "
        "the wind. The storm wind keeps blowing: his headband and the loose "
        "ends of his robes stream leeward to the right, and the wind moves "
        "his hair. Cool storm-blue light, heavy overcast sky. No sword, no "
        "scabbard, no weapon. No brick, no cut stone, no masonry, no built "
        "wall, no architecture — natural rock only.")
    repaired_sha = hashlib.sha256(repaired_prompt.encode()).hexdigest()
    print("repaired prompt sha256:", repaired_sha[:16])

    write("V2_012_F3R_REPAIRED_SPEC.json", {
        "version": "v2-012-f3r-repaired-spec-v1",
        "checkpoint": "V2012_P1_REPAIRED_SPEC_FROZEN",
        "shot_id": "SEQ7_F3_R12",
        "budget_kind": "f3r_012",
        "mutation_authorization": "exactly ONE generate, no retry, no "
                                  "provider switch (V2-012 MAX=1)",
        "authority": "V2-012 package; world = SEQ7_WORLD_LOCK_FROM_F2 end "
                     "region; original intent = fixtures/sequence007/"
                     "SEQ7_F3.json + frozen V2-011D F3R spec",
        "repair_principle": "rewrite toward observable filmmaking "
                            "instructions; concrete benign visual language; "
                            "NO safety-evasion (no euphemism, no obfuscation "
                            "— the scene itself is made clearer and benign)",
        "preserved_frozen_intent": {
            "shot_type": "medium close-up, face and shoulders, three-quarter "
                         "profile, locked camera",
            "character": "same adult protagonist: flowing white robes, black "
                         "sash, topknot, headband; identity continuity",
            "orientation": "faces frame-left; eyeline down the road ahead",
            "world": "natural dark jagged rock face of the locked-F2 family; "
                     "cold blue-grey storm; heavy overcast; no masonry "
                     "architecture",
            "performance": "post-traversal breathing settles; calm, "
                           "determined, reflective; stands still against the "
                           "wind; wind in headband/robes/hair",
            "narrative_function": "the cost, held — expressed as concrete "
                                  "observable resolve (literal phrase "
                                  "intentionally not reproduced)",
        },
        "world_lock_ref": "../quality_v2_011d_world_matched_context/"
                          "V2_011D_WORLD_LOCK.json (end region: luma 99.10, "
                          "U 141.53, V 112.97)",
        "prompt": repaired_prompt,
        "prompt_sha256": repaired_sha,
        "editorial": {
            "fps": 24,
            "provider_duration_class_s": 5,
            "planned_base_frames": [0, 76],
            "allowed_trim": "IN within 0..12 chosen by junction QC; OUT "
                            "follows IN (IN+77) preserving 3.208333s",
        },
        "hard_qc_items": {
            "world": "natural dark rock, F2 family, no masonry, cold storm "
                     "lighting",
            "identity": "same protagonist, same wardrobe/look, no "
                        "unexplained prop",
            "composition": "medium close framing, faces frame-left, "
                           "compatible eyeline",
            "performance": "post-traversal settle, calm determination, "
                           "reflective resolve; no unintended "
                           "panic/aggression",
        },
    })

    # ------------------------------------------------------------ diff
    write("V2_012_F3R_PROMPT_DIFF.json", {
        "version": "v2-012-f3r-prompt-diff-v1",
        "recorded_at": utcnow(),
        "old_prompt_sha256": got,
        "new_prompt_sha256": repaired_sha,
        "reason_vocabulary": ["CLARIFY_BENIGN_ACTION",
                              "REMOVE_NONESSENTIAL_AMBIGUITY",
                              "MAKE_VISUAL_INTENT_EXPLICIT",
                              "PRESERVE_WORLD_CONTINUITY",
                              "PRESERVE_PERFORMANCE_INTENT"],
        "forbidden_reason": "BYPASS_PROVIDER_FILTER (none used — every change "
                            "makes the scene clearer, simpler, and explicitly "
                            "benign; nothing is disguised or encoded)",
        "changes": [
            {"old": "Medium close-up portrait: the same swordsman",
             "new": "Medium close-up: the same adult traveler",
             "reason": "MAKE_VISUAL_INTENT_EXPLICIT",
             "note": "Owner-suggested benign identity noun; shot type "
                     "unchanged; 'portrait' dropped (H: redundant)"},
            {"old": "stands pressed close against a natural dark jagged rock "
                    "face",
             "new": "stands safely beside a natural dark jagged rock face",
             "reason": "CLARIFY_BENIGN_ACTION",
             "note": "proximity phrasing -> explicit safe adjacency; the "
                     "composition (beside the rock face) is unchanged"},
            {"old": "eyes narrowed, looking down the road ahead",
             "new": "with a steady gaze down the road ahead",
             "reason": "REMOVE_NONESSENTIAL_AMBIGUITY",
             "note": "eyeline preserved exactly; 'narrowed' removed"},
            {"old": "He sets his jaw and takes one slow breath: the cost "
                    "held, still, holding against the wind.",
             "new": "After crossing the mountain pass, his breathing "
                    "settles; his expression becomes calm, determined, and "
                    "reflective, and he stands still and steady against the "
                    "wind.",
             "reason": "CLARIFY_BENIGN_ACTION",
             "note": "the abstract 'cost held' is expressed as concrete "
                     "observable resolve; the narrative beat is fully "
                     "preserved (mission authorizes dropping the literal "
                     "phrase)"},
            {"old": "The storm gust keeps pulling:",
             "new": "The storm wind keeps blowing:",
             "reason": "CLARIFY_BENIGN_ACTION",
             "note": "neutral wind verb; visual identical"},
            {"old": "strands of hair whip across his face",
             "new": "the wind moves his hair",
             "reason": "REMOVE_NONESSENTIAL_AMBIGUITY",
             "note": "wind-in-hair visual preserved; 'whip across face' "
                     "removed"},
            {"old": "the same swordsman in flowing white robes",
             "new": "the same adult traveler in flowing white robes",
             "reason": "MAKE_VISUAL_INTENT_EXPLICIT",
             "note": "identity carried entirely by the wardrobe description "
                     "(the 011R-proven mechanism); recorded WITHOUT a "
                     "trigger claim: 'swordsman' is proven filter-neutral by "
                     "the accepted F2A-R/F2B-R prompts"},
            {"old": "No sword, no scabbard, no weapon.",
             "new": "No sword, no scabbard, no weapon.  (KEPT verbatim)",
             "reason": "PRESERVE_WORLD_CONTINUITY",
             "note": "PROVEN filter-neutral (F2A-R/F2B-R accepted with this "
                     "exact block); it protects the no-prop continuity "
                     "requirement — removing it could let a prop drift in "
                     "and waste the mutation on a QC failure"},
            {"old": "No brick, no cut stone, no masonry, no built wall, no "
                    "architecture — natural rock only.",
             "new": "unchanged verbatim",
             "reason": "PRESERVE_WORLD_CONTINUITY",
             "note": "proven filter-neutral world block"},
        ],
        "explicitly_not_changed": [
            "shot type (medium close-up is frozen intent)",
            "framing/orientation (three-quarter profile, facing LEFT, "
            "eyeline)",
            "world block (natural dark jagged rock, storm-blue, overcast)",
            "identity wardrobe description",
            "duration class (5s), aspect (16:9), locked camera",
        ],
    })
    print("PHASE 0/1 complete")


if __name__ == "__main__":
    main()
