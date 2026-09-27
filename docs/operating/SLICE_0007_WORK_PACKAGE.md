# SLICE-0007 — QC Kernel, Evidence Packet & Human-Authoritative Take Decision

## Accepted baseline

Start from accepted candidate:

```text
f8d58a87af7137b508a5d1fd4a3a35835c15594d
```

SLICE-0006 is PROVEN.

Use the proven Asset from Attempt 5:

```text
projects/flow_canary/outputs/95d299c70b8a5a37ec1e1fed.mp4
```

Known lineage:

```text
ShotSpec
→ PromptPlan
→ RoutingDecision
→ GenerationAttempt
→ ProviderJob
→ ProviderObservedIdentity
→ Asset
```

Do not regenerate this shot.

No Flow Generate is authorized in SLICE-0007.

---

# 1. Goal

Prove the next pipeline transition:

```text
Proven Asset
→ QC evidence
→ QCReport
→ human-authoritative disposition
→ SelectedTake
OR
→ RepairDecision
```

This slice is about:

```text
quality evaluation
structured evidence
selection semantics
repair semantics
```

not provider transport.

---

# 2. Frozen QC semantics

Respect existing V1 SoT.

QC gates remain separate:

```text
technical
visual
continuity
editorial
```

Do NOT collapse them into:

```text
one weighted score
one average score
one "AI quality score"
```

A shot can be visually attractive and still fail because a critical continuity invariant is violated.

Existing `QCReportV1` schema remains the canonical report contract.

Existing `RepairDecisionV1` remains the canonical repair contract.

Do not modify frozen SoT files unless an actual impossible semantic gap is demonstrated.

---

# 3. Real canary intent to evaluate

The exact frozen ShotSpec should be loaded from the proven lineage, not reconstructed from memory.

Expected intent includes:

```text
duration target: 8s
shot type: establishing
framing: WS
camera height: eye level
lens intent: wide
camera movement: locked

environment:
  night
  rain
  quiet reflective urban alley

blocking:
  static empty alley
  rain falls
  reflected light shimmers
  same spatial composition at end

critical invariants:
  no people
  stable alley geography
```

QC must compare output against intent wherever evidence makes that possible.

---

# 4. Mandatory solution-space exploration

Before implementation, evaluate all major QC approaches.

Do not select one technique first and tunnel into it.

Use:

```text
SEARCH
→ REUSE
→ COMPARE
→ COMPOSE
→ BUILD LAST
```

Inspect current repository and reusable utilities before creating new code.

---

# 5. Lane A — Deterministic technical QC

Evaluate deterministic checks that do not require an AI model.

Examples:

```text
file exists
file non-empty
stored SHA-256 matches bytes
ffprobe accepts file
video stream exists
duration
width
height
codec/container facts
decode succeeds
lineage Asset ↔ GenerationAttempt intact
```

Hard contract violations may automatically fail the technical gate.

For the current canary, compare actual duration to the ShotSpec target using an explicit tolerance rather than exact floating-point equality.

Do not invent arbitrary thresholds without documenting rationale.

---

# 6. Lane B — Temporal / signal heuristics

Investigate cheap media-analysis signals such as:

```text
black-frame detection
freeze detection
frame corruption
abnormal duplicated-frame runs
flicker indicators
sudden unexpected scene changes
motion magnitude
camera-motion proxies
```

Potential tools:

```text
FFmpeg / ffprobe
OpenCV only if already available or lightweight
existing utilities in AutoVideoPipeline
```

Important:

These signals are generally evidence, not artistic truth.

Example:

```text
low motion
```

must NOT automatically fail a locked observational shot.

Likewise:

```text
freeze-like statistics
```

may be correct for a deliberately static frame.

Avoid heuristic false positives.

---

# 7. Lane C — ShotSpec conformance

Evaluate whether output follows explicit ShotSpec intent.

For this canary:

```text
is this an establishing wide shot?
is the scene at night?
is rain visibly present?
is the alley empty?
are people absent?
is camera effectively locked?
is geography stable?
does the start/end composition remain sufficiently stable?
```

These claims need visual evidence.

Possible evaluation mechanisms:

```text
full-video multimodal model
sampled frames
contact sheet
motion analysis
human inspection
hybrid
```

Do not claim an invariant is verified if available evidence cannot establish it.

---

# 8. Lane D — Full-video VLM QC

Evaluate whether the already configured Gemini runtime can inspect the complete video directly.

Do not hard-code a particular model name merely from prior assumptions.

Discover from:

```text
existing project configuration
installed SDK capabilities
available configured Gemini model
```

Use existing configured API credentials only.

No billing/subscription change is authorized.

If no usable configured VLM exists, continue without it.

VLM output is advisory evidence, NOT human authority.

Require structured output.

Suggested evidence form:

```text
criterion
verdict:
  pass
  fail
  uncertain
confidence
observations
time_ranges
failure_code_candidate
```

Do not allow free-form prose alone to control QC state.

---

# 9. Lane E — Sampled-frame / contact-sheet VLM

Compare full-video analysis with a cheaper strategy:

```text
extract representative frames
+
start/end frames
+
temporal checkpoints
+
optional contact sheet
→ VLM
```

For an 8-second clip, candidate sampling may include:

```text
start
25%
50%
75%
end
```

plus any frames identified by temporal heuristics.

Do not freeze this sampling strategy unless evidence shows it is sufficient.

Evaluate:

```text
cost
latency
miss risk
temporal understanding
camera movement detection
continuity detection
```

---

# 10. Lane F — Human review packet

V1 human authority is mandatory for:

```text
identity
narrative correctness
performance
continuity
editorial usefulness
```

Therefore build a compact review artifact that minimizes Owner work.

Preferred review packet:

```text
video path
ShotSpec intent
technical QC summary
key frames/contact sheet
VLM advisory findings if available
detected failure candidates
critical invariants
recommended decision
```

The human should not need to inspect raw logs.

Human decision surface should be minimal:

```text
APPROVE
REJECT
NEEDS_REVIEW
```

with optional structured failure codes.

Do not force the Owner to manually reconstruct technical evidence.

---

# 11. Lane G — Hybrid QC

Explicitly evaluate a composed strategy such as:

```text
Deterministic technical gate
        ↓
Temporal evidence
        ↓
VLM advisory conformance
        ↓
Human-authoritative review where required
        ↓
QCReport
```

Compare this against:

```text
pure manual QC
pure VLM QC
pure deterministic QC
```

Select the smallest architecture that satisfies V1 truth.

---

# 12. Required architecture decision

Before BUILD is accepted, produce:

```text
OPTION_A_DETERMINISTIC_TECHNICAL
strength:
weakness:
cost:
selected/rejected:

OPTION_B_TEMPORAL_HEURISTICS
strength:
weakness:
cost:
selected/rejected:

OPTION_C_FULL_VIDEO_VLM
strength:
weakness:
cost:
selected/rejected:

OPTION_D_SAMPLED_FRAME_VLM
strength:
weakness:
cost:
selected/rejected:

OPTION_E_HUMAN_ONLY
strength:
weakness:
cost:
selected/rejected:

OPTION_F_HYBRID
strength:
weakness:
cost:
selected/rejected:
```

Also explicitly answer:

```text
Which checks can automatically FAIL?
Which checks can automatically PASS?
Which checks can only produce advisory evidence?
Which checks require human authority?
```

---

# 13. Evidence model

Do not overload `QCReport` with raw diagnostics.

Prefer an internal evidence layer such as:

```text
QCEvidence
```

with immutable source references.

Conceptually:

```text
evidence_id
asset_id
generation_attempt_id
evaluator_type
evaluator_version
criterion
observation
verdict
confidence if applicable
time_range if applicable
source_artifacts
```

Possible evaluator types:

```text
ffprobe
ffmpeg
temporal_heuristic
vlm
human
```

This is implementation evidence, not new Film Truth.

Do not modify frozen SoT simply to add this object.

---

# 14. Failure taxonomy

Map findings to existing taxonomy.

Use categories such as:

```text
TECHNICAL_*
IDENTITY_*
WORLD_*
CONTINUITY_*
PERFORMANCE_*
CAMERA_*
VISUAL_TEMPORAL_*
EDITORIAL_*
```

Prefer stable machine-readable failure codes plus human-readable evidence.

Examples relevant to the current canary might include:

```text
TECHNICAL_DURATION_MISMATCH
CAMERA_MOVEMENT_UNEXPECTED
WORLD_TIME_OF_DAY_MISMATCH
WORLD_WEATHER_MISMATCH
CONTINUITY_GEOGRAPHY_DRIFT
VISUAL_TEMPORAL_FLICKER
EDITORIAL_UNUSABLE
```

Do not invent a huge taxonomy in advance.

Add only codes needed by tested cases plus a minimal stable pattern.

---

# 15. QCReport derivation

`QCReportV1` must be deterministic from persisted evidence + human decision.

Valid decisions remain:

```text
pass
fail
needs_human_review
```

Rules:

```text
hard technical failure
→ fail

unresolved human-authoritative criterion
→ needs_human_review

critical continuity failure
→ fail

all required gates genuinely satisfied
→ pass
```

Do not convert model confidence directly into final pass/fail without policy.

---

# 16. SelectedTake

Repository search currently shows no existing SelectedTake implementation.

Before creating one:

```text
search entire repo
inspect canonical domain references
reuse existing representation if found
```

If still absent, create only a minimal runtime/persistence model.

Suggested concept:

```text
SelectedTake:
  selected_take_id
  shot_id
  generation_attempt_id
  asset_id
  qc_report_id
  selection_authority
  selected_at
  notes
```

Selection authority should make provenance explicit, for example:

```text
human
human_with_vlm_assist
```

Do not label an AI-only decision as human-authoritative.

Persist exact Asset identity.

---

# 17. RepairDecision branch

If the real canary fails:

produce `RepairDecisionV1`.

A failure must state:

```text
failure_codes
strategy
changes
next_action
budget impact
human approval requirement
```

Allowed repair strategies already include:

```text
shotspec_repair
prompt_recompile
provider_control_change
alternate_provider
split_shot
pickup
editorial_workaround
transient_transport_retry
human_review
```

Do not Generate the repair in this slice.

`transient_transport_retry` is not valid for visual/continuity failures.

---

# 18. Test both decision branches deterministically

The real canary may naturally PASS or FAIL.

Do not manipulate its result merely to exercise code.

Use deterministic fixtures to prove:

```text
PASS → SelectedTake
FAIL → RepairDecision
NEEDS_HUMAN_REVIEW → no automatic SelectedTake
```

Also test:

```text
technical failure overrides visual beauty
critical continuity failure prevents selection
VLM uncertainty cannot silently become pass
human approval can finalize a valid candidate
human rejection produces/links repair path
same QC evidence produces stable report identity
```

---

# 19. Real Asset proof

Run the chosen QC stack against the proven Attempt-5 Asset.

At minimum prove:

```text
Asset hash verified
lineage read back
technical QC executed
visual evidence produced
continuity evidence produced
editorial evidence produced
QCReport persisted
fresh QC readback
```

If a configured VLM is available without account/billing changes:

run the selected advisory VLM path.

Record:

```text
provider/model
input strategy
token/cost metadata if available
latency
structured result
```

Do not record API keys.

---

# 20. Cost measurement

QC itself affects production economics.

Record where possible:

```text
technical_qc_wall_clock
vlm_qc_wall_clock
vlm_cost
human_review_minutes
total_qc_cost_per_shot
```

Do not over-engineer cost accounting yet.

The benchmark later needs human minutes and approval economics.

---

# 21. No regeneration

Hard boundary:

```text
Flow Generate authorized: 0
Seedance Generate authorized: 0
```

If QC determines that regeneration is needed:

```text
produce RepairDecision
STOP at repair authorization boundary
```

Do not execute the repair.

---

# 22. Independent review

Independent review must check two dimensions:

```text
implementation correctness
solution-space completeness
```

Reviewer must explicitly ask:

```text
Did the worker prematurely lock into a VLM?
Did deterministic evidence get ignored?
Are heuristics being treated as truth?
Is human authority preserved?
Is a single scalar score sneaking back in?
Are failure codes evidence-backed?
Can QC be reproduced from persisted inputs?
```

---

# 23. Acceptance

SLICE-0007 is PROVEN when:

```text
solution space compared
chosen QC architecture documented
proven Asset consumed without regeneration
technical gate works
structured visual/continuity/editorial evidence exists
QCReportV1 persists and fresh-readbacks
human-authority semantics are preserved
PASS/FAIL/NEEDS_HUMAN_REVIEW branches are tested
SelectedTake or RepairDecision path is deterministic
no frozen SoT mutation
no secret leakage
full regression passes
```

A real human selection of the canary is desirable but not required for proving the deterministic kernel if the real QC result legitimately ends in `needs_human_review`.

---

# 24. Final report

Return:

```text
RESULT:
PROVEN | INCONCLUSIVE | DISPROVEN

SLICE:
SLICE-0007

BASELINE_SHA:

QC_ARCHITECTURE:
  deterministic:
  temporal:
  vlm:
  human:
  final_policy:

REAL_ASSET:
  asset_sha256:
  duration:
  resolution:
  lineage_verified:

TECHNICAL_GATE:
  decision:
  findings:

VISUAL_GATE:
  decision:
  findings:
  evaluator:

CONTINUITY_GATE:
  decision:
  findings:
  evaluator:

EDITORIAL_GATE:
  decision:
  findings:
  evaluator:

QC_REPORT:
  id:
  decision:
  failure_codes:
  fresh_readback:

DISPOSITION:
  SELECTED_TAKE |
  REPAIR_DECISION |
  NEEDS_HUMAN_REVIEW

SELECTED_TAKE:
  id:
  authority:

REPAIR_DECISION:
  id:
  strategy:
  changes:
  next_action:

VLM:
  used:
  model:
  input_strategy:
  cost:
  latency:

REGRESSION:
  tests:

INDEPENDENT_REVIEW:

CANDIDATE_SHA:
REMOTE_SHA:
WORKING_TREE:
SECRETS_COMMITTED:
SOT_FILES_CHANGED:

NEXT:
```