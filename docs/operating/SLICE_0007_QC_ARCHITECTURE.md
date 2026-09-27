# SLICE-0007 QC architecture decision

Decision made against the frozen V1 QC contracts and the proven Attempt-5 Asset, before implementation. The current runtime has FFmpeg/ffprobe and the existing immutable lineage store. The repository initially had no QC adapter; `config/runtime.example.yaml` names `VERIFY_AT_RUNTIME`. The AutoVideoPipeline Gemini client provides an established default model and key pool but only text-input requests. Subsequent safe runtime discovery confirmed the existing key can list `generateContent` models and the established `gemini-3.8-flash` default is available. Google documents inline image input for `generateContent`; the selected adapter uses five small timestamped frames, with a fake transport test before the real advisory call. No billing or subscription setting is changed.

| Lane | Strength | Weakness | Incremental cost | Decision |
| --- | --- | --- | --- | --- |
| OPTION_A_DETERMINISTIC_TECHNICAL | Reproducible byte, stream, duration, decode and lineage checks | Cannot judge shot intent or editorial value | Local CPU, seconds | Select as hard gate |
| OPTION_B_TEMPORAL_HEURISTICS | Surfaces black frames, freezes or scene changes for review | Static locked shot makes low-motion and freeze signals ambiguous | Local CPU, seconds | Select as advisory evidence only |
| OPTION_C_FULL_VIDEO_VLM | Can potentially reason over motion and continuity | No qualified configured video input runtime here; model error and cost uncertainty | External call and possible charges | Defer until separately qualified |
| OPTION_D_SAMPLED_FRAME_VLM | Cheaper visual snapshot comparison; available configured model discovered | Can miss short people, rain/motion and transient geography changes | One external call with possible usage charge | Select as advisory, after fake transport proof |
| OPTION_E_HUMAN_ONLY | Human can judge identity, narrative, continuity and editorial usefulness | Repeats mechanical checks and burdens reviewer with raw data | Human minutes | Select for subjective final authority, with a compact packet |
| OPTION_F_HYBRID | Separates reproducible facts, advisory signals and human authority | Requires explicit evidence/policy boundaries | Local CPU plus human minutes | Select as minimal V1 stack |

## Selected composition and policy

1. Verify exact ShotSpec → Attempt → ProviderJob → Asset lineage, stored digest, media metadata and full decode. A byte or required technical contract violation automatically **fails** the technical gate. Duration tolerance is ±0.5 seconds, chosen for a nominal eight-second generated clip and container timestamp rounding; it is explicit and tested.
2. Extract start, quarter, midpoint, three-quarter and end frames and a contact sheet. Record frame hashes and temporal FFmpeg observations as immutable evidence. These can prompt inspection but cannot certify artistic truth or fail a deliberately locked shot by low motion alone.
3. Record separate visual, continuity and editorial criteria from the exact ShotSpec. Run the sampled-frame VLM once if the configured model accepts the structured request; retain its observations as advisory evidence only. Until a human review resolves subjective gates, the report decision is `needs_human_review`.
4. A human `APPROVE` with resolved required criteria may yield `pass` and an exact-Asset SelectedTake. A human `REJECT` with evidence-backed failure codes yields `fail` and RepairDecision. A critical continuity failure or technical hard failure prevents selection even if other gates pass. `NEEDS_REVIEW` leaves no SelectedTake. No scalar score or confidence threshold controls a gate.

Automatically fail: digest mismatch, missing/invalid stream, decode error, duration outside tolerance, broken lineage, human-confirmed critical continuity failure. Automatically pass: only deterministic technical subchecks and a technical gate with all required subchecks met. Advisory only: black/freeze/scene/motion statistics, sampled frames, any future VLM observation. Human authority: identity, visual conformance, narrative, performance, continuity, editorial usefulness, and final take selection. A VLM `uncertain` result stays unresolved.

The QCReportV1 schema has boolean gate fields but no unresolved value. Therefore `pass=false` plus an explicit `VISUAL_HUMAN_REVIEW_REQUIRED`, `CONTINUITY_HUMAN_REVIEW_REQUIRED`, or `EDITORIAL_HUMAN_REVIEW_REQUIRED` issue denotes a pending gate, while overall `needs_human_review` distinguishes it from a confirmed failure. QCEvidence retains the evaluator, criterion, verdict, source artifact and exact Asset identity; report identity derives deterministically from that persisted evidence and a persisted human decision.

API input reference: [Google Gemini image understanding](https://ai.google.dev/gemini-api/docs/generate-content/image-understanding). Availability was checked against the configured account's model listing before the one advisory call; model listing alone was never treated as QC proof.
