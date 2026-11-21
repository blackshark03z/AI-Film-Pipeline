# Merge inventory: in-flight work before M3

Rule: STUDIO_ARCHITECTURE §11, "In-flight work across the merge" (Owner, 2026-11-21: "Ghi và lập danh sách").
The M3 code merge starts only when every row marked **P1** or **pre-M3** is done, and both repos are clean.
The coordinator keeps this file current; change a row's state when its work is verified, not when it is reported.

Columns: item · owner · state (2026-11-21) · "done" means · needed for.

**Order change (Owner, 2026-11-21: "Tạm bỏ qua, hoàn thành việc hợp nhất và hoàn thiện hệ thống trước khi chạy
tiếp").**
- Film runs are paused: P0 (M8) stops with a PARTIAL baseline, and BIKER (M9) stays off.
- The M3 code merge now comes before Round A/B, S2-lite, S5 and P1. The rows A2-A4 and M4-M5 are built inside the
  merged repo.
- The merge plan is `docs/production/M3_MERGE_PLAN.md` (session `m3-merge-plan`, local_1d450294), v3.2, accepted by the
  coordinator after 3 Codex rounds.
- Merge precondition: A1, M1 (with fixes a-c), M2, M3 and M6 are done.
- How the pause is enforced: the Muse TL published a machine-wide Muse halt, reason `OWNER_PAUSE` ("Not a
  CAPTCHA"), in `D:\Muse\muse_studio\data\muse_halt.json`. It blocks every Muse sender, BIKER included, until the
  Owner runs `--clear-halt`. The BIKER folder is left untouched (the Owner told the Muse TL not to touch it).

## AFP (`D:\AI FILM MAKER\AFP-stable`, branch `feature/drama-preprod-p0`)

| # | Item | Owner | State | Done means | Needed for |
|---|---|---|---|---|---|
| A1 | S1 broker addendum (spec `_archive/s1_broker_20261120/S1_ADDENDUM_SPEC.md`, as trimmed by the P1 freeze) | session `s1-addendum` (local_488a0266) | done: 6e606905, cfb29744, c962414e (R8), c101a974 (R9); 285 passed / 2 skipped. R8 and R9 Highs fixed; round 10 got no verdict (Codex quota), so the coordinator reviewed c101a974 against `codex_out9.md`: both findings fixed as prescribed. ACCEPTED by the coordinator | items committed with tests; Codex round 8 over `5e264c45^..HEAD` = ACCEPT (no High) | P1 |
| A2 | S2-lite: job rows, frozen inputs, intake, synchronous from the CLI | session `s2-lite` (local_d65dafd1, Sonnet), worktree `D:\AI FILM MAKER\wt-s2-lite`, branch `feature/s2-lite` | in progress | lane tests green with the mock/rehearsal runners | P1 |
| A3 | S5 adapter: AFP lane wraps Muse `pool_runner` per lane contract v8 | not started | — | B14 offline parity; recovery drill passes | P1 |
| A4 | P1 pilot: one real film through the AFP lane on Muse | not started | — | no duplicate send, recovery drill passed, quality ≥ P0; technical/product/Owner verdicts | P1 (gate) |
| A5 | Push of the local commits | Owner | done: Owner "Yes, push" (2026-11-21); 53 commits pushed, origin at 6f8e1579 | pushed | pre-M3 |
| A6 | film08 Gate 6 (Owner review); film05 rights | Owner | OWNER_PENDING | Owner verdict recorded | not blocking (Flow film, finished runtime) |
| A7 | Flow films film03-film08 | — | delivered, or paused with Flow | stay as is; no migration | not blocking |
| A8 | Old Muse attempts: worktrees `codex/muse-video-gateway` (`C:\Users\ADMIN\.codex\worktrees\muse-video-gateway\AFP-stable`) and `feature/muse-flight-pilot` (`D:\AI FILM MAKER\wt-muse-flight-pilot`). Both at 5d981c34 (2026-11-13), 9 dirty files each. Superseded by the lane contract. | coordinator | harvested: dirty diffs saved as `_archive/merge_triage/a8_*.patch`, ideas in the M3_MERGE_PLAN backlog (ce0d81aa), both branches tagged `archive/*`. Left: remove the two worktrees at M3 (the 6.4 GB pilot films stay in place) | worktrees removed | pre-M3 |
| A9 | Old worktree `D:\AI FILM MAKER\AI-Film-Pipeline` (`mission/quality-v2-022-120s`, 2026-11-10, 50 dirty) and the paused Film120-Gemini worktree | Owner decision (fate) | stale | archived or explicitly kept | pre-M3 |
| A10 | 28 local branches not merged into `feature/drama-preprod-p0` | coordinator | triaged (`_archive/merge_triage/AFP_TRIAGE_20261121.md`): 12 merged-equivalent, 3 harvest (done), 9 keep, 4 Owner-data. All 28 tagged `archive/<branch>`; no branch deleted yet | each one merged, archived or kept with a reason | pre-M3 |

## Muse (`D:\Muse`)

Source: the Muse Tech Lead (local_e75f8a13), checked 2026-11-21 ~10:05.

| # | Item | Owner | State | Done means | Needed for |
|---|---|---|---|---|---|
| M1 | r15 stop-all fix | session `r15-finish` (local_f8de5db1, Sonnet; replaces local_3a840c58) | in progress, with fixes A-C and the r14 release test | all Round 15 tests green; Codex re-review ACCEPT | P1 |
| M1a | r15 fix A: test guard (L37). A test wrote the real halt file and stopped P0 run 1 | local_3a840c58 | briefed | tests can never reach the production halt path (pytest guard plus module-level env); test added | P1 |
| M1b | r15 fix B: HALTED / exit 4, no silent drop (L37) | local_3a840c58 | briefed | a send-stop refusal gives HALTED / exit 4 with the halt record; a not-submitted failure with no standby goes into batch_errors (keyframe and video paths) | P1 |
| M1c | r15 fix C: unique batch id per run (L38). P0 run 2 reused KF_ANCHOR_01, leaving 4 sends UNCONFIRMED | local_3a840c58 | briefed | per-run batch id and a fresh out dir; the result card must be a real attachment, with no loose-text fallback | P1 |
| M2 | PRE-TAG #11 (no `src.unlink()`) | Muse TL | not started | per contract v8 round plan | P1 |
| M3 | accounts.json lock | Muse TL | not started (after r15, same files) | locked read-modify-write; a `_read_all` error is not `[]` | P1 |
| M4 | Round A (lane mode: forced `--no-ui-sync`, per-child RESULT, no implicit login, film ledger, no unlink) | Muse TL | not started | contract v8 Round A tests green; Codex | P1 |
| M5 | Round B (broker bridge: token on stdin, incarnation, `child_keys` check, halt lock and pending marker, single-mode allocator refusal) | Muse TL | not started; needs A1 | contract v8 §14 Round B tests green; Codex | P1 |
| M6 | `muse_studio` git baseline plus .gitignore for secrets; includes the 31 staged scratch deletions and the modified .gitignore | Muse TL | unblocked: Owner confirmed in the Muse TL session (\"Xác nhận\", 2026-11-21); runs after M1, M2, M3 | `muse_studio` tracked, secrets ignored | P1 (needed before worktrees and the tag) |
| M7 | Pinned tag `muse-v1.0-r15` (D8); the M3 import tag | Muse TL | after M1, M2, M3 and M6 only (M4/M5 Round A/B are built after the merge and ship under a runtime tag, M3_MERGE_PLAN §8) | tag exists; secret scan clean | P1 |
| M8 | P0 BLACK_PILOT (`C:\film-work\BLACK_PILOT_P0_20261120`) | Muse TL | paused (OWNER_PAUSE; run 3 HALTED exit 4, no batch cut mid-send). PARTIAL `P0_BASELINE.json` written: plates 22/22, anchors 12/16, turnarounds 20/32, keyframes 0/171; ledger 54 RESULT / 4 NOT_SENT / 4 UNCONFIRMED (anchors harold, judge_moore, mother, teen); send wall 1386 s; code hash fbbcfef34485ce01 | `P0_BASELINE.json` with per-stage timing and quality, tied to the hash list in `P0_CODE_HASHES.txt` | P1 (parity reference) |
| M9 | BIKER_DEAD_ENGINE_20261120 (`C:\film-work`, 284 shots) | unknown (not a known session; possibly Codex) | last status 2026-11-20 16:32 "NATIVE PROOF RUNNING"; no live process; lease expired. Runs on its own runtime snapshot but shares the account and profile data | finishes on its own runtime, or is closed by the Owner | not P1. Its sends would share accounts with P0 and the lanes, so it must not restart unannounced |
| M10 | Stale film folders in `C:\film-work`: black-drama-eutlzb7ycky (11-17), muse-gateway-20261112, muse-pilot-3m-20261112 | unknown | no activity since 11-13 to 11-17 | archived or kept with a reason | pre-M3 |
| M11 | Muse worktrees: `_worktrees/craft-skills` (clean, 11-19) and `_worktrees/pilot-60s-zero-defect` (49 dirty, 11-02) | unknown | stale | harvested, then archived | pre-M3 |
| M12 | `HANDOFF_CLAUDE_MUSE_20261119.md`, `_director_review_B14_20261119`, `_live_v50_*` (4 dirs, 11-18) | unknown | unchanged since 11-19 | closed or kept | pre-M3 |
| M13 | Idle sessions with cwd `D:\Muse`: local_04a27087 agy-setup, local_3af0d00b lane-leases (failed), local_dc86a1a2 p0-black-pilot (failed, superseded), local_f56b6f23 muse-director | — | idle | archived (Owner) | pre-M3 |
| M14 | Lane contract | both TLs | AGREED v8, Codex ACCEPT, committed in AFP (c73b4dd4) | done | done |
