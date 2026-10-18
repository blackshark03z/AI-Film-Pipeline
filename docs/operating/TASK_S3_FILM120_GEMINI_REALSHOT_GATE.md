# S3 FILM120 — Gemini Real-Shot Gate WP

**FROZEN Tech Lead contract:** S3 real 120s film, no generated-footage permission yet. Do not create frameworks or redefine Goal.
**Primary authoritative repo:** `D:\AI FILM MAKER\AI-Film-Pipeline`, branch `mission/quality-v2-022-120s`, root HEAD `baa75e5420afeab7f755398946bf45daa124aea4`, root `docs/operating/CURRENT_SLICE.md` and `IMPLEMENTATION_STATUS.md`; Film Product/System SoT under `docs/sot/film/`. Primary root is **dirty and READ-ONLY for Worker**.
**Assigned isolated worktree:** `D:\AI FILM MAKER\AI-Film-Pipeline-Film120-Gemini`, branch `feature/film120-gemini-realshot-001`, expected pre-WP HEAD `baa75e5420afeab7f755398946bf45daa124aea4`.
**POLICY_REF:** `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` — verify exact commit and read `git show POLICY_REF:AGENTS.md`; HEAD policy blob must match.
**Worker:** **Gemini**, in the Owner-selected execution environment, via copy-ready Owner relay. Do not infer Gemini CLI/API model, launch MAR coding Worker, or use quota-exhausted OpenCode. Gemini owns BUILD/HOW and bounded operational PROVE; Tech Lead owns independent PROVE and SoT.

## Product Goal and independently verified starting evidence

Ship **one genuine playable 120-second AI film**: 24 planned chronological five-second scenes all provider-issued shot-specific `QC_ACCEPT` footage with real lineage, sound, continuity-aware editorial and Owner creative acceptance. The existing 120s slate workprint is NOT a final film; do not rebuild and count it as progress.

Primary state `projects/quality_v2_022_longform_120s/v2_022_run_state.json` has exactly **8 accepted** S01–S07 and S10; **16 pending** S08–S09 and S11–S24. Eight corresponding MP4s physically exist in `assets/`; 16 pending do not. Frozen `V2_022_LONGFORM_COMPILATION.json` holds 24 shot plans. `V2_022_POOL_GATE.json` `total_available=1`, `mutations_used=11`, `authorized_cap=27` and old S03/S08 repair wording are historical snapshots, not present entitlement or permission. Older conditional one-free S15 attempt from historical WP at `e7e281d` is NOT current authorization.

## Bounded R1–R6 acceptance

**R1 — Snapshot + safety:** Verify Git worktree/HEAD/dirty/policy, read primary Film SoT and exact Current Slice. Reconcile all 24 Film State slots and full SHA-256 of eight accepted original MP4s without writing mission state. Preserve dirty root `opencode.json`, `tests/test_v2_022_compilation.py`, `tools/v2_020_runner.py`, `tools/v2_021_recover.py`, untracked WIP, other worktrees and protected media.

**R2 — Real asset salvage:** Inspect only pre-existing local shot/journal evidence: primary `assets/`, `slots/` including archives, per-shot current/archived dispatch journals, relevant local snapshots and approved read-only linked worktree paths. Search for a **genuine existing provider-issued shot-specific MP4** absent from Film State. A candidate requires verified shot ID, ShotSpec hash, request/attempt/job/asset lineage, MP4 full hash, decode/ffprobe and QC. Never turn frames, screenshots, unrelated MP4, or slates into `QC_ACCEPT`. **No mutation to Film State, journals, accepted assets or source clips.** If none, record `ZERO_RECOVERABLE` truthfully.

**R3 — Targeted readiness:** Produce a concise truthful readiness matrix for **S08, S09, S11–S24**: missing/possible already-real footage, exact source evidence, continuity role and next action. Choose **one highest-value missing shot** for next real-product progress using story/continuity and previous refusals. Do not rewrite creative ShotGraph or substitute clips.

**R4 — Independent authorization/cost gate:** Review only already available **read-only** evidence on provider model/mode/length, eligible account binding, current-vs-stale credit, per-shot constraints and expected cost. If any account/browser/credential query would exceed approved read-only scope, do not do it; mark `OWNER_ACTION_REQUIRED`. Old cap, expected quota, conditional S15 and previously successful account are NOT current authorization. **NO Generate, Enter/POST, login, paid/free provider call, account rotation or proxy change.**

**R5 — Product decision:** If a legitimate local recoverable asset exists, provide exact candidate + technical evidence for Tech Lead independent acceptance without changing canonical state. Otherwise make **one specific `OWNER_GENERATE_AUTH_REQUIRED` proposal** for the selected missing shot: ID/role, existing approved provider/mode/shot length, identity/account only if verified, current credit confidence, maximum one proposed attempt, cost estimate or UNKNOWN, no retries, stop conditions and required evidence to promote an actual shot. Do not falsely claim a new shot or product delta from tests/memo.

**R6 — Delivery:** Submit one compact report `docs/operating/S3_FILM120_GEMINI_REALSHOT_GATE_DELIVERY.md` with before/after *independently provable* real shot count, R1–R5, exact asset/evidence pointers, genuine blocker, a single next shot/authority decision, tests if any code changed, exact Git revision and protected-state integrity. Commit only the report (or truly necessary pure read-only helper+focused tests if a real defect is demonstrated) on the Worker branch; no media commit. Worker may nominate `PARTIAL` or `PROOF_CANDIDATE` only. Tech Lead independently PROVEs and updates root truth.

## STOP / non-goals

- No new Generate, provider API/UI mutation, credit spend (free or paid), source-site navigation/login, cookie/session/token/DPAPI access, 2FA, proxy/fingerprint/account alteration, deferred GPM profile, release/deploy/push/merge, Film120 source mutation or account rebind.
- Owner's "next ship milestone" authorizes S3 priority and this **local read-only** investigation, NOT a standing budget. Stop at exact external-consent gate.
- No untracked resets/clean, no root code rewrite or refactor, no new SoT/lifecycle/framework, no repeated workprint with 16 slates; no long blind retry loop.
- Limit to one bounded pass; **8/24 remains the honest baseline** unless genuine attributable accepted footage is independently verified. Technical PASS is not product/creative/release PASS.
