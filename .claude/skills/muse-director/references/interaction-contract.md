# Interaction contract — who speaks to whom, from where, looking at what

Ported from AFP-stable `docs/production/PRODUCTION_PROCESS_V2.md` §1–§2, §5–§6 (film04: "MARA talks to nobody").
Muse records people, props, framing and staging kinds, but does not connect them into a staged encounter: there is
no addressee, no listener position and no gaze target. Fill the contract by hand per dialogue beat; fields marked
**proposed field (backlog)** do not exist in code — write them as a `contract` note in the beat (no beat schema
rejects extra keys; the compiler reads only the keys it knows) and list them in the stage report. Backlog: `CRAFT_GAP_BACKLOG.md`.

## Principles

1. **Scene presence ≠ frame visibility.** A character cut out of the frame keeps their mark, listening role, gaze
   target and prop custody.
2. Every relation that must hold on screen exists as data; keyframe and video prompts come from one placement source.
3. Machine checks prove a coherent spec, not the pixels. Pixels need contact-sheet, animatic and take review by the
   Owner.
4. Block before choosing coverage: marks, barrier, gaze, props and the listener's position first.

## Contract per dialogue beat → Muse fields

| Item | What to decide | Muse today | Gap |
|---|---|---|---|
| Speaker | who says the line | beat/shot `speaker`, `dialogue`; `primary_character_id` | — |
| **Addressee** | who the line is spoken *to*; mode in person / off-screen / phone / voice-over / self | none. Staging `reaction` only proves a *different present* listener exists (`core/staging.py` `_resolve`: speaking beat, listener in `characters_present`, listener ≠ speaker) | `addressees` — **proposed field (backlog)** |
| **Listener anchor** | VISIBLE (in frame), OTS_FOREGROUND (partner's shoulder/back of head near camera), OFF_FRAME (just past the lens, side named) | VISIBLE ≈ `is_multi_person` + `characters_present` + framing "two-shot"; OTS ≈ framing "over-the-shoulder" + second character's anchor in `extra_refs` (multi-person shots only). `foreground_element` is only copied from the beat (authored, or set by `script_ingestor`); the compiler never derives it from the partner — on the B14 dry-run copy S06 compiled with `None`. Single shots get "Only this character in frame" with no addressee; OFF_FRAME: none | `listener_anchor {character, mode, side, established_by}` and partner-derived OTS foreground — **proposed field (backlog)** |
| **Marks** | where each person stands in the set (world, not camera, positions) | location `set_facts` ("Set layout lock: …" in every prompt) + master plate `assets/setups/<loc>__master_plate.png`; positions are free text in `action_summary` | `locations[].marks` + beat `blocking {character: {mark, posture, facing}}` — **proposed field (backlog)** |
| **Gaze target** | what each person looks at (a character, a mark, an object) | character `axis_gaze` and beat `gaze` (compiler line ~440, default "looking screen-right") — a **screen direction**, not a target | `gaze_target` — **proposed field (backlog)** |
| **Prop custody** | who holds/supports each prop, transfers with a cause | `props_ledger[].state_tracking[beat_id]` (state text), staging `state_insert.state`, `source_action.before_state/after_state`, shot `prop_continuity` | holder per state, one holder at a time — **proposed field (backlog)**; until then write the holder inside the state text ("in PAMELA's left hand") |
| **180° axis** | which side of the line the camera stays on | `axis_gaze` per character, locked into prompts; compiler 30° jump-cut warning; `transition_in` | no axis check across shots of different characters — review in the animatic |
| **Coverage (D2)** | geography first, then OTS pairs; clean singles only CLOSE or tighter with OFF_FRAME anchor | `audit_coverage` D2 warns only when a chapter has ≥ 3 dialogue shots, ≥ 2 speakers and no multi-person shot; also "missing wide/two-shot" per chapter | no per-line check that the addressee is anchored — **proposed check (backlog)** |
| **Must show** | evidence the audience must see | bible `must_show` (D6 warns if never shown) | — |
| **Encounter hand-off** | posture and prop state carry across the cut, also across scene numbers | staging groups by `(chapter_id, location, scene_id)`; `source_action.before_state` must match the previous beat of the same scene; Muse pins only the first frame (keyframe) | `encounter_id` + end-state check of the previous take before the next send — **proposed field (backlog)** |
| Relations / knowledge | stance, power, what each knows per beat | none | **proposed field (backlog)**, low priority |

## Rules for Muse dialogue coverage

- Establish readable geography first (wide / two-shot / OTS, or inherited within the encounter).
- Then complementary OTS shots are the default; the partner in the foreground must be the distinct addressee.
- A clean single only at close-up or tighter, after geography, with an OFF_FRAME anchor: prompt "X stands just off
  frame-left beside the camera; her eyes go just past the lens to the left". The keyframe must not show the
  listener's place empty.
- A clean single wider than close-up needs a written directing exception backed by the composition, shown to the
  Owner with the keyframe (AFP `PRODUCTION_PROCESS_V2.md` §6.6).
- Name the addressee in the prompt ("she speaks to THEO"), never a bare "him/her".
- Add a `reaction` when the line changes the listener, not after every line; write the source behaviour into the
  reaction as `staging.visible_behavior` (optional `framing`); without it the compiler writes a generic
  "silently takes in the line" action with hands out of frame.
- Narration about faces, hands and the crowd becomes performance, picture and sound (B14).

## Review questions (contact sheet, animatic, take)

- Who is X talking to? Can you see the listener or their shoulder, or does X look just past the lens toward them?
- Is the listener's place shown empty? Is the body (feet, hips, chest, face) turned to the addressee? (B14 01A r3)
- Does X look at the target the whole shot? Do near/far order and sides match the previous shot?
- Correct holder, hand and support for every prop? After the cut, do posture and prop state match?
- Did the camera angle stay the same across the selected lines? (B14 01B: Muse switched angle between two lines)
