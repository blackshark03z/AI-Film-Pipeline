# Merge inventory: in-flight work before M3

Rule: STUDIO_ARCHITECTURE §11, "In-flight work across the merge" (Owner, 2026-11-21: "Ghi và lập danh sách").
The M3 code merge starts only when every row marked **P1** or **pre-M3** is done, and both repos are clean.
The coordinator keeps this file current; change a row's state when its work is verified, not when it is reported.

Columns: item · owner · state (2026-11-21) · "done" means · needed for.

## AFP (`D:\AI FILM MAKER\AFP-stable`, branch `feature/drama-preprod-p0`)

| # | Item | Owner | State | Done means | Needed for |
|---|---|---|---|---|---|
| A1 | S1 broker addendum (spec `_archive/s1_broker_20261120/S1_ADDENDUM_SPEC.md`, as trimmed by the P1 freeze) | session `s1-addendum` (local_488a0266) | in progress | items committed with tests; Codex round 8 over `5e264c45^..HEAD` = ACCEPT (no High) | P1 |
| A2 | S2-lite: job rows, frozen inputs, intake, synchronous from the CLI | not started | — | lane tests green with the mock/rehearsal runners | P1 |
| A3 | S5 adapter: AFP lane wraps Muse `pool_runner` per lane contract v8 | not started | — | B14 offline parity; recovery drill passes | P1 |
| A4 | P1 pilot: one real film through the AFP lane on Muse | not started | — | no duplicate send, recovery drill passed, quality ≥ P0; technical/product/Owner verdicts | P1 (gate) |
| A5 | Push of ~25 local commits | Owner | pending | pushed | pre-M3 |
| A6 | film08 Gate 6 (Owner review); film05 rights | Owner | OWNER_PENDING | Owner verdict recorded | not blocking (Flow film, finished runtime) |
| A7 | Flow films film03-film08 | — | delivered, or paused with Flow | stay as is; no migration | not blocking |
| A8 | Old Muse attempts: worktrees `codex/muse-video-gateway` (`C:\Users\ADMIN\.codex\worktrees\muse-video-gateway\AFP-stable`) and `feature/muse-flight-pilot` (`D:\AI FILM MAKER\wt-muse-flight-pilot`). Both at 5d981c34 (2026-11-13), 9 dirty files each. Superseded by the lane contract. | coordinator | stale | decide: harvest anything useful into the backlog, then archive the branches (no deletion without a look) | pre-M3 |
| A9 | Old worktree `D:\AI FILM MAKER\AI-Film-Pipeline` (`mission/quality-v2-022-120s`, 2026-11-10, 50 dirty) and the paused Film120-Gemini worktree | Owner decision (fate) | stale | archived or explicitly kept | pre-M3 |
| A10 | 28 local branches not merged into `feature/drama-preprod-p0` | coordinator | unknown | each one merged, archived or kept with a reason | pre-M3 |

## Muse (`D:\Muse`)

Pending: the Muse Tech Lead (local_e75f8a13) has been asked for this half. Rows marked "unknown" are not yet
confirmed.

| # | Item | Owner | State | Done means | Needed for |
|---|---|---|---|---|---|
| M1 | r15 stop-all fix, plus 2 new fixes: test guard on the production halt path; refusal → HALTED / exit 4, no silent drop | r15 session (local_3a840c58), Muse TL | in progress | Codex ACCEPT; tests green | P1 |
| M2 | Clear the fake halt written by a test at 02:55Z | Owner | pending | halt cleared by the Owner | P0 rerun |
| M3 | PRE-TAG #11 (no `src.unlink()`), accounts.json lock, Round A, Round B (lane contract v8) | Muse TL | not started (after M1) | per contract §14; Codex scoped round | P1 |
| M4 | `muse_studio` under git, secrets excluded; resolve the staged scratch deletions | Muse TL, after the Owner's direct confirmation | pending | baseline commit; .gitignore covers `muse_studio/data/accounts.json*`, `profiles/`, `lane_leases.json`, cookie/session files | pre-M3 (and a safety net now) |
| M5 | Pinned tag `muse-v1.0-r15` (D8) | Muse TL | after M1+M3 | tag exists, secret scan clean | P1 |
| M6 | P0 BLACK_PILOT baseline (`C:\film-work\BLACK_PILOT_P0_20261120`) | Muse TL | run 1 stopped by the fake halt (22/22 plates, 12/16 anchors) | full standalone run; timings, QC, defects, quota reported | P1 (parity reference) |
| M7 | BIKER film | unknown | lease expired 2026-11-20, process gone | unknown | unknown |
| M8 | Other sessions and handoffs in `D:\Muse` (`HANDOFF_*`, `_director_review_*`) | unknown | unknown | listed and closed or kept | pre-M3 |
