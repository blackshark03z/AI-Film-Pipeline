# FLOW-ACTION-INTENT-CAUSALITY-018 — Evidence Record

**Status: OWNER_DECISION_GATE** — the authoritative intent was
recovered for both targets, three bounded causal canaries rendered
clean, and the Owner must now judge whether the action actually
communicates its purpose. Tech Lead retains final PROVE acceptance.
**Exact start SHA:** `895ca4cb7d8344f2bedcb0740e695ebfc9a4c259`
(Package-017, OWNER_DECISION_GATE). **017 evidence binding:**
`docs/operating/FLOW_PERFORMANCE_MOTION_CANARY_017_EVIDENCE.md`
(017 candidates NOT promoted; canonical F2C/G3C remain the
authoritative baselines). Canonical master `976876a1…786595`
byte-identical throughout (live hash checks).

## 1. Phase 0 — authority rebind (`phase0_rebind_018.json`)

Bound: git HEAD, Package-016 freeze identity (`3494c7b1…`), 017
evidence, canonical master, F2C/G3C takes + hashes, the three 017
candidate assets (B `751f0bb5…`, C `c540b5ea…`, D `a163b188…` —
untouched), all seven neighbor ShotSpecs (hashes), the frozen sequence
plan (scene purposes), edit manifest, the narration/script authority
state (STILL `NARRATION_TEXT_AUTHORITY_MISSING` — the trace uses shot
design authority, not narration). **A0 ✓**

## 2. Phase 1 — upstream causality trace (`action_authority_trace_018.json`)

Every assertion binds artifact + id + field; classification
AUTHORITATIVE/DERIVABLE per assertion; nothing inferred as fact.

- **F2**: trigger "a hard gust hits" (AUTHORITATIVE, beat) → goal
  "through the gate, road onward" (DERIVABLE: scene purpose "Obstacle"
  + F1 behavior "pushes on toward the gate" + F2 end state) → action
  "drives a step through it" (AUTHORITATIVE) → outcome "through the
  worst gust" (AUTHORITATIVE end state) → next: F3 "the cost, held".
- **G3**: trigger "the arc completed" (AUTHORITATIVE: G2 draw/arc +
  G3 purpose "the exhale after the arc") → goal "release the effort"
  (DERIVABLE paraphrase of the frozen exhale/shoulders-drop/let-go) →
  action/outcome (AUTHORITATIVE) → next: G4 "the walk resumes".
- **Gate A1: ACTION_INTENT_AUTHORITY = RESOLVED for both** — the
  sources explain causal purpose, not merely "run toward stone". The
  recorded honest ambiguity: G3's arc is not visible inside its CU
  framing (an observability constraint, Phase 4). Generation
  authorized within the 3-Generate budget.

## 3. Phases 2–7 — the causal layer (commit `5956e9a`)

- **ActionIntent v1** (action-intent-v1): optional ShotSpec field;
  legacy digests byte-stable (the canonical_json exclusion now covers
  both extension fields); the layer distinction is frozen —
  NarrativeBeat (what beat) → ActionIntent (why now, to what end) →
  PerformanceSpec (how the body does it).
- **Causal legibility contract** (`action_intent.py`): 7 deterministic
  checks (TRIGGER_VISIBLE…/GOAL_INFERABLE/ACTION_SERVES_GOAL/
  CONTACT_HAS_FUNCTION/OUTCOME_VISIBLE/REACTION_MATCHES_OUTCOME/
  NEXT_STATE_CHANGED) → LEGIBLE / PARTIALLY_LEGIBLE / NOT_LEGIBLE /
  INCONCLUSIVE, with the anti-pattern guard: a shot never passes
  merely because animation is natural and identity stable.
- **Observability classification**: F2 =
  REQUIRES_REACTION_CUE; G3 = REQUIRES_PREVIOUS_SHOT_CONTEXT
  (recommendations only — the edit is never rewritten).
- **Shot causality graph** (`shot_causality_graph_018.json`): F1→F2→F3
  and G2→G3→G4 edges with incoming/outgoing world states; the
  state-change invariant enforced (meaningless chains refused — test
  proves the refusal).
- **Causal prompt compiler** `flow-r2v-causal-compact-v1`: renders
  Trigger → Goal → Action → Movement (capped) → Outcome in causal
  order inside the same 500-char/75-word fail-closed envelope; default
  compilers untouched; Film Core neutral.
- **Causal complexity**: causal-beat counting with advisory
  SPLIT_NARRATIVE_BEAT / INSERT_REACTION_SHOT / ESTABLISH_TRIGGER.
  10 new tests. **A2–A7 ✓**

## 4. Phase 8–9 — baseline MEANING review + the generation decision
(`baseline_action_legibility_018.json`)

MOTION_NATURALNESS (017, frozen) is explicitly separated from
ACTION_MEANING. Honest findings against the recovered intents:
canonical F2C **NOT_LEGIBLE** (goal + outcome unreadable; trigger
partial), 017-B/C **PARTIALLY_LEGIBLE**, canonical G3C **NOT_LEGIBLE
standalone** (speech-like mouth artifact), 017-D PARTIALLY (context-
dependent). **Decision: CANARY_REQUIRED_WITHIN_BUDGET** — no existing
surface conveys the recovered intent; prompt control can reasonably
improve it. **A8 ✓**

## 5. Phases 10–11 — frozen canary matrix + 3 live generations
(`experiment_freeze_018.json`, ledger 3/3, 0 retries, 0 uploads)

| Candidate | Design | Provider job | Output identity | Asset sha |
|---|---|---|---|---|
| F2C-P018-A | CAUSAL_INTENT_ONLY (017-C motion + trigger/goal/action/outcome) | `job_…` (frozen intent) | `796040db-4af1-4d38-9da0-28260aabd4c6` | `5ef2eade…` |
| F2C-P018-B | + VISUAL_LEGIBILITY (glance-into-the-gust cue, nothing beyond authority) | `job_…` | `2cf20dcc-d640-456e-8a65-3b9b9b68f312` | `4ab6cd40…` |
| G3C-P018-C | REACTION_CAUSALITY (the arc's effort visibly leaves the body) | `job_…` | `d4b427d7-2697-4e36-a05d-a1bbc0f8e3b3` | `0536388b…` |

All bodies inside the qualified envelope (A 490 chars/73 words ·
B 472/70 · C 462/68); prompts sha-recorded in
`candidate_custody_018.json`; fresh mutation-authority scope
`FLOW-ACTION-INTENT-CAUSALITY-018` (OPEN). Two earlier launches failed
LOCALLY before any mutation (a missing `action_intent` kwarg in the
freeze hook, then a stale-result short-circuit) — the ledger stayed
0/3 through both; the stale result was archived loudly
(`result_attempt1.json` + reentry note) and the fixed run consumed
exactly 3/3. **A10–A11 ✓**

## 6. Phase 12 — technical/identity QC (`tech_identity_qc_018.json`)

All three: SHOT_PROVEN, 8.0 s, 1280x720, full decode EOF. Identity: A
and B PASS (consistent face/hair/costume; the storm-gate world intact);
C PASS with a **minor hair-pin accessory drift** flagged for the Owner
and a slightly slimmer facial read (as 017-D). Guard recorded: improved
meaning does not compensate identity regression — no material
regression observed. **A12 ✓**

## 7. Phase 13 — blind legibility surface
(`blind_action_legibility_packet_018.json` + separate
`answer_key_action_intent_018.json`)

Seven clips under neutral BLIND-1…7 labels with the three meaning
questions; the answer key is a separate file (leak check recorded);
the worker contamination is disclosed in the packet itself (the worker
wrote the prompts — **the true blind first view belongs to the
Owner**; worker answers are advisory). **A13 ✓**

## 8. Phase 14 — causal effect classification
(`action_causality_experiment_018.json`)

- **F2C-P018-A: CAUSAL_CONTROL_EFFECT_OBSERVED** — the gust renders
  VISIBLY between the gate stones, the drive reads as passing through,
  and he emerges past the gate: trigger/goal/outcome all readable.
- **F2C-P018-B: PARTIAL_EFFECT** — the reaction cue renders (arm-shield
  brace into the blast; cause unmistakable) but staging drifted to
  bracing AT the rock; through-state less clear than A.
- **G3C-P018-C: CAUSAL_CONTROL_EFFECT_OBSERVED (REACTION_CAUSALITY)** —
  the exhale reads as release-of-effort (closed mouth, softening jaw,
  visible shoulder drop, eyes ease), replacing the baseline's
  speech-like artifact; the completed-arc trigger remains
  context-dependent by framing.
- **Q1** yes-within-experiment · **Q2** A yes / B partial / C partial
  (context) · **Q3** gust→drive→through (A) and exhale→settle (C)
  visible · **Q4** the remaining problem is **UPSTREAM_EDITORIAL_
  CONTEXT** (G3's trigger lives in G2 and the canonical master cut
  already supplies that adjacency), not generation quality and not
  architecture. **A14 ✓**

## 9. Phases 15–17 — Owner surface + delta

- `OWNER_ACTION_CAUSALITY_COMPARE_018.mp4` sha256 `08e49f70…` (42.1 s,
  full decode): BLIND section first (F2C 1-4, G3C 1-3 — neutral labels,
  no intent, no verdicts), then two wrapped AUTHORITATIVE INTENT cards
  (the first build's clipped drawtext cards were found by viewing the
  reel and rebuilt as PNG cards). Manifest:
  `owner_action_causality_compare_018.json` (9 segments, hashes, job
  ids). **A15 ✓**
- `owner_action_decisions_018.template.json` — F2: KEEP_CANONICAL /
  SELECT_017_C / SELECT_018_A / SELECT_018_B / REQUIRES_REDESIGN /
  DEFER; G3: KEEP_CANONICAL / SELECT_017_D / SELECT_018_C /
  REQUIRES_REDESIGN / DEFER; every option binds the exact asset sha;
  no auto-promotion. **A16 ✓**
- `pipeline_delta_018.json`: ActionIntent contract, causal legibility,
  causality graph, causal compiler, causal classifier, blind review —
  all ADOPTED_AS_MECHANISM (MECHANISM_PROVEN) with quality-effect
  recorded separately (choreography-of-meaning EVIDENCE_SUPPORTS; no
  universal claims). No historical shots rewritten; all semantics
  versioned. **A17 ✓**

## 10. Phase 18 — recovery/adversarial matrix

`recovery_matrix_018.json`: **106/106 PASS** — covers the full
required list (motivation invented, wrong story source, fabricated
trigger/goal, unrepresented outcome, meaningless contact, no state
change, missing context, too many causal beats, unfilmable intent,
reordered causality, answer-key leak, worker-as-truth, auto-promotion,
identity-for-meaning, provider ambiguity, blind retry, canonical
mutation, stale asset, wrong reference, secret leak) with
OWNER_AMBIGUITY_GATE mappings. **A18 ✓**

## 11. Final verification

- **Full network-free regression: 903 passed, 0 failed** (893 + 10 new
  action-intent tests) incl. all predecessor suites.
- Matrices: 018 106/106 · 017 104/104 · SoT 30/30 · compileall clean ·
  `git diff --check` clean · secret scan clean (0 real secrets).
- Canonical master byte-identical (live check) · canonical takes
  byte-identical · canonical fixtures untouched · **no candidate
  promoted**.

## 12. Unresolved unknowns

1. The Owner's true blind read of the seven clips (the deciding
   authority) — the worker's blind answers are prompt-contaminated by
   construction.
2. Whether B's brace staging or A's through-staging better serves the
   film is an Owner call.
3. G3's in-CU causal completeness is bounded by framing; in the
   master cut the G2 adjacency supplies the trigger.
4. The G3C-P018-C hair-pin accessory drift (minor) — Owner call.
5. External spend: 3 generation submissions (all rendered); 0 uploads;
   0 external AI API calls; 0 TTS. Two earlier launch attempts failed
   locally pre-mutation (ledger untouched).

## 13. Final status

**OWNER_DECISION_GATE** — the Owner watches the blind section of
`OWNER_ACTION_CAUSALITY_COMPARE_018.mp4` first, then the intent cards,
and fills `owner_action_decisions_018.template.json`; nothing becomes
canonical during Package-018 and nothing was auto-promoted.
