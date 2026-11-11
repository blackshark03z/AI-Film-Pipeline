# P20 — approved 25–30 minute production implementation

Owner approved this plan in the current Codex chat on 2026-11-10. Implement on AFP-stable,
feature/drama-preprod-p0, base804727952f87d793b19b0eaf9cda15fdf629c04d.
POLICY_REF45f71d6226c5ffc58b4e70f3bcea1bb0151b7003, AGENTS blob6cab2103e32448a10e13b7f00c1a3eb4adb4a221.

## Product contract
- Agent produces each25–30minute original drama; Owner approves brief/rights/budget before generation and final film.
- Dialogue plus standing/sitting, entering/leaving and simple pick/place actions; no complex physical contact or parallel films.
- Flow Omni1.2Flash360p; preserve film06's accepted media, receipts, rights decisions, budget baseline and historic results.
- Budget each film from its script and current quotes. Existing256.8credit cap is not raised by this implementation.
- Two consecutive25–30minute films accepted by Owner are required for STABLE_SUPERVISED. Offline qualification is not that result.
- Zero new provider calls/uploads/purchases/push/publication during M0–M2. M3 draft/estimate is reviewable before asking for live approval.

## Milestones / acceptance
- [ ] M0: pin environment/source, reconcile stale operating instructions, reclaim only owned pytest fixtures after preserving
  logs/JUnit; at least20GiB scratch; environment/disk/provider preflight before expensive work.
- [ ] M1: immutable sent prompt snapshot, film/Flow writer exclusion, pending reservations, idempotent reconcile and immutable
  versioned delivery. Crash/restart and duplicate-command tests preserve original evidence and never blindly send again.
- [ ] M2: scene-duration-aware feasibility; resumeable finish; bounded cached picture/portrait processing (60s or12events),
  transition/J/L handles, PCM intermediate audio, graph files. Real Windows1800s/~300event fixture, both aspects, decode/hash/
  captions/disclosure/restore proof. One FFmpeg process, <=12GiB peak RAM, >=4GiB free reserve. Required scratch is
  max(20GiB,1.5x measured peak scratch). Synthetic footage stays explicitly rehearsal, never creative acceptance.
- [ ] M3: draft original pilot script/shot plan/rights and current quote estimate; Owner confirms before Generate. Qualify
  first3–5minutes of that same film, then complete25–30minutes, without manual registry/receipt/manifest repair.
- [ ] M4: separately approved second film; exact software release qualification/cold install; both films accepted. Only then
  claim stable operation for this scene class and report measured production cadence.

## Interfaces and implementation decisions
- `film.py reconcile --film DIR --take-id ID`: no generation. Bind/download/hash/register exactly once, preserve original
  intent payload, resolve only on evidence. Registering a clip never accepts its creative quality. Legacy receipts may use
  the current prompt only if its hash matches. New sends capture immutable `takes/intents/<take-id>.prompt.txt` first.
- `film.py finish --film DIR [--dry-run]`: requires accepted production inputs and locked EDL. Existing chain in explicit
  order: grade/titles/clean render -> mix(titled picture) -> mastercheck -> portrait -> dialoguecheck -> deliver/verify.
  Only verified fresh outputs are skipped; no automatic final Owner acceptance.
- Extend existing status with pending receipts and structured next step; keep human next_action/runbook compatibility.
- Reuse package/EDL/scenes/TakeLog/post hashes; no new database or orchestration service. One process owns each mutable scope.
- New delivery archives are immutable versioned directories under media/deliveries; the existing07_delivery.manifest path
  is the authoritative pointer, atomically updated only after verification. Shared resolver for report/gates/accept supports
  legacy delivery/MANIFEST.json. An open old master is never renamed/replaced; failed promotion preserves old pointer.
- Per-scene feasibility derives available speech/time from allocated generations, retaining per-generation checks and
  existing standalone defaults. No global relaxation of short-shot limits.
- Picture cache keys include media/trim/grade/reframe/local captions/style and transition neighbours. Absolute timeline and
  final mix are recalculated when durations change; unchanged local picture can be reused. Cards appear once.
- Preserve existing picture-lock/dirty-input gates. Graph values load via FFmpeg `-/filter_complex` on pinned9.0.1.

## Checks and rollout
Meaningful failing tests first; focused checks during work; independent review for risky integration; full/protected suite
on exact committed RC, not on every edit. Native CLI journey and the long benchmark are required, not just mocked PASS.
Fault cases: before/after submit; download before registration; repeated reconcile; changed plan; competing writers; every
finishing interruption; changed take/trim; open old master; corrupted/missing cached bytes; clean restore of both aspects.
Final films: >=95%in-send bind target,100%selected-take lineage,0unintended duplicate sends/overspend/unresolved sends,
all gatesPASS, hash-bound Owner acceptance. Report first-pass acceptance, elapsed time, costs and forecast deviation separately.

## Execution checkpoint
Initial implementation tranche180minutes; no progress after2attempts changes diagnosis. Main owns CLI/integration/status.
Isolated rendering worker may own post/edit/versions/cache files only; no overlapping writes or source-policy changes.
Exact progress/evidence/next action live in docs/drama/STATUS.md and canonical operating status, not agent memory.
