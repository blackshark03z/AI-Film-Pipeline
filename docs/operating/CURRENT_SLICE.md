# SLICE-0008 — EditManifest + Rough Cut Kernel + Editorial Provenance

## Worker model

```text
Primary model: GPT-5.6 Sol
Thinking effort: High
```

After the editorial architecture decision is frozen and implementation becomes mechanical:

```text
GPT-5.6 Sol / Medium is sufficient
```

---

# 1. Accepted baseline

Start from:

```text
9ed65e6000518daa8270cdffa38470e3300d724c
```

SLICE-0007 is PROVEN AND CLOSED.

Exact approved take:

```text
selected_take_id:
take_a4f85e57ca88fe9629eb0c377ca6751711116c2f61425d9595d75ba09898647b

shot_id:
FLOW_CANARY_001

generation_attempt_id:
attempt_600664fc7042d7e7c7321afe521b758f64da312f70d679552b027eb1b145a6b5

asset_id:
asset_c45abad93f33adbf43a6da62f3a04091b1cb712314ef209e6d84bea31a653c01

asset_sha256:
c5014f1438dd8b4e1fbcd85df85fc5216bf91985b2164d0afbe5c3a0695abacf
```

Human selection authority:

```text
human_with_vlm_assist
```

Do not reopen QC.

Do not regenerate media.

---

# 2. Goal

Prove:

```text
SelectedTake
→ EditManifest
→ deterministic editorial plan
→ rough-cut media artifact
→ validation
→ provenance/readback
```

while preserving a clean boundary between:

```text
editorial intent
```

and:

```text
render implementation
```

The rough cut is NOT the final film master.

---

# 3. Frozen domain semantics

Use existing `EditManifestV1`.

Do not redesign or replace it merely because another format is more convenient.

Canonical editorial state:

```text
SelectedTake
PickupRequest
EditManifest
MasterRecord
```

Relationship:

```text
SelectedTake
→ EditManifest usage

EditManifest
→ PickupRequest?
→ new ShotSpec / GenerationAttempt if necessary
```

Do not create PickupRequest unless actual editorial evidence requires one.

---

# 4. Real slice limitation

The real project currently contains only one approved SelectedTake.

Therefore the real rough cut will naturally be:

```text
one clip
```

This is acceptable for proving real provenance and render plumbing.

However, one clip cannot prove:

```text
ordering of multiple shots
cut boundaries
multi-clip trims
timeline duration accumulation
duplicate/missing ordering protection
```

Therefore prove those semantics separately with deterministic local fixtures/tests.

Do NOT generate additional AI video solely to make the test look more realistic.

---

# 5. Mandatory solution-space exploration

Before implementation, compare all credible editorial strategies.

Use:

```text
SEARCH
→ REUSE
→ COMPARE
→ COMPOSE
→ BUILD LAST
```

Inspect:

```text
current repository
AutoVideoPipeline
existing FFmpeg helpers
installed local video tooling
existing Resolve/export utilities if any
```

Do not assume FFmpeg is automatically the answer.

---

# 6. Option A — EditManifest only

Architecture:

```text
SelectedTake
→ EditManifest JSON/SQLite
```

Strength:

```text
simple
provider-neutral
perfect provenance
no render complexity
```

Weakness:

```text
does not prove actual media assembly
```

Evaluate but likely insufficient alone for SLICE-0008 acceptance.

---

# 7. Option B — FFmpeg concat/remux

Possible pipeline:

```text
EditManifest
→ resolved source files
→ concat plan
→ FFmpeg
→ rough_cut.mp4
```

Evaluate:

```text
stream copy where compatible
versus
controlled re-encode
```

Do not blindly use `-c copy` if trims/keyframes make output semantics unreliable.

Strength:

```text
lightweight
mature
fast
already aligned with implementation plan
```

Weakness:

```text
format compatibility
keyframe trim behavior
mixed media characteristics
```

---

# 8. Option C — FFmpeg filtergraph

Possible use for:

```text
precise trims
scale/pad normalization
framerate normalization
audio handling
multi-clip concat
```

Strength:

```text
deterministic
precise
flexible
```

Weakness:

```text
more complexity
usually requires re-encode
```

Compare against simple concat.

Do not build a giant generic FFmpeg abstraction.

---

# 9. Option D — EDL

Evaluate EDL as a Resolve/editorial interchange option.

Strength:

```text
simple
well understood
easy timeline interchange
```

Weakness:

```text
limited metadata
timecode constraints
weak modern feature representation
```

Do not select solely because it is historically common.

---

# 10. Option E — FCPXML / Resolve-compatible XML

Evaluate whether generating a lightweight Resolve-importable interchange file materially improves V1.

Strength:

```text
stronger editor handoff
timeline reconstruction
```

Weakness:

```text
schema/version complexity
Resolve-specific edge cases
additional testing burden
```

Do not make Resolve XML the canonical Film state.

It may only be a derived export from EditManifest.

---

# 11. Option F — OpenTimelineIO

Evaluate OTIO.

Questions:

```text
already installed?
already reused somewhere?
does it reduce complexity now?
does the current one-shot pipeline need it?
```

Current SoT previously positions OTIO as a later upgrade, so do not introduce it merely for architectural elegance.

Select only if concrete reuse/economic evidence justifies it.

---

# 12. Option G — direct DaVinci Resolve scripting

Evaluate but treat cautiously.

Potential:

```text
create project
import media
create timeline
place clips
```

Benefits:

```text
direct production integration
```

Risks:

```text
local Resolve dependency
version/API coupling
headless/runtime complexity
harder deterministic testing
```

Do not make Resolve runtime availability required for Film Core.

---

# 13. Option H — Remotion / browser video rendering

Explicitly evaluate and likely reject for this kernel unless surprising reuse exists.

The pipeline already has immutable real media clips.

Rendering them through Chromium/React generally adds:

```text
CPU overhead
encoding overhead
browser dependency
unnecessary abstraction
```

Do not reuse technology merely because it exists elsewhere.

---

# 14. Required architecture decision

Before BUILD, produce:

```text
OPTION_A_MANIFEST_ONLY
availability:
strength:
weakness:
decision:

OPTION_B_FFMPEG_CONCAT
availability:
strength:
weakness:
decision:

OPTION_C_FFMPEG_FILTERGRAPH
availability:
strength:
weakness:
decision:

OPTION_D_EDL
availability:
strength:
weakness:
decision:

OPTION_E_FCPXML_RESOLVE
availability:
strength:
weakness:
decision:

OPTION_F_OTIO
availability:
strength:
weakness:
decision:

OPTION_G_RESOLVE_SCRIPTING
availability:
strength:
weakness:
decision:

OPTION_H_REMOTION
availability:
strength:
weakness:
decision:
```

Then document the smallest sufficient composition.

Likely target shape, but DO NOT assume before investigation:

```text
canonical EditManifest
+
FFmpeg rough-cut renderer
+
optional derived editor handoff artifact
```

---

# 15. EditManifest construction

Construct the real manifest strictly from persisted SelectedTake data.

Do not type asset IDs from memory if store readback is available.

For each clip prove:

```text
shot exists
SelectedTake exists
SelectedTake belongs to shot
SelectedTake points to Asset
QCReport final decision = pass
Asset SHA matches local bytes
```

Reject unapproved assets.

Reject arbitrary GenerationAttempt output that has not become SelectedTake.

---

# 16. Manifest identity

Manifest ID should be deterministic from canonical editorial intent.

Same:

```text
project
ordered clips
source trims
target durations
```

should produce the same logical manifest ID.

Changing:

```text
clip order
selected take
trim
```

must change manifest identity.

Do not include absolute machine-specific filesystem paths in canonical identity.

---

# 17. Ordering rules

`order` must form an unambiguous timeline.

For V1 prefer:

```text
1..N
```

with:

```text
no duplicate order
no missing selected_take_id
no missing asset_id
```

The schema alone may not enforce uniqueness; runtime validation should.

Do not silently sort malformed manifests and pretend they were valid.

---

# 18. Trim semantics

Define exact semantics for:

```text
source_in_s
source_out_s
target_duration_s
```

At minimum:

```text
source_in_s >= 0
source_out_s > source_in_s when provided
source_out_s <= actual media duration + documented tolerance
```

Define whether `target_duration_s` is:

```text
validation intent
```

or:

```text
request for retiming
```

For V1, strongly prefer:

```text
no implicit speed change
```

unless current SoT says otherwise.

If target duration differs from trimmed duration, flag rather than silently retime.

---

# 19. Audio policy

Explicitly decide V1 behavior.

Possible:

```text
preserve source audio
strip audio
preserve only when stream exists
```

Do not accidentally lose source audio because FFmpeg invocation omitted it.

Do not invent music/sound design in this slice.

Record chosen policy.

---

# 20. Timeline normalization

Evaluate whether V1 should normalize:

```text
resolution
pixel format
frame rate
audio sample rate
```

before concat.

For current single real clip, no unnecessary transformation is required.

For deterministic multi-clip fixtures, prove behavior when clip properties differ.

Prefer explicit fail/normalize rules over FFmpeg implicit behavior.

---

# 21. RoughCutRecord

Do NOT automatically create a new canonical Film entity unless existing schema/model already provides one.

First search for existing representation.

If none exists, rough-cut render metadata may remain implementation/runtime evidence:

```text
manifest_id
output_path
output_sha256
duration
resolution
codec
render_method
render_command_fingerprint
created_from_manifest
```

Canonical truth remains:

```text
EditManifest
```

not FFmpeg command lines.

---

# 22. Real rough cut

Use:

```text
FLOW_CANARY_001
```

and its approved SelectedTake.

Generate:

```text
rough cut media file
```

from exactly that selected asset.

No AI generation occurs.

Validate:

```text
file exists
non-empty
ffprobe valid
video stream exists
duration consistent with manifest
expected resolution
full decode succeeds
SHA-256 recorded
```

---

# 23. Provenance

Must be able to traverse:

```text
rough cut
→ EditManifest
→ clip
→ SelectedTake
→ final QCReport
→ Asset
→ GenerationAttempt
→ ShotSpec
```

Fresh storage/readback must prove the links.

Do not allow a rendered rough cut with unverifiable source lineage.

---

# 24. Deterministic multi-clip proof

Because the live project has only one take, construct local deterministic test media.

Allowed:

```text
small FFmpeg-generated color/test clips
existing fixture media
other deterministic synthetic local media
```

Not allowed:

```text
Flow Generate
Seedance Generate
external paid generation
```

Tests must prove:

```text
2–3 clips ordered correctly
clip order affects manifest/render
trims work
timeline duration is correct
duplicate order rejected
invalid source bounds rejected
missing SelectedTake rejected
non-approved Asset rejected
missing file rejected
wrong SHA rejected
```

---

# 25. Render reproducibility

Distinguish:

```text
editorial reproducibility
```

from:

```text
byte-identical encoder reproducibility
```

The primary V1 guarantee is:

```text
same canonical manifest resolves to the same editorial sequence
```

Do not claim byte-identical H.264 output across FFmpeg versions/platforms unless actually proven and controlled.

Record FFmpeg version where useful.

---

# 26. Resolve handoff

Produce a decision, not necessarily a full integration.

At slice end explicitly state one:

```text
RESOLVE_HANDOFF = EDIT_MANIFEST_ONLY
```

or:

```text
RESOLVE_HANDOFF = DERIVED_EDL
```

or:

```text
RESOLVE_HANDOFF = DERIVED_FCPXML
```

or another evidence-backed choice.

If no interchange export is justified yet, that is acceptable.

Do not directly automate Resolve merely to check a box.

---

# 27. PickupRequest

The real single establishing shot should not create a PickupRequest unless actual editorial evidence finds a missing requirement.

Implement/test the invariant:

```text
EditManifest can reference zero PickupRequests
```

Do not fabricate editorial problems.

PickupRequest execution/generation is out of scope.

---

# 28. No external-effect authorization

Hard boundary:

```text
Flow Generate: 0
Seedance Generate: 0
Google API consequential generation: 0
Resolve destructive project modification: 0 unless explicitly authorized later
```

Local:

```text
FFmpeg
ffprobe
filesystem
SQLite
```

are allowed.

---

# 29. Independent review

Reviewer must inspect both:

```text
implementation correctness
solution-space completeness
```

Questions:

```text
Was FFmpeg selected before alternatives were compared?
Is EditManifest still canonical truth?
Did render-specific details leak into SelectedTake/ShotSpec?
Can unapproved Assets enter a timeline?
Are trims mathematically well-defined?
Is media provenance complete?
Are paths machine-dependent inside canonical IDs?
Did worker overbuild OTIO/Resolve integration prematurely?
Is a one-clip success being incorrectly claimed as proof of multi-clip editing?
```

---

# 30. Acceptance

SLICE-0008 is PROVEN when:

```text
solution space explored and documented
EditManifestV1 reused unchanged unless impossible gap proven
real approved SelectedTake becomes a persisted EditManifest clip
manifest identity deterministic
manifest validation rejects invalid lineage/order/trims
real rough cut is rendered locally
real rough cut validates and hashes
rough cut provenance traces to exact SelectedTake/Asset/QC/ShotSpec
fresh readback succeeds
multi-clip behavior proven with deterministic fixtures
no AI generation occurs
full regression passes
no secret leakage
frozen SoT unchanged
```

Resolve import is NOT required for PROVEN unless the architecture decision specifically chooses it as required.

---

# 31. Final report

Return:

```text
RESULT:
PROVEN | INCONCLUSIVE | DISPROVEN

SLICE:
SLICE-0008

MODEL:
  model:
  thinking_effort:

BASELINE_SHA:

EDITORIAL_ARCHITECTURE:
  canonical:
  renderer:
  resolve_handoff:
  otio:
  rationale:

EDIT_MANIFEST:
  id:
  project_id:
  clip_count:
  selected_take_ids:
  deterministic_identity:
  fresh_readback:

REAL_ROUGH_CUT:
  path:
  sha256:
  duration:
  resolution:
  codec:
  audio_policy:
  full_decode:
  manifest_match:

PROVENANCE:
  rough_cut_to_manifest:
  manifest_to_selected_take:
  selected_take_to_qc:
  selected_take_to_asset:
  asset_to_attempt:
  attempt_to_shotspec:
  fresh_readback:

MULTI_CLIP_PROOF:
  fixture_clips:
  ordering:
  trims:
  total_duration:
  invalid_cases:

PICKUP_REQUEST:
  created:
  reason:

GENERATION:
  flow: 0
  seedance: 0

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