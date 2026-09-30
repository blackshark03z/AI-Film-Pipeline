# SLICE-0011 reference transport integration and recovery

## Current stop after reference recovery

Reference recovery below is complete and remains valid. The one authorized
fresh Shot A request later received HTTP200 acknowledgement but yielded no
qualified exact output within 600s. Runner stopped at OWNER_AMBIGUITY_GATE;
no provider operations followed. Shot B was not dispatched; no QC/takes/assembly.
The current report/status contain the precise existing job lineage. Further
Shot A read-only reconciliation needs explicit Owner ambiguity direction.

## Current V2 continuation — recovered, 2026-09-30

Owner's new brief supersedes the historical ambiguity stop below. Resume HEAD
was clean `22dfe4b4f721eba462124998f7a35a5ef34b0890`. Implementation milestone
`54b6b3f8d2085d2cb5e16a26b287890d71b8a79a` fixes primary response slot parsing,
removes recursive metadata UUID conflicts and versions the conjunctive CDN
comparison. 61 focused/230 full tests PASS; compile and diff check PASS;
independent review found no material blocker.

Both existing reservations are now durably VERIFIED with **zero new uploads**.
Read-only exhaustive reconciliation matched Owner's expected canary UUID
`347f9951-5bbc-4910-b6fd-3a17c74e29d2` and original UUID
`53b5a413-7bb5-4f97-9be4-2461794a7d80` before binding; both CDN byte hashes
match V2 evidence. The canary retains its historical FAILED_AMBIGUOUS event and
records honest `catalog_strong_match` / `recovered_existing_upload` provenance.
Fresh-process local qualification readback and zero-network second ensure PASS.

This live evidence qualifies current catalog/readback/reuse of the existing
uploaded resources. No new upload was authorized: the corrected upload parser
is covered by structural offline tests, not a new live response replay. V2's
illustrative 647-byte response was not a captured raw fixture. No claims of
permanent RPC stability, exactly-once delivery or complete ambiguity coverage.

Next: bounded one-generation-per-shot A/B, technical QC and Owner character
review. Historical sections below preserve the earlier checkpoint only.

## Scope and checkpoint

Owner's 2026-09-30 continuation starts from clean branch `codex/slice-0011-reference-i2v-continuity`, SHA `39e08e03f36aaeadd2cbb84fe61829f516d08a31`.

Authority: one additional **research upload-only canary** in a fixed, separate local lineage; zero research video generations. The original reservation `refup_1521a9ea3a8582852abbe2b97bf8de4df2ddba6cb689df67c04e06b26021e3ce` remains consumed and cannot be re-uploaded. After offline integration and live canary pass, Owner authorizes bounded read-only forensic reconciliation of the frozen reference. Production still has at most one fresh generation per exact A/B shot, and the final joint human review gate.

## Gemini audit

Accepted: separate request/identity/verification stages; persist a valid unique Flow UUID immediately before `as29s`, CDN fetch, decode or comparison; verified reuse and identified restart need no upload; externally uncertain restart uses read-only reconciliation.

Rejected or weakened: pre-POST `WIRE_DISPATCHED`; first-match catalog selection; silently skipping unreadable candidates; 64-bit dHash described as dHash256; accepting dHash OR color comparison; unguarded identity replacement/re-arm; incompatible reservation ID/schema; catalog miss as proven absence or fresh upload authority; broad exactly-once/zero-duplicate claims; raw authenticated tracebacks. Gemini's eight simulated tests establish a research state-machine result, not integrated live qualification.

## Implementation decisions

- Existing Film Asset/SQLite primitives remain; no canonical domain entity or frozen schema changes.
- Preserve legacy `reference_uploads` identity, request ID, binding and payload. Add an append-only hash-linked operational event table. The frozen legacy row is `LEGACY_RESERVED_UNCERTAIN`, never a safe new local intent.
- New research intent: `LOCAL_RESERVED` (no legacy row or POST) → atomic reservation plus `REQUEST_ARMED` → `HTTP_RESPONSE_OBSERVED` where actually returned → immediate `REMOTE_RESOURCE_IDENTIFIED` → atomic receipt plus `REMOTE_RESOURCE_VERIFIED`. No durable wire-delivery claim.
- Arm is transactional and single-use. Effective reads reject receipt/journal disagreement and immutable identity changes. Delivery semantics: `AT_MOST_ONCE_WITH_POSSIBLE_LOSS`.
- Reconciliation inspects all qualified length-7 candidate image identities. Strong comparison prefers exact bytes, then exact decoded RGB, then conservative same-dimension color/detail checks requiring **all** bounds (RGB MAE/RMS, outlier fraction, tile error and 256-bit dHash). Unreadable candidates, collisions, drift and bounded catalog misses remain unresolved. Repeated stable observations describe the observed catalog, not a proven remote absence bound.
- Dedicated canary database and different synthetic geometric PNG use the existing accessible project, avoiding another project creation. Fixed lineage prevents a canary allowance reset by changing the CLI root. Production upload command is reuse-only. Generation checks both qualification and recovered original reference against the exact fixed production database.
- Canary artifacts can be reconstructed after interruption using durable arm/HTTP/upload-response UUID/verification evidence. A second ensure and a fresh local process use a session that rejects every network method.

## Milestones and status

1. Gemini audit and minimal integration: implemented.
2. Offline matrix: 42 focused tests passed, including required failure windows plus collision, unreadable candidate, source tamper, concurrent arm, HTTP-before-parse persistence, secret exclusion, canary orchestrator restart and safe session-bootstrap stops. These are offline tests only.
3. Independent review: no remaining material prewrite code blocker after fixing production-root bypass and canary artifact restart; the auth-stop delta also reviewed clean. Full regression: **211 passed**; compileall and diff check passed. Authentication is now resolved through Owner-operated ordinary Chrome followed by ordinary Playwright cookie export; exact-project runner catalog preflight qualified 3 rows. The authorized live canary then consumed one arm and observed HTTP200/647 bytes, but persisted no qualified media identity. It stopped immediately at **OWNER_AMBIGUITY_GATE**; no provider query/write followed the stop. Live transport qualification remains unproven.
4. Frozen reference read-only forensic recovery: not started; original row remains unchanged.
5. Two production I2V shots, reference/paired QC and Owner review: pending reference recovery.
6. Approval-only final QC/takes, ordered rough cut/export, candidate handoff: pending Owner visual approval.

No Story Auto runtime import, AutoEdit change, provider switch, Seedance generation or billing change.

## Durable stop and next action

The research database has one synthetic reference Asset, zero upload reservations/events and zero attempts/jobs. Research SHA: `dc766e136c039ce4ae25f78dc7555c161a6178e8c835cf3d37600b4d7d0e8b0e`. The original database still has its exact one consumed reservation, `RESERVED`, null remote identity/hash, one reference Asset and zero attempts/jobs. No frozen-reference forensic query was performed; live qualification has not passed.

**Superseding canary stop:** research now has one consumed reservation and four events, effective `FAILED_AMBIGUOUS`, with no remote UUID/provider hash. Reservation `refup_2773df1c9a68e852ad4ccad0abbe1c12ed9cd7f1ccb02984ef181df9538275dd`; request `e817207e-f0c4-5b90-b425-33230e3f7b9d`. The actual callback recorded HTTP200 and 647 bytes; this is HTTP observation, not proven upload acceptance. No retry/reconciliation/provider query after the stop. Canonical local timeline SHA `c8f75c6441a8e53dba94cf432553a1fae35ea50e32c9efb4a3a1e8b83b1a9903`. Both original and research attempts remain consumed; Owner ambiguity direction is now required. The older auth descriptions below are historical.

Local sanitized bootstrap evidence: `projects/character_continuity/reference_qualification_20260930/session_failure.json` (ignored runtime output). Standard Google account login has been opened in the visible Codex browser. Its previous account could not access the exact project, so Owner must sign in as the previously attested `hoangbsea` account. Obtain a refreshed local cookie export without printing its values, then resume the same fixed canary lineage. The additional upload allowance is unconsumed; the original consumed reservation must never be re-uploaded. No automatic SLICE-0012.

### Login follow-up

Owner has completed login. The original sign-in tab became unresponsive, but a fresh tab in the same browser loaded normally. The visible Google account chooser listed Hoang/hoangbsea; selecting it exposed the exact project, whose UI fully loaded at `/u/3/project/f6b40e79-d6f8-4354-80ae-c863260e96f5`. Browser/project access is now verified; this UI observation is not live RPC qualification or frozen media attribution.

The supported Codex browser capabilities have no cookie/session export. An export from the previous dedicated Flow owned profile was saved outside Git using the browser context cookie API; its read-only runner preflight failed at authentication, with zero upload/video RPC calls. No profile copying, credential decryption, automated sign-in, CAPTCHA intervention or provider write was used. A fresh local cookie JSON from the newly authenticated session is still needed. Current stop remains `OWNER_AUTH_REQUIRED` for that transfer, with both research upload and generation allowances unconsumed. Screenshot: `projects/character_continuity/reference_qualification_20260930/flow_project_ready.png` (ignored).
