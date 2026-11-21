# AFP ↔ Muse lane contract (S5, wrapped Muse)

Status: **AGREED v8 (2026-11-21, Codex ACCEPT)** — frozen P1 contract; any change needs both TLs + one scoped Codex round. History:
- v2 = AFP TL review items 1-9 + the Muse finding on `accounts.json`.
- v3 = Codex review of v2 (REJECT, 11 findings).
- v4 = Codex review of v3 (REJECT: v2 #1, #2, #4, #6-#11 CLOSED; #3 and #5 OPEN; 6 new defects) + AFP TL
  answers to §15.3.
  - Muse share (v3 review): #1 (closes #5), #2 (closes #3), #5, #6.
  - AFP share: #3 (architecture enum, done in AFP commit 724f0833) and #4 (incarnation). Their Muse side is marked
    **AFP TL**.
- v5 = Codex review of v4 (REJECT: v3 #1, #3, #4, #6 and v2 #5 CLOSED; v3 #2, v3 #5 and v2 #3 OPEN; 3 new High) +
  AFP TL decisions:
  - v4 #1: machine-wide pending-stop marker (§11 halt).
  - v4 #2: durable standalone obligations registry (§6, §11 allocator).
  - v4 #3: proofs 1 and 3 become committed, fenced broker settlements (§0, §5, §9, §11).
- v6 = Codex review of v5 (REJECT: proof 3 CLOSED; remaining: the standalone edge + the pending-stop failure path)
  + AFP TL decisions:
  - v5 #1: `HALT_PENDING_UNWRITTEN` enforced by the supervisor.
  - v5 #2: obligations bootstrap.
  - v5 #3: one obligation per child.
  - v5 #4: fencing by owner process identity.
  - v5 #5: clear semantics.
- v7 = Codex review of v6 (REJECT: bootstrap, per-child obligations and pending-clear CLOSED; 4 left) + AFP TL
  decisions:
  - v6 #1: send-stop kernel event, set first.
  - v6 #2: `ABANDONED` latch + cancel/join.
  - v6 #3: Windows process fencing.
  - v6 #4: per-incident unwritten flags.
- **v8 = P1 SCOPE FREEZE** (Owner decision via AFP TL, 2026-11-21: "Đồng ý, chốt gọn"). v7 was not sent to Codex.
  - **P1 = single mode.** While Film Studio lanes are in use, the broker is the only allocator. Standalone real-send
    refuses while `allocator_owner.json` says `afp-broker`. Going back to standalone = Owner-run
    `afp-film broker allocator-release` (§11).
  - Moved, text kept, to **Appendix M (M3 backlog, NOT in P1)**: allocator transfer protocol,
    `muse_obligations.json` (bootstrap, per-child obligations, ABANDONED latch), Windows process fencing, standalone
    lease registration under the halt lock, `halt_pending_unwritten/` flags, the `Local\FilmStudio-SendStop` event
    and the session-id check.
  - Kept in P1 (all already reviewed and CLOSED by Codex): §0 custody + the 3 committed NOT_SENT proofs, the film
    ledger before Enter, per-child RESULT, no implicit login, token on stdin + `incarnation_id`, the `child_keys[]`
    batch check, `settle_not_sent`, rebind after settled + fenced, `--no-ui-sync`, the accounts lock, no
    `src.unlink()`, the halt-file lock boundary and the `halt_pending/` marker.
  - Accepted residual (AFP TL): lock timeout AND marker write failure (§11).
  - **Review stop rule:** the next Codex round reviews v8 only. ACCEPT = no High finding inside P1 scope. Mediums go
    to Appendix M unless they are one-line text fixes. At most 2 more rounds.

Owners: Muse Tech Lead (this file), AFP Tech Lead (review, then copy into `AFP-stable/docs/production/muse/`).
Product name after M3: **Film Studio**.

Decisions D1-D12 were agreed between the two Tech Leads on 2026-11-20/21. Code facts below cite `D:\Muse` at the
round-14 tree. Round 15 (stop-all) changes the halt file location and is marked **R15**.

Legend:
- **EXISTS** = behaviour in Muse today.
- **NEW** = Muse code still to write. Round A = input side, Round B = bridge. Each round = one Codex review + a B14
  re-run + the r6-r15 rule tests unchanged.
- **PRE-TAG** = must land before the first tag `muse-v1.0-r15`.
- **S1** = AFP broker work that Muse depends on.

## 0. Custody rule (applies to every section)

A child is **NOT_SENT** only when it is `NOT_SENT_PROVEN`. There are exactly three proofs:

Every proof is a **committed broker transaction** that leaves the child terminal NOT_SENT and **fenced**: any later
check of that child is refused. A NOT_SENT read, observation or ledger absence on its own proves nothing.

1. **The broker refused the batch check with `NOT_SENT_PROVEN`.** In that same txn the broker moved the children
   from PREPARING to terminal NOT_SENT and fenced them, so the lane can never re-check them (S1).
2. **The original lane incarnation proved it did not press Enter.** The lane:
   - has `enter_issued == False` in memory;
   - wrote RESOLVED / NOT_SENT in both ledgers;
   - had the broker accept `mark(state=NOT_SENT, reason=ENTER_NOT_ISSUED)` from the same lease, token, epoch and
     `incarnation_id` that made the check (§11). The broker terminalizes and fences the child in that txn.
3. **Atomic conditional settlement: `settle_not_sent(child_key, evidence)` committed** (S1, §11). It is used for
   reconciliation when there is no lane to ask, e.g. a valid film-ledger read shows no attempt. In one txn the
   broker:
   - if the child is still PREPARING → moves it to terminal NOT_SENT and fences it;
   - if it is SUBMITTING (a send won the race) → refuses, and the child stays AMBIGUOUS / HELD.

   Only after that commit may any ledger show NOT_SENT_PROVEN and `fenced: true`.

A missing, unreadable or invalid ledger never establishes NOT_SENT. Everything that is neither NOT_SENT_PROVEN nor
an exact, identity-bound RESULT or proven terminal failure is **AMBIGUOUS**, and the account stays **HELD** until
it is reconciled. That covers:
- timeouts, lost replies, and refusals that may follow a committed SUBMITTING;
- crashes and restarted lanes;
- missing or contradictory evidence;
- design changes.

No Muse code path settles custody on its own in lane mode.

## 1. Principle

AFP is the brain and the single allocator. Muse is a pinned executor that AFP calls through files and CLI. Muse's
send path, ledger, recovery and integrity code is **wrapped, never ported or rewritten** (non-regression rule,
STUDIO_ARCHITECTURE §11). Changes to Muse are input/selection changes plus the lane-mode restrictions listed here
(D2). Every lane-mode restriction is gated on `--batch-request`. Standalone behaviour stays as it is, except where
a row below says so.

The only Muse entry point a lane may call for real sends is `python -m muse_studio.pool_runner`. AFP never uses the
web UI render worker, `cli keyframes` or `autoprod`; after R15 those delegate to the pool engine or refuse.

## 2. Ownership and boundary (D12)

| AFP owns | Muse owns (pinned tools) |
|---|---|
| intake, brief, story, treatment, beats, story bible (Gates 1-3, interaction contract, off-frame protection) | `cli compile` (screenplay compiler + staging), keyframe composition |
| approvals and gates (signed `agent:film-<id>`), defects registry, review | stills and video generation through `pool_runner` lanes |
| custody, job journal, leases, halt, reservations, allocator claim and its transfer (broker) | FilmQC + `quality_score` (tool), `qc-audit` selection |
| take log (AFP `takes/`, copies with sha + receipt), UI projection after intake | audio, `assemble`, `deliver` (kept on Muse for P1 so output matches P0) |

**Working store.** The Muse project dir sits at a short path, `C:\film-work\<film>` (MAX_PATH 260). The AFP package
`films/<id>` records that path and the pinned Muse tag.

**Boundary input.** AFP writes `beats.json`, `story_bible.json` and the SRT (the B14 input set) into the Muse
project.

**Schemas.** The Muse loaders are the contract. **NEW (Round A):** one schema file per input,
`docs/afp_muse_contract_examples/*.schema.json`, generated from the loaders and checked by a test that loads B14.

## 3. Units (D1)

- **Lane** = one OS process bound to exactly one account. The broker never runs two lanes on one account.
- **Lane incarnation** = one start of a lane process. At start the lane generates a random `incarnation_id` and
  keeps it in memory. A restarted or replacement process is a new incarnation (§11).
- **Wave** = one atomic broker admission (`wave_id`), with one batch per lane per wave. A video batch holds up to
  6 slots; a stills batch up to 4.
- **Capacity per wave** = usable accounts × 6 videos (or × 4 stills). Today: 3 READY accounts → 18.
- **Take identity** = (film, shot_id, shot_version, take_index) (**AFP TL #1**).
  - It is unique for the life of the film, independently of any budget cap (Muse is uncapped).
  - Every identity field is required.
  - One identity has one or more **attempts** (batch_id + request_id). A new attempt is allowed only by the
    rebind rule (§5).
  - Two takes of the same shot version never share a batch. The broker AND pool_runner both enforce this (refuse).

## 4. Dependencies between jobs (D11)

**EXISTS:** nothing is chained inside a video batch.
- Each video request carries `first_frame` (the shot's own keyframe) and `references` (anchors/turnarounds).
- `last_frame` is always `None` (`core/batch_packager.py:250`).
- The engine never uses one shot's output as another shot's input.

Stage-level dependencies the broker must order. A job is admitted only when its inputs are accepted and frozen.

1. Character anchors → turnarounds (`keyframe_composer.plan_missing_character_turnarounds`, :75; anchors :209).
2. Anchors + location plates (:250) → shot keyframes. Multi-character keyframes use anchors and plates as refs.
3. Accepted keyframe (Owner/delegated approval of the contact sheet) → that shot's video takes.
4. Accepted takes of all shots → `qc-audit` selection → `assemble` → `deliver`.

There is no shot-to-shot chaining today. If one is added later (e.g. last-frame continuity):
- it must declare the dependency in `batch_request.json` (`depends_on`);
- the broker must keep the chained shot out of its predecessor's wave.

## 5. Job dir, `batch_request.json` and the film ledger (D2, D3) — NEW (Round A)

Per batch the broker freezes `C:\film-work\<film>\jobs\<job_dir>\`, where `<job_dir>` is AFP's 12-hex job id:

```
jobs/<job_dir>/
  batch_request.json      # frozen by AFP, read-only for Muse; holds NO capability
  shots_manifest.json     # subset: only the shots in this batch (Muse schema)
  assets/keyframes/...    # frozen copies of the first frames + references named in the request
  render_fingerprints.json# frozen input digests (same function as today, _render_fingerprint)
```

`batch_request.json`:

```json
{
  "contract": "afp-muse-lane/1",
  "film_id": "<afp film id>",
  "wave_id": "<broker admission id>",
  "batch_id": "<unique, = job_dir>",
  "kind": "video | stills",
  "account_id": "acc_xxxxxxxx",
  "lease": {"lease_key": "...", "epoch": 7},
  "muse_tag": "muse-v1.0-r15",
  "quality": "max",
  "slots": [
    {"slot_id": "shot_01", "child_key": "...", "shot_id": "S012", "shot_version": 3, "take_index": 1,
     "input_digest": "<sha256 = render fingerprint>", "request_id": "<uuid>", "depends_on": [],
     "rebind_of": null}
  ]
}
```

`rebind_of` is null for a first attempt, or `{"batch_id", "request_id"}` of the settled attempt it replaces.

### Lease token (#9, AFP TL v3 #4)

- **Delivery.** `lease_token` is not in any file. The supervisor passes it to pool_runner once, through the inherited
  **stdin pipe**, as one JSON line `{"lease_token": "..."}`, then drops its own copy.
- **In the lane.** pool_runner reads it once at start-up and keeps it in memory only. Lane mode refuses to start
  without it (nothing sent, NOT_SENT_PROVEN).
- **Calls to the broker.** The lane passes the token to the broker CLI on that CLI's stdin, never in argv. When the
  broker API is importable, it calls it in-process.
- **Never stored.** The token never reaches argv, environment, job dir, film dir, data dir, `lane_result.json`,
  receipts, ledgers, logs, exception text, archives or projections. Chromium child processes do not inherit the
  pipe.
- **Issued once (S1).** The broker issues the token once and acquire replay no longer returns it. A replacement
  process never receives the authority of the original incarnation (§11).
- **Test.** After a normal completion AND after `kill -9` mid-run, search the job dir, film dir, data dir and logs
  for the token.

### Quality

- `quality: "max"` (Owner decision): the relay text asks the Muse agent for the highest resolution and best model it
  offers. **NEW:** Muse code sets neither today.
- Evidence: each slot's actual width, height, fps and duration (ffprobe) go into `lane_result.json`.
- If Muse ignores the request, that is recorded, not treated as a failure.

### Job dir helper

**NEW:** `python -m muse_studio.cli job-dir <film_project> <batch_request.json>` builds the job dir.
- It is deterministic and sends nothing.
- It freezes the manifest subset, first frames, references and `render_fingerprints.json` from the film project.
- Muse keeps its schema knowledge; AFP only calls the helper.

### Command (lane mode)

```
python -m muse_studio.pool_runner videos|keyframes <job_dir> --batch-request <job_dir>/batch_request.json \
       --film-project C:\film-work\<film> --account <id> --max-rounds 1        # token on stdin
```

- **Failover OFF.** `--account` (exactly one) switches failover off.
  - Today failover re-queues a not-sent batch to a standby account (`parallel_pool_engine.py` videos :1228 `_FO`,
    keyframes :583; line numbers move with R15).
  - In lane mode a quota/login failure before Enter ends the child as NOT_SENT_PROVEN, and the broker reassigns it
    (rebind, below).
  - A submitted child never moves account.
  - Standalone defaults stay unchanged.
- **Exact slots.** pool_runner sends exactly the slots in the request and does no planning of its own. It refuses:
  - a request that puts two takes of one shot version in the batch;
  - a request whose `input_digest` differs from the frozen fingerprint (→ STALE_INPUT, nothing sent).
- **`--no-ui-sync` forced (#10).** Lane mode refuses `--ui-sync`, so `sync_project_to_web_ui` never runs from a lane
  (`parallel_pool_engine.py:1366-1369`, `cli.py:219-239`, `:295`). Intake does the film's UI projection once (§7).
- **Lock (D3).** The engine holds a project-wide OS `SessionLock` for the whole run (`parallel_pool_engine.py:614`
  keyframes, `:871` videos; lock impl `core/autoprod_orchestrator.py:96`). Running pool_runner on the per-batch job
  dir makes that lock per batch, so lanes of one film run in parallel. The lock itself does not change.

### Film ledger: published before Enter (CRITICAL, v2 #2)

The job-dir ledgers (`unconfirmed_submissions.json`, `unconfirmed_keyframes.json`, EXISTS) stay. Across job dirs
the authority is a **NEW** film-level ledger:
- file `C:\film-work\<film>\film_send_ledger.json`;
- guarded by an OS byte-range lock on `C:\film-work\<film>\.film_ledger.lock` (same lock primitive as SessionLock);
- no broker call is ever made while this lock is held.

Before Enter, the lane runs one locked check-and-record transaction for the whole batch (all slots or none):

1. **Read the film ledger.** An unreadable or invalid file refuses the batch with reason `FILM_LEDGER_UNREADABLE`.
   This is NOT_SENT_PROVEN only because nothing was recorded and the broker check was never called.
2. **Refuse the batch (`BLOCKED_BY_FILM_LEDGER`)** if either holds:
   - a slot's take identity already exists, unless the slot is a valid **rebind** (below);
   - the same (shot_id, shot_version) has a blocking entry (PENDING_SEND, UNCONFIRMED, EXPIRED_NEEDS_RECONCILE,
     RESULT_CORRUPT, AMBIGUOUS) from a different `wave_id`.
3. **Otherwise record each slot as PENDING_SEND.** For each slot, append one attempt under its take identity:
   film_id, wave_id, batch_id, slot_id, child_key, request_id, shot_id, shot_version, take_index, account_id,
   input_digest, recorded_at. Then write tmp + fsync + `os.replace` and release the lock.

**Rebind (v3 #6).** A slot with `rebind_of` may reuse an existing take identity only when the identity's current
attempt:
- matches `rebind_of` (same batch_id and request_id);
- has status RESOLVED / NOT_SENT, settled by a committed broker settlement (§0 proof 1, 2 or 3);
- is marked `fenced: true`, written only after that commit (the broker fenced the old attempt);
- has no earlier attempt that is not settled NOT_SENT and fenced in the same way.

The new attempt carries a fresh batch_id and request_id. The old attempt stays in the identity's history, and no
second identity is created. Any other reuse is refused. The broker applies the same rule at admission (S1).

**After the record.**
- The job-dir ledger PENDING_SEND is written after the film-ledger record, as today.
- The lane updates its own attempts under the same lock, keyed by (batch_id, slot_id, request_id): UNCONFIRMED
  after Enter, RESOLVED / NOT_SENT under §0 proof 2, per-child RESULT per §10.
- Intake updates attempts and never creates one. An attempt missing at intake is a contradiction → AMBIGUOUS +
  alarm.
- A lane that dies after step 3 leaves PENDING_SEND visible to every other job dir, so a later wave for that shot
  version is refused before intake runs.
- A crash between this record and the broker check stays AMBIGUOUS. The two are deliberately separate transactions.
- Belt and braces: the broker applies the cross-wave block at admission (**AFP TL #1**). Either refusal is enough.

### `lane_result.json`

**NEW:** pool_runner writes `<job_dir>/lane_result.json`. Today the result dict is only printed to stdout
(`pool_runner.py:194`, `:217`). The file has the same keys as today's result plus a per-child `children[]` list
(§8, §10).

## 6. Shared state written outside the job dir (CRITICAL, D3 consequence)

Per-batch job dirs make the project lock per batch, but N lane processes still share global state. In lane mode
the rows below are the only paths a lane may write outside its job dir; any other write is a defect.

Test: snapshot the data dir, `PROJECTS_DIR`, the film dir and the AFP state dir before and after a 3-lane simulate
wave. Only the rows below may differ.

**`data/accounts.json`** (credential store: status, last_used, total_rendered, usage_info, cookie write-back)
- Writers today: `core/account_manager.py:156` `_save_all`, UI account edits, headless cookie write-back.
- Today:
  - in-process `RLock` + unique tmp + `os.replace`, with **no cross-process lock** around the read-modify-write;
  - `_read_all` (:147) returns `[]` on ANY read error, e.g. a Windows sharing violation during another process's
    replace, and a later save then writes that empty list back.
- Required:
  - an OS lock on `data/accounts.lock`, held across the **whole** reload → mutate → replace, for **every** writer
    (engine, UI, cookie write-back, relogin);
  - `_read_all` raises instead of returning `[]` on a non-empty unreadable file;
  - `os.replace` with retry;
  - never write fewer accounts than were read, unless deleting explicitly.
- Test: 3 lanes + a UI edit in parallel; the store stays valid JSON and no account or field is lost.
- When: a Muse safety fix ahead of Round A. It is also a live risk for standalone multi-lane production today.

**`data/profiles/<account>/`** (Chromium profile)
- Writer: the headless client. Today: one lane per account (D1).
- Required: exclusive profile claim (STUDIO_ARCHITECTURE §9 M9), refused if busy.

**`data/lane_leases.json`**
- Writer: `core/lane_leases.py:206`. Today: unique tmp + replace-with-retry, and expired records are pruned
  (`core/lane_leases.py:220-229`).
- P1: a lane never writes it. Standalone keeps today's behaviour, and only runs when the broker is not the allocator
  (§11). Standalone lease registration under the halt lock is in Appendix M.

**`<AFP_STATE_DIR>/halt_pending/<lane_id>-<incarnation_id>.json`** (NEW; machine-wide pending stop)
- Written by a Muse lane that cannot get the halt-file lock to publish a halt (§11).
- Create-exclusive + fsync, lock-free by design. No secrets: provider, account_id, reason, ts.
- Removed only by the Owner halt-clear (§11).

**Muse halt file** (`core/send_halt.py`)
- Today: per project. R15: machine-wide, `MUSE_HALT_FILE`.
- Required: written only under the shared halt-file lock (§11).

**`film_send_ledger.json`** (NEW)
- Writers: the lane (pre-Enter record + its own updates) and intake (updates only).
- Required: under `.film_ledger.lock` (§5).

**`PROJECTS_DIR/.../project.json` + media** (UI projection)
- Writer today: `sync_project_to_web_ui`, on every default video run.
- Required: never written by a lane (`--no-ui-sync` forced); intake projects once (§7).

**`allocator_owner.json`** (AFP state dir)
- Muse never writes it. The broker bootstrap sets it to `afp-broker`; `allocator-release` removes it (§11).

**Lock order (AFP TL, Codex-checked, no cycle).**
- **Broker side.** Broker txn (`BEGIN IMMEDIATE`) → halt-file lock, which is always the innermost lock.
  - The broker `check` takes the halt-file lock inside its txn and holds it through the commit of SUBMITTING.
  - Under that lock it reads the AFP halt, `MUSE_HALT_FILE`, the `halt_pending/` dir and `allocator_owner.json`.
- **Muse side.** Muse's own locks nest only as halt-file → film ledger → accounts. In P1 each is taken alone.
- **Rule.** Muse never calls the broker (CLI or API) and never waits on a broker txn while holding ANY Muse lock
  (halt-file, film ledger, accounts).

## 7. Intake (D3b) — AFP side (S2-lite), Muse provides the files

The Muse project is on `C:` and the AFP package is on `D:`. A rename cannot cross volumes, so there are two staging
dirs, one per destination volume.

1. **Copy and verify (no lock).** Copy these from the job dir into both `<muse film>/.staging/<job_dir>/` and
   `<afp package>/.staging/<job_dir>/`:
   - `verified_clips/`, the `BATCHES_V2/<batch>/` receipts, `render_fingerprints.json`, `integrity_failed.json`;
   - `lane_result.json` and the job-dir ledger entries.

   Verify every sha256 against its receipt in each copy.
2. **Commit (film ledger lock; short, no long I/O, no broker call).**
   - Atomic renames from each `.staging/` into its destination: `BATCHES_V2/` and per-take clips on the Muse side,
     AFP `takes/` on the AFP side.
   - **Update** the film-ledger attempts that the lane published before Enter (§5). Intake never creates one.
   - Update the take log.
3. **QC and projection.** `qc-audit` runs on the film project (D4). Then intake runs the UI projection once
   (`sync_project_to_web_ui` on the film project); this is the only projection writer in lane mode.
4. **Halt.** If the lane exited 4, or the job dir holds `muse_halt.json`, or `lane_result.json` says
   `halt_publication: PENDING`:
   - intake sets the AFP halt;
   - for PENDING, intake also resumes the Muse halt publication under the halt-file lock (§11). The machine-wide
     pending-stop marker keeps every lane stopped meanwhile.

## 8. Output files (EXISTS unless marked)

**`lane_result.json`** (**NEW**; stdout only today) — job dir
- `status`: COMPLETED / HALTED / BLOCKED_NO_ACCOUNTS / NEEDS_LOGIN / STALE_INPUT / REFUSED / other.
- `muse_tag`, `muse_commit`, `incarnation_id` (an audit field; it grants nothing without the token), and
  `halt_publication`: `PUBLISHED` / `PENDING` / null.
- `children[{slot_id, child_key, request_id, custody, reason, evidence}]`, where `custody` ∈ NOT_SENT_PROVEN /
  RESULT / FAILED_TERMINAL / AMBIGUOUS.
- Today's keys (`parallel_pool_engine.py` ~:1380-1413): `passed_count`, `remaining_shot_ids`,
  `failed_shots[{shot_id, reason, defects}]`, `sends_by_shot`, `takes_by_shot`, `submitted_unconfirmed_shot_ids`,
  `unconfirmed_submissions`, `unconfirmed_expired`, `unconfirmed_released`, `unconfirmed_ttl_min`, `batch_errors`,
  `halted`.
- No lease token.

**`film_send_ledger.json`** (**NEW**) — film project
- One entry per take identity, holding `attempts[]` with the §5 fields + `status`, `reason`, `result_eligible`,
  `fenced`, history.

**`halt_pending/<lane_id>-<incarnation_id>.json`** (**NEW**) — `<AFP_STATE_DIR>`, machine-wide
- Pending-stop marker: this Muse halt is not yet published under the lock, but every broker check/admission and
  every lane pre-Enter gate already refuses while it exists (§11).

(`muse_obligations.json` and `halt_pending_unwritten/` are Appendix M, NOT in P1.)

**`unconfirmed_submissions.json`** — job dir
- Entries: `shot_id`, `batch_id`, `take`, `submitted_at`, `submitted_epoch`, `fingerprint`, `status`, `reason`,
  `age_min`, history (`parallel_pool_engine.py` ~:1005-1015).

**`unconfirmed_keyframes.json`** — job dir
- Keyframe ledger, same state model (`parallel_pool_engine.py:83`, :86).

**`muse_halt.json`**
- Location: per project today (`core/send_halt.py:13-51`). R15: one machine-wide file, `MUSE_HALT_FILE` override.
- Fields: `reason` BLOCKED, `account_id`, `batch_id`, `detail`, `clear_with`.

**`BATCHES_V2/<batch>/render_fingerprints.json`** — job dir
- shot_id → input digest at send time.

**`BATCHES_V2/<batch>/integrity_failed.json` + `integrity_failed/`** — job dir
- Clips whose sha256 ≠ receipt, or (lane mode) clips with no receipt sha.
- Excluded from selection, never deleted (§10, #11).

**`<batch>_result.zip` receipts** — job dir
- Per slot `<slot>_receipt.json`, plus `batch_receipt.json`.
- Fields: batch_id, shot_id, slot_id, request_id, sha256.

**`verified_clips/<sid>.mp4`** — project
- Canonical clip of the selected take.

**`qc_audit_report.json`** — film project
- `per_shot_qc.<sid>`: `verdict`, `defect_code`, `defects`, `take`, `clip_path`, `batch_id`, `fingerprint`,
  `sha256`, `metrics.quality_score`, `candidates`, `selected_by`.
- Top level: `passed_clips`, `failed_or_missing`.

Redacted examples: `docs/afp_muse_contract_examples/` (**NEW**, written with Round A from a B14 simulate run).

## 9. Exit codes (steer only; files are the truth)

`pool_runner` exit codes (`pool_runner.py` ~:170-228):

| Exit | Meaning |
|---|---|
| `0` | COMPLETED |
| `1` | incomplete / other error |
| `2` | BLOCKED_NO_ACCOUNTS |
| `3` | SESSION_CONFLICT (project lock held) |
| `4` | HALTED (stop-all, `_halted_exit`); also on `HALT_PUBLICATION_PENDING` |

`cli qc-audit` and `assemble` exit 0 even with rejected shots: read `qc_audit_report.json`, not the exit code.

The broker reads custody from `lane_result.json.children[]` and checks it against the film ledger and its own child
states. The exit code only steers. Rules (§0):

- **No `lane_result.json`** (crash, kill, power loss):
  - every slot with a film-ledger attempt is AMBIGUOUS;
  - a slot with no attempt (after a valid, authoritative ledger read) becomes NOT_SENT only when
    `settle_not_sent` commits (§0 proof 3); if the broker refuses because the child is SUBMITTING, it is
    AMBIGUOUS.
- **Film ledger unreadable or invalid at reconciliation** → every child of the batch is AMBIGUOUS until a
  `settle_not_sent` commits for it. Ledger absence alone is never a reason to settle.
- **Lane says NOT_SENT_PROVEN** → accepted only when the broker shows the matching committed, fenced settlement
  (§0 proof 1 or 2).
- **Child disagreement.** A child whose `custody` is missing, or disagrees with the film ledger or with the
  broker's state (e.g. the lane says NOT_SENT_PROVEN but the broker holds SUBMITTING with no accepted
  ENTER_NOT_ISSUED mark) → AMBIGUOUS.
- **Exit 2 and 3.** Today's code raises them before the pre-Enter record (no account granted / lock not acquired).
  Until a Round A test proves "exit 2/3 ⇒ no film-ledger attempt", the rules above apply.

## 10. State mapping Muse → AFP (§9 of STUDIO_ARCHITECTURE)

| Muse ledger / file state | AFP job state | Muse name kept as |
|---|---|---|
| one of the three §0 proofs, committed and fenced by the broker | NOT_SENT (NOT_SENT_PROVEN; broker may rebind, §5) | reason |
| no entry without a committed settlement; ledger unreadable; broker SUBMITTING; `settle_not_sent` refused; contradictory evidence | AMBIGUOUS (HELD) | reason code |
| PENDING_SEND, UNCONFIRMED, EXPIRED_NEEDS_RECONCILE | AMBIGUOUS (account HELD) | reason code |
| RESULT_CORRUPT | AMBIGUOUS + INTEGRITY_FAILED evidence | reason code |
| per-child RESULT (identity-bound, rule #7 below) | RESULT (go to intake) | reason |
| slot receipt with exact identity and an explicit failure status | FAILED_TERMINAL (settled; another take needs a new take_index) | reason |
| shot in request, no slot in result (NO_RESULT_IN_BATCH); receipt missing, malformed, unknown slot, duplicate slot, identity or sha mismatch | AMBIGUOUS (HELD); evidence only, **never** resend permission | reason code |
| design changed or shot removed while a child is outstanding (#6) | stays AMBIGUOUS (HELD); old result marked `result_eligible: false` | STALE_DESIGN / SHOT_REMOVED as evidence |
| RELEASED (any reason) | only via the broker's reconcile/Owner release; Muse never produces it in lane mode | reason |
| clip in `integrity_failed.json` | INTEGRITY_FAILED (every reader honours it) | — |
| `qc-audit` STALE_RENDER | STALE_INPUT | defect code |
| `qc-audit` verdict + `defect_code` | AFP defect code via registry; unknown → STOP_UNKNOWN_DEFECT | detector version recorded (D4) |

Lane QC per take is advisory. Film-level `qc-audit` after intake is authoritative for selection (D4).

Muse code changes behind this table. They apply in lane mode only, and standalone is unchanged, unless an item says
otherwise.

- **#6: no auto-release (Round A).**
  - Today outstanding entries are released automatically as STALE_DESIGN / SHOT_REMOVED
    (`parallel_pool_engine.py:929-945`). Lane mode disables this.
  - The entry keeps its blocking status and gains `result_eligible: false`.
  - A new shot version is a different take identity and is not blocked by it.
  - The account stays HELD until the broker reconciles the old child.
- **#7: per-child RESULT (Round A).**
  - Today a partial ZIP marks the whole chunk RESULT_RECEIVED (`parallel_pool_engine.py:1332-1334`).
  - Today the unpacker accepts a large-enough clip without a receipt sha or an exact request-id binding
    (`batch_packager.py:567-568`, `:611-636`).
  - In lane mode a child is RESULT only when its slot receipt carries the exact batch_id + slot_id + request_id
    from the request AND the clip sha256 equals the receipt sha256.
  - Ledger status is set per slot, never per chunk. Anything else follows the AMBIGUOUS rows above.
- **#11: never delete (PRE-TAG, all modes).**
  - Remove the `src.unlink()` fallback taken when the quarantine rename fails (`batch_packager.py:580-589`).
  - On failure the file stays where it is and is listed in `integrity_failed.json`; every reader excludes it.
  - If that exclusion cannot be persisted, the run STOPs (status `INTEGRITY_UNPERSISTED`, children AMBIGUOUS).
  - Test: the quarantine rename fails (file held open) → the file still exists, is listed, and is never selected.

## 11. Lease, halt, allocator and account bridge (D5, D6, D7) — NEW (Round B)

S1 broker API (`agentic/broker_api.py`; may shift slightly in S1 Codex round 7):
- `acquire(account_id, lease_key, children, unit, provider)` — issues the token once; replay never returns it (S1).
- `check_before_enter(lease_key, lease_token, child_keys[], epoch, incarnation_id)` — atomic: every child goes
  SUBMITTING, or none. A `NOT_SENT_PROVEN` refusal terminalizes and fences every child in the same txn.
- `settle_not_sent(child_key, evidence)` — conditional, atomic: PREPARING → terminal NOT_SENT + fenced;
  SUBMITTING → refused (stays AMBIGUOUS / HELD).
- `mark(lease_key, lease_token, child_key, state, spent, reason, incarnation_id)`
- `release(lease_key, lease_token)`
- `settle(lease_key, spent, child_key)`
- `halt(provider, account_id, reason, kind)`
- `halt_file_lock_path()` + a lock context manager.

CLI: `afp-film broker acquire|check|mark|release|settle|settle-not-sent|halt|status|allocator-claim|allocator-release|login-check|login-result|claim`
- Output is JSON.
- `check` takes a repeatable `--child` and `--incarnation <id>`; the token goes on stdin.
- `claim` is the profile claim. `allocator-claim` is the single-mode bootstrap that writes `allocator_owner.json` (§11 below).
- Exit codes: `0` ok · `1` refused · `2` usage · `3` not found / token mismatch.
- `status` is read-only. `probe` is a quota write and is never used for liveness.

### One allocator in P1: single mode (D7, v8 scope freeze)

P1 has one mode. While Film Studio lanes are in use, the AFP broker is the only allocator.

- **Claim file.** `<AFP_STATE_DIR or ~/.afp>/allocator_owner.json` = `{"owner": "afp-broker", ...}`. The broker
  bootstrap writes it once. Muse never writes it and finds it through `AFP_STATE_DIR` (default `~/.afp`).
- **Lane mode** (`--batch-request`) runs only when that file says `afp-broker`. The broker also checks it inside every
  admission and every check, under the halt-file lock.
- **Standalone real-send refuses while the file exists and says `afp-broker`.** This covers `muse_studio.lane open`
  and `pool_runner` without `--batch-request`. It is one plain read at start, with no lock and nothing written:
  - file says `afp-broker` → refuse, reason `ALLOCATOR_IS_BROKER`, nothing sent, nothing written;
  - file exists but is unreadable or invalid → refuse, reason `ALLOCATOR_UNKNOWN`;
  - file absent → standalone runs as today.
  `--simulate` is not a real send and is never refused by this rule.
- **Going back to standalone.** The Owner runs `afp-film broker allocator-release`. The broker refuses it while any
  lease or unresolved child (PREPARING, SUBMITTING, AMBIGUOUS) exists in the broker. On success it removes the claim
  file. Standalone sends after that are protected by Muse's own ledgers (project ledgers, and the film ledger for a
  film that lanes touched), not by the broker.
- **Not in P1:** no transfer protocol, no epoch handshake, no standalone obligations. The full design is kept in
  Appendix M.

**Accepted gap (P1).** A standalone process that started before the bootstrap wrote the claim keeps running; it
read "absent" at start. Operator rule: stop every standalone Muse run before the bootstrap. The bootstrap command
prints this rule. Closing this gap mechanically is the Appendix M transfer protocol.

### Lane incarnation and ENTER_NOT_ISSUED (AFP TL v3 #4)

- **Start.** At start the lane generates a random `incarnation_id`, kept in memory, and passes it with its first
  check. The broker binds the checked children to that incarnation.
- **`enter_issued`.** The lane keeps an in-memory `enter_issued` flag. It is set to `True` immediately BEFORE the
  call that presses Enter or sends the message, and is never reset.
- **Claiming ENTER_NOT_ISSUED.** Only a lane with `enter_issued == False`, using the same lease_key, token, epoch and
  `incarnation_id` as the check, may call `mark(state=NOT_SENT, reason=ENTER_NOT_ISSUED)`. The lease must be
  neither released nor expired.
- **Replacements.** A restarted or replacement process is a new incarnation and can never clear existing SUBMITTING
  children. Those stay AMBIGUOUS until reconciled. The broker no longer returns the token on acquire replay, so a
  replacement cannot recover the original authority.

### Pre-Enter gate (v2 #4)

Per batch, in this order, with no Muse lock held during the broker call:
1. §5 film-ledger record; the lock is released afterwards.
2. Muse's own gate (R15: the Muse halt and the page state).
3. Broker batch check, `check_before_enter(child_keys[])`. Muse's pre-submit `lease_guard` makes this call
   (EXISTS: `headless_muse_client.py:265`, checked at :373). Muse Enter is one action per batch (one ZIP, one
   message), hence the all-or-nothing batch check.
4. Enter.

Outcomes of the check:

| Check outcome | Lane action |
|---|---|
| OK for every child | `enter_issued = True` → Enter → UNCONFIRMED in both ledgers → `mark(...)` per child |
| Refused with `NOT_SENT_PROVEN` (the broker already terminalized and fenced the children) | No Enter; RESOLVED / NOT_SENT + `fenced: true` in both ledgers |
| Anything else: timeout, lost reply, `ALREADY_SUBMITTING`, broker unreachable, malformed reply, token mismatch after a possible commit | No Enter; the lane stops the batch; attempts stay blocking with reason `BROKER_CHECK_UNCERTAIN`; children reported AMBIGUOUS. Only a committed `settle_not_sent` (§0 proof 3) may later turn them into NOT_SENT |
| Check OK, but Enter not issued (page error, auth expiry) | With `enter_issued == False`: RESOLVED / NOT_SENT, then `mark(NOT_SENT, ENTER_NOT_ISSUED)`. If that mark fails or is refused, the child is AMBIGUOUS until reconciled |

### Halt is one signal with one serialization boundary (D5, v3 #1, closes v2 #5)

**Stop signals every pre-Enter gate reads.** The gates are the broker check and admission (AFP, S1) and the Muse
lane gate (R15 gate). Each reads all of the following under the halt-file lock, and the broker holds that lock
through the commit of SUBMITTING. Any one present → refuse; any one unreadable → refuse.
1. the AFP halt;
2. `MUSE_HALT_FILE`;
3. the `<AFP_STATE_DIR>/halt_pending/` dir (any entry).

On any Muse block (CAPTCHA, verification, unusual activity), the lane first disables Enter in memory, then
publishes the halt as below. (The machine-wide kernel send-stop event and the per-incident unwritten flags are in
Appendix M, NOT in P1.)

**Publishing a Muse halt.** Muse publishes its halt only under the same lock: `halt_file_lock_path()` = `halt_path()
+ ".lock"`, a 1-byte OS lock, 60 s default timeout, taken via the S1 context manager.
1. Take the lock.
2. Write `muse_halt.json` (tmp + fsync + replace).
3. Release the lock.
4. Call broker `halt(provider="muse", account_id, reason, kind)` with no lock held.

So every check either committed before the publication (that send was legitimately admitted) or sees the halt.

**Lock timeout.** If the lock cannot be taken, Muse **never** writes the authoritative halt without it. The status
is `HALT_PUBLICATION_PENDING`:
1. Enter is already disabled in memory (above).
2. **Immediately**, before any retry, the lane latches the machine-wide pending stop: it writes
   `<AFP_STATE_DIR>/halt_pending/<lane_id>-<incarnation_id>.json` (provider, account_id, reason, ts; no secrets).
   - The write is create-exclusive + fsync, and lock-free by design: the halt lock is exactly what it could not
     get.
   - From this point every broker check/admission and every lane pre-Enter gate refuses. They read the dir under
     the halt-file lock; an unreadable dir also refuses.
3. It keeps retrying the locked publication with backoff. On success it publishes, calls broker `halt` and exits 4
   with `halt_publication: PUBLISHED`. The pending marker stays.
4. After 15 min without success, it exits 4 with `halt_publication: PENDING`. Intake (§7.4) or the supervisor
   resumes the locked publication and reports the pending halt to the Owner; the marker keeps every gate refusing
   meanwhile.

**Residual (lock-timeout degraded mode).** A check that already holds the halt-file lock when the marker appears
may still commit. That is equivalent to a send admitted just before the halt.

**Accepted residual: lock timeout AND marker write failure (AFP TL, P1).** If the lane cannot take the halt lock AND
cannot write the pending marker (`HALT_PENDING_UNWRITTEN`):
- the lane stays alive refusing every send, keeps retrying the locked publication and the marker, and after the same
  15 min exits 4 with `HALT_PENDING_UNWRITTEN` in `lane_result.json` (earlier if either retry succeeds);
- on that exit, the AFP lane supervisor terminates every Muse lane on the machine and refuses new lane starts until
  a durable global halt is acknowledged;
- **the gap until the supervisor reacts is documented, not engineered away:** another lane may pass a check in that
  window. The Owner is told. The engineered fix (kernel event + per-incident flags) is in Appendix M.

**Broker failure.** If the broker `halt` call fails, the halt file stays and the lane exits 4; intake sets the AFP
halt.

**Clearing.** Clearing is Owner-only: one AFP command that also runs Muse `--clear-halt`. Nothing clears
automatically.
- **Without `--include-pending`,** `afp-film halt clear` refuses while any `halt_pending/` marker exists.
- **With `--include-pending` (v5 #5, AFP side),** the command:
  1. first PUBLISHES each pending marker into the authoritative halt history (`set_halt` from it);
  2. removes exactly those published marker ids;
  3. then clears the halts.

  It never bypasses publication, and it never removes a marker it did not publish.

**Standalone.** Without AFP, Muse uses its own R15 lock as today.

### No implicit login in lane mode (v2 #8, Round A)

- Lane mode disables the in-submit auto-login (`headless_muse_client.py:141-151`, `:333-342`), the unchecked-account
  verification and the OTP fallback.
- Auth expiry before Enter ends the batch as NOT_SENT_PROVEN (§0 proof 1 or 2) with status `NEEDS_LOGIN`. Control
  returns to the broker's separately throttled login path.
- Standalone keeps today's behaviour.

### Accounts (D6)

- `muse_studio/data/accounts.json` is the only credential store, read only inside Muse processes.
- **NEW probe:** `python -m muse_studio.lane accounts --json` → `[{"account_id", "status", "weekly_remaining_pct",
  "probed_at"}]`, with no other field.
- **NEW (M2):** `python -m muse_studio.lane relogin --account <id>`.
  - Invoked only by the broker, under the §9 throttle: 1 per 2 h; 2 failures → NEEDS_LOGIN; never inside submit;
    CAPTCHA → halt.
  - Until then, the Owner re-logs in through the Muse Studio UI.

## 12. Pinned runtime (D8)

- **Tag.** Each AFP job records `muse_tag`, and lanes run only a tagged tree. A Muse change = a new tag + a B14
  re-run.
- **Tree.** A clean, read-only worktree/checkout of the tag at a short path, e.g. `C:\film-work\_rt\muse-v1.0-r15`;
  never the dirty `D:\Muse` tree.
- **Data dir.** The live data dir (`accounts.json`, `profiles/`, `lane_leases.json`) is passed by **NEW**
  `MUSE_DATA_DIR` (today `core/config.py:5` derives `DATA_DIR` from the code location), so secrets never enter the
  tagged tree.
- **Check.** pool_runner records the tag and commit it actually ran from in `lane_result.json`, and refuses to run
  when they differ from `muse_tag` in the request.
- **Token.** The lease token never enters the pinned tree, the job dir or any archive (§5).
- **First commit.** Muse today is one baseline commit plus a dirty tree. Tagging needs an **Owner-approved** commit:
  - include `muse_studio/`, `.claude/skills`, `.agents`, `docs/`;
  - exclude film folders and secrets: `data/accounts.json`, `data/profiles/`, cookie/session files, `.env`, logs;
    add them to `.gitignore` first;
  - scan the staged tree for cookie/password patterns before tagging.
- **First tag:** `muse-v1.0-r15`, after stop-all passes Codex and the PRE-TAG items (§10 #11) are in.

## 13. Agent independence (D10)

- Lanes start detached: the CLI or a supervisor owns the process.
- The supervisor hands the token over once through the pipe and keeps no copy.
- A brain session dying (usage limit, crash) never kills a wave.
- Resume is safe through the film ledger and the job journal. A resumed or replacement lane is a new incarnation
  and never inherits ENTER_NOT_ISSUED authority (§11).

## 14. Acceptance (S5 / P1)

**B14 parity.** `D:\Muse\_director_review_B14_20261119`, copied to a short TEMP path: offline `--simulate` parity of
the whole chain through lanes + intake.

**Rule tests unchanged and green:** `test_review6_fixes.py`, `test_review7_fixes.py`, `test_review9_fixes.py`,
`test_review11_fixes.py`, `test_blocked_halt.py`, `test_stop_all_r14.py`, the round-15 tests.

**PRE-TAG test.** A quarantine rename failure keeps the file, lists it and never selects it; an unpersistable
exclusion STOPs.

**Round A tests**
- **Request handling.**
  - batch_request honoured exactly;
  - two takes of one shot version refused;
  - duplicate take identity refused unless it is a valid rebind;
  - stale digest → STALE_INPUT with no send;
  - failover off with `--account`;
  - two lanes of one film run in parallel;
  - `lane_result.json` written with `children[]`.
- **Film ledger.**
  - Job A records PENDING_SEND and is killed **before intake** → job B (other wave, same shot version) refused
    `BLOCKED_BY_FILM_LEDGER`, zero sends.
  - Two lanes recording at the same instant → exactly one attempt per take identity, no lost entry.
  - An unreadable film ledger → batch refused.
- **Rebind.**
  - A broker-settled, fenced NOT_SENT attempt + `rebind_of` matching → accepted; the old attempt stays in history;
    still one identity.
  - Rebind of an unfenced, AMBIGUOUS or non-matching attempt → refused.
- **Per-child RESULT.**
  - Partial ZIP → only matching slots RESULT, the rest AMBIGUOUS.
  - Clip without receipt sha, wrong request_id, duplicate or unknown slot → AMBIGUOUS.
  - NO_RESULT_IN_BATCH is never re-admitted.
- **Design change while outstanding** → the entry stays blocking with `result_eligible: false`; the account stays
  HELD.
- **Lane-mode restrictions.**
  - No auto-login / OTP path is reachable (stale session → NEEDS_LOGIN, NOT_SENT_PROVEN).
  - `--ui-sync` refused and `PROJECTS_DIR` untouched.
  - The write-set snapshot (§6) shows only allowed paths.
- **Accounts store.** 3 lanes + a UI edit keep `accounts.json` valid, with no account or field lost; a reader error
  never yields `[]`.
- **Lease token.** Missing on stdin → refused. After a normal completion AND after `kill -9` mid-run, no token in
  the job dir, film dir, data dir or logs; the token never appears in any argv.
- **Other.**
  - Exit 2/3 write no film-ledger attempt.
  - Tag mismatch → refused.
  - `cli job-dir` is deterministic (same input → byte-identical job dir) and sends nothing.
- **Reconciliation without `lane_result.json`.**
  - Film ledger deleted or unreadable + broker SUBMITTING → AMBIGUOUS, never NOT_SENT.
  - No attempt + a valid ledger read → NOT_SENT only after `settle_not_sent` commits; the ledger shows
    `fenced: true` only after that commit.

**Round B tests**
- **Settlement race (proof 3).**
  - Reconciliation calls `settle_not_sent` while the original lane resumes and checks the same child.
    - If the settlement commits first → the lane's check is refused (fenced) and nothing is sent.
    - If the check commits first → the settlement is refused and the child stays AMBIGUOUS.
- **Batch check.**
  - `NOT_SENT_PROVEN` before Enter → NOT_SENT; a re-check of the same children is refused (fenced).
  - Lost reply, timeout, `ALREADY_SUBMITTING` or unreachable broker → no Enter AND AMBIGUOUS.
  - The batch check is all-or-nothing.
- **Incarnation.**
  - The original incarnation with `enter_issued == False` → `mark(NOT_SENT, ENTER_NOT_ISSUED)` accepted.
  - The original with `enter_issued == True` cannot claim it.
  - A replacement lane (new incarnation, after the original crashed with SUBMITTING children) → its mark is
    refused; the children stay AMBIGUOUS.
  - Acquire replay returns no token.
- **Halt.**
  - Muse halt published between a lane's own gate and its broker commit → that send was either committed before
    the publication or refused.
  - Both write orders (Muse first / AFP first).
  - Broker unreachable → Muse halt file written under the lock, exit 4, intake sets the AFP halt.
  - Halt lock held past the timeout → NO halt file written without the lock; `HALT_PUBLICATION_PENDING`; the
    machine-wide `halt_pending/` marker written before the first retry; the lane sends nothing more; exit 4;
    intake resumes the locked publication.
  - Two lanes: A times out and latches the marker; B takes the lock between A's retries → B's check is refused,
    zero sends.
  - Unreadable `halt_pending/` dir → check and lane gate refuse.
  - Clear without `--include-pending` refuses while markers exist. With it, each marker is published into the halt
    history first and only those marker ids are removed.
  - Accepted residual: lock held AND marker dir not writable → the lane sends nothing more and exits 4
    `HALT_PENDING_UNWRITTEN`; the supervisor terminates every Muse lane and refuses new starts.
- **Allocator (single mode).**
  - Claim `afp-broker` → `lane open` and standalone real-send pool_runner refuse (`ALLOCATOR_IS_BROKER`) and write
    nothing; `--simulate` still runs.
  - Claim unreadable or invalid → standalone refuses (`ALLOCATOR_UNKNOWN`); lane mode refuses.
  - No claim file → lane mode refuses; standalone runs as today.
  - `allocator-release` refused while any broker lease or unresolved child exists; on success the claim is removed.
  - Muse never writes `allocator_owner.json`.
- **Other.** The probe JSON has no secret field. A Muse block sets both halts.

**Recovery drills**
- Kill the lane after Enter → no resend; the child is AMBIGUOUS, then reconciled.
- Kill the brain mid-film → a fresh session resumes from the journal with zero resends.

**P0 parity reference:** `C:\film-work\BLACK_PILOT_P0_20261120\P0_BASELINE.json` (per-stage timings, takes per
shot, QC verdicts, defects, quota per account).

## 15. Decided questions

1. **Thread URL capture** stays out of Round A/B. Without it, §9 F5 falls back to UNBINDABLE + account HELD.
2. **Job dirs** are built by the Muse `cli job-dir` helper (§5), not by AFP.
3. **AFP TL answers (2026-11-21):**
   - (a) The halt lock is `halt_path()+".lock"`, a 1-byte OS lock with a 60 s timeout, used via S1
     `halt_file_lock_path()` and its context manager. The lock order is broker txn → halt-file lock (innermost).
   - (b) `check_before_enter(child_keys[])` is atomic.
   - (c) `mark(NOT_SENT, ENTER_NOT_ISSUED)` is accepted only from the live original incarnation (§11).
   - (d) Only `NOT_SENT_PROVEN` is a proven refusal; the lane-side reason is `BROKER_CHECK_UNCERTAIN`.
4. **Allocator in P1 = single mode** (v8): bootstrap claim `afp-broker`, standalone refuses on one read,
   `allocator-release` to go back. The `allocator-transfer` verb and its protocol are Appendix M.
5. **Accepted residual** (AFP TL, v8): lock timeout AND marker write failure → stay alive refusing, exit 4,
   supervisor terminates every lane; the window until it reacts is documented (§11).
6. **Review stop rule** (v8): the next Codex round reviews v8 only. ACCEPT = no High finding inside P1 scope.
   Mediums go to Appendix M unless they are one-line text fixes. At most 2 more rounds.


## Codex findings → v7 location

v8 note: the tables below map findings to the v7 layout. Rows about the allocator transfer, standalone
obligations, the ABANDONED latch, process fencing, the send-stop event and the unwritten flags now point into
Appendix M (NOT in P1). In P1 those findings are answered by single mode (§11 "One allocator in P1") and the
accepted residual (§11 "Accepted residual").

v6 review (`codex_out_v6.md`; bootstrap, per-child obligations and pending-clear CLOSED):

| v6 # | Owner | Where in v7 |
|---|---|---|
| 1 (stop-all with no disk write) | Muse + AFP S1 item 15 | §11 "Stop signals" + "Send-stop event" (set first, held until durable, same-session rule), lock-timeout steps, "Marker write fails" + residual, §6, §14 |
| 2 (live NOT_SENT removal does not fence Enter) | Muse | §11 obligations: `ABANDONED` latch + cancel/join before removal, §14 |
| 3 (Windows fencing) | Muse | §11 Owner reconcile: retained handle, `GetProcessTimes`, UNKNOWN on inspection failure, confirmed exit incl. Chromium tree, §14 |
| 4 (fixed flag erases newer incident) | Muse + AFP S1 item 16 | §6 / §8 per-incident flags, §11 "Clearing", §14 |

## Codex findings → v6 location

v5 review (`codex_out_v5.md`; proof 3 CLOSED, lane-mode unknowns can no longer become RESULT or NOT_SENT, no lock
cycle):

| v5 # | Owner | Where in v6 |
|---|---|---|
| 1 (`HALT_PENDING_UNWRITTEN` loses stop-all) | Muse + AFP supervisor | §11 halt "Marker write fails" (supervisor-wide stop, standalone flag, stay-alive), §6, §8, §14 Round B halt |
| 2 (obligations bootstrap) | AFP S1 + Muse side | §11 "Registry bootstrap", transfer step 3, §6, §14 Round B allocator |
| 3 (standalone partial RESULT) | Muse | §11 one obligation per child + per-child removal (§10 #7 rule applied), §15.6, §14 |
| 4 (reconcile without fencing) | Muse | §11 owner process identity, removal rules, Owner reconcile only for a dead/terminated holder, §14 |
| 5 (pending clear semantics) | AFP | §11 "Clearing" (`--include-pending` publishes first, removes exact ids), §14 |

## Codex findings → v5 location

v4 review (`codex_out_v4.md`):

| v4 # | Owner | Where in v5 |
|---|---|---|
| 1 (pending halt does not stop other lanes) | Muse + AFP S1 | §11 halt (machine-wide `halt_pending/`, residual), §6, §7.4, §8, §14 Round B halt |
| 2 (standalone registration not durable; closes v2 #3 / v3 #2) | Muse + AFP S1 read | §6 `muse_obligations.json`, §11 allocator obligations + transfer step 3, §14 Round B allocator |
| 3 (proof 3 read-to-settlement race; closes v3 #5) | AFP S1 + Muse side | §0 all proofs committed + fenced, `settle_not_sent`, §5 rebind, §9, §10, §11 API/outcomes, §14 settlement race |

## Codex findings → v4 location

v3 review (`codex_out_v3.md`):

| v3 # | Owner | Where in v4 |
|---|---|---|
| 1 (closes v2 #5) | Muse | §11 halt (no unlocked publication, `HALT_PUBLICATION_PENDING`), §7.4, §8 (job-local marker replaced in v5 by the machine-wide `halt_pending/`), §14 Round B halt |
| 2 (closes v2 #3) | Muse + AFP S1 | §11 broker-owned transfer; Muse never writes the claim; §6; §14 Round B allocator |
| 3 | AFP | architecture §6 enum `afp-broker` (AFP commit 724f0833); §11 uses the same two values |
| 4 | AFP S1 + Muse side | §3 incarnation, §5 token issued once, §11 incarnation + ENTER_NOT_ISSUED, §13, §14 |
| 5 | Muse | §0 three proofs, §9 reconciliation rules, §10 rows 1-2, §14 Round A reconciliation |
| 6 | Muse | §3 attempts, §5 rebind rule + `rebind_of`, §14 Round A rebind |

v2 review: #1, #2, #4, #6-#11 CLOSED by Codex on v3. Their text is unchanged in v4, except the lock order (§6) and
the §0 proofs.
## Appendix M — M3 backlog (NOT in P1)

Everything below was designed and reviewed in v4-v7 and is **NOT in P1 scope** (v8 scope freeze). The text is kept
as it was in v7, so section references inside it (§6, §11, §14, S1 items 15/16) point to the v7 layout. Full v7
snapshot: `docs/AFP_MUSE_LANE_CONTRACT_v7_full.md`. Codex status at v6/v7: allocator bootstrap, per-child
obligations and pending-clear CLOSED; the send-stop event, ABANDONED latch, Windows fencing and per-incident flags
were written for v7 and never reviewed.

### M.1 Shared-state rows (v7 §6)

**`<AFP_STATE_DIR>/muse_obligations.json`** (NEW; path override `MUSE_OBLIGATIONS_FILE`)
- The durable registry of standalone children that block an allocator transfer (§11). There is one obligation per
  expected child.
- Created empty by the broker's `allocator-transfer --to muse-standalone` (with `muse_obligations_required`).
- Writers: standalone Muse appends and removes, under the halt-file lock.
- No secrets. Fields: account_id, project path, batch_id, slot_id, shot_id, take, request_id, created_at, status,
  and the owner {pid, process creation time, incarnation_id}.
- It is never pruned by TTL, heartbeat loss, close or GC.
- The broker only reads it, under the halt-file lock.

**`<AFP_STATE_DIR>/halt_pending_unwritten/<incident_id>.flag`** (NEW; lane and standalone; S1 item 16)
- Written (one per incident, create-exclusive) when a Muse process could not write its pending marker (§11).
- Every pre-Enter gate refuses while any flag exists or the dir is unreadable.
- Only the Owner halt-clear removes flags, and only the incident ids it published.

**Named kernel event `Local\FilmStudio-SendStop`** (NEW; no disk; S1 item 15)
- Set first by any Muse process on a block; the handle is held until a durable signal exists (§11).
- Not a file. It is listed here because every gate reads it.

### M.2 Allocator transfer protocol and standalone obligations (v7 §11)


Ownership is one machine-wide record, `<AFP_STATE_DIR or ~/.afp>/allocator_owner.json`:

```json
{"owner": "afp-broker | muse-standalone", "claim_epoch": 0, "claimed_at": "...", "claimed_by": "..."}
```

Its only writer is the broker. Muse finds it through `AFP_STATE_DIR` (default `~/.afp`).

**Reading the claim.** Muse reads the claim only under the halt-file lock, using the S1 context manager, and never
calls the broker while holding that lock.
- **Lane mode** (`--batch-request`) needs `afp-broker`. The broker also re-validates ownership inside every
  admission and every check (same lock order).
- **Standalone allocation** needs `muse-standalone`. This covers `muse_studio.lane open` and standalone real-send
  `pool_runner` (no `--batch-request`).
  - Under the halt-file lock, standalone allocation reads the claim and writes its lease into `lane_leases.json`,
    one lease per account used; then it releases the lock.
  - **Registry bootstrap (v5 #2).** The broker op `allocator-transfer --to muse-standalone` (S1) does both of these
    in the same txn:
    - sets `muse_obligations_required = true` in the broker DB;
    - creates the empty registry.

    `muse-standalone` ownership comes only from that op, so the flag always precedes the first standalone Enter.
    Standalone Muse never Enters unless the registry exists and is valid; otherwise the send is refused
    (NOT_SENT, nothing entered). From then on a missing, invalid or unreadable registry refuses every transfer.
  - **One obligation per child (v5 #3, NEW, closes v2 #3).** Each standalone process generates an
    `incarnation_id` at start and keeps an in-memory `enter_issued` flag per batch (same rule as §11 lanes).
    Before each standalone Enter (with the Muse ledger at PENDING_SEND), Muse:
    1. takes the halt-file lock;
    2. re-reads the claim (`muse-standalone`, else refuse);
    3. appends **one obligation per expected child** of the batch to `muse_obligations.json` (tmp + fsync +
       replace). Each obligation records: account_id, project path, batch_id, slot_id, shot_id, take, request_id,
       created_at, and the **owner process identity** {pid, exact OS creation time (`GetProcessTimes` on the
       process's own handle), incarnation_id};
    4. releases the lock;
    5. presses Enter.
  - **Removal is per child, under the halt-file lock, and only with exact, identity-bound terminal evidence for that
    child.** Allowed:
    - **RESULT:** a slot receipt with that exact batch_id + slot_id + request_id, and receipt sha256 == clip sha256.
      The §10 #7 per-child rule applies to standalone obligation reconciliation too.
    - **NOT_SENT by the original holder (v6 #2):** only from the same live incarnation, in-process, with
      `enter_issued == False` for that batch, and only after abandonment is complete:
      1. atomically latch the batch `ABANDONED` in-process (one lock-protected flag, never reset);
      2. cancel and join every submission continuation for that batch (thread / task / coroutine, including any
         queued browser action);
      3. only after the join completes, remove the obligations.

      Every Enter path checks `ABANDONED` immediately before the keystroke / send call, under the same in-process
      lock that sets `enter_issued`, and rejects it permanently. If the join fails or times out → no removal; the
      batch stays AMBIGUOUS for an Owner reconcile.
    - **Owner reconcile (v5 #4, v6 #3, Windows fencing):** only when the owning process is proven gone:
      1. Open the recorded pid with `OpenProcess` and keep that handle for the rest of the check. This retained
         handle prevents pid reuse in between.
      2. Compare its `GetProcessTimes` creation time with the recorded one:
         - no such process → gone;
         - a process with a different creation time → gone (pid reused);
         - the same creation time → alive.
      3. `AccessDenied` or any other inspection failure → **UNKNOWN** → reconcile refused.
      4. If the holder is alive, the Owner may terminate it: `TerminateProcess` on the retained handle, then wait on
         that handle until exit is confirmed (no timeout counts as success). The holder's owned descendants (the
         Chromium/transport child tree that could finish a queued Enter) must be terminated and confirmed exited
         the same way. Any descendant that cannot be confirmed → UNKNOWN → refused.

      A restarted process is a new incarnation and proves nothing about an earlier one. Because the holder and its
      descendants are confirmed dead, no reconciled attempt can ever Enter. The Owner reconcile records the child as
      AMBIGUOUS-resolved-by-Owner with the reason; it does not invent a RESULT or NOT_SENT.
  - **Never removed by:**
    - a partial ZIP or a chunk-wide RESULT_RECEIVED (`parallel_pool_engine.py:1333`), for any child without its own
      matching receipt;
    - the STALE_DESIGN / SHOT_REMOVED auto-release;
    - TTL expiry, heartbeat loss, `lane close` or GC.
  - If the registry cannot be written, the send is refused (NOT_SENT, nothing entered).
- **Missing, unreadable or lock timeout** → refuse and write nothing (NOT_SENT_PROVEN, reason `ALLOCATOR_UNKNOWN`).
  There is no liveness probing in either direction.

**Switching owner.** Switching is one explicit Owner command:
`afp-film broker allocator-transfer --to afp-broker|muse-standalone --expect-epoch N`.
- Muse's `python -m muse_studio.lane claim --to ...` is only a thin wrapper that runs that AFP command while
  holding no Muse lock.
- So switching to standalone needs the AFP CLI installed; reading the claim does not.
- The transfer is one broker operation:
  1. `BEGIN IMMEDIATE` → halt-file lock;
  2. re-validate the owner and `claim_epoch == N`;
  3. require no live lease and no unresolved child in the broker, no live lease in `lane_leases.json`, AND no
     entry in `muse_obligations.json`. When `muse_obligations_required` is true, a missing, invalid or unreadable
     registry also refuses;
  4. replace the claim with `claim_epoch + 1`;
  5. commit.
- A transfer that fails any check changes nothing.

### M.3 Send-stop event and per-incident unwritten flags (v7 §11)

4. the `<AFP_STATE_DIR>/halt_pending_unwritten/` dir (any entry; S1 item 16);
5. the named kernel event `Local\FilmStudio-SendStop` (`broker_api.send_stop_event_name()`, S1 item 15): open it
   read-only. Not found → absent. Exists and signalled → refuse with `SEND_STOP`. Any other query error → refuse.

**Send-stop event: the first step on any block (v6 #1).** On any Muse block (CAPTCHA, verification, unusual
activity), the process does this FIRST, synchronously, before any disk write, lock wait or retry:
1. create (or open) and set the event `Local\FilmStudio-SendStop`, and keep its handle open;
2. disable Enter in memory (all of its accounts, for standalone).

The event needs no disk. While the handle is open, every gate on the machine refuses.
- **Holding the handle.** The process keeps the handle until a durable stop covers the machine: the authoritative
  halt is published, or at least a durable `halt_pending/` marker or `halt_pending_unwritten/` flag exists. Only
  then may it exit. The event dies with its last handle, and by then the durable signal covers it.
- **Same session.** `Local\` is per Windows logon session, so all Muse senders and the broker must run in the same
  interactive session. Muse refuses real sends from session 0 (services) or from a session other than the one the
  broker records (S1 to expose the recorded session id).
- **Non-Windows.** The event is treated as absent; the disk signals still apply.


**Marker write fails: `HALT_PENDING_UNWRITTEN` (v5 #1, v6 #4).** The send-stop event, held open by the live
process, is what stops every other sender, in lane and standalone mode alike. The process also:
- writes a per-incident flag `<AFP_STATE_DIR>/halt_pending_unwritten/<incident_id>.flag` (create-exclusive +
  fsync; `incident_id` = a fresh random id; no secrets). Every gate refuses while any flag exists or the dir is
  unreadable (S1 item 16);
- stays alive holding the event handle until a durable signal exists (the authoritative halt, a pending marker or
  a flag), retrying all three with backoff. It never exits on its own while only the event protects the machine.

Lane mode adds a second barrier: on exit 4 with `HALT_PENDING_UNWRITTEN`, the lane supervisor (AFP side) terminates
every Muse lane on the machine and refuses new lane starts until a durable global halt is acknowledged.

**Residual (stated, not claimed as enforced).** Both remain unprotected:
- the event cannot be created AND both disk writes fail: the process stays alive refusing its own sends, and in
  lane mode the supervisor kills all lanes on exit 4, but other senders are not blocked until then;
- the holding process is killed before any durable signal exists: the event dies with it.

The Owner is told in every case.

- The same command handles `halt_pending_unwritten/<incident_id>.flag` the same way: it publishes each incident
  into the halt history, then removes only the incident ids it published. Flags written after it read the dir
  stay (S1 item 16).
- The send-stop event is not cleared by command. It ends when its last holder closes the handle, after the durable
  halt exists.

### M.4 Acceptance tests (v7 §14 Round B)

  - Send-stop event, two processes: A sets the event while its marker and flag writes are made to fail (dir
    creation denied, dirs still readable and empty) → B's broker check, B's standalone gate, and a NEW process on
    another project are all refused (`SEND_STOP`), zero sends. A stays alive holding the handle.
  - The event is set before any disk write: inject a stall at A's first marker write → B is already refused.
  - A exits only after a durable signal exists; event query error → gate refuses; session 0 sender → refused.
  - Lane mode, exit 4 `HALT_PENDING_UNWRITTEN` → the supervisor terminates every Muse lane and refuses new starts.
  - Per-incident flags: clear publishes incident A; incident B's flag, written concurrently, survives and still
    refuses.
  - Abandonment (standalone): a submission continuation paused before Enter + live NOT_SENT removal → the
    continuation is cancelled and joined first; if resumed, it hits `ABANDONED` and never presses Enter; a join
    timeout → no removal.
  - Windows fencing: `AccessDenied` on the holder → UNKNOWN → reconcile refused; termination requested but exit not
    confirmed → refused; a holder's Chromium child still alive → refused; a reused pid with another creation time
    → treated as gone.
- **Allocator.**
  - Missing or unreadable claim → both allocators refuse.
  - Owner `afp-broker` → `lane open` and standalone pool_runner refuse and write nothing.
  - Owner `muse-standalone` → lane mode refuses.
  - A transfer is refused while a lease or unresolved child exists in the broker OR in `lane_leases.json`.
  - Standalone crash after Enter → lease expiry + `lane_leases.json` GC → transfer still refused (an obligation
    remains). Obligations survive `lane close`. A registry that cannot be written refuses the send.
  - Bootstrap: `allocator-transfer --to muse-standalone` sets `muse_obligations_required` and creates the empty
    registry in one txn. Standalone with no or an invalid registry → no Enter. Registry deleted after a
    standalone crash → transfer refused.
  - Per-child removal:
    - a 6-child standalone batch returns one valid clip → only that child's obligation is removed; the other 5
      stay;
    - chunk-wide RESULT_RECEIVED removes nothing by itself.
  - Fencing:
    - a standalone process paused after appending its obligations, before Enter → the Owner reconcile refuses while
      that pid + creation time is alive; after it and its Chromium children are terminated with confirmed exit,
      reconcile removes the obligations and nothing is ever entered;
    - a restarted process (new incarnation) cannot remove the earlier incarnation's obligations as NOT_SENT.
  - A transfer with a stale `--expect-epoch` is refused.
  - Admission racing a transfer → either the admission commits first and the transfer is refused, or the transfer
    commits first and the admission is refused.
  - Muse never writes `allocator_owner.json`.

### M.5 Decided questions (v7 §15)

4. **Open:** the final name of the `allocator-transfer` verb, after S1 lands.
5. **Obligations live in a separate file**, `<AFP_STATE_DIR>/muse_obligations.json` (override
   `MUSE_OBLIGATIONS_FILE`), not inside `lane_leases.json`. Leases keep their TTL pruning; the broker reads one
   path with the rule "any entry → refuse".
6. **Standalone obligations are one per child** (not one per batch listing its children). This is simpler: removal
   is per child, with no partial-batch bookkeeping.

7. **S1 spec alignment.** S1_ADDENDUM_SPEC item 15 says a lane sets the event only when it cannot write its
   marker. v7 (AFP TL decision) sets it FIRST on every block. S1 to align its text; the broker read side is
   unchanged.
