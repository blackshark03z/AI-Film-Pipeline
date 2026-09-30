# SLICE-0011 reference transport integration and recovery

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
2. Offline matrix: 40 focused tests passed, including required failure windows plus collision, unreadable candidate, source tamper, concurrent arm, HTTP-before-parse persistence, secret exclusion and canary orchestrator restart. These are offline tests only.
3. Independent prewrite review: no remaining material blocker after fixing production-root bypass and canary artifact restart. Full regression: **209 passed**; compileall and diff check passed. Current live upload-only canary is next; no new provider effects have occurred in this continuation yet.
4. Frozen reference read-only forensic recovery: not started; original row remains unchanged.
5. Two production I2V shots, reference/paired QC and Owner review: pending reference recovery.
6. Approval-only final QC/takes, ordered rough cut/export, candidate handoff: pending Owner visual approval.

No Story Auto runtime import, AutoEdit change, provider switch, Seedance generation or billing change.
