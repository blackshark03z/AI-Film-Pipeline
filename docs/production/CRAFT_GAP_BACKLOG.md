# Craft gap backlog (not implemented)

Written 2026-11-19 from the orchestrator's gap analysis (gaps G1–G5; the file lives **outside this repo**, in the
Owner's Claude user folder: `C:\Users\ADMIN\.claude\film-craft-inputs\GAP_ANALYSIS_2026-11-19.md`) after checking each
gap against the code on branch `feature/drama-preprod-p0`. Scope of that pass was docs and skills only: **nothing below
is implemented.** Each item says why (evidence), where it would land, and when it is done. References name symbols
(module, class, function, constant) rather than line numbers, which drift.

The craft side is covered for now by the shared skills `film-treatment` (G1), `film-creative-review` (G2),
`film-sound-design` (G3) and `film-lessons`, and by `.claude/skills/film-post` +
[POST_PLAYBOOK.md](../director/POST_PLAYBOOK.md); these items turn those habits into checks.

Order of value: G2 → G7 → G1 → G6 → G3 → G4 → G5.

## G1 — Visual treatment fields in `02_direction.json`

**Why.** `production/direction.py` `DirectionPlan` holds `vision` (`Vision`: tone + word references), `visual_rules`
(`VisualRule`: rule + why), per-scene `SceneDirection` (POV, emphasis, curve, pacing, transitions) and `coverage_plan`.
There is no motif, colour script or intensity → size/lens/movement grammar: grep `motif|color_script` in
`src/film_pipeline` finds nothing. `production/camera.py` `CameraSetup` declares size/angle/lens per shot but nothing
ties those choices to the emotional curve. Colour (`production/color.py`) only matches shots to a per-scene reference;
there is no per-scene target look and no grain/texture step (`drama/post.py` has one global `GRADE`).

**Where.** `production/direction.py`: optional `treatment` block — `motifs[]` (id, meaning, plant scene/shot, payoff
scene/shot), `color_script{scene_id: {palette words, key/fill feel, saturation intent}}`, `grammar[]` (intensity band →
size range / lens intent / movement). Checks in `direction_issues`: motif plant before payoff and both carried by real
shots. `production/camera.py` `camera_issues`: WARN when a shot's size/lens is outside the grammar for its scene's
intensity. `production/color.py` / `color/color_plan.json`: optional per-scene look target taken from the colour script.

**Done when.** A film can declare the block; Gate 2 BLOCKs a motif whose payoff has no carrier shot; `film.py camera`
WARNs grammar breaks; tests cover a passing and a failing treatment; an existing package without the block still
validates (optional, all-or-nothing like `camera`).

## G2 — Creative review record alongside the QC record

**Why.** `production/qc_model.py` `TakeQc` has 16 groups (`Group` literal: narrative … delivery) that measure defects;
`production/master_qc.py` is technical only (its docstring: it never says the film is good). DIRECTOR_PLAYBOOK §0: a
green gate means the declared rules hold, never that the film is good — but no record captures the creative read
(emotional beat lands, performance, rhythm, "AI slop" markers). film08 passed Gates 4–6 and was Owner-accepted with an
EDL that is the untouched `edit --init` draft (300 events, no trims, no J/L; POST_PLAYBOOK §8). No package under
`films/` has a trimmed event: nothing recorded a cut-level creative judgment.

**Where.** New `production/creative_review.py`: a `CreativeReview` record per still / board / take / cut (rubric items
from `film-creative-review`, each scored with an evidence path and a reviewer, `human:` or delegated `agent:` as in
`qc_model.py`, with `rehearsal.refuse_undelegated` applied), stored next to the QC record
(`takes/reviews/<take_id>.creative.json`, `qc/cut_creative_review.json`). `production/report.py` / `film.py status`:
show the creative score next to the technical verdict. `film.py review --ingest` accepts it. It never changes
ACCEPTED/REJECTED by itself.

**Done when.** `status --film` reports technical verdict, creative score and Owner acceptance as three separate lines;
a cut review record exists for the locked EDL (stale after relock like a post item); `deliver` WARNs (not blocks)
when the locked cut has no creative review.

## G3 — Voice bible → voice ID and an explicit dialogue route

Extends the "voice and sound evidence" remainder of **P16-10** (`LOOP_BACKLOG.md`, `PRODUCTION_PROCESS_V2.md` §9) and
P14-05 (one voice per character).

**Why.** Partly present: `production/sections.py` `CharacterSpec.voice` (voice-bible words compiled into each spoken
line) and `CharacterSpec.voice_reference` (`VoiceReference`: an accepted take span); `production/takes.py` dailies add
a reviewer question "sounds like the voice bible … same voice as <ref>?"; `production/generators.py` `ROLES` includes
`voice`; `film.py dialoguecheck` checks the words only (English STT). Missing: a measured voice match (the reference is
only listened to), a declared dialogue route per shot (native model audio vs. separate TTS/voice clone + lip-sync), and
any lip-sync check beyond master QC's cue offset.

**Where.** `production/sections.py`: `CharacterSpec.voice_id` (provider + voice id or `NATIVE`) and `04_shots`
`dialogue_route` (`NATIVE` | `TTS_OVERLAY` | `ADR`). New advisory `production/voice_match.py`: speaker-embedding
distance of each speaking take against `voice_reference` → WARN in `review` dailies. `production/mix.py`
`build_stems`: dialogue stem from the TTS/ADR files when the route says so. Any paid voice service is an Owner purchase.

**Done when.** `review` dailies show a voice-match number per speaking character; a shot with `TTS_OVERLAY` mixes the
declared file and master QC sync still passes; packages without the fields behave as today.

## G4 — Closed VLM judge loop before regenerate

**Why.** Existing pieces: `src/film_pipeline/semantic_qc.py` (frozen interface, `SEMANTIC_QC_STATUS =
"SEMANTIC_QC_UNQUALIFIED"`: no qualified VLM key, evaluator-only), `src/film_pipeline/semantic_backends.py`,
`src/film_pipeline/gemini_semantic.py` (advisory backend), `src/film_pipeline/drama/autoqc.py` `judge_scale`,
`src/film_pipeline/agentic/pre_send_critic.py`. Planned but open: LOOP_BACKLOG **P15-04** (= P14-03, "VLM judge …
WARN and ranking only": end-still match on the last second, tracked prop vs end still, look bible per character) and the
"advisory VLM judge" remainder of **P16-10**. Nothing scores a take against the script beat + references and feeds the
retake cause (`production/retake.py`: PROMPT / START_FRAME / PROVIDER_LIMIT / STAGING) before the next send.

**Where.** Finish P15-04 in `src/film_pipeline/semantic_qc.py` / `src/film_pipeline/semantic_backends.py`
(qualification: positive, negative and ambiguous controls); call it from `film.py review` (dailies WARN + ranking) and
`film.py retake` (suggested cause). Never a PASS for a content group (`qc_model.py` rule: `auto:` can only WARN).

**Done when.** The judge is qualified on the control set and recorded as such; `review` shows its WARNs and rank for
each new take; `retake` proposes a cause from it; acceptance still needs a human or delegated reviewer.

## G5 — Benchmark shot set re-run on route change

**Why.** The provider registry marks unmeasured fields `unverified` until a live probe (`providers/capability.py`
module docstring); `core.py` carries a `benchmark_policy_version` field and `production/report.py` computes
`first_pass_rate` per film, but there is no fixed benchmark set (GREEN/AMBER/RED beats, dialogue, two-person
interaction, prop hand-off) that is re-run when the model, provider or route changes (Flow Omni 1.2 Flash, Vilao H3
480P in `OWNER_POLICY.md`). Generability levels (`drama/generability.py`) are therefore calibrated on one route only.

**Where.** `films/benchmark_v1/` package (rehearsal-style, small) + a `film.py` command or script that sends it under
`OWNER_POLICY.md` §2 (experiment route and VND cap), reviews it with the normal QC record, and writes a scorecard
(`docs/production/benchmarks/<route>_<date>.json`: first-pass rate per generability band, credits per usable second).
`drama/generability.py`: levels read per route from the latest scorecard.

**Done when.** A route change cannot become a film's default route without a scorecard for it; the scorecard shows
per-band first-pass rates; generability uses the route's figures.

## G6 — Shot-size distribution / coverage pyramid lint (partly present)

**Verified 2026-11-19.** AFP already lints:
- `CAMERA_SIZE_RUN` — three identical sizes in a row: BLOCK inside one scene, WARN across scenes, unless each repeat
  has `declared_repeat` (`production/camera.py` `_size_runs`);
- `CAMERA_SIZE_COVERAGE` — size vs coverage type, and `CAMERA_ACTION_LEGIBLE` — unreadable WIDE beats
  (`camera.py` `_per_shot`);
- `JUMP_CUT_RISK` at the cut — same scene, same size/angle, same subject (`production/edit.py` `cut_continuity`);
- `coverage_plan` — required coverage types per beat appear in `04_shots` (`production/direction.py`
  `direction_issues`);
- `OFF_FRAME_NOT_ESTABLISHED` — P16-02's **encounter-level** check that an off-frame listener was established
  (`production/interaction.py`, BLOCK).

**Missing.** (a) Share of tight sizes per scene/film — nothing measures the pyramid. (b) A **scene-level** establishing
check, distinct from P16-02's encounter-level `OFF_FRAME_NOT_ESTABLISHED`: no check that a scene opens wide (or says
why not) or that a wide/master returns after N tight shots or a blocking change. (c) `_size_runs` runs in `04_shots`
generation order and only over shots that declare `camera`, not in EDL order and not on the coverage-derived size
(`drama/coverage.py` `_SIZE`) of packages without a camera plan.

**Where.** `production/camera.py`: `CAMERA_SIZE_SHARE` (WARN when the tight share per scene is outside a band set in
`03_preprod` limits, default e.g. 30–70%). "Tight" reuses the existing `_TIGHT_SIZES = {"CLOSE", "INSERT"}` so one
definition serves legibility and the pyramid; `MEDIUM_CLOSE` (what OTS maps to) is reported as its own share beside it
rather than widening the set, so existing `_TIGHT_SIZES` rules do not change. `CAMERA_NO_ESTABLISH` (WARN: the scene's
first shot is not in `_WIDE_SIZES` or MEDIUM and has no note why; a tight run longer than N with no re-establish). Size
falls back to the coverage-derived size when `camera` is absent. `production/edit.py` `cut_continuity`: the same
run/share checks in EDL order (advice at CUT level, like the rhythm report).

**Done when.** `film.py camera` and `film.py cut` print the shares per scene and the two new findings; tests cover a
pyramid-shaped scene (no finding), an all-close scene (WARN) and a scene with no establishing shot (WARN); existing
packages keep their current BLOCK set (new checks are WARN).

## G7 — Direction devices vs. shot camera, and an edit check that is not satisfied by the draft

Found by a read-only dry-run of the `film-post` skill on film03 (2026-11-19).

**Why.** (a) film03 `02_direction.json` plans a `push` emphasis device on SC04_g2 and SC07_g2, but all 16 shots in
`04_shots.json` declare `camera.movement: "STATIC"`. `production/direction.py` `direction_issues` only checks that an
emphasis carrier is a shot of its scene; nothing compares the device (`push`, `insert`, `hold`, `reaction`) with the
carrier's `CameraSetup` (movement, size) or with the edit (a hold that is cut short). (b) `production/edit.py`
`rhythm_report` compares the scene's average used length with `pacing.target_avg_shot_s`; in film03 every scene target
is 8.0 s, the generation length, so untrimmed takes give a ratio of about 1.0 and pass. Nothing checks that takes were
trimmed or that dialogue scenes use J/L cuts: an `edit --init` draft passes the cut checks unchanged (no package under
`films/` has a trimmed event; POST_PLAYBOOK §6.1).

**Where.** (a) `production/direction.py` or `production/camera.py`: `EMPHASIS_DEVICE_UNSTAGED` (WARN) when a `push`
carrier is `STATIC` with no note, an `insert` carrier is not `INSERT`/`CLOSE`, or a `reaction` carrier is not a
SINGLE/REACTION on the listener; `production/edit.py` `rhythm_report`: WARN when a declared hold's shot is cut shorter
than its hold. (b) `production/edit.py`: `EDIT_UNTRIMMED` (WARN at CUT level, BLOCK-free) when more than a set share of
TAKE events use the whole clip, and `DIALOGUE_NO_SPLIT` advice when a dialogue scene has no J/L; `rhythm_report` warns
when the scene target equals the generation length (the check cannot discriminate).

**Done when.** `film.py camera` (or `validate`) reports film03's two `push` carriers; `film.py cut` on an `edit --init`
draft reports `EDIT_UNTRIMMED`; tests cover a staged push (no finding), a static push (WARN), a trimmed EDL (no finding)
and the untouched draft (WARN); existing BLOCKs unchanged.

## Not added: master QC peak "sample vs true peak"

The dry-run reported that `production/master_qc.py` compares a sample peak (`peak_dbfs`) against a dBTP limit.
Checked 2026-11-19: `drama.post.measure_ebur128` runs ffmpeg `ebur128=peak=true` and parses the summary "Peak:" line,
which under `peak=true` is the **true peak** (ffmpeg labels it "dBFS"). The comparison is correct; only the field name
`peak_dbfs` is misleading. A rename (`true_peak_dbtp`) is a cosmetic code item, not a gap; recorded in POST_PLAYBOOK
§4.3 instead.
