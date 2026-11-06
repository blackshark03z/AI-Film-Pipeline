# Category coverage — Owner's 168 production categories

Branch `feature/drama-preprod-p0`, written 2026-11-06 (loop item P0-01). Source list: Owner's `Danh mục sản xuất phim e2e.txt`; prior root-branch analysis: `docs/research/E2E_FILM_CATEGORY_MATRIX_168_20261104.md` (root repo, read-only). Status describes this branch's code only, not Owner acceptance or quality of output.

**Summary:** HAVE 39 · PARTIAL 88 · GAP 15 · N/A 26 · total 168

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
| 41 | Props | `production/continuity.py` OBJECT (cause rule, hand-off equality) + versioned `prop_*` designs (`impact.py`) | HAVE | - |
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
| 52 | Technical planning | `production/package.FilmHeader` records aspect/fps/resolution/generation_s; `plan` supports 16:9 only (refuses others) + `PreflightLimits` | PARTIAL | P6-02 |
| 53 | Production scheduling | `production/planning.py` schedule: hand-off chains, waves, stills before videos (`film.py planning`) | HAVE | - |
| 54 | Budgeting | `planning.budget`: generations x 12 credits x retake factor from the film01-03 KPI ledgers; Owner estimate checked against it, shown by `validate` | HAVE | - |
| 55 | Risk & safety | `planning.risks`: CONTACT/HANDOVER HIGH need a fallback plan (BLOCK), prop/crowd/depth reported; failures feed `retake` (PROVIDER_LIMIT cause); no provider-moderation risk model | PARTIAL | P7-01 |
| 56 | Legal clearance | `03_preprod.rights` ledger, unresolved entries listed as Owner decisions; final compliance check is P6 | PARTIAL | P6-02 |

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
| 83 | Take management | `production/takes.py` take log `takes/index.json`: take id per generation, prompt/start-frame/output hashes, route, model, credits, status from review | HAVE | - |
| 84 | Script supervision | `drama/qc.py` post-render gating + `sequence` | PARTIAL | P3-02 |
| 85 | Live monitoring | `flow_send.py` network-bound output capture; `film.py generate` payload + intent receipt written before any send, take registered after (live path untested until P3-05) | PARTIAL | P3-05 |
| 86 | Production sound | AI-generated sound; no separate capture. N/A | N/A | - |
| 87 | Data management | Take log hashes + `<gid>_t<N>` ids; no archive/restore yet | PARTIAL | P6-02 |
| 88 | Dailies review | `film.py review`: template per new take (shot questions + 16-group QC) and `--ingest` bound to the take's hash | HAVE | - |
| 89 | Pickup / reshoot | `production/retake.py`: cause-based RETRY / CHANGE_APPROACH / ESCALATE per generation; `film.py retake --pickup` writes shot version N+1 with `repair_of` + history | HAVE | - |
| 90 | Safety management | N/A for AI generation | N/A | - |

## V. Post-production

| ID | Category | Responsibility (code path / package field / operator receipt / N/A) | Status | Backlog |
|---|---|---|---|---|
| 91 | Media ingest | `editorial.probe_media`, `validate_source` | HAVE | - |
| 92 | Logging | Take log + stored reviews (`takes/reviews/`); no unified shot/sound log | PARTIAL | P7-01 |
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
| 107 | Dialogue editing | Dialogue is generated with the clip; loudness only | PARTIAL | P5-01 |
| 108 | Dialogue cleanup | Dialogue is generated with the clip; loudness only | PARTIAL | P5-01 |
| 109 | ADR / dubbing | N/A for current route (no ADR) | N/A | - |
| 110 | Foley | Generated room tone only; no stems or SFX cues | GAP | P5-01 |
| 111 | Sound effects | Generated room tone only; no stems or SFX cues | GAP | P5-01 |
| 112 | Ambience | Generated room tone only; no stems or SFX cues | GAP | P5-01 |
| 113 | Room tone | Generated room tone only; no stems or SFX cues | GAP | P5-01 |
| 114 | Sound perspective | Generated room tone only; no stems or SFX cues | GAP | P5-01 |
| 115 | Music scoring | No music pipeline | GAP | P5-02 |
| 116 | Music editing | No music pipeline | GAP | P5-02 |
| 117 | Sound mixing | No mixer | GAP | P5-01 |
| 118 | Audio mastering | `drama/post.normalize_loudness` EBU R128 | HAVE | - |
| 119 | VFX cleanup | Not needed unless a shot demands it; watermark/artifact handling manual | N/A | - |
| 120 | Compositing | Not needed unless a shot demands it; watermark/artifact handling manual | N/A | - |
| 121 | CGI integration | Not needed unless a shot demands it; watermark/artifact handling manual | N/A | - |
| 122 | Motion graphics | `post.title_card`, `context_card_clip`, `identity_tag_png` | HAVE | - |
| 123 | Color correction | `post.GRADE` global eq only | PARTIAL | P5-03 |
| 124 | Color matching | No shot matching | GAP | P5-03 |
| 125 | Color grading | `post.GRADE` fixed look | PARTIAL | P5-03 |
| 126 | Reframing | No reframe/stabilise | GAP | P5-04 |
| 127 | Retiming | No retime tool (and Owner rejects retime as proof) | N/A | - |
| 128 | Titles & credits | Title + end card in `post.assemble`; no credits builder | PARTIAL | P5-04 |
| 129 | Subtitles & captions | `post.write_srt`, `clamp_cues`, EN/VI sidecars | HAVE | - |
| 130 | Final compositing | `post.assemble` single pass | PARTIAL | P5-04 |

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
| 139 | Temporal QC | No temporal/sequence QC beyond `sequence.validate_shot_sequence` (plan) | PARTIAL | P6-01 |
| 140 | Sequence QC | No temporal/sequence QC beyond `sequence.validate_shot_sequence` (plan) | PARTIAL | P6-01 |
| 141 | Audio QC | Loudness measured; no clipping/silence/sync checks | PARTIAL | P6-01 |
| 142 | Sync QC | Loudness measured; no clipping/silence/sync checks | PARTIAL | P6-01 |
| 143 | Color QC | No colour QC | GAP | P5-03 |
| 144 | Technical QC | `rough_cut._full_decode`, `editorial.probe_media`; no black/freeze detect | PARTIAL | P6-01 |
| 145 | Compliance QC | `disclosure.check_release`; no rights/platform compliance | PARTIAL | P5-02 |
| 146 | Delivery QC | `delivery.verify`, `e2e status --package` | PARTIAL | P6-03 |

## VII. Delivery & distribution

| ID | Category | Responsibility (code path / package field / operator receipt / N/A) | Status | Backlog |
|---|---|---|---|---|
| 147 | Mastering | `post.assemble` + `normalize_loudness` final master | HAVE | - |
| 148 | Encoding | Single H.264/AAC output | PARTIAL | P6-02 |
| 149 | Versioning | 16:9 only | GAP | P6-02 |
| 150 | Localization | EN/VI subtitle sidecars | PARTIAL | P5-04 |
| 151 | Packaging | No thumbnail/metadata draft; `disclosure` JSON only | GAP | P6-02 |
| 152 | Metadata | No thumbnail/metadata draft; `disclosure` JSON only | GAP | P6-02 |
| 153 | Platform compliance | `disclosure.check_release` AI label rules | PARTIAL | P6-02 |
| 154 | Publishing | Publishing prohibited unless Owner asks | N/A | - |
| 155 | Analytics | Post-release; out of scope until a film is published | N/A | - |
| 156 | Archive | `delivery.finalize/verify`; no restore rehearsal | PARTIAL | P6-03 |

## VIII. Production management

| ID | Category | Responsibility (code path / package field / operator receipt / N/A) | Status | Backlog |
|---|---|---|---|---|
| 157 | Project management | Operating docs + this backlog; no per-film tracker | PARTIAL | P7-01 |
| 158 | Resource management | Operating docs + this backlog; no per-film tracker | PARTIAL | P7-01 |
| 159 | Asset management | `ReferenceUploadStore`, runtime assets, hashes; no unified asset index | PARTIAL | P2-01 |
| 160 | Cost management | `drama/kpi.FilmKPI` credits per usable second | HAVE | - |
| 161 | Version control | `designs` versions + `design_refs` pins; takes/stills keep hashes; no version id for shots or assets | PARTIAL | P2-01 |
| 162 | Dependency management | `production/impact.py` `affected_by`: shots, stills, takes (+handoff cascade), edit/post items for one design; design dependencies only | PARTIAL | P2-01 |
| 163 | Change management | Stale-pin issues + `film.py impact` list what to redo; no approval/ledger workflow for a change | PARTIAL | P2-01 |
| 164 | Quality management | `qc_model` P0/P1/P2 take verdicts + waivers (`film.py qc`); Owner gate | PARTIAL | P3-02 |
| 165 | Risk management | `planning.risks` register + `retake` credits-spent / escalation per shot; no run-wide mitigation log | PARTIAL | P7-01 |
| 166 | Rights management | No rights ledger | GAP | P5-02 |
| 167 | Data integrity | SHA-256 in manifests; `delivery.verify` | HAVE | - |
| 168 | Production reporting | KPI ledger, `e2e status`; no cross-film report | PARTIAL | P7-01 |
