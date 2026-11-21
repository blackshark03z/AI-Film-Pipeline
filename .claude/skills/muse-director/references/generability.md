# Generability — rate every shot before stills

Ported from AFP-stable (`docs/director/DIRECTOR_PLAYBOOK.md` §5–§6, `docs/production/PRODUCTION_PROCESS_V2.md`
§2, §7) and adapted to Muse. AFP lost ~14 h on film04 to beats the video model cannot do; Muse has the same
pattern on a smaller sample (evidence below). Muse has **no generability field or check in code yet** — the rating
is a director step recorded by hand (see "Where it lives"). Backlog: `CRAFT_GAP_BACKLOG.md`.

## When

After the first `cli compile` (stage 3a) and **before** `keyframes` (stage 2.5). Re-rate after any restage or
recompile that changes a shot's action, framing or props. A restage is a new design that gets a new rating; it is
not a waiver, and extra sends do not cure a structural difficulty.

## Rating (per shot; a shot takes its worst phase: RED > UNKNOWN > AMBER > GREEN)

| Level | Muse meaning | Typical actions |
|---|---|---|
| GREEN | Supported action family with matching conditions and evidence | faces, looks, glances, a line of dialogue to a visible or anchored partner, small head/hand gestures with nothing held, holds, light change; `state_insert` of a prop with no hands (needs `--cinematic-cutaways`) |
| AMBER | Understood variability; may need a second send | walking in/out, sitting/standing with nothing pinned nearby, placing a large object, a door that only opens, two people with a body action, turning the whole body toward an on-screen partner (B14 01A), dialogue with numbers or names that must be heard exactly, crowds whose poses must match across takes, a dropped prop's resting place on the floor matching in the next shot (B14 final wide: clipboard at the frame's bottom edge, hard to read) |
| RED | Evidenced hard constraint or coupled interaction | hands on small objects (keys, coins, glasses, tickets, pens), a body moving near a pinned prop, a held object released to fall, a mechanism stopping part way (drawer, shutter, window), pouring, counting, text that must read, a body entering a fixed gap |
| UNKNOWN | No rule above matches, or no Muse evidence yet | any new action family — say so instead of guessing GREEN. No Muse evidence yet: turning toward an **off-screen** person or a crowd (gaze/body to a point past the lens) |

Also scan the opening state (the keyframe pose) and holds: a still hand resting on a prop the shot pins is already
a RED constraint.

## Send caps (caps, not permission to spend)

| Level | Cap | Condition |
|---|---|---|
| GREEN | 1 send | approved keyframe |
| AMBER | up to 2, reviewed one after the other | change the prompt or keyframe between sends based on the first take |
| UNKNOWN | 1 exploratory send | after the keyframe is approved, with written review questions |
| RED | 0 | restage first; only the Owner can grant an exception |

Mapping to the generation step: `pool_runner videos` re-sends every failing shot each round (`--max-rounds`,
default 3) and auto-repairs prompts by default. Set `--max-rounds` to the cap of the strictest shot in the batch,
and add `--no-auto-repair` when the batch holds AMBER/UNKNOWN shots you want to review between sends. QC `PASS`
does not consume or refund the cap — the Owner's verdict does. On Muse there are no send caps, in or out of a lane
(Owner, 2026-11-20; the caps above apply only to providers that still need spend approval, e.g. Flow): this table
becomes the takes policy (GREEN 1, AMBER 2, UNKNOWN 3 parallel takes, dialogue / lip-sync at least 2, RED never
sent), run as `videos --max-rounds 1 --takes K` per review cycle; `sends_by_shot` / `takes_by_shot` are information only, and the
quality stop rule (2nd occurrence → change approach, 3rd → cut/BLOCKED) still applies (`SKILL.md`, "Lane mode").

**RED exception record** (Owner only; the rating stays RED): shot id, keyframe SHA-256 and manifest version, reason,
evidence, attempt cap, credit cap, expiry. Reusing an already accepted take covers that exact take only.

## Where it lives

Until the compiler has a field, write `<P>/generability_review.md` next to the manifest: one row per shot —
`shot_id | level | phase/reason | evidence | restage chosen | cap | Owner exception`. Show it with the keyframe
contact sheet when asking for spend. A shot without a row is UNKNOWN. Proposed code home: a `generability` block per
shot in `shots_manifest.json` written by `core/screenplay_compiler.py`, checked by `preflight` (RED without an
exception = HARD) — backlog item, not built.

Note: `pool_runner videos` sends only shots not yet in `passed_clips`; it has no flag to pick a subset, so every
pending shot in the manifest is sent each round.

## Restage options for a RED shot

1. **Cut around it:** show the before and the after in two GREEN shots; the action happens across the cut.
2. **Prop-only insert, no hands:** use staging kind `state_insert` (the prop in its ledger state) instead of
   `source_action`. `source_action` always compiles to a 100 mm "Macro Prop Insert" of the action — exactly the RED
   hand-on-small-object shape of `S06__prop_insert`. `state_insert` (and `reaction`) only materialise when both
   compiles use `--cinematic-cutaways`; otherwise they are dropped with no `staging_review` row. They are capped at
   floor(20%) of source beats. Check `staging_review` after compile to see the restage actually landed.
3. **Off screen + sound:** keep the cause → result → response readable; the assembler's Foley layer carries the
   sound. Leave a legible interval (a dropped object is not instantly on the floor).
4. **Frame the prop out:** the face carries the moment; the prop's state is shown in an earlier/later shot.
5. **Composite** (last resort, Owner approval, record sources). B14 Pamela (face/upper body from one take, hands
   from another) is the version currently used in the cut, with Owner acceptance still pending (handoff §5) — not
   an approved precedent.

## Writing rules that lower the rating (Muse form of AFP §6)

- **Faithful action:** extract actor → action → receiver → consequence from the source; add no harder or extra
  action and do not merge a later event into this shot.
- **One principal action per generation.** Duration ≈ 1 s setup + the action + 0.5–1 s settle. Fill story time
  with a scripted beat, not a hold. Check the returned duration and size against the request.
  **Conflict with the compiler:** `screenplay_compiler.py` sets `duration_s = 10.0` for every dialogue shot (a
  5-word line included) and 5.0 for silent `native_drama` shots. Since 2026-11-19 the prompt's speech window follows
  the line length (`dialogue_timing`, ~2.4 words/s, then "No further words"), and `DIALOGUE_OVER_CAPACITY` flags
  lines over 8.5 s; the clip is still 10 s, so note the intended length per shot and trim in the edit.
- **The keyframe is the opening state.** Hands are *off* every prop the shot pins; the pose matches the beat's
  first moment (macro retest fixed skin tone and the hand gap only by changing the keyframe).
- **Pin what must not change:** "Unchanged the whole shot: <prop> <state>"; anchor the state to the set, never to a
  moving body; never name the pinned prop with a verb, not even negated.
- **A once-only action is written once, in observable words**, at the moment it happens (the short macro prompt
  touched the key twice).
- **Camera:** the compiler writes "Locked-off static tripod shot of exactly N seconds"; keep that clause in any
  hand-written prompt. Muse still adds push-ins on its own (59-word macro prompt), so review camera motion per take.
- **Do not depend on exact framing** for a story point; plan so a close-up that renders as a medium still reads.
- **An uncontrolled outcome (falls, spills, tears) is never relied on across a cut:** verify the take's end state
  before generating the next shot.

## Muse evidence

| Shot | Action | Rating it should have had | What happened |
|---|---|---|---|
| `S06__prop_insert` macro 100 mm, long prompt (`_live_v50_macro_video_20261118/REPORT.md`; SOT line 99) | hand lowers onto a brass key on a table | RED (hands on small object + pinned prop) | QC `PASS`; background and hand jump between 1.88 and 1.92 s; key tilts and its ring lifts off the table ~3.25–3.50 s; suggested trim 2.00–4.00 s kept the defect |
| same shot, 59-word prompt (`_live_v50_macro_short_video_20261118/REPORT.md`; SOT line 100) | same | RED | 5 s asked, 10.00 s at 1248×704 returned; camera pushed in against a locked-off ask; the key was touched twice (~3.75 s and ~8.50 s) |
| same shot, keyframe (`_live_v50_20261118/REPORT.md`, `_live_v50_macro_retest_20261118/REPORT.md`) | opening pose | AMBER at keyframe | first still had fingers already on the key and the wrong skin tone; a keyframe fix (anchor-locked skin, visible gap) solved the still, not the motion |
| B14 Pamela (`HANDOFF_CLAUDE_MUSE_20261119.md` §5) | clipboard slips from her hand to the carpet | RED (held object released to fall) | Muse kept lifting the board and holding it with two hands; two release-only takes failed; a composite is used in the current cut, Owner acceptance pending |
| B14 Todd 01A (handoff §5) | body turned toward Pamela while speaking | AMBER | two prompt passes still turned him toward camera; fixed at the keyframe (r3), Owner-approved |
| B14 Todd 01A (handoff §5) | says "Flight 1128" | AMBER (number must be heard) | two ASR models heard 128; later take 1118 vs 1128 between models; still awaiting a listen |
