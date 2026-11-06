# Category coverage — Owner's 168 production categories

Branch `feature/drama-preprod-p0`, written 2026-11-06 (loop item P0-01). Source list: Owner's `Danh mục sản xuất phim e2e.txt`; prior root-branch analysis: `docs/research/E2E_FILM_CATEGORY_MATRIX_168_20261104.md` (root repo, read-only). Status describes this branch's code only, not Owner acceptance or quality of output.

**Summary:** HAVE 14 · PARTIAL 79 · GAP 49 · N/A 26 · total 168

Status: HAVE = code path covers the responsibility at the level the dramas need; PARTIAL = covers plan/declared level or one slice; GAP = no path; N/A = not applicable to the AI route (reason in the responsibility column). Update Status/Backlog when an item closes.

## I. Story development

| ID | Category | Responsibility (code path / package field / operator receipt / N/A) | Status | Backlog |
|---|---|---|---|---|
| 1 | Concept | No field; operator/model decision recorded in package 01_story.json | GAP | P1-01 |
| 2 | Audience | No field; operator/model decision recorded in package 01_story.json | GAP | P1-01 |
| 3 | Premise | `comprehension.StoryFact` covers facts only; no premise/conflict model | PARTIAL | P1-01 |
| 4 | Logline | No field; operator/model decision recorded in package 01_story.json | GAP | P1-01 |
| 5 | Story structure | `drama.script` scene/character parse only; no structure/arc/beat model | GAP | P1-01 |
| 6 | Plot & subplot | `drama.script` scene/character parse only; no structure/arc/beat model | GAP | P1-01 |
| 7 | Character arcs | `drama.script` scene/character parse only; no structure/arc/beat model | GAP | P1-01 |
| 8 | Dramatic beats | `drama.script` scene/character parse only; no structure/arc/beat model | GAP | P1-01 |
| 9 | Scene design | `drama.script` scene/character parse only; no structure/arc/beat model | GAP | P1-01 |
| 10 | Screenplay | `drama/script.py` Fountain intake (Vietnamese-first); version/approval not tracked | PARTIAL | P0-02 |
| 11 | Dialogue | `drama/coverage.SpokenLine` + `feasibility` syllable limits | HAVE | - |
| 12 | Rewrite | `drama.script` scene/character parse only; no structure/arc/beat model | GAP | P1-01 |
| 13 | Script breakdown | `drama/feasibility.py` + `scene_bible` occupancy; heuristic breakdown | PARTIAL | P2-05 |
| 14 | Adaptation | `e2e` source SRT hash lock; rights status not modelled | PARTIAL | P1-01 |

## II. Creative direction

| ID | Category | Responsibility (code path / package field / operator receipt / N/A) | Status | Backlog |
|---|---|---|---|---|
| 15 | Directorial vision | No treatment/visual-rule record; film README only | GAP | P1-02 |
| 16 | Visual language | No treatment/visual-rule record; film README only | GAP | P1-02 |
| 17 | Mise-en-scène | `drama/scene_bible.py` occupancy + location look | PARTIAL | P2-03 |
| 18 | Shot composition | `coverage.CoverageShot` size/angle fields; no composition check | PARTIAL | P2-03 |
| 19 | Shot size | `coverage._SIZE` + `autoqc.shot_scale_from_ratio` (WARN) | HAVE | - |
| 20 | Camera angle | `coverage.CoverageShot` size/angle fields; no composition check | PARTIAL | P2-03 |
| 21 | Camera movement | ShotSpec camera.movement (locked default); no movement plan | PARTIAL | P2-03 |
| 22 | Blocking | `choreography.GenerationChoreography` phases + `core.Blocking` | HAVE | - |
| 23 | Staging | `scene_bible` occupancy + `Blocking`; layering not modelled | PARTIAL | P2-03 |
| 24 | Screen direction | `drama/axis.py` AxisBook 180-degree | HAVE | - |
| 25 | Spatial geography | `drama/storyboard.py` schematic frames + `scene_bible` | PARTIAL | P2-03 |
| 26 | Temporal continuity | `drama/continuity.py` + `scene_bible.StoryTime` | PARTIAL | P2-02 |
| 27 | Performance direction | `choreography.PerformanceCue` visible cues + prohibited misread | PARTIAL | P1-02 |
| 28 | Emotional direction | No emotional curve model | GAP | P1-02 |
| 29 | Rhythm & pacing | Phase lengths in choreography; no pacing plan or hold check | PARTIAL | P4-02 |
| 30 | Coverage strategy | `drama/coverage.CoveragePlanner` master/OTS/single/reaction | PARTIAL | P1-02 |
| 31 | Transitions | No transition intent record | GAP | P1-02 |
| 32 | Visual storytelling | `action_meaning` + choreography once_actions (must-show) | PARTIAL | P1-02 |
| 33 | Point of view | No POV model | GAP | P1-02 |
| 34 | Dramatic emphasis | No emphasis/reveal model | GAP | P1-02 |

## III. Pre-production

| ID | Category | Responsibility (code path / package field / operator receipt / N/A) | Status | Backlog |
|---|---|---|---|---|
| 35 | Casting | `drama/bible.py` approved reference images (CharacterBrief) | PARTIAL | P2-01 |
| 36 | Character design | `drama/bible.py` CharacterLook + reference binding per generation | PARTIAL | P2-01 |
| 37 | Location scouting | `scene_bible.LocationLook` (AI-only: approved location image) | PARTIAL | P2-01 |
| 38 | Production design | `scene_bible` location look; no set geometry/palette record | PARTIAL | P2-03 |
| 39 | Set design | `scene_bible` location look; no set geometry/palette record | PARTIAL | P2-03 |
| 40 | Set dressing | `scene_bible`/`continuity` prop positions; no version or ownership | PARTIAL | P2-02 |
| 41 | Props | `scene_bible`/`continuity` prop positions; no version or ownership | PARTIAL | P2-02 |
| 42 | Costume design | `CharacterLook.text` wardrobe/hair; no version or story-day state | PARTIAL | P2-01 |
| 43 | Hair & makeup | `CharacterLook.text` wardrobe/hair; no version or story-day state | PARTIAL | P2-01 |
| 44 | Cinematography planning | No camera/lighting plan beyond `scene_bible.lighting` string | GAP | P2-03 |
| 45 | Lighting design | No camera/lighting plan beyond `scene_bible.lighting` string | GAP | P2-03 |
| 46 | Storyboarding | `drama/storyboard.py` schematic board + Gate 2 | HAVE | - |
| 47 | Previsualization | Still storyboard only; no timed animatic | GAP | P2-04 |
| 48 | Blocking diagram | `storyboard.render_schematic_frame` + AxisBook | PARTIAL | P2-03 |
| 49 | Shot planning | `generation.py` split into 8 s units + `coverage` shot list | PARTIAL | P2-05 |
| 50 | Continuity planning | `drama/continuity.py` + `sequence.validate_shot_sequence` | PARTIAL | P2-02 |
| 51 | Sound planning | Prompt carries room tone/SFX strings (`prompt.py`); no sound plan | PARTIAL | P5-01 |
| 52 | Technical planning | `PreflightLimits`, 1280x720/24 fps fixed in post; no spec record | PARTIAL | P0-02 |
| 53 | Production scheduling | No schedule/order record | GAP | P2-05 |
| 54 | Budgeting | `drama/kpi.py` actuals only; no estimate | PARTIAL | P2-05 |
| 55 | Risk & safety | Moderation notes in memory only; no risk record | GAP | P2-05 |
| 56 | Legal clearance | `disclosure` metadata; no rights/clearance ledger | GAP | P2-05 |

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
| 76 | Emotional continuity | No emotional continuity check | GAP | P4-02 |
| 77 | Interaction | `choreography` ACTION phases + `action_meaning` | PARTIAL | P3-02 |
| 78 | Background performance | `occupancy`/`EXTRAS` strings in film tools | PARTIAL | P2-03 |
| 79 | Action timing | Phase timings in `GenerationChoreography` | PARTIAL | P4-02 |
| 80 | Set operation | No crew/rehearsal on AI route; animatic is the rehearsal analogue | N/A | P2-04 |
| 81 | Assistant directing | No crew/rehearsal on AI route; animatic is the rehearsal analogue | N/A | P2-04 |
| 82 | Rehearsal | No crew/rehearsal on AI route; animatic is the rehearsal analogue | N/A | P2-04 |
| 83 | Take management | `SelectedTake`/`qc` lineage in runtime; drama takes only in file names | PARTIAL | P3-02 |
| 84 | Script supervision | `drama/qc.py` post-render gating + `sequence` | PARTIAL | P3-02 |
| 85 | Live monitoring | `tools/drama_flow_ui/flow_send.py` network-bound output capture | PARTIAL | P3-04 |
| 86 | Production sound | AI-generated sound; no separate capture. N/A | N/A | - |
| 87 | Data management | `drama/disclosure.sha256_file`, runtime hashes; no naming/metadata convention | PARTIAL | P3-02 |
| 88 | Dailies review | `e2e` review template; no drama dailies review | PARTIAL | P3-02 |
| 89 | Pickup / reshoot | No pickup plan; repair path exists in `e2e` runtime only | PARTIAL | P3-03 |
| 90 | Safety management | N/A for AI generation | N/A | - |

## V. Post-production

| ID | Category | Responsibility (code path / package field / operator receipt / N/A) | Status | Backlog |
|---|---|---|---|---|
| 91 | Media ingest | `editorial.probe_media`, `validate_source` | HAVE | - |
| 92 | Logging | `qc.py` evidence + selected take records | PARTIAL | P3-02 |
| 93 | Synchronization | Audio in generated clips; `post.cue_offsets` for subtitles | PARTIAL | P4-01 |
| 94 | Selects | `qc.SelectedTake` | HAVE | - |
| 95 | Assembly cut | `drama/post.assemble` + `rough_cut` FFmpeg | PARTIAL | P4-01 |
| 96 | Rough cut | `drama/post.assemble` + `rough_cut` FFmpeg | PARTIAL | P4-01 |
| 97 | Structural editing | Order fixed by plan; no structural/continuity/performance edit tool | GAP | P4-02 |
| 98 | Continuity editing | Order fixed by plan; no structural/continuity/performance edit tool | GAP | P4-02 |
| 99 | Performance editing | Order fixed by plan; no structural/continuity/performance edit tool | GAP | P4-02 |
| 100 | Narrative editing | Hard cuts only; no transition/rhythm tooling | GAP | P4-02 |
| 101 | Rhythm editing | Hard cuts only; no transition/rhythm tooling | GAP | P4-02 |
| 102 | Transition design | Hard cuts only; no transition/rhythm tooling | GAP | P4-02 |
| 103 | Montage | Not needed for current dramas; add only if a script needs it | N/A | - |
| 104 | Fine cut | No per-event in/out tool beyond `film_e2e finish --trim` | PARTIAL | P4-01 |
| 105 | Picture lock | No picture lock | GAP | P4-03 |
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
| 131 | Narrative QC | `comprehension.check_comprehension` on the plan; footage unchecked | PARTIAL | P3-01 |
| 132 | Coverage QC | `CoveragePlanner` plan-level only | PARTIAL | P1-02 |
| 133 | Character QC | `drama/autoqc` identity (YuNet/SFace) WARN-only | PARTIAL | P3-02 |
| 134 | Spatial QC | `autoqc` side/handoff set (WARN); `AxisBook` | PARTIAL | P3-02 |
| 135 | Action QC | Human review only; `action_meaning.qc_questions` template | PARTIAL | P3-02 |
| 136 | Motion QC | No automated motion/visual artifact detector (human review) | GAP | P3-01 |
| 137 | Camera QC | `autoqc.shot_scale` WARN | PARTIAL | P3-02 |
| 138 | Visual QC | No automated motion/visual artifact detector (human review) | GAP | P3-01 |
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
| 161 | Version control | Git + hashes; no shot/asset version ids | PARTIAL | P2-01 |
| 162 | Dependency management | No dependency/change-impact index | GAP | P2-01 |
| 163 | Change management | No dependency/change-impact index | GAP | P2-01 |
| 164 | Quality management | `qc` evidence + Owner gate; no P0/P1/P2 model | PARTIAL | P3-01 |
| 165 | Risk management | No risk register | GAP | P2-05 |
| 166 | Rights management | No rights ledger | GAP | P5-02 |
| 167 | Data integrity | SHA-256 in manifests; `delivery.verify` | HAVE | - |
| 168 | Production reporting | KPI ledger, `e2e status`; no cross-film report | PARTIAL | P7-01 |
