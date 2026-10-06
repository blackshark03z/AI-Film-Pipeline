# AI-FILM-QUALITY-V2-011R — Targeted F2 Creative / Continuity Repair

```text
STATUS
  COMPLETED_CANDIDATE — PRODUCTION LOCK GRANTED (worker advisory; the
  Owner visual read of owner_review_011r/ is the ruling surface)

FINAL HEAD
  branch quality-v2/011r-targeted-repair (base ddd4eb9 = 011A)

F2A-R
  provider:        Dola BrowserNetwork (ACCOUNT_A / dola-main)
  asset:           assets/f2a_r.mp4 — 5.088s, 1280x720, 24fps, hevc,
                   full decode PASS
  direction:       PASS — LATERAL FRAME-LEFT, full-profile right-to-left
                   crossing (t000→t100); the 011A failure is repaired
  geography:       PASS — natural rough boulder ridge both sides, single
                   gap, road funnels in; NO architecture
  identity:        PASS — white robes/black sash/topknot; NO sword
  selected range:  1.2–4.0s (approach-and-enter; 2.8s editorial slot)
  verdict:         PROVEN — critical QC PASS
  advisories:      a black cape-like cloth mass streams behind the
                   character (model-added; reads as storm-cloak); bare feet
  sha256:          50a133c891aaa0060bc1f7d9d6c48c77a3fab1e802bc5f7a4fc43e112404d99b

F2B-R
  provider:        Dola BrowserNetwork (ACCOUNT_A / dola-main)
  asset:           assets/f2b_r.mp4 — 5.088s, 1280x720, 24fps, hevc,
                   full decode PASS
  geography:       PASS — natural dark cliff, NO cut blocks/lintel/roof/
                   parapet/gate (the 011A fortress failure is repaired)
  sword:           ABSENT (the 011A prop failure is repaired)
  wind:            PASS — robes billow hard, headband streams, dust kicks;
                   wind from the left opposing travel (the 011A causal
                   failure is repaired)
  palette:         PASS — cool storm-blue overcast (the 011A warm-palette
                   failure is repaired)
  direction:       PASS — lateral frame-left, full profile
  selected range:  0.4–3.2s (break-out-and-continue; 2.8s editorial slot)
  verdict:         PROVEN — critical QC PASS
  advisories:      dark shoes (F2A-R bare feet — minor costume note)
  sha256:          8679709b00860a2e3af45354b2166eae2b6d6b365731a278f21809a42babbbff

PAIR
  continuity:      PASS — identity/wardrobe/props/world/palette/weather/
                   travel axis/screen direction/action energy/camera axis/
                   spatial geography ALL MATCH (the gap connects the
                   shots: F2A-R ends entering it, F2B-R starts leaving it)
  cut:             READS NATURALLY (side-by-side junction provided)
  production lock: GRANTED (advisory)

MUTATIONS USED / 2
  F2A-R 1/1 — released ~06:32Z; the runner crashed post-release on a
  PRE-EXISTING codebase regex defect (semantic-family; fixed during this
  slice) — the journal's fsync'd NETWORK_RELEASE_OBSERVED made the release
  provable; knowledge resolved RESOLVED_EFFECT_IDENTIFIED; latch terminal
  F2B-R 1/1 — released with the fixed code; the receipt capture timed out
  (video dispatch streams stay open >120s — capture-design limitation
  recorded); reconciled completion
  No retry. No provider switch. Account binding immutable per release.

TESTS
  Full regression 1316 passed (011A state); journal tests 14 green.
SECRET AUDIT
  CLEAN (zero marker hits in tracked 011R files).
PROVIDER LINEAGE
  ACCOUNT_A → F2A-R conversation 38417852262252561 → creation
  1543341075843857 (vid v186a3gm000cdb29k67og65phfv1unkg,
  filehash 57da1f4e…) → F2B-R conversation 38418085966239761 → creation
  1546449850446097 (vid v186a3gm000cdb2acjfog65s7c1c025g, filehash
  117b8eb1…). Credits: daily 4 → 1 remaining across the two repair
  dispatches (provider acks authoritative).
EVIDENCE
  projects/quality_v2_011r_targeted_repair/: V2_011R_{F2A,F2B}_REPAIR_SPEC
  /EVIDENCE/PAIR_CONTINUITY/EDITORIAL_SELECTION/MUTATION_LEDGER/
  PROVIDER_LINEAGE/SECRET_AUDIT/CANDIDATE_SEAL.json + dispatch journals +
  V2_011R_REPAIR_SPECS.json + owner_review_011r/
  docs/operating/AI_FILM_QUALITY_V2_011R_TARGETED_REPAIR_EVIDENCE.md
WORKTREE
  011R work committed on quality-v2/011r-targeted-repair.
STOP REASON
  None — production lock granted (advisory). Owner items: visual read of
  the 011R pack; watermark decision (Dola AI mark present bottom-right,
  unwatermarked variants exist but remain OBSERVED_NOT_AUTHORIZED);
  final trim/crop call.
```

## What the repair actually changed

1. **F2A-R — the minimal fix**: same world/wardrobe/wind that QC-PASSED in
   011A, with ONE decisive change: the camera moved from inside the pass
   (head-on) to BESIDE the traversal axis (profile), plus explicit
   right-to-left crossing language. Result: the lateral frame-left axis
   the frozen plan demands — everything 011A passed stayed passed.
2. **F2B-R — the rebuild**: negative-architecture block (no cut blocks/
   lintel/roof/parapet/gate/castle/fortress), no-weapon constraint, cool
   storm palette, enumerated causal wind vectors (lean/cloth/headband/
   grass/dust), lateral exit with the ridge behind-right. Result: the
   fortress world is GONE — natural cliff, wind, storm, no sword.
3. **All vectors agree**: wind from the left (opposing the right-to-left
   travel), robes/headband streaming right, lean into the gust, effortful
   gait — the causal environment the 011A F2B lost entirely.

## Tooling defects hit and fixed during this slice (recorded)

1. stale `\1\2` regex templates in three tools (pre-existing codebase
   defect surfaced twice) — fixed; the second occurrence crashed F2A-R
   post-release and the journal carried the proof (the 010E durability
   rule held under a real crash, again);
2. receipt-capture window: video-dispatch streams stay open beyond 120s —
   recorded as a capture-design limitation; reconciled completions are
   the honest recovery path;
3. multi-instance reconciliation raced on one browser profile — one
   launch per account at a time.
