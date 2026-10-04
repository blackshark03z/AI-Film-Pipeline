# FLOW-PERFORMANCE-MOTION-CANARY-017 — Evidence Record

**Status: OWNER_DECISION_GATE** — the bounded live canary ran clean;
the Owner must now decide from the compare reel whether any candidate
actually looks better. Tech Lead retains final PROVE acceptance.
**Exact start SHA:** `932866464c3fea3fae31c956fe9f27c1d469812e`
(Package-016 closure, OWNER_DECISION_GATE).
**Package-016 freeze identity:** `AI_FILM_V1_TECHNICAL_FREEZE_016`
sha256 `3494c7b182a06026aba060e3a1a54107d57c7a14cb084070ab92bb9dba3d389e`
— not invalidated; the V1 freeze stands.

## 1. Phase 0 — authority rebind (`phase0_rebind_017.json`)

Canonical master `976876a1…786595` immutable throughout. Character
authority: `swordsman_white_robes_v1` / `white_robes_cloud_summit_dawn_v1`;
the ONLY visual identity authority is the chest-up base reference
(`asset_2ab16c9f…`, sha `ed75a8b2…`) — **no full-body reference exists;
no standalone Character Bible file existed**. Flow route (frozen,
unchanged from Packages 003–009): `flow_veo` / model label
`veo_3_1_r2v_lite`, project `93a579b4…`, account `clean-pro-qualified`,
headful native UI with OneGenerateGuard. Prompt compiler:
`compact_r2v_prompt` (`flow-r2v-runtime-compact-v1`, 500 chars / 75
words creative body). **Both original canonical prompts reconstructed
byte-exactly offline** (F2C sha `5cc9eb36…` ✓, G3C sha `ac796025…` ✓).
F2C baseline: take `take_91e4997b…`, asset `e84ba56c…`, F1 last-frame
reference (`8f2f5277…`); G3C baseline: take `take_d6ae980a…`, asset
`ffe42e7e…`, base reference. Search-before-build classification
recorded (REUSE/COMPOSE/ADAPT/EXTEND/BUILD_LAST). **P0 ✓**

## 2. Phase 1 — the frozen quality gap (`performance_motion_gap_017.json`)

Owner observations preserved in meaning: identity stable/consistent;
body proportions can appear too short/compact; physical actions stiff;
UNKNOWN how much is provider ceiling vs controllable direction.
Categories: IDENTITY/LOOK/WORLD = ACCEPTABLE_BASELINE ·
BODY_PROPORTION = NEEDS_INVESTIGATION · PERFORMANCE_NATURALNESS and
BIOMECHANICS = NEEDS_REPAIR · TEMPORAL_MOTION_QC =
INSUFFICIENT_CURRENT_SAMPLING. No fake numeric truths; F2C/G3C are
baselines, not failures. Proof goals Q1/Q2/Q3 recorded. **P1 ✓**

## 3. Phases 2–6 — the performance control layer (commit `1825de9`)

- **Body authority** (`fixtures/character_bible/
  swordsman_white_robes_body_v1.json` + `BodyProportionAuthority` v1):
  extends the existing identity authority; every measured body field
  stays **UNKNOWN** (a measured value without exact authority is
  refused by the model validator); the Owner's directional constraint
  `avoid_short_compact_silhouette = true` is recorded as direction, not
  measurement.
- **PerformanceSpec v1** (optional ShotSpec field, schema-validated):
  separates ACTION DESCRIPTION from PERFORMANCE DIRECTION
  (anticipation/locomotion/weight_transfer/foot_plant/hip-torso/
  arms/contact/reaction/recovery/secondary + BEATS). Quiet shots need
  only primary_action. **Legacy identity byte-stable**: shots without a
  spec hash exactly as before (verified — the pinned compact-plan
  digests still pass).
- **Action-complexity classifier**: deterministic LOW/MEDIUM/HIGH/
  EXTREME + advisory SPLIT_SHOT recommendation only; nothing auto-
  rewrites story/edit structure.
- **Performance prompt compiler** `flow-r2v-performance-compact-v1`
  (beside the Flow adapter; Film Core stays neutral): renders the body
  direction + a phrase-capped Movement clause (beats + filled
  biomechanics values) inside the same 500/75 fail-closed rails;
  overlength fails closed. The runtime's `prompt_compiler` hook
  defaults to the untouched compact compiler.
- **MotionReviewPacket v1** (`motion_qc.py`): 8–12 fps dense
  deterministic frame extraction over the relevant 2–4 s window
  (read-only), 11 motion dimensions, PASS/FAIL/INCONCLUSIVE, sealed to
  the packet digest; ADVISORY only — no promotion from any motion
  score. 11 new tests; full regression stayed green.

## 4. Phase 7 — baseline motion evidence (frozen before any generation)

`MOT-Q017-BASE-F2C` (40 frames @10 fps over 0.4–4.4 s of asset
`e84ba56c…`) and `MOT-Q017-BASE-G3C` (32 frames @10 fps over 0–3.2 s of
asset `ffe42e7e…`), observations sealed to packet digests
(`baseline_motion_observations_017.json`). Honest findings: F2C — feet
occluded by robes/rock (gait/foot dims INCONCLUSIVE), visible action
reads stiff/glide-like (FAIL, owner-aligned), cloth/hair secondary
motion good, hand-to-rock contact plausible. G3C — face identity
stable (PASS), but the directed "long exhale + shoulders settle" is
weakly realized and the mid-clip mouth parting **reads as speech, not
breath** (FAIL recovery_settling). **P7 ✓**

## 5. Phase 8 — experiment frozen before Generate #1
(`experiment_freeze_017.json`)

Route/model/settings/references/hashes/compiler versions/all four
candidate prompts (compiled bodies: A 327 chars/48 words · B 453/66 ·
C 492/72 · D 425/62 — all inside the qualified envelope) + budget
(max 4 Generates, 0 retries, 0 uploads) + advisory complexity classes.
Creative reduction (tighter prose, same narrative intent) applied to
the NEW candidate fixtures only — canonical fixtures untouched. **P8 ✓**

## 6. Phase 9 — the four live Generations (budget 4/4, 0 retries)

| Candidate | Purpose | Provider job id | Outcome |
|---|---|---|---|
| F2C-P017-A | BODY_PROPORTION_ONLY | `job_09cdb387…db4142` | **PROVIDER_RENDER_FAILED_NOT_CHARGED** — Flow rendered an explicit failure card ("unusual activity… not charged") right after our single released request; attribution unambiguous; recorded durable, **no retry permitted** |
| F2C-P017-B | PERFORMANCE_MOTION_ONLY | `job_ed72ee8d…4f2fbbe` | SHOT_PROVEN — output `8b33431e-9872-4bab-8a05-47a4a85f6077`, asset sha `751f0bb5…d81d5e34` |
| F2C-P017-C | COMBINED (main) | `job_579be6d4…699af13` | SHOT_PROVEN — output `23d63bc0-17e8-439f-8536-9b8621d32cc6`, asset sha `c540b5ea…9f086e` |
| G3C-P017-D | GENERALIZATION_CHECK | `job_529aaad9…2ab802` | SHOT_PROVEN — output `b9a59fc4-06ab-49ea-a714-f8b54878b2f5`, asset sha `a163b188…c56e50e` |

All four submissions consumed (ledger `generate_ledger.json`, 4/4),
zero retries, zero uploads (both references already-bound provider
media), prompt sha256 per candidate recorded above, fresh mutation
authority scope `FLOW-PERFORMANCE-MOTION-CANARY-017` (OPEN, not
latched). **P9A–P9D ✓**

## 7. Phase 10 — technical QC

Every rendered candidate: 8.0 s, 1280x720, full decode EOF, exact
reference binding, unique output identity. No technically broken
candidate among B/C/D. **P10 ✓**

## 8. Phases 11–12 — identity/body + temporal comparison
(`performance_control_experiment_017.json`, made from the dense
packets + side-by-side stills)

- **B (motion-only)**: materially more natural motion than baseline —
  visible stride, weight transfer, hip/torso counter-rotation, arm
  counter-swing (PASS on the core motion dims). Staging re-framed
  wider (full body vs waist-up): silhouette reads taller/leaner but
  the proportion attribution is confounded; gate contact not
  preserved. Identity consistent.
- **C (combined, main)**: natural motion AND preserves the
  hand-on-rock gate contact; slightly leaner silhouette; identity
  consistent. Best continuity of the candidates.
- **D (G3C generalization)**: the baseline's speech-like mouth
  artifact is **eliminated** (closed-mouth exhale); recovery/settling
  PASS; face reads slightly slimmer/more angular than baseline —
  MINOR_DRIFT_OWNER_JUDGMENT (exactly the Owner's call, on the reel).
- Improved apparent quality never compensates identity regression;
  nothing observed here is a material identity regression, and
  nothing is promoted regardless.

## 9. Phase 13 — control vs ceiling (within observed scope only)

- **Q1 body proportion: INCONCLUSIVE** — A failed provider-side before
  rendering; C's silhouette delta is confounded by re-staging.
- **Q2 performance choreography: CONTROL_EFFECT_OBSERVED** — same
  provider/model/reference, materially more natural motion (B/C) and
  the G3C settle improvement (D).
- **Q3: the baseline stiffness is NOT evidence of a provider ceiling
  in this shot class** — frozen choreography direction moved the
  outcome materially; the A failure was an anti-abuse render
  rejection (not charged), not a capability signal. No universal
  provider claim. **P13 ✓**

## 10. Phases 14–16 — Owner surface + pipeline delta

- `OWNER_MOTION_COMPARE_REEL_017.mp4` sha256
  `15ec2fbb1a62b7c6c70cf1363a29634058014c0239d6772a35d54c7670ef20c5`
  (23.3 s, 5 segments: F2C BASELINE → B → C, G3C BASELINE → D;
  minimal labels; no worker verdicts; full decode ✓) +
  `owner_motion_compare_manifest_017.json` (time ranges, candidate
  ids, asset hashes, prompt fingerprints/job ids, trims).
- `owner_motion_decisions_017.template.json` sha256
  `5c6e058ec452dfac14d11c7e768e423ef193ad178a10c4bcde42fcd277ee0485` —
  F2C: KEEP_BASELINE / SELECT_A (explicitly unavailable) / SELECT_B /
  SELECT_C / NEEDS_FURTHER_REPAIR / DEFER; G3C: KEEP_BASELINE /
  SELECT_D / NEEDS_FURTHER_REPAIR / DEFER; every option binds the
  exact asset sha; no auto-promotion; selection later still requires
  an explicit Owner decision bound to the exact SHA.
- `pipeline_delta_017.json`: MECHANISM_PROVEN separated from
  QUALITY_EFFECT_PROVEN — body-authority extension, PerformanceSpec,
  classifier, performance compiler adopted as mechanisms (proportion
  quality effect NOT proven; choreography effect evidence-supported);
  temporal motion QC accepted on its evidence boundary. No historical
  ShotSpec rewritten; all new semantics versioned. **P14–P16 ✓**

## 11. Phase 17 — recovery/adversarial matrix

`recovery_matrix_017.json`: **104/104 PASS** (pytest-bound + evidence
rows) covering the full required case list (fake height, identity
drift, overstuffing, wrong baseline/trim/asset, stale reference,
duplicate dispatch, ambiguous dispatch/output, blind-retry refusal,
label swap, sampling drift, illegal promotion, canonical mutation,
contamination, secrets — with OWNER_AMBIGUITY_GATE mappings). **P17 ✓**

## 12. Final verification

- **Full network-free regression: 893 passed, 0 failed** (882 + 11 new
  performance/motion tests), incl. all predecessor suites.
- recovery matrix 017 104/104 · SoT manifest 30/30 · compileall clean ·
  `git diff --check` clean · secret scan: bundle/repo hits are scan
  tokens and a truncated task-id only — **0 real secrets**.
- **Canonical master byte-identical to pre-017** (`976876a1…`, live
  hash check) · canonical F2C/G3C assets byte-identical · canonical
  fixtures untouched · **no candidate promoted**.

## 13. Unresolved unknowns

1. Q1 (body proportion as an isolated control) is unanswered — A was
   rejected by the provider's anti-abuse gate and no retry was
   permitted; C's evidence is confounded by re-staging.
2. The Flow "unusual activity" render rejection cause is UNKNOWN
   (browser-extension heuristic suspected; not charged; whether it
   recurs on a future scope is unknown).
3. Whether the Owner prefers any candidate is exactly the open
   decision; worker classifications are advisory.
4. Whether a full-body reference will ever exist (needed for exact
   BODY_PROPORTION_EXACT_AUTHORITY) is an Owner/content question.
5. External spend: 4 generation submissions (1 rejected uncharged by
   the provider); 0 uploads; 0 external AI API calls; 0 TTS.

## 14. Final status

**OWNER_DECISION_GATE** — the Owner reviews
`OWNER_MOTION_COMPARE_REEL_017.mp4` and fills
`owner_motion_decisions_017.template.json`; no candidate becomes
canonical during Package-017, and nothing was auto-promoted.
