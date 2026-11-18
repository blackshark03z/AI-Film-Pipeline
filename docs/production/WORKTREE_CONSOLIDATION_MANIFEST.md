# Worktree Consolidation & Branch Disposition Manifest (2026-11-18)

- **Pinned Policy:** `POLICY_REF = 45f71d6226c5ffc58b4e70f3bcea1bb0151b7003` (blob `AGENTS.md` = `6cab2103...`)
- **Primary Canonical Line:** `D:/AI FILM MAKER/AFP-stable` (branch `feature/drama-preprod-p0`, `film08` M4 candidate committed at `98535367`, Phase 2/3 hardening integrated here).
- **Root Repository:** `D:/AI FILM MAKER/AI-Film-Pipeline` (branch `mission/quality-v2-022-120s`, HEAD `34f9e0dc`, read-only canonical `docs/sot/*` + protected WIP + MAR-reconciled `docs/operating/*`).

---

## 1. Git Worktree Inventory (`17` registered + historical shard cleanup)

| Worktree Path | Branch / Ref | HEAD | Disposition (2026-11-18) |
|---|---|---|---|
| `D:/AI FILM MAKER/AFP-stable` | `feature/drama-preprod-p0` | `98535367+` | **Active canonical production & upgrade baseline** (`film06`, `film07`, `film08`). |
| `D:/AI FILM MAKER/AI-Film-Pipeline` | `mission/quality-v2-022-120s` | `34f9e0dc` | **Root SoT & operating status**; `47` protected WIP/untracked files verified SHA-identical to pre-run snapshot; `3` `docs/operating/*.md` prepended with dated MAR & Product Progress Gate headers. |
| `C:/Users/ADMIN/.codex/worktrees/muse-video-gateway/AFP-stable` | `codex/muse-video-gateway` | `5d981c34` | **Ported into `AFP-stable`** (`src/film_pipeline/production/muse_gateway.py`, `docs/production/MUSE_GATEWAY.md`, `tests/test_muse_gateway.py`, `TakeEntry.cost_unit="muse_requests"`, `film.py muse`). Isolated `muse_pilot_three_minutes` left untouched in branch history. |
| `D:/AI FILM MAKER/wt-muse-flight-pilot` | `feature/muse-flight-pilot` | `5d981c34` | Same commit `5d981c34`; code ported cleanly, pilot assets untouched. |
| `D:/AI FILM MAKER/AFP-film-package` | `feature/post-engine-delegation` | `eceaa135` | **Ported into `AFP-stable`** (`docs/integration/film_package.v1.schema.json`, `film_package_export/*`, `production/post_engine.py`, opt-in `mix --engine` / `AFP_POST_ENGINE_DIR`). Default AFP mix & closed-loop `drama/post.py` loudness normalizer preserved intact. |
| `C:/AFP-Live-v3-20261110` | `codex/real-film-v3-20261110` | `719e77e9` | **Retained / Superseded (not merged)**: legacy v3.1 R2V runtime (`e2e_omni.py`, `flow_r2v_runtime.py`) overlaps root/pre-P0 runtime paths and is superseded by `film_pipeline.production.*`. Kept clean as historical archive. |
| `D:/AI FILM MAKER/AFP-provider-a` | `provider-adapters-a` | `ef3b4c79` | Provider adapters already present in `AFP-stable` (`providers/*`). |
| `C:/Users/ADMIN/.codex/worktrees/film-e2e-ship/AI-Film-Pipeline` | `codex/film-e2e-ship` | `88a99bee` | Historical local v3 ship snapshot; protected. |
| `D:/AI FILM MAKER/AI-Film-Pipeline-System-Ship-20261110` | `codex/production-system-ship-20261110` | `88a99bee` | Same `88a99bee` snapshot; protected. |
| `D:/AI FILM MAKER/AI-Film-Pipeline-Claude-Forensics` | `claude/flow-max-causal-forensics-001` | `174ff2d0` | Historical October forensics branch; retained read-only. |
| `D:/AI FILM MAKER/AI-Film-Pipeline-Film120-Gemini` | `feature/film120-gemini-realshot-001` | `1381e42b` | Historical Film120 branch; retained read-only. |
| `D:/AI FILM MAKER/AI-Film-Pipeline-Live-Qual` | `zcode/live-runtime-qual-001` | `f3167c4e` | Historical ZCode live qual branch; retained read-only. |
| `D:/AI FILM MAKER/AI-Film-Pipeline-Overnight` | `zcode/overnight-qual-001-r2v-runtime-integration` | `717547b6` | Historical overnight R2V qual branch; retained read-only. |
| `D:/AI FILM MAKER/AI-Film-Pipeline-S2-Audio-Review` | `feature/s2-audio-review-001` | `2dad68f9` | Historical S2 audio review branch; retained read-only. |
| `D:/AI FILM MAKER/AI-Film-Pipeline-ZCode-ControlledShot-20261025` | `zcode/controlled-shot-v0-reproof-20261025` | `77deb8a0` | Historical controlled-shot branch; retained read-only. |
| `D:/MAR/.mar/w/a6ab82659f737d19a2f5a1489e251805` | `(detached)` | `22e9d8ea` | MAR audit worktree; untouched. |
| `D:/MAR/.mar/w/f31dc273222277af8f87d89fa27b29da` | `(detached)` | `56bec9ad` | MAR audit worktree; untouched. |
| `AFP-film08-{03,03b,04,571}` & `wt-film08-script` *(5 pruned earlier)* | *(removed)* | *(merged)* | Empty temporary `film08` execution shards verified merged via `shard_merge.py` into `AFP-stable` and unregistered cleanly before `film08` post-production. |

---

## 2. Root `D:/AI FILM MAKER/AI-Film-Pipeline/tools/` Untracked Scripts Inventory (Protected — Untouched)

Per `AGENTS.md` protected-work rules, the 29 untracked experimental runner/inspection scripts (plus 2 tracked modified scripts `tools/v2_020_runner.py`, `tools/v2_021_recover.py`) in the root checkout are **preserved untouched in place** (SHA-256 verified against `custody_before.json`):

- Tracked modified (` M`): `tools/v2_020_runner.py`, `tools/v2_021_recover.py`
- Untracked (`??`, `29` scripts):
  - `tools/build_directed_part2_final.py`, `tools/build_part2_ai_masters.py`, `tools/download_card_video.py`, `tools/export_155_shots.py`, `tools/export_part1_181_shots.py`, `tools/extract_char_dna.py`, `tools/gen_court_extras.py`, `tools/generate_chapter2_shots.py`, `tools/generate_chapter3_shots.py`, `tools/generate_chapter4_shots.py`, `tools/generate_chapter5_shots.py`, `tools/generate_chapter6_shots.py`, `tools/generate_director_shots.py`, `tools/generate_part2_proven_shots.py`, `tools/generate_part2_shots.py`, `tools/inspect_chat_cards.py`, `tools/inspect_first_2mins.py`, `tools/inspect_muse.py`, `tools/inspect_muse_thread.py`, `tools/inspect_video_dom.py`, `tools/muse_pool.py`, `tools/plan_155_shots.py`, `tools/qc_chapter4.py`, `tools/qc_chapter5.py`, `tools/qc_chapter6.py`, `tools/rebuild_cinematic_part2_masters.py`, `tools/test_gen_more.py`, `tools/test_muse_download.py`, `tools/test_muse_submit.py`
