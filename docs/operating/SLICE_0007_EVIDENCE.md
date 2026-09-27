# SLICE-0007 QC evidence ledger

## Authority and source

- Accepted baseline: `f8d58a87af7137b508a5d1fd4a3a35835c15594d`.
- Exact work package: `CURRENT_SLICE.md`; preserved SLICE-0006 package separately. No Flow or Seedance Generate was authorized or invoked in this slice.
- Source database (ignored local runtime): `projects/flow_canary/slice0006/attempt_05/runtime.sqlite`.
- Source lineage was freshly read as ShotSpec `FLOW_CANARY_001` → PromptPlan → RoutingDecision → GenerationAttempt `attempt_600664fc7042d7e7c7321afe521b758f64da312f70d679552b027eb1b145a6b5` → ProviderJob `job_62eab53994a2b8b1bde875b67f0068da97798a02f8aa75f8765d042edb07f0ea` → exact output binding/acquisition receipt → Asset `asset_c45abad93f33adbf43a6da62f3a04091b1cb712314ef209e6d84bea31a653c01`.
- ProviderJob readback: `SUCCEEDED`, `dispatch_count=1` from SLICE-0006. The immutable GenerationAttempt payload still says `created`; the Job and Asset are the current outcome evidence. SLICE-0007 did not change that dispatch count.
- Exact local Asset: `projects/flow_canary/outputs/95d299c70b8a5a37ec1e1fed.mp4`; SHA-256 `c5014f1438dd8b4e1fbcd85df85fc5216bf91985b2164d0afbe5c3a0695abacf`.

## Solution selection

The six required approaches, their costs and limits, and the selected hybrid policy are in `SLICE_0007_QC_ARCHITECTURE.md`. Deterministic technical checks can fail/pass their own gate; temporal statistics and Gemini observations are advisory. Human review retains authority for identity, visual conformance, continuity, editorial usefulness and final take selection. No weighted or scalar score exists.

## Real QC and cost

| Gate | Result | Evidence |
| --- | --- | --- |
| Technical | PASS | File exists/nonempty; SHA-256 matches; ffprobe valid; 8.0s vs 8.0s target within explicit ±0.5s tolerance; 1280×720; stored metadata matches; full FFmpeg video decode succeeds. |
| Visual | Pending human review | Five frames at 0.2, 2.0, 4.0, 6.0 and 7.8s plus contact sheet. Gemini advisory says wide rainy night alley; it marks whole-video absence of people **uncertain** from samples. |
| Continuity | Pending human review | Start/end and intermediate frames supplied. Gemini advisory sees stable geography and aligned composition, but is not final authority. |
| Editorial | Pending human review | Exact dramatic purpose and review media supplied. Gemini advisory sees an atmospheric establishing view; Owner decides editorial usefulness. |

FFmpeg black-interval detector events: 0; freeze detector events: 0. These are advisory observations, not proof of visual quality. The configured AutoVideoPipeline Gemini key was used without exposing it. Read-only model discovery confirmed the existing `gemini-3.8-flash` default; one sampled-frame advisory call produced six structured criterion observations. Its `empty_no_people` verdict was `uncertain` with 0.6 model-reported confidence; five others were `pass` with 0.75 model-reported confidence. These confidence values did not control any gate. Measured advisory latency: 6.147s; usage metadata: 5,745 prompt tokens, 497 candidate tokens, 6,682 total tokens. Billed cost is unknown. Measured full QC run: 9.410s. A separate deterministic technical rerun measured 0.498s. Human review minutes and total cost per approved shot remain unknown.

The review packet and copied, hash-identical contact sheet/frames are committed under `docs/operating/qc_slice0007/`. The exact MP4 and SQLite database remain local and ignored by Git. The packet links to the local video and committed visual evidence; its six Gemini observations include criterion/verdict/observation and evidence ID. Git blob SHA-256 of the staged packet: `13f8fbb569ac8ba73b2ebef0d89700958b030ff9d0a1dca391f4018fc277a10d` (local CRLF checkout bytes may differ).

## Durable report and disposition

- `QCReportV1` ID: `qcr_fa1ef8247c17b733d2a010a7f090dc847404d3f9954b9163bbc521d4b8e9c86d`.
- Decision: `needs_human_review`; failure codes: none. Gate issues are `VISUAL_HUMAN_REVIEW_REQUIRED`, `CONTINUITY_HUMAN_REVIEW_REQUIRED`, `EDITORIAL_HUMAN_REVIEW_REQUIRED`.
- Fresh SQLite readback rederived the report from 20 immutable evidence records and verified exact Asset lineage plus frame/contact hashes.
- DB counts: 20 evidence, 1 report, 0 human decisions, 0 SelectedTakes, 0 RepairDecisions. No Owner decision was fabricated.
- Pending Owner surface: `APPROVE`, `REJECT` with code-specific concrete observation, or `NEEDS_REVIEW`. Approval must resolve all subjective gates; rejection yields a `RepairDecisionV1`. A technical or confirmed critical continuity failure blocks selection. No repair execution is authorized here.

## Deterministic branch and safety proof

Focused tests cover stable report identity; PASS → exact Asset SelectedTake with explicit human approval; FAIL → RepairDecision with failure code and concrete change; NEEDS_HUMAN_REVIEW → no automatic take; technical failure despite human approval and VLM beauty; confirmed continuity failure; VLM uncertainty; missing technical check; unsupported human rejection; persistence/readback and tamper detection; changed Asset before approval leaves no SelectedTake; changed review frame invalidates readback; fake Gemini transport; real-media technical fail and repair packet. Full suite and independent review results are recorded in the final candidate report.

No frozen Film SoT or root schema file was modified. No secret, cookie, signed URL, authorization header, or API key is included in the candidate.
