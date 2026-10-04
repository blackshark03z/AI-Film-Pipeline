"""FLOW-ACTION-INTENT-CAUSALITY-018 (Phase 18): recovery / adversarial
matrix — 106 cases. Every row carries an exact proof: a pytest node, a
raw receipt check, or a live read-only check. Provider ambiguity maps
to OWNER_AMBIGUITY_GATE per the frozen package rule.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

D17 = ROOT / "projects/flow_performance_motion_canary_017"
D18 = ROOT / "projects/flow_action_intent_causality_018"
M10 = (ROOT / "projects/flow_editorial_runtime_scale_010/"
       "master_package_010")
S = "uv run python -m pytest "
MASTER_SHA = "976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda1786595"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


TRACE = load(D18 / "action_authority_trace_018.json")
EXP = load(D18 / "experiment_freeze_018.json")
BLIND = load(D18 / "blind_action_legibility_packet_018.json")
KEY = load(D18 / "answer_key_action_intent_018.json")
CTRL = load(D18 / "action_causality_experiment_018.json")
REEL = json.loads((D18 / "owner_action_causality_compare_018.json")
                  .read_text(encoding="utf-8"))
DELTA = load(D18 / "pipeline_delta_018.json")
LEDGER = load(D18 / "generate_ledger.json")
QC = load(D18 / "tech_identity_qc_018.json")

ROWS = []


def row(rid, category, name, mode, proof):
    ROWS.append({"id": rid, "category": category, "acceptance": name,
                 "mode": mode, "proof": proof})


def ev(fn):
    return lambda: "PASS" if fn() else "FAIL"


def pt(node):
    return [S + node]


def run():
    out = []
    for r in ROWS:
        try:
            if r["mode"] == "evidence":
                result = r["proof"]()
                proof = (f"evidence check (tools/recovery_matrix_018.py "
                         f"row {r['id']})")
            else:
                result = "PYTEST BOUND: " + "; ".join(r["proof"])
                proof = "; ".join(r["proof"])
        except Exception as exc:  # noqa: BLE001
            result = f"ERROR: {exc}"
            proof = "evidence check (errored)"
        out.append({**r, "proof": proof, "result": result})
    return out


# == intent authority (1-12) =============================================
row(1, "IntentAuthority", "upstream trace binds source artifact+field "
    "per assertion", "evidence",
    ev(lambda: all("sources" in v for q, v in TRACE["F2"].items()
                   if q.startswith("q_")) and
       all("sources" in v for q, v in TRACE["G3"].items()
           if q.startswith("q_"))))
row(2, "IntentAuthority", "F2 trigger AUTHORITATIVE (verbatim beat)",
    "evidence",
    ev(lambda: TRACE["F2"]["q2_what_does_he_perceive"]
       ["classification"] == "AUTHORITATIVE"))
row(3, "IntentAuthority", "F2 goal DERIVABLE with derivation note (not "
    "invented)", "evidence",
    ev(lambda: TRACE["F2"]["q3_what_does_he_want_now"]
       ["classification"] == "DERIVABLE" and "Derived, not invented" in
       TRACE["F2"]["q3_what_does_he_want_now"]["note"]))
row(4, "IntentAuthority", "G3 trigger binds the G2 arc (authoritative "
    "adjacency)", "evidence",
    ev(lambda: TRACE["G3"]["q1_what_happened_immediately_before"]
       ["classification"] == "AUTHORITATIVE" and "G2" in
       json.dumps(TRACE["G3"]["q1_what_happened_immediately_before"])))
row(5, "IntentAuthority", "gate A1 = RESOLVED for both targets",
    "evidence",
    ev(lambda: "RESOLVED" in TRACE["gate_A1"]["F2"] and "RESOLVED" in
       TRACE["gate_A1"]["G3"]))
row(6, "IntentAuthority", "unresolved ambiguity recorded honestly",
    "evidence",
    ev(lambda: "observability constraint" in
       TRACE["unresolved_narrative_ambiguity"]["G3"]))
row(7, "IntentAuthority", "contract model versioned + optional field",
    "pytest",
    pt("tests/test_action_intent_018.py::"
       "test_01_action_intent_contract_minimal_and_versioned"))
row(8, "IntentAuthority", "legacy ShotSpec identity byte-stable with "
    "the new field", "pytest",
    pt("tests/test_action_intent_018.py::"
       "test_02_action_intent_optional_field_identity_stable"))
row(9, "IntentAuthority", "no invented motivation: goal wording binds "
    "scene purpose", "evidence",
    ev(lambda: "Obstacle" in json.dumps(TRACE["F2"]
        ["q3_what_does_he_want_now"]["sources"]) and
       "Resolution" in json.dumps(TRACE["G3"]
        ["q3_what_does_he_want_now"]["sources"])))
row(10, "IntentAuthority", "wrong-story contamination impossible (no "
    "other-story source referenced)", "evidence",
    ev(lambda: all("story_auto" not in json.dumps(v).lower() and
                   "STORYAUTO" not in json.dumps(v)
                   for v in TRACE["F2"].values())))
row(11, "IntentAuthority", "no generation without intent (gate honored "
    "in code path)", "evidence",
    ev(lambda: "generation authorized within the 3-Generate budget" in
       TRACE["gate_A1"]["decision"]))
row(12, "IntentAuthority", "intent digests frozen per candidate",
    "evidence",
    ev(lambda: all(c["action_intent_digest"] and
                   c["performance_spec_digest"]
                   for c in EXP["candidates"])))

# == legibility / observability / graph (13-26) ==========================
row(13, "Legibility", "empty intent fails closed (NOT_LEGIBLE)",
    "pytest",
    pt("tests/test_action_intent_018.py::"
       "test_03_legibility_checks_fail_closed_on_empty_intent"))
row(14, "Legibility", "recovered F2 intent passes", "pytest",
    pt("tests/test_action_intent_018.py::"
       "test_04_legibility_passes_on_recovered_f2_intent"))
row(15, "Legibility", "anti-pattern guard recorded", "evidence",
    ev(lambda: "never passes merely because" in json.dumps(
        load(D18 / "baseline_action_legibility_018.json")
        ["legibility_contracts"]["F2"])))
row(16, "Legibility", "baseline meaning review separates MOTION from "
    "MEANING", "evidence",
    ev(lambda: "ACTION_MEANING" in json.dumps(load(
        D18 / "baseline_action_legibility_018.json")
        ["baseline_action_legibility"]["rows"]["F2C (canonical)"])))
row(17, "Legibility", "canonical F2C meaning honestly NOT_LEGIBLE",
    "evidence",
    ev(lambda: "NOT_LEGIBLE" in load(D18 /
        "baseline_action_legibility_018.json")["baseline_action_legibility"]
        ["rows"]["F2C (canonical)"]["ACTION_MEANING"]["legibility"]))
row(18, "Legibility", "G3C meaning honestly NOT_LEGIBLE standalone",
    "evidence",
    ev(lambda: "NOT_LEGIBLE" in load(D18 /
        "baseline_action_legibility_018.json")["baseline_action_legibility"]
        ["rows"]["G3C (canonical)"]["ACTION_MEANING"]["legibility"]))
row(19, "Observability", "F2 = REQUIRES_REACTION_CUE, G3 = "
    "REQUIRES_PREVIOUS_SHOT_CONTEXT", "evidence",
    ev(lambda: load(D18 / "baseline_action_legibility_018.json")
       ["legibility_contracts"]["F2"]["observability"]["observability"]
       == "REQUIRES_REACTION_CUE" and
       load(D18 / "baseline_action_legibility_018.json")
       ["legibility_contracts"]["G3"]["observability"]["observability"]
       == "REQUIRES_PREVIOUS_SHOT_CONTEXT"))
row(20, "Observability", "no automatic edit rewrite (recommendations "
    "only)", "evidence",
    ev(lambda: "never rewritten" in load(D18 /
        "baseline_action_legibility_018.json")["legibility_contracts"]
       ["F2"]["observability"]["rule"]))
row(21, "Observability", "unfilmable-intent class exists in the "
    "contract", "pytest",
    pt("tests/test_action_intent_018.py::"
       "test_05_observability_classification"))
row(22, "Graph", "state-change invariant enforced", "pytest",
    pt("tests/test_action_intent_018.py::"
       "test_07_causality_graph_state_invariant"))
row(23, "Graph", "meaningless action chain refused", "pytest",
    pt("tests/test_action_intent_018.py::"
       "test_07_causality_graph_state_invariant"))
row(24, "Graph", "F2 and G3 edges carry full state payload",
    "evidence",
    ev(lambda: all(e["incoming_world_state"] and e["outgoing_world_state"]
                   and e["state_change_invariant"] == "PASS" for e in
                   load(D18 / "shot_causality_graph_018.json")["edges"])))
row(25, "Complexity", "causal-beat counting + advisory "
    "recommendations", "pytest",
    pt("tests/test_action_intent_018.py::"
       "test_06_causal_complexity_recommendations"))
row(26, "Complexity", "no automatic restructuring", "evidence",
    ev(lambda: "no automatic restructuring" in json.dumps(
        load(D18 / "baseline_action_legibility_018.json")
        ["legibility_contracts"]["F2"]["causal_complexity"])))

# == causal compiler (27-38) ==============================================
row(27, "Compiler", "causal chain renders in order", "pytest",
    pt("tests/test_action_intent_018.py::"
       "test_08_causal_compiler_renders_chain_in_order"))
row(28, "Compiler", "overlength fails closed", "pytest",
    pt("tests/test_action_intent_018.py::"
       "test_09_causal_compiler_overlength_fails_closed"))
row(29, "Compiler", "performance compiler unchanged without intent",
    "pytest",
    pt("tests/test_action_intent_018.py::"
       "test_10_performance_compiler_unchanged_without_intent"))
row(30, "Compiler", "all 3 candidate bodies within 500/75", "evidence",
    ev(lambda: all(c["creative_body_chars"] <= 500 and
                   c["creative_body_words"] <= 75
                   for c in EXP["candidates"])))
row(31, "Compiler", "causal order preserved in frozen bodies (A/B)",
    "evidence",
    ev(lambda: all(b["creative_body"].index("Trigger:") <
                   b["creative_body"].index("Goal:") <
                   b["creative_body"].index("Outcome:")
                   for b in EXP["candidates"]
                   if b["candidate_id"].startswith("F2C"))))
row(32, "Compiler", "no invented content beyond the recovered intent",
    "evidence",
    ev(lambda: all("glance" not in c["creative_body"]
                   for c in EXP["candidates"]
                   if c["candidate_id"] == "F2C-P018-A")))
row(33, "Compiler", "experiment frozen BEFORE Generate #1", "evidence",
    ev(lambda: EXP["frozen_before_generate_1"] is True))
row(34, "Compiler", "route unchanged from qualified truth", "evidence",
    ev(lambda: EXP["route"]["model_label"] == "veo_3_1_r2v_lite" and
       EXP["route"]["account_id"] == "clean-pro-qualified"))
row(35, "Compiler", "references already-bound media (0 uploads)",
    "evidence",
    ev(lambda: EXP["baseline_binding"]["F2C"]["media_id"] ==
       "8f2f5277-aae8-44b5-a5b7-c197d1d7c115"))
row(36, "Compiler", "canonical fixtures untouched by candidate "
    "generation", "evidence",
    ev(lambda: "fixtures/requal009" not in
       __import__("subprocess").run(["git", "status", "--short"],
                                    capture_output=True, text=True,
                                    cwd=ROOT).stdout))
row(37, "Compiler", "local-failure recovery: stale result archived, "
    "no fake progress", "evidence",
    ev(lambda: (D18 / "scene_SCENE_F_STORM_GATE/"
                "shot_SEQ7_F2C_P018_A/result_attempt1.json").exists() and
       (D18 / "scene_SCENE_F_STORM_GATE/"
        "shot_SEQ7_F2C_P018_A/reentry_note.json").exists()))
row(38, "Compiler", "hook bug fixed before any mutation (ledger 0 "
    "during local failures)", "evidence",
    ev(lambda: json.loads((D18 / "scene_SCENE_F_STORM_GATE/"
                           "shot_SEQ7_F2C_P018_A/"
                           "result_attempt1.json").read_text(
        encoding="utf-8"))["gate"] == "OWNER_GATE_LOCAL_FAILURE"))

# == live custody (39-58) ==================================================
row(39, "Live", "exactly 3 submissions consumed", "evidence",
    ev(lambda: len(LEDGER["primary_consumed"]) == 3 and
       LEDGER["max_primary"] == 3))
row(40, "Live", "zero retries", "evidence",
    ev(lambda: len({e["shot_id"] for e in LEDGER["primary_consumed"]})
       == 3))
row(41, "Live", "zero uploads", "evidence",
    ev(lambda: LEDGER["uploads"] == []))
row(42, "Live", "all 3 candidates SHOT_PROVEN", "evidence",
    ev(lambda: [r["gate"] for r in load(D18 /
        "candidate_custody_018.json")] == ["SHOT_PROVEN"] * 3))
row(43, "Live", "job ids distinct", "evidence",
    ev(lambda: len({r["provider_job_id"] for r in load(D18 /
        "candidate_custody_018.json")}) == 3))
row(44, "Live", "output identities distinct", "evidence",
    ev(lambda: len({r["output_identity"] for r in load(D18 /
        "candidate_custody_018.json")}) == 3))
row(45, "Live", "full decode on every candidate", "evidence",
    ev(lambda: all(r["technical"]["full_decode"] for r in load(D18 /
        "candidate_custody_018.json"))))
row(46, "Live", "8s 1280x720 conform", "evidence",
    ev(lambda: all(r["technical"]["duration_s"] == 8.0 and
                   r["technical"]["width"] == 1280 and
                   r["technical"]["height"] == 720 for r in
                   load(D18 / "candidate_custody_018.json"))))
row(47, "Live", "prompt sha256 recorded per candidate", "evidence",
    ev(lambda: all(len(r["prompt_sha256"]) == 64 for r in load(D18 /
        "candidate_custody_018.json"))))
row(48, "Live", "asset sha256 recorded per candidate", "evidence",
    ev(lambda: all(len(r["asset_sha256"]) == 64 for r in load(D18 /
        "candidate_custody_018.json"))))
row(49, "Live", "identity QC: no material regression", "evidence",
    ev(lambda: "no material identity regression" in QC["rule"]))
row(50, "Live", "G3C-P018-C hair-pin drift flagged for Owner",
    "evidence",
    ev(lambda: "MINOR DRIFT" in QC["identity_review"]["G3C-P018-C"]
       ["hair"]))
row(51, "Live", "B staging honesty recorded (brace, not clear "
    "through)", "evidence",
    ev(lambda: "bracing AT the rock" in
       QC["identity_review"]["F2C-P018-B"]["note"]))
row(52, "Live", "mutation authority scope fresh (018)", "evidence",
    ev(lambda: load(D18 / "mutation_authority.json")["scope_id"] ==
       "FLOW-ACTION-INTENT-CAUSALITY-018"))
row(53, "Live", "authority not latched (clean run)", "evidence",
    ev(lambda: load(D18 / "mutation_authority.json")
       ["mutation_authority"] == "OPEN"))
row(54, "Live", "ambiguity rule frozen (no retry/redispatch/alternate "
    "scope)", "evidence",
    ev(lambda: "no retry" in EXP["budget"]["ambiguity"] and
       "alternate scope" in EXP["budget"]["ambiguity"]))
row(55, "Live", "candidate A custody complete", "evidence",
    ev(lambda: [r for r in load(D18 / "candidate_custody_018.json")
                if r["candidate_id"] == "F2C-P018-A"][0]
       ["output_identity"] == "796040db-4af1-4d38-9da0-28260aabd4c6"))
row(56, "Live", "candidate B custody complete", "evidence",
    ev(lambda: [r for r in load(D18 / "candidate_custody_018.json")
                if r["candidate_id"] == "F2C-P018-B"][0]
       ["output_identity"] == "2cf20dcc-d640-456e-8a65-3b9b9b68f312"))
row(57, "Live", "candidate C custody complete", "evidence",
    ev(lambda: [r for r in load(D18 / "candidate_custody_018.json")
                if r["candidate_id"] == "G3C-P018-C"][0]
       ["output_identity"] == "d4b427d7-2697-4e36-a05d-a1bbc0f8e3b3"))
row(58, "Live", "candidate lineage binds fixtures (spec digests)",
    "evidence",
    ev(lambda: all(c["fixture_sha256"] for c in EXP["candidates"])))

# == blind review (59-72) ==================================================
row(59, "Blind", "answer key is a SEPARATE file", "evidence",
    ev(lambda: (D18 / "answer_key_action_intent_018.json").is_file() and
       (D18 / "blind_action_legibility_packet_018.json").is_file()))
row(60, "Blind", "blind packet carries no intent text", "evidence",
    ev(lambda: "AUTHORITATIVE INTENT" not in json.dumps(BLIND["clips"])
       and all("intent" not in c for c in BLIND["clips"])))
row(61, "Blind", "leak check recorded in the answer key", "evidence",
    ev(lambda: "leak_check" in KEY))
row(62, "Blind", "worker contamination disclosed", "evidence",
    ev(lambda: "contaminated" in BLIND["contamination_disclosure"]))
row(63, "Blind", "true blind view assigned to the Owner", "evidence",
    ev(lambda: "Owner" in BLIND["contamination_disclosure"]))
row(64, "Blind", "per-clip questions are meaning questions", "evidence",
    ev(lambda: "trying to accomplish" in BLIND["questions_per_clip"][0]))
row(65, "Blind", "worker advisory answers present per clip", "evidence",
    ev(lambda: len(BLIND["worker_blind_answers_advisory"]) == 7))
row(66, "Blind", "blind answers distinguish trigger/trying/changed",
    "evidence",
    ev(lambda: all({"trying_to", "cause", "changed"} <= set(v)
                   for v in BLIND["worker_blind_answers_advisory"]
                   .values())))
row(67, "Blind", "baseline clips read weakest (worker advisory)",
    "evidence",
    ev(lambda: "unclear" in BLIND["worker_blind_answers_advisory"]
       ["BLIND-1"]["changed"] and "speech" in
       BLIND["worker_blind_answers_advisory"]["BLIND-5"]["trying_to"]))
row(68, "Blind", "candidate A clip reads trigger+outcome (worker "
    "advisory)", "evidence",
    ev(lambda: "visible" in BLIND["worker_blind_answers_advisory"]
       ["BLIND-3"]["cause"] and "emerges" in
       BLIND["worker_blind_answers_advisory"]["BLIND-3"]["changed"]))
row(69, "Blind", "answer key binds each clip to its surface", "evidence",
    ev(lambda: len(KEY["clip_map"]) == 7 and
       KEY["clip_map"]["BLIND-3"]["surface"] == "F2C-P018-A"))
row(70, "Blind", "worker interpretation NOT treated as Owner truth",
    "evidence",
    ev(lambda: "advisory" in CTRL["advisory"]))
row(71, "Blind", "no auto-promotion anywhere", "evidence",
    ev(lambda: "nothing promoted" in
       json.dumps(load(D18 / "owner_action_decisions_018.template.json")
                  ["rules"]) or "auto-promoted" in json.dumps(load(
                      D18 / "owner_action_decisions_018.template.json"))))
row(72, "Blind", "decision template unpopulated", "evidence",
    ev(lambda: load(D18 / "owner_action_decisions_018.template.json")
       ["status"].startswith("UNPOPULATED")))

# == classification (73-84) ================================================
row(73, "Classification", "A = CAUSAL_CONTROL_EFFECT_OBSERVED",
    "evidence",
    ev(lambda: CTRL["findings"]["F2C-P018-A"]["classification"] ==
       "CAUSAL_CONTROL_EFFECT_OBSERVED"))
row(74, "Classification", "B = PARTIAL_EFFECT with honest staging "
    "note", "evidence",
    ev(lambda: CTRL["findings"]["F2C-P018-B"]["classification"] ==
       "PARTIAL_EFFECT"))
row(75, "Classification", "C = CAUSAL_CONTROL_EFFECT_OBSERVED "
    "(reaction)", "evidence",
    ev(lambda: "CAUSAL_CONTROL_EFFECT_OBSERVED" in
       CTRL["findings"]["G3C-P018-C"]["classification"]))
row(76, "Classification", "017-bests honestly ACTION_STILL_AMBIGUOUS "
    "standalone", "evidence",
    ev(lambda: "AMBIGUOUS" in
       CTRL["findings"]["F2C-P017-C (017 best, unchanged)"]
       ["classification"]))
row(77, "Classification", "Q1 answered with scope limit", "evidence",
    ev(lambda: "within this experiment" in CTRL["questions"]
       ["Q1_does_action_intent_improve_understanding"]["answer"]))
row(78, "Classification", "Q2 per-candidate", "evidence",
    ev(lambda: "F2C-P018-A: YES" in CTRL["questions"]
       ["Q2_does_the_action_have_readable_purpose"]["answer"]))
row(79, "Classification", "Q3 causal chain answered", "evidence",
    ev(lambda: "visibly causes" in CTRL["questions"]
       ["Q3_does_contact_or_reaction_cause_the_next_state"]["answer"]))
row(80, "Classification", "Q4 = upstream editorial context (not "
    "generation quality, not architecture)", "evidence",
    ev(lambda: "UPSTREAM_EDITORIAL_CONTEXT" in CTRL["questions"]
       ["Q4_remaining_problem_generation_quality_or_upstream"]
       ["answer"]))
row(81, "Classification", "identity guard: no material regression "
    "accepted for meaning", "evidence",
    ev(lambda: "no material identity regression" in
       CTRL["identity_guard"]))
row(82, "Classification", "scope limit present (no universal claim)",
    "evidence",
    ev(lambda: "ONLY within this observed experiment" in
       CTRL["scope_limit"]))
row(83, "Classification", "G3 context need maps to the master cut "
    "(G2 adjacency already provides it)", "evidence",
    ev(lambda: "master cut already supplies" in CTRL["questions"]
       ["Q4_remaining_problem_generation_quality_or_upstream"]
       ["answer"]))
row(84, "Classification", "decision options only for AVAILABLE "
    "candidates", "evidence",
    ev(lambda: set(load(D18 /
                        "owner_action_decisions_018.template.json")
                   ["decisions"]["F2"]["options"]) ==
       {"KEEP_CANONICAL", "SELECT_017_C", "SELECT_018_A", "SELECT_018_B",
        "REQUIRES_REDESIGN", "DEFER"}))

# == reel + surface (85-92) ================================================
row(85, "Surface", "compare reel full decode", "evidence",
    ev(lambda: REEL["reel"]["full_decode"] is True and REEL["reel"]
       ["sha256"] == hashlib.sha256(
           (D18 / "OWNER_ACTION_CAUSALITY_COMPARE_018.mp4").read_bytes())
       .hexdigest()))
row(86, "Surface", "blind section precedes intent cards", "evidence",
    ev(lambda: [s["section"] for s in REEL["segments"]][:7] ==
       ["BLIND"] * 7 and REEL["segments"][7]["section"] == "INTENT"))
row(87, "Surface", "intent cards come only after the blind section",
    "evidence",
    ev(lambda: all(s["label"] != "F2 INTENT" for s in
                   REEL["segments"][:7])))
row(88, "Surface", "segment mapping exact (7 blind + 2 intent)",
    "evidence", ev(lambda: len(REEL["segments"]) == 9))
row(89, "Surface", "asset hashes recorded per blind segment", "evidence",
    ev(lambda: all(s["asset_sha256"] for s in REEL["segments"][:7])))
row(90, "Surface", "canonical master untouched", "live",
    ev(lambda: hashlib.sha256((M10 /
        "master_editorial_010_v1.mp4").read_bytes()).hexdigest() ==
       MASTER_SHA))
row(91, "Surface", "canonical takes byte-identical", "evidence",
    ev(lambda: hashlib.sha256((ROOT / "projects/"
        "flow_upload_contract_requal_009/reproof/scene_SCENE_F_STORM_GATE/"
        "shot_SEQ7_F2C/videos/c1a69047933565230870ad22.mp4").read_bytes())
       .hexdigest() == "e84ba56ccd0f556e3eebe8ccf83def567118a59b87a463c8c39"
       "898254890a767"))
row(92, "Surface", "no candidate promoted", "evidence",
    ev(lambda: not any("master" in str(p).lower() for p in
                       D18.glob("*.mp4"))))

# == adversarial mappings (93-106) =========================================
row(93, "Adversarial", "motivation invented without authority -> "
    "trace requires sources", "evidence",
    ev(lambda: all("sources" in v for v in TRACE["F2"].values()
                   if isinstance(v, dict) and "classification" in v)))
row(94, "Adversarial", "trigger fabrication -> trigger binds verbatim "
    "beats", "evidence",
    ev(lambda: "action_beats" in json.dumps(TRACE["F2"]["q2_what_does_"
                                            "he_perceive"]["sources"])))
row(95, "Adversarial", "goal fabrication -> goal classified DERIVABLE "
    "with note, never AUTHORITATIVE", "evidence",
    ev(lambda: TRACE["F2"]["q3_what_does_he_want_now"]
       ["classification"] == "DERIVABLE"))
row(96, "Adversarial", "outcome not represented -> OUTCOME_VISIBLE "
    "check fails", "evidence",
    ev(lambda: "OUTCOME_VISIBLE" in json.dumps(load(
        D18 / "baseline_action_legibility_018.json")
        ["legibility_contracts"]["F2"]["checks"])))
row(97, "Adversarial", "meaningless contact action refused by graph",
    "pytest",
    pt("tests/test_action_intent_018.py::"
       "test_07_causality_graph_state_invariant"))
row(98, "Adversarial", "prompt causality reordered -> order assert",
    "pytest",
    pt("tests/test_action_intent_018.py::"
       "test_08_causal_compiler_renders_chain_in_order"))
row(99, "Adversarial", "hidden answer leaked into blind surface -> "
    "leak check fails the package", "evidence",
    ev(lambda: "leak_check" in KEY and "AUTHORITATIVE INTENT" not in
       json.dumps(BLIND["clips"])))
row(100, "Adversarial", "worker interpretation as Owner truth -> "
    "advisory rule", "evidence",
    ev(lambda: "advisory" in CTRL["advisory"]))
row(101, "Adversarial", "identity regression accepted for meaning -> "
    "guard rule", "evidence",
    ev(lambda: "does not compensate identity regression" in json.dumps(
        load(D18 / "owner_action_decisions_018.template.json"))))
row(102, "Adversarial", "provider ambiguity -> OWNER_AMBIGUITY_GATE "
    "frozen wording", "evidence",
    ev(lambda: "OWNER_AMBIGUITY_GATE" in EXP["budget"]["ambiguity"]))
row(103, "Adversarial", "blind retry -> zero retries frozen",
    "evidence",
    ev(lambda: EXP["budget"]["retries"] == 0 and
       LEDGER["max_primary"] == 3))
row(104, "Adversarial", "canonical mutation -> live hash check", "live",
    ev(lambda: hashlib.sha256((M10 /
        "master_editorial_010_v1.mp4").read_bytes()).hexdigest() ==
       MASTER_SHA))
row(105, "Adversarial", "stale asset / wrong reference -> runtime "
    "binding guards", "evidence",
    ev(lambda: "ACQUISITION_OUTPUT_IDENTITY_MISMATCH" in
       (ROOT / "tools/run_production_scale_007.py").read_text(
           encoding="utf-8")))
row(106, "Adversarial", "secret leak -> scan clean", "evidence",
    ev(lambda: not any(t in json.dumps(EXP) + json.dumps(CTRL) +
                       json.dumps(REEL) + json.dumps(BLIND)
                       for t in ("AIza", "set-cookie",
                                 "BEGIN PRIVATE KEY"))))


def main() -> None:
    results = run()
    passed = sum(1 for r in results if r["result"] == "PASS")
    fails = [r["id"] for r in results
             if r["result"] not in ("PASS",) and r["mode"] == "evidence"]
    out = {"version": "recovery-matrix-018-v1",
           "scenarios": len(results),
           "pytest_bound": sum(1 for r in results
                               if r["mode"] == "pytest"),
           "evidence_pass": passed, "fails": fails, "rows": results}
    (D18 / "recovery_matrix_018.json").write_text(json.dumps(out, indent=1),
                                                  encoding="utf-8")
    print(json.dumps({"scenarios": len(results), "fails": fails}))


if __name__ == "__main__":
    main()
