# RFC: Agentic Filmmaking v2 — Local-First Production Architecture Upgrade

- **Status:** Proposed Reference Architecture + Reference Implementation (`src/film_pipeline/agentic/`, CLI `film.py agentic-plan`)
- **Date:** 2026-11-18
- **SoT Alignment:** Strict compliance with `docs/sot/development/AI_NATIVE_DEV_MODEL_SOT_v1_FROZEN.md` and `docs/sot/film/00_SOT_INDEX.md` (Python + SQLite WAL + FFmpeg local-first; zero heavy external orchestrators; zero autonomous gate-lowering).
- **Empirical Baseline:**
  - `film06_six_am` (150 generations, Owner-accepted `Gate 6 PASS`).
  - `film07_first_shift` (300 generations, Owner-accepted `Gate 6 PASS`, archive `f3476aa23f`).
  - `film08_chain_of_custody` (`300/300` `ACCEPTED`, `353` total takes, `first_pass_rate = 0.863`, `2,118.0` credits = `99.0%` of `2,140` estimate; `0` off-frame listener intrusions after opt-in `de_personify_off_frame`; `16:9` & `9:16` masters delivered `Gate 6 OWNER_PENDING`).
  - `R44` Prop-Action Temporal QC findings (gap-aware camera jitter R44F, edge-intrusion delta, sparkle watermark corner preservation, Whisper/Vosk speech-window trim).

---

## 1. Problem Statement from Long-Form Production (`film07` -> `film08`)

Completing two consecutive ~30-minute, 300-generation dramas surfaced five concrete bottlenecks in the V1 single-writer loop:

1. **Global Send Lock & Multi-Worktree Sharding Overhead:** Before `P20`, any unresolved `SEND_PENDING` receipt blocked the entire package, forcing manual multi-worktree cloning (`AFP-film08-{03,03b,04,571}`) and post-hoc `shard_merge.py`.
2. **Pre-Send Prompt & Still Contradictions Burned Live Credits:** Repeated `SINGLE` takes (`SC09_g03`, `SC12_g01`, `SC12_g02`) suffered off-frame listener intrusion because off-frame character nouns appeared in compiled prompts, and `SC11_g01` paired prop placement with `"No touching."`.
3. **Opaque Retake Loops:** Failures were mapped manually in status docs instead of bounded causal strategies with hard retry caps.
4. **Monolithic Final Conform Delay:** `cut` / `grade` / `titles` / `mix` ran only after all 300 takes finished, turning a single late retake into full-film rework checks.
5. **High Operator Attention Tax:** Checking every intermediate still, storyboard frame, and shot step-by-step created 30+ manual handoffs rather than folding routine validation behind 3 strategic Owner checkpoints.

---

## 2. Five Local-First Architectural Pillars

### Pillar 1 — DAG Wave & Multi-Account Lease Scheduler (`scheduler.py`, `lease_pool.py`)
- **`WaveDAGScheduler`** builds the directed acyclic dependency graph from `04_shots.json` (`previous_generation_id`) and `takes/index.json` (`ACCEPTED` current-version takes).
- Generations whose predecessor is `None` or already `ACCEPTED` form **`Wave 0` (Ready Frontier)**; dependent continuations form `Wave 1..N`.
- **`AccountLeasePool`** coordinates N provider browser/API accounts on **one single worktree** via a lightweight **SQLite WAL** lease table (`acquire`, `release`, `quarantine_account`), enforcing:
  - Minimum reserve floor (`min_reserve_credits = 20.0`).
  - Cooldown windows between account sends.
  - Instant `COOLDOWN_QUARANTINE` when an account trips UI/unusual-activity warnings, releasing its pending claim without stalling healthy accounts.

### Pillar 2 — Zero-Credit Pre-Send Critic Loop (`pre_send_critic.py`)
- **`PreSendCritic`** performs a deterministic 3-way check before spending any credit:
  1. `CROSS_ATTENTION_LEAK_RISK`: Flags off-frame character names or handles inside `SINGLE` shot prompts.
  2. `PROHIBITION_ACTION_CONFLICT`: Flags `"No touching."` paired with prop-handling verbs in `>=2`-person shots.
  3. `START_STILL_NOT_READY`: Verifies chain heads have `APPROVED` start stills with valid image aspect ratio matching `film.json`.

### Pillar 3 — Two-Tier Dailies & Causal Repair Router (`dailies_triage.py` + `causal_repair.py`)
- **Tier 1 (`production/dailies_triage.py`, `film.py triage`):** Offline advisory-only signal scanner measuring left/right 8% edge-intrusion deltas, bottom-right 12% sparkle corner signal, R44F border camera jitter, and `-45 dBFS` speech lead/tail trim hints. **Invariant:** never writes `reviews/*.json` and never auto-PASSes human QC groups.
- **Tier 2 (`CausalRepairRouter`):** Maps structured defect codes (`OFF_FRAME_INTRUSION`, `AXIS_EYELINE_DRIFT`, `PROP_CONTINUITY_BREAK`, `DIALOGUE_TRUNCATED`, `CAMERA_INSTABILITY`, `PROVIDER_CONTENT_REFUSAL`) to deterministic repair actions (`enable_de_personify_off_frame`, `restage_start_still`, `reframe_safe_edge`, `upgrade_single_to_ots`, `trim_or_pace_line`, `HALT_HUMAN_DECISION`), strictly capped at **`max_attempts = 2`** before `ESCALATE_TO_TECH_LEAD` and halting immediately on `PROVIDER_CONTENT_REFUSAL`.

### Pillar 4 — Scene-Level Incremental Conform (`incremental_conform.py`)
- **`SceneIncrementalConformer`** groups generations by `scene_id`, computes a deterministic `input_sha256` per completed scene (`accepted takes + color/reframe + cues`), and caches intermediate `<film>/media/scenes/SCxx.mkv` + `SCxx.scene.json` artifacts so dialogue joins and visual continuity can be previewed as each scene finishes instead of waiting for beat 300.

### Pillar 5 — Capability-Aware Provider Router & 3-Checkpoint Human Loop (`capability_router.py`)
- **`CapabilityRouter`** routes each generation based on empirical capabilities:
  - `flow_omni_flash`: strict cast/face lock from an approved Flow start still (`360p` / `6s` / `6 cr`).
  - `muse_gateway`: multi-location cast adaptation or non-face/recast B-roll via immutable `muse_gateway.py` handoff bundles.
  - `vilao_probe`: low-cost blocking/pacing pre-visualization probes on `experiment` / `rehearsal` budgets.
- Consolidates human sign-off around **3 Strategic Checkpoints** while keeping all underlying Gates `1..6` non-bypassable:
  - **CP1 — Brief, Cast & Budget Approval** (Gates `1..3` + `planning.budget`).
  - **CP2 — Pilot Scene Reel Approval** (`SC01`–`SC02` accepted reel, ~5 minutes, calibrating visual & vocal anchor before bulk generation).
  - **CP3 — Master Creative Acceptance** (`Gate 5` Picture Lock + `Gate 6` `16:9` / `9:16` `OWNER_PENDING` -> `deliver --accept`).

---

## 3. Hard Guardrails & Non-Goals
1. **No Auto-Accept / No Gate Lowering:** Agentic helpers only triage, advise, schedule, and prepare artifacts; human QC review (`qc_model`) and Owner `deliver --accept` remain mandatory.
2. **No Extra Services:** Zero Redis, Celery, Kubernetes, or background daemon requirements; CLI `film.py agentic-plan` is purely read-only on `<film>`.
3. **Provider Safety & Custody:** Content refusals and unusual-activity warnings halt immediately; no proxy evasion or account rotation bypass.
