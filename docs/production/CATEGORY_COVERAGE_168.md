# Category coverage — Owner's 168 production categories

Branch `feature/drama-preprod-p0`, written 2026-11-06 (loop item P0-01). Source list: Owner's `Danh mục sản xuất phim e2e.txt`; prior root-branch analysis: `docs/research/E2E_FILM_CATEGORY_MATRIX_168_20261104.md` (root repo, read-only). Status describes this branch's code only, not Owner acceptance or quality of output.

**Summary:** HAVE 58 · PARTIAL 81 · GAP 3 · N/A 26 · total 168

Status: HAVE = code path covers the responsibility at the level the dramas need; PARTIAL = covers plan/declared level or one slice; GAP = no path; N/A = not applicable to the AI route (reason in the responsibility column). Update Status/Backlog when an item closes.

## I. Story development

| ID | Category | Responsibility (code path / package field / operator receipt / N/A) | Status | Backlog |
|---|---|---|---|---|
| 1 | Concept | `production/story.py` `StorySection.concept` (required; presence only) | PARTIAL | P1-01 |
| 2 | Audience | `StorySection.audience` who + expectation (required; presence only) | PARTIAL | P1-01 |
| 3 | Premise | `StorySection.premise` + `central_conflict` (required; presence only) | PARTIAL | P1-01 |
| 4 | Logline | `StorySection.logline` with protagonist/goal/obstacle; Gate 1 checks the text carries them | HAVE | P1-01 |
| 5 | Story structure | `StorySection.structure` acts/beats; Gate 1: function order, required beats, every scene in a beat | HAVE | P1-01 |
| 6 | Plot & subplot | `StorySection.plot` (text) + `subplots` with scene refs checked | PARTIAL | P1-01 |
| 7 | Character arcs | `StoryCharacter` want/need/flaw/arc; Gate 1: protagonist arc needs an existing change scene | HAVE | P1-01 |
| 8 | Dramatic beats | `Beat` function/scenes/summary, ordered and covering all scenes (Gate 1) | HAVE | P1-01 |
| 9 | Scene design | `StoryScene` purpose/conflict/outcome/value shift required per scene; scenes match script.fountain (Gate 1) | HAVE | P1-01 |
| 10 | Screenplay | `drama/script.py` Fountain intake; `production.load_package` parses `script.fountain`; version/approval tracked by Gate 1 (P1-01) | PARTIAL | P1-01 |
| 11 | Dialogue | `drama/coverage.SpokenLine` + `feasibility` syllable limits | HAVE | - |
| 12 | Rewrite | `StorySection.rewrite_log` records versions; no diff against the script | PARTIAL | P1-01 |
| 13 | Script breakdown | `drama/feasibility.py` + `scene_bible` occupancy; heuristic breakdown | PARTIAL | P2-05 |
| 14 | Adaptation | `StorySection.adaptation` rights_status (drama) and `NarrationStory.rights_status` (narration); not cleared -> OWNER_PENDING | HAVE | P1-01 |

## II. Creative direction

| ID | Category | Responsibility (code path / package field / operator receipt / N/A) | Status | Backlog |
|---|---|---|---|---|
| 15 | Directorial vision | `production/direction.py` `Vision` (tone, references as words); required by Gate 2, not enforced against shots | PARTIAL | P1-02 |
| 16 | Visual language | `DirectionPlan.visual_rules` rule + why; required by Gate 2, not enforced against shots | PARTIAL | P1-02 |
| 17 | Mise-en-scène | `drama/scene_bible.py` occupancy + location look | PARTIAL | P2-03 |
| 18 | Shot composition | `production/camera.py` `CameraSetup.composition` note + size/coverage check; note is free text and not compiled into the prompt | PARTIAL | P3-02 |
| 19 | Shot size | `coverage._SIZE` + `autoqc.shot_scale_from_ratio` (WARN) | HAVE | - |
| 20 | Camera angle | `camera.CameraSetup.angle/height` declared and reviewed; the Flow route cannot take angle in a prompt | PARTIAL | - |
| 21 | Camera movement | `camera.CameraSetup.movement` declared; Flow route generates static camera only | PARTIAL | - |
| 22 | Blocking | `choreography.GenerationChoreography` phases + `core.Blocking` | HAVE | - |
| 23 | Staging | `scene_bible` occupancy + `Blocking`; layering not modelled | PARTIAL | P2-03 |
| 24 | Screen direction | `drama/axis.py` AxisBook 180-degree | HAVE | - |
| 25 | Spatial geography | `drama/storyboard.py` schematic frames + `scene_bible` | PARTIAL | P2-03 |
| 26 | Temporal continuity | `production/continuity.py` (TEMPORAL: story-time order + one time of day per scene) + `scene_bible.check_temporal` | HAVE | - |
| 27 | Performance direction | `choreography.PerformanceCue` visible cues + prohibited misread | PARTIAL | P1-02 |
| 28 | Emotional direction | `SceneDirection.curve` 0-5 per character; Gate 2 blocks jumps > 2 without a cause beat | HAVE | P1-02 |
| 29 | Rhythm & pacing | `Pacing` target + holds, now measured: `edit.rhythm_report` sets used shot lengths per scene against the target (30% band), flags holds over target + planned hold and unplanned long shots | HAVE | - |
| 30 | Coverage strategy | `drama/coverage.CoveragePlanner` master/OTS/single/reaction | PARTIAL | P1-02 |
| 31 | Transitions | `Transition` kind + reason per scene boundary; recorded, not yet applied by an edit stage | PARTIAL | P1-02 |
| 32 | Visual storytelling | `action_meaning` + choreography once_actions (must-show) | PARTIAL | P1-02 |
| 33 | Point of view | `SceneDirection.pov`: whose view, facts the audience/characters know (ids checked against comprehension) | PARTIAL | P1-02 |
| 34 | Dramatic emphasis | `Emphasis` device per moment; `reveals` must have an emphasis device on a scene shot (Gate 2) | HAVE | P1-02 |

## III. Pre-production

| ID | Category | Responsibility (code path / package field / operator receipt / N/A) | Status | Backlog |
|---|---|---|---|---|
| 35 | Casting | `drama/bible.py` approved reference images (CharacterBrief) | PARTIAL | P2-01 |
| 36 | Character design | `CharacterLook` + versioned `designs` (look) pinned by shots as `id@version`; stale pin = package issue | PARTIAL | P2-01 |
| 37 | Location scouting | `scene_bible.LocationLook` text + `approved` flag; no image identity or hash | PARTIAL | P2-01 |
| 38 | Production design | `scene_bible` location look; no set geometry/palette record | PARTIAL | P2-03 |
| 39 | Set design | `scene_bible` location look; no set geometry/palette record | PARTIAL | P2-03 |
| 40 | Set dressing | `production/continuity.py` OBJECT: prop state machine, changes need a causing ACTION phase; no ownership/version of dressing | PARTIAL | P2-03 |
| 41 | Props | `production/continuity.py` OBJECT (cause rule, hand-off equality) + versioned `prop_*` designs (`impact.py`); Gate 3 reads the plan record and its staleness | HAVE | - |
| 42 | Costume design | `designs` kind costume with version; shots pin it; no story-day wardrobe state yet | PARTIAL | P2-01 |
| 43 | Hair & makeup | `designs` kind hair_makeup with version; shots pin it; no story-day state yet | PARTIAL | P2-01 |
| 44 | Cinematography planning | `production/camera.py`: per-shot camera setup + per-scene lighting plan, all-or-nothing rule, `film.py camera`, `plan` BLOCKs | HAVE | - |
| 45 | Lighting design | `camera.LightingPlan` (key direction/quality/colour temp/motivation/practicals, LIGHT_JUMP warn); not compiled into prompts | PARTIAL | - |
| 46 | Storyboarding | `drama/storyboard.py` schematic board + Gate 2 | HAVE | - |
| 47 || `production/animatic.py`: timed storyboard/still frames + captions + optional temp audio -> mp4/srt/timing report (`film.py animatic`) | HAVE | - |
| 48 | Blocking diagram | `storyboard.render_schematic_frame` + AxisBook | PARTIAL | P2-03 |
| 49 | Shot planning | `generation.py` split into 8 s units + `coverage` shot list | PARTIAL | P2-05 |
| 50 | Continuity planning | `production/continuity.py`: six kinds over per-generation start/end states, `film.py continuity`, hooked into `plan` | HAVE | - |
| 51 | Sound planning | Prompt carries room tone/SFX strings (`prompt.py`); no sound plan | PARTIAL | P5-01 |
| 52 | Technical planning | `production/package.FilmHeader` records aspect/fps/resolution/generation_s; `plan` supports 16:9 only by design (`PreflightLimits`); 9:16 is derived in post (`versions`) | HAVE | - |
| 53 | Production scheduling | `production/planning.py` schedule: hand-off chains, waves, stills before videos (`film.py planning`) | HAVE | - |
| 54 | Budgeting | `planning.budget`: generations x 12 credits x retake factor from the film01-03 KPI ledgers; Owner estimate checked against it, shown by `validate` | HAVE | - |
| 55 | Risk & safety | `planning.risks`: CONTACT/HANDOVER HIGH need a fallback plan (BLOCK), prop/crowd/depth reported; failures feed `retake` (PROVIDER_LIMIT cause); no provider-moderation risk model | PARTIAL | - |
| 56 | Legal clearance | `03_preprod.rights` + sound asset ledger + attributions go into `delivery/rights/rights.json`; open entries are WARN and keep `release_ready` false; Owner confirmations still pending | PARTIAL | - |

## IV. Production

| ID | Category | Responsibility (code path / package field / operator receipt / N/A) | Status | Backlog |
|---|---|---|---|---|
| 57 | Camera placement | Provider-side (text/image-to-video); intent in prompt only. N/A as physical camera control | N/A | - |
| 58 | Framing | Provider-side (text/image-to-video); intent in prompt only. N/A as physical camera control | N/A | - |
| 59 | Lens selection | Provider-side (text/image-to-video); intent in prompt only. N/A as physical camera control | N/A | - |
| 60 | Depth of field | Provider-side (text/image-to-video); intent in prompt only. N/A as physical camera control | N/A | - |
| 61 | Focus control | Provider-side (text/image-to-video); intent in prompt only. N/A as physical camera control | N/A | - |
| 62 | Exposure | Provider-side (text/image-to-video); intent in prompt only. N/A as physical camera control | N/A | - |
| 63 | Frame rate | Provider-side (text/image-to-video); intent in prompt only. N/A as physical camera control | N/A | - |
| 64 | Camera movement | Provider-side (text/image-to-video); intent in prompt only. N/A as physical camera control | N/A | - |
| 65 | Camera stability | Provider-side (text/image-to-video); intent in prompt only. N/A as physical camera control | N/A | - |
| 66 | Lighting execution | Provider-side (text/image-to-video); intent in prompt only. N/A as physical camera control | N/A | - |
| 67 | Color temperature | Provider-side (text/image-to-video); intent in prompt only. N/A as physical camera control | N/A | - |
| 68 | Dynamic range | Provider-side (text/image-to-video); intent in prompt only. N/A as physical camera control | N/A | - |
| 69 | Composition continuity | `autoqc.shot_scale` + `HandoffSetReport` (WARN) | PARTIAL | P3-02 |
| 70 | Actor positioning | `core.Blocking.start` + preflight positions | PARTIAL | P2-02 |
| 71 | Movement choreography | `choreography.GenerationChoreography` phases + `core.Blocking` | HAVE | - |
| 72 | Facial performance | `choreography.PerformanceCue` visible cues + prohibited misread | PARTIAL | P1-02 |
| 73 | Body language | `choreography.PerformanceCue` visible cues + prohibited misread | PARTIAL | P1-02 |
| 74 | Dialogue delivery | `SpokenLine` + prompt dialogue; delivery unchecked | PARTIAL | P3-02 |
| 75 | Reaction timing | `choreography.PerformanceCue` visible cues + prohibited misread | PARTIAL | P1-02 |
| 76 | Emotional continuity | `continuity.py` EMOTIONAL: intensity leap of 2 between chained generations is a WARN; no cut-level check | PARTIAL | P4-02 |
| 77 | Interaction | `choreography` ACTION phases + `action_meaning` | PARTIAL | P3-02 |
| 78 | Background performance | `occupancy`/`EXTRAS` strings in film tools | PARTIAL | P2-03 |
| 79 | Action timing | Phase timings in `GenerationChoreography` | PARTIAL | P4-02 |
| 80 | Set operation | No crew/rehearsal on AI route; animatic is the rehearsal analogue | N/A | P2-04 |
| 81 | Assistant directing | No crew/rehearsal on AI route; animatic is the rehearsal analogue | N/A | P2-04 |
| 82 | Rehearsal | No crew/rehearsal on AI route; animatic is the rehearsal analogue | N/A | P2-04 |
| 83 | Take management | `production/takes.py` take log `takes/index.json`: take id per generation, prompt/start-frame/output hashes, route, model, credits, status from review; Gate 4 (`gate_checks.py`) needs a human-accepted take of the current shot version per generation | HAVE | - |
| 84 | Script supervision | `drama/qc.py` post-render gating + `sequence` | PARTIAL | P3-02 |
| 85 | Live monitoring | `flow_send.py` network-bound output capture; `film.py generate` payload + intent receipt written before any send, take registered after (live path untested until P3-05) | PARTIAL | P3-05 |
| 86 | Production sound | AI-generated sound; no separate capture. N/A | N/A | - |
| 87 | Data management | `film.py deliver` archive with MANIFEST (size + sha256 per file, take dependencies by hash) and `film.py status --package` restore check; take clips are not archived | HAVE | - |
| 88 | Dailies review | `film.py review`: template per new take (shot questions + 16-group QC) and `--ingest` bound to the take's hash | HAVE | - |
| 89 | Pickup / reshoot | `production/retake.py`: cause-based RETRY / CHANGE_APPROACH / ESCALATE per generation; `film.py retake --pickup` writes shot version N+1 with `repair_of` + history | HAVE | - |
| 90 | Safety management | N/A for AI generation | N/A | - |

## V. Post-production

| ID | Category | Responsibility (code path / package field / operator receipt / N/A) | Status | Backlog |
|---|---|---|---|---|
| 91 | Media ingest | `editorial.probe_media`, `validate_source` | HAVE | - |
| 92 | Logging | Take log + stored reviews (`takes/reviews/`) + `status` production counts; no unified shot/sound log | PARTIAL | - |
| 93 | Synchronization | `production/edit.py`: per-event J/L audio split rendered (source handles checked), picture clock independent of sound; subtitle sync still via `post.cue_offsets` (P5-04); stems/mix in P5-01 | PARTIAL | P5-01 |
| 94 | Selects | `qc.SelectedTake` | HAVE | - |
| 95 | Assembly cut | `05_edit.json` EDL of take_ids from the take log; `film.py cut` checks it (unknown/rejected/superseded/changed takes block) and `--render` assembles via `drama.post.assemble`; film03 golden within 1 frame per event | HAVE | - |
| 96 | Rough cut | `film.py cut --render`: rough cut from selects (title, graded clips, cards, identity tags, end card) with a `.cut.json` report; unreviewed takes warn, `--accepted-only` blocks | HAVE | - |
| 97 | Structural editing | EDL order and trims decide structure; `rhythm_report` and `cut_continuity` give the review; no automatic structural judgement | PARTIAL | - |
| 98 | Continuity editing | `edit.cut_continuity`: end/start state at each cut via `continuity._handoff` (BLOCK only for chained, untrimmed handoffs), trimmed chained cuts flagged, axis side/eyeline flip, jump-cut risk | HAVE | - |
| 99 | Performance editing | Per-event take choice and `src_in_s`/`src_out_s` trims; no automatic performance judgement (human at CUT level) | PARTIAL | - |
| 100 | Narrative editing | Reorder events, insert context cards, drop or reuse takes (`SHOT_NOT_IN_CUT`, `TAKE_REUSED` warnings); narrative judgement stays human | PARTIAL | - |
| 101 | Rhythm editing | `edit.rhythm_report` + per-event trims and holds; advisory WARNs, never BLOCK | HAVE | - |
| 102 | Transition design | CUT / MATCH_CUT / DISSOLVE / DIP_TO_BLACK and J/L cuts declared per event and rendered (xfade); the direction's planned `transition_in/out` is not yet compared with the EDL | PARTIAL | - |
| 103 | Montage | Not needed for current dramas; add only if a script needs it | N/A | - |
| 104 | Fine cut | Per-event `src_in_s`/`src_out_s` trims (frame-accurate in the filter), dissolves, dips, J/L cuts rendered; `film.py cut` checks and reports | HAVE | - |
| 105 | Picture lock | `production/lock.py`: `film.py lock --lock --by NAME` freezes EDL hash + per-event fingerprints (take bytes, accepted flag, tags) and keeps every lock; `dirty_items` flags post/delivery items built on a different cut; Gate 5 (drama) passes only for a fresh lock | HAVE | - |
| 106 | Online conform | N/A (generated sources are the final quality) | N/A | - |
| 107 | Dialogue editing | `mix.build_stems`: dialogue stem = the cut's own sound (J/L cuts included); no editing beyond the EDL | PARTIAL | - |
| 108 | Dialogue cleanup | Dialogue is generated with the clip; loudness normalised; no denoise/cleanup tool | PARTIAL | - |
| 109 | ADR / dubbing | N/A for current route (no ADR) | N/A | - |
| 110 | Foley | No Foley recording; effects only from licensed assets placed by `mix` (see 111) | GAP | - |
| 111 | Sound effects | `mix` places declared `sfx` from `audio/sfx/<slug>.wav`; `sound_rights` blocks `validate` until each used file has a cleared record (source, license, sha256, usage); no sound library yet, assets are put in place by a human | PARTIAL | - |
| 112 | Ambience | `mix`: one generated, calibrated (`ambience_lufs`) noise bed per scene span coloured by the location's `room_tone`, cross-faded at the edges | HAVE | - |
| 113 | Room tone | `mix`: room tone per location from `room_tone` text; silent over title/end cards | HAVE | - |
| 114 | Sound perspective | Generated room tone only; no stems or SFX cues | GAP | P5-01 |
| 115 | Music scoring | `mix_plan.json` music cues (asset, range, gain, fades, why, scene) mixed under dialogue; `sound_rights.cue_sheet` advises IN/HOLD/DUCK/OUT per scene from the emotional curve; no score is composed or sourced automatically | PARTIAL | - |
| 116 | Music editing | Cue start/end/fades/gain in the plan, ducking by `mix`; no waveform editing | PARTIAL | - |
| 117 | Sound mixing | `production/mix.py`: four stems, side-chain ducking of ambience+music under dialogue (depth measured), sum, -14 LUFS / -1 dBTP master; `film.py mix` | HAVE | - |
| 118 | Audio mastering | `drama/post.normalize_loudness` EBU R128, applied by `mix.mix_cut` with the measured result checked | HAVE | - |
| 119 | VFX cleanup | Not needed unless a shot demands it; watermark/artifact handling manual | N/A | - |
| 120 | Compositing | Not needed unless a shot demands it; watermark/artifact handling manual | N/A | - |
| 121 | CGI integration | Not needed unless a shot demands it; watermark/artifact handling manual | N/A | - |
| 122 | Motion graphics | `post.title_card`, `context_card_clip`, `identity_tag_png` | HAVE | - |
| 123 | Color correction | `color.match` per-shot channel gains (exposure + white balance) applied in `edit.render_cut(corrections=)` | HAVE | - |
| 124 | Color matching | `color.match`: scene reference (plan shot or median), clamped gains, before/after deviation report, `film.py grade` | HAVE | - |
| 125 | Color grading | `post.GRADE` default look, replaceable per film via `color_plan.json` `look` | HAVE | - |
| 126 | Reframing | `titles/reframe.json` crop box per event (aspect-checked) applied by `edit.render_cut(reframes=)`; `stabilize` = ffmpeg `deshake` (quality not judged); 9:16 not built | HAVE | - |
| 127 | Retiming | No retime tool (and Owner rejects retime as proof) | N/A | - |
| 128 | Titles & credits | `titles.credits_lines` end card from the package: cast, AI disclosure, sound attributions, fiction line (EN/VI, fitted or BLOCK) | HAVE | - |
| 129 | Subtitles & captions | `titles.prepare`: cues from script + speech windows (or `titles/cues.json`), burned source language, EN/VI sidecar SRTs, `TRANSLATION_MISSING` blocks | HAVE | - |
| 130 | Final compositing | `post.assemble` single pass (cards, look, tags, cues, credits) + mastered mix + `versions` (9:16, thumbnails, metadata draft) | HAVE | - |

## VI. Finishing & QC

| ID | Category | Responsibility (code path / package field / operator receipt / N/A) | Status | Backlog |
|---|---|---|---|---|
| 131 | Narrative QC | `comprehension.check_comprehension` on the plan; `qc_model` records a human narrative verdict per take (auto cannot PASS) | PARTIAL | P3-02 |
| 132 | Coverage QC | `CoveragePlanner` plan-level only | PARTIAL | P1-02 |
| 133 | Character QC | `autoqc` identity WARN-only; dailies pre-fill WARNs but need anchors (not wired); human PASS in `qc_model` | PARTIAL | P6-01 |
| 134 | Spatial QC | `autoqc` SET_DRIFT as a dailies WARN; start/end-state questions per take; `AxisBook` | PARTIAL | P6-01 |
| 135 | Action QC | Dailies questions generated from every choreography phase/once-action; human FULL_MOTION review only; rejected action takes route to `retake` | PARTIAL | P6-01 |
| 136 | Motion QC | `qc_model` motion group: human FULL_MOTION review only, P0/P1/P2; no automated detector | PARTIAL | P3-02 |
| 137 | Camera QC | `autoqc.shot_scale` WARN against the planned size in dailies | PARTIAL | P6-01 |
| 138 | Visual QC | `qc_model` visual group: human SAMPLED review, P0/P1/P2; no automated detector | PARTIAL | P3-02 |
| 139 | Temporal QC | `master_qc`: black frames, frozen frames, duplicated-frame share on the master (title/end/card windows exempt); take-level temporal stays human | PARTIAL | - |
| 140 | Sequence QC | No temporal/sequence QC beyond `sequence.validate_shot_sequence` (plan) | PARTIAL | P6-01 |
| 141 | Audio QC | `master_qc`: codec, -14 LUFS +-1.5, true peak <= -1 dBTP, clipping runs, silent gaps > 3 s | HAVE | - |
| 142 | Sync QC | `master_qc`: A/V length agreement; dialogue cues vs `audio/stems/dialogue.wav` activity (offset > 0.3 s blocks); UNASSESSED without stem or timed cues | PARTIAL | - |
| 143 | Color QC | `color.match` deviation per shot + `OUT_OF_RANGE` WARN; `master_qc` crushed/blown-out frame share; no banding detector | PARTIAL | - |
| 144 | Technical QC | `master_qc`: streams, resolution/fps/codec/pix_fmt, duration vs planned clock, black/freeze/duplicate frames, faststart; record `qc/master_qc.json` at level CUT | HAVE | - |
| 145 | Compliance QC | `disclosure.check_release`; no rights/platform compliance | PARTIAL | P5-02 |
| 146 | Delivery QC | `delivery.verify`, `e2e status --package`; Gate 6 (`gate_checks.py`) checks QC record, picture lock, archive hashes and the Owner's `deliver --accept` bound to the manifest; not yet run on real takes | PARTIAL | P10-05 |

## VII. Delivery & distribution

| ID | Category | Responsibility (code path / package field / operator receipt / N/A) | Status | Backlog |
|---|---|---|---|---|
| 147 | Mastering | `post.assemble` + `normalize_loudness` final master | HAVE | - |
| 148 | Encoding | H.264/AAC 16:9 master and 9:16 version (`versions`, 720x1280, sound copied), faststart | HAVE | - |
| 149 | Versioning | `versions`: 16:9 master + 9:16 reframe (focus from tags / reframe boxes, cards fitted); language versions are sidecar SRTs only | PARTIAL | - |
| 150 | Localization | EN/VI subtitle sidecars | PARTIAL | P5-04 |
| 151 | Packaging | `delivery/`: marked masters, sidecars, thumbnails, metadata, QC, rights, package JSON, MANIFEST | HAVE | - |
| 152 | Metadata | `versions/metadata.json`: title (source/vi), logline description, tags, AI disclosure, credits, hashes; DRAFT_NOT_PUBLISHED | HAVE | - |
| 153 | Platform compliance | `deliver` runs `disclosure.check_release` on both masters (tags, hash-bound record, visible AI label burned in the opening title); C2PA only with a supplied cert (dev signer is untrusted); platform-specific rules are the Owner's at upload | PARTIAL | - |
| 154 | Publishing | Publishing prohibited unless Owner asks | N/A | - |
| 155 | Analytics | Post-release; out of scope until a film is published | N/A | - |
| 156 | Archive | `delivery.finalize/verify`; no restore rehearsal | PARTIAL | P6-03 |

## VIII. Production management

| ID | Category | Responsibility (code path / package field / operator receipt / N/A) | Status | Backlog |
|---|---|---|---|---|
| 157 | Project management | `film.py status`: gates, stage completeness, production counts, post/delivery state and one next action per film | HAVE | - |
| 158 | Resource management | `status` credits spent vs estimate and cap, credits per usable second, retake rate; `status --all` side by side | HAVE | - |
| 159 | Asset management | `ReferenceUploadStore`, runtime assets, hashes; no unified asset index | PARTIAL | P2-01 |
| 160 | Cost management | `drama/kpi.FilmKPI` credits per usable second | HAVE | - |
| 161 | Version control | `designs` versions + `design_refs` pins; takes/stills keep hashes; no version id for shots or assets | PARTIAL | P2-01 |
| 162 | Dependency management | `production/impact.py` `affected_by`: shots, stills, takes (+handoff cascade), edit/post items for one design; design dependencies only | PARTIAL | P2-01 |
| 163 | Change management | Stale-pin issues + `film.py impact` list what to redo; no approval/ledger workflow for a change | PARTIAL | P2-01 |
| 164 | Quality management | `qc_model` P0/P1/P2 take verdicts + waivers (`film.py qc`); Owner gate | PARTIAL | P3-02 |
| 165 | Risk management | `planning.risks` register + `retake` credits-spent / escalation per shot + open retake decisions in `status`; no run-wide mitigation log | PARTIAL | - |
| 166 | Rights management | No rights ledger | GAP | P5-02 |
| 167 | Data integrity | SHA-256 in manifests; `delivery.verify` | HAVE | - |
| 168 | Production reporting | `report.py`: per-film status report, `status --all FILMS_DIR` cross-film table, `ledger.json` learnings (observation / replicated) | HAVE | - |
