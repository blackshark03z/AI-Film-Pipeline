# `<P>/LANE_REVIEW.md` template

Create it at stage 0; append, never rewrite history. Keep it short: verdicts and evidence, not media dumps.
Credit is not a constraint in a lane: there are no caps to track. `sends_by_shot` / `takes_by_shot` are recorded for information only.

```markdown
# Lane <lane id> — <film title>

## Grant (from the Owner's opening message, quoted)
> <opening message, verbatim>
- lane: <id> · accounts N: <n> (granted <g>) · project: <abs P> · SRT: <abs path> (full story | excerpt from <hh:mm:ss>)
- lane opened: <timestamp> · renewed: <timestamps> · closed: <timestamp>

## Story assumptions
- <your reading of the SRT where it is unclear (value at stake, ending, addressee); SRT events unchanged>

## Runs
| when | command | items requested | items returned (`sends_by_shot`, `takes_by_shot` for videos) | exit / status |
|---|---|---|---|---|

Takes per shot:

| shot | level | dialogue? | takes per wave (`takes_by_shot`) | waves sent | verified take (`per_shot_qc` `take`) | kept take (self-review) + `clip_path` | status (pending / PASS / RESTAGE / BLOCKED / CUT) |
|---|---|---|---|---|---|---|---|

## Generability
See `generability_review.md` (one row per shot). RED shots restaged: <list> · cut: <list>

## Dialogue edits (meaning unchanged)
| beat | reason (`DIALOGUE_OVER_CAPACITY` / lip-sync fit) | before | after |
|---|---|---|---|

## Reviews (self-review, not independent)
| ★ point | artifact (file) | evidence (cell / timecode) | CREATIVE_REVIEW line | lane verdict | action |
|---|---|---|---|---|---|
| anchors | assets/anchors/anchors_contact_sheet.jpg | r1c2: … | CREATIVE_REVIEW … self_review=yes … | PASS / RESTAGE / CUT | … |

## Defects
| beat/shot | class | occurrence (1st fix / 2nd new approach / 3rd CUT-BLOCKED) | stage that should have caught it | fix (upstream) | ledger row added |
|---|---|---|---|---|---|

## BLOCKED / CUT beats
| beat | reason | story cost |
|---|---|---|
```

# Final report (to the Owner, in Vietnamese)

```markdown
**Lane <id> — <title>: <stage reached>**

1. Technical PASS: preflight <0 HARD / n warnings>, QC <passed>/<total> (`qc_audit_report.json`), SRT gate <ran | SKIPPED_BY_FLAG: excerpt>.
2. Agent self-review (self-review, not independent): anchors <…>, plates <…>, keyframes <…>, animatic <…>, takes <k kept / r restaged / c cut>, master <…>. Details: `<P>/LANE_REVIEW.md`.
3. Owner acceptance: pending — review: <contact sheets>, `ANIMATIC/animatic_preview.mp4`, `MASTER_OUTPUT/final_master_1080p.mp4`, `MASTER_OUTPUT/DELIVERY_KIT/`.

- Runs (information): stills runs <n>, video waves <n>, `sends_by_shot` / `takes_by_shot` <summary or path>
- Lane: <id>, accounts <ids or count, no credentials>, closed <yes/no>
- BLOCKED/CUT beats: <list with reason and story cost>
- Dialogue edits: <n> (before/after in `LANE_REVIEW.md`)
- Story assumptions: <list>
- Lessons ledger rows added: <n> (`.claude/skills/muse-director/references/lessons.md`)
- Not done / skipped: <…>
```
