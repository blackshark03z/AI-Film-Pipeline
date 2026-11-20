# AFP Studio — multi-film production architecture

**Status: PROPOSAL v3, 2026-11-20.** The Owner agreed the outline in chat.
- v1 was reviewed by Codex (gpt-6.1-sol, read-only) with the verdict **REWORK**. Review:
  `D:/AI FILM MAKER/_archive/studio_arch_20261120/review_v1.md`.
- v2 answers its 10 findings; §14 maps each one to the section that answers it.
- v2 was re-reviewed with the verdict **ACCEPT_WITH_FIXES** (`review.md` in the same folder). v2.1 applies its 6
  ranked fixes, marked F1-F6 in place.
- v3 folds in the Muse Tech Lead's positions (session message, 2026-11-20), marked M1-M10 in place, and the Muse
  Tech Lead's review of v3 (ACCEPT with 4 text changes in §9 and §11, applied); §13 lists the
  port backlog and §14 maps every finding. Muse code references point into `D:\Muse\muse_studio\`; the Muse
  round-10 safety fixes may still move those lines.
- Base: `feature/drama-preprod-p0` @ `2dd752ff` (upgrade steps 1-5 done).
- Switching Muse production to AFP (D5) is decided on the pilot P1 verdicts (§11).

## 1. Goal

- The Owner hands over a script plus a brief card.
- An AI "brain" drives the film from script to delivery with the default skill for each stage. The brain may be
  Claude Code, Codex or Antigravity.
- Several films run at once without competing for accounts, money or files.
- Generation route and thread count can be set in a UI or left on auto.

## 2. Principle: the brain decides, the daemon does the I/O

```
 Owner ──(script + brief card)──► Studio inbox / UI
                                        │
          ┌─────────────────────────────┼─────────────────────────────┐
          ▼                             ▼                             ▼
   Film session A (brain)       Film session B (brain)        Film session C ...
   any runtime; calls only the `afp-film` CLI; one script per session
          │  afp-film next / plan / enqueue / review / cut ...         │
          └───────────────┬────────────────────────────────────────────┘
                          ▼  (SQLite job + event journal, film_lock for package metadata)
 ┌───────────── STUDIO DAEMON (deterministic Python, no LLM, exactly one per machine) ─────────────┐
 │ Broker  : accounts x provider, batch leases, atomic quota/budget reservation, halt admission     │
 │ Queue   : durable jobs (frozen assets) → batches → lane workers                                 │
 │ Lanes   : one OS process per account lane — Flow (CDP/GPM) · Muse (headless) · HTTP providers   │
 │ Intake  : download → hash → register take (film_lock) → event → wake adapter                     │
 │ Git     : the single git writer (explicit path staging)                                          │
 │ Web UI  : localhost, token-authenticated — Accounts · Films · Queue · Routes                     │
 └───────────────────────────────────────────────────────────────────────────────────────────────────┘
                          ▼
           films/<id>/  (package, receipts, takes, events, derived STATUS.md)
```

- Brains never hold a browser, a cookie or an account lease. They queue jobs, then stop until woken (§7).
- The daemon makes no creative decisions. It sends exactly what was frozen into the job (§4).

## 3. Custody contract (answers review finding 1)

A **job** is the unit of custody. Its states, with the owner of each transition:

| State | Meaning | Written by | Recovery after a hard kill |
|---|---|---|---|
| QUEUED | job row + frozen assets durable; no lease, no money | brain via `afp-film enqueue` (film_lock + job DB txn) | stays QUEUED |
| ADMITTED | in one broker transaction: batch lease taken, quota and budget reserved, halt checked, receipt PENDING/PREPARING written | daemon | lease and reservation are rolled back if no receipt exists; otherwise PREPARING is resolved offline as not dispatched |
| SUBMITTING | receipt says SUBMITTING, written just before the provider "Enter" | lane process | never released automatically: reconcile only |
| SUBMITTED | provider job id bound | lane | poll or reconcile |
| HARVESTED | clip downloaded, hash recorded | lane | re-register from the recorded hash (idempotent) |
| REGISTERED | take in the take log, receipt final, lease settled | daemon (film_lock) | idempotent replay |
| FAILED / AMBIGUOUS / CANCELLED | final, or held for reconcile | daemon | AMBIGUOUS keeps the lease held, as step 4 does today |

- **Authoritative records (F1).** The broker/job SQLite DB is the source of truth for custody. Receipts under
  `takes/intents/` and `events.jsonl` are projections written from the DB and are re-derivable on restart. A crash
  between the DB commit and the projection write is repaired by re-projecting.
- **Lane fencing (F1).** Each account carries an epoch in the broker.
  - A lane may submit only while its epoch is current, checked in the same short broker transaction that writes
    SUBMITTING, right before the Enter.
  - On daemon start, the daemon kills every old lane process (Windows Job Object) and bumps all epochs. Only then
    does it roll back PREPARING admissions or reuse an account.
  - An orphan lane therefore can never submit.
- **Stable ids (F6).** The logical key `job_key` = `<film_id>:<generation_id>:v<shot_version>:<seq>` is used in the
  DB. On disk, `job_dir` = the first 12 hex digits of sha256(`job_key`), because colons are invalid in Windows
  paths (F6). It is kept short because Muse keyframe ids reach ~100 characters and nested batch folders overflow
  the 260-character path limit (M8); the daemon also enables long-path support. `enqueue` is idempotent: the same
  generation and version with the same frozen-asset digest returns the existing job, and a different digest is
  refused while a job is live. `take_id` is assigned at ADMITTED, not at enqueue.
- **One owner per transition.** A lease is never acquired without the receipt write in the same admission step.
  A hard kill between them leaves no stranded ACTIVE lease, because the broker rolls back leases that have no
  receipt on startup.
- **Unknown is never released.** A dead worker does not release a lease after SUBMITTING. It goes through reconcile
  and `lease settle`, unchanged from step 4.
- **Singleton daemon.** An OS-level lock file plus a heartbeat row; a second daemon refuses to start. Direct
  `afp-film generate` stays available for single-film work, but takes its lease and admission through the same
  broker transaction, so the two paths cannot double-book.

## 4. Frozen jobs (answers review finding 4)

- At enqueue, the job copies its inputs into `films/<id>/takes/jobs/<job_dir>/`: the prompt text, start and end
  stills, and reference images. It records each one's sha256.
- It also records the resolved route, provider, model, tier, duration, the expected cost and the package revision:
  the hash of the plan and shots used.
- Lanes send only the frozen copies. Flow currently receives the still's working path, so §9 S2 changes the adapter
  argv to the frozen path.
- **Stale jobs (F4).**
  - At admission the daemon recomputes the generation's current input digest: prompt, stills, route and the
    relevant plan or shot entries. If it differs from the job's frozen digest, the job is CANCELLED, not sent.
  - Changing those inputs after admission requires a new shot version; `afp-film plan` enforces this.
  - At intake the take records its frozen digest. A mismatch with the current digest marks the take STALE_INPUT, a
    new Gate 4 check (Gate 4 today only compares shot version and prompt).
- **Locking.** Brain edits to package metadata and daemon intake take the same `film_lock`. Directory ownership is
  not relied on.

## 5. Accounts, batches and money (answers review finding 3)

- **Invariant: one exclusive batch lease per account.** A batch holds 1 to `slots` children, all from one film and
  one job kind. Slots per batch: Flow 1; Muse video 6; Muse stills 4 (keyframes, plates, turnarounds). Stills are
  jobs with the same custody as video (M3).
  - Each child has its own job, receipt and outcome.
  - The batch lease settles when every child is final.
  - If one child is AMBIGUOUS, the whole account stays held until that child is reconciled. This is conservative
    and simple.
- **Atomic reservation.** Admission reserves the batch's quota and expected cost in the broker DB, in the same
  transaction as the lease. Reservations cover:
  - the per-account daily quota;
  - the per-film budget;
  - the per-provider machine daily cap.

  This replaces today's scan of the other films' receipts, which runs outside any transaction
  (`generate._spent_on_elsewhere`).
- **Cap scope (F3).** The machine-wide daily cap stays aggregated per unit across providers, as it is today
  (`routes.json` VND limit, `generate.py` unit aggregation). Per-provider and per-account limits are additional
  limits, never replacements. Settlement turns each reservation into a spend or a release. Day rollover uses
  the local date recorded on the reservation.
- **Units.** Budgets are kept per unit: credits, VND or `muse_requests`. Converting money into affordable jobs uses
  the capability registry price for the frozen route. A unit without a price cannot be admitted.
- **Threads.** Auto mode uses the minimum of these, all read in the admission transaction:
  - free batch capacity on eligible accounts;
  - quota left;
  - budget left ÷ the job price;
  - the Owner's caps.

  Manual mode lets the Owner set caps per film or globally in the UI.
- **Account states shown:** FREE · BUSY (film, children in flight e.g. 4/6) · COOLDOWN · NEEDS_LOGIN ·
  QUARANTINED · HELD (an ambiguous child) · HALTED.
- **Fairness:** batches are handed out round-robin by film priority, with an optional per-film share cap.
- **Multi-take (M2).** A shot version may have K parallel takes; each take is its own child with its own `take_id`.
  - Two takes of the same shot version are never in one batch.
  - The best passing take is selected by the QC `quality_score`. The brain may promote another passing take; a
    promotion needs the immutable source clip and a matching input digest.
  - K comes from the take policy on the brief card. Proposed default: GREEN 1, AMBER 2, UNKNOWN 3, dialogue shots
    at least 2, RED restaged and never sent. This replaces OWNER_POLICY's attempt caps for that provider (§10).
- **Quota source (M10).** An account's quota is either a configured constant or *probed*. Muse has no daily cap in
  code; its only quota signal is `weekly_remaining_pct` on the Settings page.
  - Admission refuses an account whose probe is older than a set age, or below a reserve percentage, and asks the
    lane to re-probe first.
  - The "200/day" figure in our notes is unsourced and is not used as a limit.

## 6. Halt admission and lane isolation (answers review findings 2 and 5)

- **Halt is checked twice.** Admission checks the halt inside the broker transaction. The lane re-checks it under
  the broker lock immediately before each Enter and before each login attempt. Setting the halt takes the same
  lock.
  - A job admitted but not yet at SUBMITTING when the halt lands is rolled back to QUEUED.
  - A SUBMITTING or SUBMITTED job is finished and reconciled, never re-sent.
  - The same rule applies to the direct CLI path and to every provider.
- **One OS process per account lane**, started by the daemon with an explicit target in its arguments: CDP endpoint,
  project, account id and store path. No process-wide environment switching: `_flow_target_env` is retired from
  the daemon path.
- **Lock rules (F2), one contract for lane startup, direct CLI, submission, intake and halt:**
  - The broker transaction and `film_lock` are **leaf locks**. They are held for milliseconds, and nothing is
    acquired while holding them: no other lock, no provider I/O, no waiting.
  - `composer_lock` (one per browser profile) is the only long-held lock, taken per job for the provider-UI
    interaction, never for the life of a lane. Holding it while briefly taking a leaf lock is allowed; the reverse
    is not.
  - Because no leaf holder ever waits on anything, no cycle is possible. This replaces today's composer-then-film
    nesting in `generate`, which already satisfies the rule.
  - **Profile ownership (M9)** is a claim, not a lock anyone waits on. A Muse lane process owns its account's
    Chromium profile for its whole life. The claim is registered in the broker with the lane epoch and checked
    with the busy-profile probe at lane start. A second claimant is refused at once, never queued.
- **Halt scope (M4).** The current Owner rule is that any account warning stops ALL sending, so the default is a
  machine-wide halt.
  - The Owner may instead choose a scoped halt: the warning quarantines the account and halts that provider only,
    escalating to a machine-wide halt if a second account warns within 24 h.
  - This is an Owner decision (§10) and is not assumed.

## 7. Brains, sessions and wake-up (answers review findings 6 and 10)

| Session | Count | Job | Never does |
|---|---|---|---|
| Studio (coordinator) | 1 | inbox → scaffold → opens one film session per script; Films board; collects Owner-reserved questions | film work, code |
| Film (brain) | 1 per script | runs the film with `afp-film next`; **approves stills, boards and takes under the OWNER_POLICY delegation** (that delegation is extended from "Tech Lead" to "film brain sessions", see §10) | code, accounts, git, push |
| Tech Lead | 1 | pipeline code, tests, reviews | film creative approvals |

- **`afp-film next --film F`** is a deterministic conductor. It returns:
  - the stage and its named start and end conditions, plus the blocking gate;
  - the skill to use (see the table below);
  - the commands to run;
  - Owner-reserved items, which it refuses to perform;
  - stale-state warnings, e.g. a job finished since the last read.

  | Stage | Default skill |
  |---|---|
  | Treatment | film-treatment |
  | Preprod and shots | film-director, film-craft |
  | Sound | film-sound-design |
  | Review | film-creative-review |
  | Post and delivery | film-post |
  | Defects | film-lessons |

  It reports a missing skill as a blocker.
- **State location:** film state is in `films/<id>/`, accounts and halt are in the broker, and the conductor joins
  both. `films/<id>/STATUS.md` is a derived summary written by `next`, not a source of truth.
- **Events (F1).** Each event (job finished, failed, held, halted) is a row written in the SAME DB transaction as
  the state change it reports, so a registered take always has its event. `films/<id>/events.jsonl` is a projection
  of those rows, with a durable event id. `afp-film events --film F --since <id>` replays them and `--ack` acknowledges them. If the daemon dies
  after registering a take but before notifying, a restart replays the unacknowledged events.
- **Wake adapters.** An event file does not resume anything by itself, so there are three options:
  - Claude desktop: the Studio session messages the film session, using the supported session-message tool.
  - Codex and Antigravity: no supported wake API is assumed. The Studio UI shows "film X has N new events", and the
    Owner or the Studio resumes that session by hand.
  - Any runtime may start fresh: `afp-film next` plus event replay restores the full context.
- **Concurrency:** 3 active film sessions by default, because LLM usage is the bottleneck. A usage limit was hit on
  2026-11-20.

## 8. Git and runtime pinning (answers review finding 7)

- **The daemon is the only git writer on the production checkout.** Brains never run git.
  - At milestones (gate pass, film delivered) the daemon commits with explicit path staging:
    `git add -- films/<id>/...`, never `-A`. It holds a machine git lock and commits one film per commit.
- **The Tech Lead works in a separate worktree and branch.**
- **Pinned runtime.** Production runs from a pinned install of a tagged revision (`studio-runtime-<date>`). Each
  film records the runtime revision it started with, and the daemon refuses to run a film on a different revision
  unless the Tech Lead migrates it. Code changes therefore never alter a running film midway.

## 9. Muse lane (answers review findings 8 and 9)

- **Accounts.** The Owner adds accounts by hand in the Muse Studio UI. They run headless with stored cookies, and
  the lane re-logs in with the stored login details when a session dies (OWNER_POLICY exception, 2026-11-20).
- **Secrets.**
  - Cookies and login details are read from the Muse Studio store only inside the Muse lane process. They are used
    transiently, in memory, for the HTTP session or headless browser that authenticates.
  - They are never written to logs, traces, screenshots, receipts, events, the repo, exports or any persisted
    profile outside that store.
  - A refreshed cookie is written back to the store atomically.
  - The store path is configured; read access stays with the Owner's user account.
- **Re-login never happens inside the submit path (M5).** Today `headless_muse_client` can re-log in during a
  submit, through `account_manager._auto_login_and_verify_impl`, with no rate limit and no auth-only trigger. That
  call is NOT ported as is.
  - An expired session found during a submit ends the child as NOT_SENT if Enter was not reached, or AMBIGUOUS if
    it was.
  - The broker then schedules a rate-limited re-login under the rules below.
  - After a successful batch the lane may write refreshed cookies back to the store, atomically, only when they
    changed.
  - The tempmail/OTP fallback in `account_manager` is not ported.
- **Re-login rules**, kept in the broker so they survive restarts:
  - At most 1 attempt per account per 2 h, and 2 consecutive failures → NEEDS_LOGIN.
  - Only an expired-authentication failure triggers a re-login. Quota, payment and network errors never do.
  - A re-login never re-sends a job and never rotates to another account to get past a warning.
  - CAPTCHA, verification or unusual activity → stop, quarantine the account, set the halt. Nothing is solved or
    evaded.
- **Recovery contract (M1).** This is new work; today's `muse_gateway` claim journal and `reconcile` (Flow-only) do
  not cover it. Muse has **no provider job id**: the provider is a Muse chat agent.
  - **Transport.** The lane uploads a handoff ZIP with the relay text `AFP MUSE BATCH REQUEST <batch_id>` (today
    `core/batch_packager.py`, `create_batch_handoff`). Muse answers with `<batch_id>_result.zip`, which holds
    `<slot>.mp4`, `<slot>_receipt.json` and `batch_receipt.json` (shot_id, slot_id, request_id, sha256).
  - **Binding handle:** `batch_id` (unique per invocation, its folder created exclusively) + `slot_id` +
    `request_id` + the receipt sha256. The lane SHOULD capture the chat thread URL into the SUBMITTING record as
    soon as it exists. This is new work: Muse does not capture it today. Reopening the URL is a candidate
    reconcile path, unproven until the S5 recovery drill passes (§11).
  - Each child of a Muse batch gets a receipt and job state as in §3. A child whose result cannot be bound after an
    authentication expiry is AMBIGUOUS, and its account is HELD.
  - **Rules ported from Muse rounds r6-r9; each one fixed a real defect:**
    1. The lease and epoch are re-checked right before the submit keystroke. Losing them there is
       RESOLVED/NOT_SENT, which never blocks.
    2. The submission record is written before Enter (PENDING_SEND). History is kept.
       - Blocking states: PENDING_SEND, UNCONFIRMED, EXPIRED_NEEDS_RECONCILE, RESULT_CORRUPT
         (`UNCONFIRMED_BLOCKING`, `parallel_pool_engine.py:73`).
       - Non-blocking terminal states, set in the same run: RESOLVED with reason NOT_SENT or RESULT_RECEIVED.
       - Non-blocking terminal states, set when a later run re-checks the ledger: RELEASED with reason
         RESULT_RECEIVED, RECONCILED_PASSED, STALE_DESIGN, SHOT_REMOVED, or an explicit Owner or lane release.
       - **AFP mapping:** one AFP vocabulary (§3). UNCONFIRMED and EXPIRED_NEEDS_RECONCILE map to AMBIGUOUS;
         RESULT_CORRUPT maps to AMBIGUOUS with INTEGRITY_FAILED evidence. The Muse name is kept only as a reason
         code.
    3. Any exception after submit, including a bookkeeping error, keeps the child as submitted. It goes to
       reconcile, never to a resend.
    4. TTL expiry never re-sends. The child becomes EXPIRED_NEEDS_RECONCILE and stays blocking until a verified
       result or an explicit release.
    5. A 0-byte, truncated or corrupt result ZIP (it fails to open, or has no members) has not arrived. It is
       RESULT_CORRUPT and keeps blocking.
    6. Batch ids are unique per invocation, and batch folders are created exclusively.
    7. The per-batch render fingerprint equals the frozen input digest of §4. A take whose digest differs from the
       current design is STALE_INPUT (Muse calls it STALE_RENDER).
    8. Every state writer takes a real OS lock (`film_lock`, the equivalent of Muse's SessionLock).
    9. Multi-take rules as in §5.
  - **Integrity quarantine (M6).** A clip whose sha256 does not match its receipt is INTEGRITY_FAILED, recorded in
    the broker DB. Every reader honours it: the receipt and take API, discovery, QC, review, cut and promote, not
    just the unpacker. RESULT_CORRUPT is handled the same way.
    - Integrity is judged per file: each file's own sha256 is compared with its recorded receipt or promote SHA.
    - A promoted or canonical clip that still matches its recorded SHA stays valid, even when its source take is
      missing or INTEGRITY_FAILED. (Muse r10 regression: an audit deleted the last good canonical clip because its
      source had gone corrupt.)
    - A file that fails is quarantined: moved and recorded, never deleted.
  - **Partial batch.** Missing or failed children become NO_RESULT_IN_BATCH or INTEGRITY_FAILED one by one. A new
    round is a new batch with new ids. Prompt repair between rounds goes only through the defects registry (a
    reviewed defect code → a repair action; an unknown code → STOP).
  - **Submitted but unbindable (F5).** The lease and reservation stay held. The reconciler reopens the persisted
    thread URL and looks for exact evidence: batch_id, slot_id, request_id and the receipt sha.
    - Exactly one match → bind it. Otherwise → `UNBINDABLE`, escalated to the Tech Lead with the account held.
    - If no URL was captured, the reopen fails, or the card has no download → `UNBINDABLE` at once. The account
      stays HELD and the reservation stays held; nothing is retried automatically.
    - The job is never re-dispatched automatically.
  - **Timeouts** keep Muse's adaptive rule (`compute_adaptive_timeout`, `headless_muse_client.py:96-101`; n = slots
    in the batch):
    - video: max(180, min(600, 120 + 65·n)) s;
    - stills: max(120, min(320, 90 + 35·n)) s.
    - The result card is polled every 2.5 s, and the download window is 90 s (`headless_muse_client.py:373`, `:402`).
    - A timeout after Enter is never NOT_SENT: it goes to reconcile.
- **Registry and budgets.**
  - Add a `muse` registry entry, an adapter kind and the `muse_requests` unit to the capability model. Today only
    `credits`, `USD` and `VND` exist.
  - Film budgets in `package.py` must accept the new unit.
  - The conditional limit is expressed per input mode: no dialogue from a first-frame still. A model-wide audio
    flag cannot express it.
- **No automatic account creation** (no tempmail or OTP; D2 stays open).

## 10. Authority (answers review finding 10)

**Owner decisions, 2026-11-20** (recorded in OWNER_POLICY.md, which now replaces the old generation policy):
- Muse is the video and stills provider, at its highest resolution and best model, with no request cap. Flow and
  Vilao are paused for new sends.
- Pilot P1 runs on Muse.
- When an account is out of quota or cannot log in, the Owner is told and adds accounts; work continues on the other
  accounts. A CAPTCHA, verification or unusual-activity notice stops ALL Muse sending (halt scope = Muse, which is
  today the whole machine).
- The take policy is delegated to the agent (default GREEN 1, AMBER 2, UNKNOWN 3, dialogue ≥2, RED restaged).
- Muse's proven controls must not be broken: they are ported unchanged and proven by parity (§11).

Items 1-5 below are therefore settled by the new OWNER_POLICY; only D0 (item 6) remains open.

1. **Brief card = start authorisation.** A script plus a brief card authorises that film.
   - The card holds: title, budget cap per unit, route policy, target length, deadline and priority.
   - Today, starting a new film is reserved to the Owner.
2. **Delegated approvals** (stills, boards, takes, gate passes) extend to film brain sessions, signed
   `agent:film-<id> (delegated by owner, OWNER_POLICY.md)`. The normal loop has no Owner stop: "send a script, get
   a film" stops only for the reserved list below (M4c).
3. **Go-live.** The daemon's admission replaces the one-send `OWNER_GO_LIVE` switch for films with a brief card. The
   card's caps are the Owner's go-live.
4. **Models and resolutions.** The Owner-reserved rule on models and resolutions extends to the providers a card
   names; a card cannot name a model the policy does not allow.
5. **Muse (F3).** The cookie exception (recorded 2026-11-20) carries the boundaries in §9. It does NOT yet
   authorise generation on Muse. Before S5 the Owner must also add to OWNER_POLICY:
   - Muse as an authorised generation provider (sending frames and references to it counts as part of a send);
   - the allowed Muse model(s) and resolution;
   - the Muse cap in `muse_requests` per day and per film. The Owner has said "Credit trên Muse không phải là vấn
     đề, tập trung vào tốc độ và chất lượng đầu ra", so the value may be very high; the mechanism stays (M4a);
   - the Muse take policy (K takes per shot version, §5), which replaces GREEN 1 / AMBER 2 / RED 0 for Muse;
   - the halt scope: machine-wide (today's rule) or scoped per provider (§6).

   Until then, a brief card cannot name Muse. `MUSE_CONSOLIDATION.md` §2.3
   is superseded on cookies.
6. **D0.** The Owner pins a `POLICY_REF` before any implementation handoff (AGENTS.md:7).

Still reserved to the Owner: publishing, `git push`, raising caps, changing story meaning, purchases and new
accounts.

## 11. Milestones and acceptance

| # | Milestone | Done when (tests, not claims) |
|---|---|---|
| S1 | Broker v2: provider, batch leases, atomic reservations, halt admission, NEEDS_LOGIN, `afp-film accounts` | migration with held and uncertain leases; competing processes; atomic quota and budget reservation under a race; day rollover; protected-film prompt hashes unchanged |
| S2 | Daemon: job journal, frozen assets, lane processes (Flow), intake, events, git writer | one SHARED mock broker across 2 films; a hard kill at every state boundary in §3, incl. a daemon killed while its lane lives (orphan fenced by epoch) and a kill between DB commit and projection; duplicate enqueue; partial batches; daemon restart; halt races; registration and settlement replay; a second daemon refused |
| S3 | Conductor `next`, events, wake adapters, brain playbook, OWNER_POLICY updates | a fresh Claude and a fresh Codex session each take a rehearsal film from a named start stage to a named end stage; resume after a kill; event replay; refusal of reserved actions; a missing-skill blocker |
| P1 | **Pilot**: 1 real film through S1-S3, plus S5 if on Muse, on the provider the Owner authorises. Muse is recommended because it is the Owner's production provider (M5b) | Owner-authorised; caps fixed in advance; full playback and listening on review; no duplicate send; recovery drill passed. Verdicts given separately: technical, product, Owner |
| S4 | Web UI | enqueue, cancel, route and cap edits; stale-edit refusal; reconnect; token authentication with origin/CSRF checks; an automated secret-leak scan of the rendered pages |
| S5 | Muse lane: video and stills jobs, multi-take, the r6-r9 rules of §9 | offline parity on fixture **B14** (`D:\Muse\_director_review_B14_20261119`: 20 shots, dialogue, 2 locations, 4 characters; copied to a short path); one test per r6-r9 rule; partial N×6 failures; auth expiry after submit; restart-safe throttling; no re-dispatch; integrity quarantine honoured by every reader; exclusive profile ownership; **recovery drill**: kill the lane after Enter and before download, then a fresh lane reopens the persisted thread URL and binds the result by batch_id + slot_id + request_id + receipt sha with zero new sends (if the drill fails, F5 falls back to UNBINDABLE + HELD only). Live parity: BIKER_DEAD_ENGINE_20261120 if the Owner accepts it, else BLACK_PILOT_EXTENDED_FEATURE_FILM (M5a) |
| S6 | 2 films in parallel | Owner-authorised; predefined delivery, playback and listening, budget, duplicate-send and recovery criteria; separate technical, product and Owner verdicts |

- Order (Owner chose Muse for P1, 2026-11-20): S1 → S2 → S3 → S5 → **P1** → S4 → S6. S4 is not needed for P1.
  S2's lane tests use the mock and rehearsal runners; Flow live sends stay paused.
- **Muse non-regression rule.** Muse controls video differently from Flow (a chat agent, handoff ZIP batches, a
  submission ledger). The S5 lane wraps or ports Muse's proven code paths and rules unchanged; a rewrite is allowed
  only where a parity test proves the same behaviour. The Muse Tech Lead reviews every S5 change that touches
  sending, the ledger, recovery or integrity. Reference: the Muse verification report,
  `docs/production/muse/Bao-cao-tong-hop-kiem-chung-Muse-FINAL.md`.
- **Until P1 passes, the standalone Muse lanes stay the production path**, with safety fixes only; after its round
  10 Muse gets no new features.
- D5 (switching Muse production to AFP) is decided on the P1 verdicts.
- **Ownership.** AFP Tech Lead: S1-S4, P1, S6, and the S5 implementation. Muse Tech Lead: the S5 lane spec, the
  r6-r9 rule tests and the parity fixtures; the AFP Tech Lead reviews them.

## 12. Risks

- Moving Phase B/C behind a queue touches the most guarded code. Every step 2-4 custody test must still pass, plus
  the S2 kill matrix.
- Re-login raises the chance of provider flags. The controls are the halt-on-warning rule, the re-login rate limit
  and "auth only" triggers.
- The daemon is a new long-running component. It needs a supervisor and a heartbeat, and its state must be fully
  recoverable from SQLite and the receipts.

## 13. Port backlog from Muse (ranked by the Muse Tech Lead; diff against AFP before porting)

1. **film_qc_engine detectors and `quality_score`:** freeze or partial freeze, flicker or jump cut, internal scene
   cut, camera drift, unlicensed head motion, identity drift, black frames, spoken stage direction, dialogue
   mismatch (Whisper WER), silent dialogue track, frozen-mouth lip-sync, hand mutation, audio clipping, and
   aspect, duration or corrupt file. Each becomes a detector signal mapped to `production/defects.py`, calibrated
   as in upgrade step 5.
2. **Best-take selection and promote-take** (§5).
3. **screenplay_compiler and staging pieces:** diff the interaction contract (AFP has one); dialogue timing with NFC
   and DIALOGUE_OVER_CAPACITY; hand and prop detection; location plates, turnarounds and multi-character
   keyframes.
4. **prompt_repair_agent:** rewrites keyed on defect codes, through the registry.
5. **srt_normalizer and srt_diarizer:** a coverage gate and speaker turns, with explicit and inferred labels kept
   apart.
6. **cinema_audio_engine:** voice timbre lock, dialogue cleanup, ambience.
7. **delivery_packager and master_assembler:** M&E and dialogue stems, EBU R128, slate and credits, Netflix-style
   SRT, i18n template, trailer, 9x16 cut, poster, chapters.
8. **Agent layer:** the Antigravity payload handling in `.claude/hooks/stage_skills.py`, reused by the conductor
   (§7).

## 14. Review finding → answer

| # | Finding | Section |
|---|---|---|
| 1 | Custody transfer for Phase A/B/C | §3 |
| 2 | Process-wide env and composer lock | §6 |
| 3 | Slots, batches, accounting | §5 |
| 4 | Immutable assets, stale jobs, film_lock | §4 |
| 5 | Halt boundary | §6 |
| 6 | Wake-up, replay, where state lives | §7 |
| 7 | Git and runtime pinning | §8 |
| 8 | Muse recovery, registry, budgets | §9 |
| 9 | Secrets, login boundaries, UI auth | §9, S4 |
| 10 | Authority, roles, D0 | §7, §10 |
| M1 | Muse has no provider job id; bind by batch/slot/request/sha + thread URL | §9 |
| M2 | One dispatch per shot version vs multi-take | §5 |
| M3 | Stills are Muse jobs too (4 slots) | §5 |
| M4 | Halt scope; unlimited Muse cap; no Owner stops in the loop | §6, §10 |
| M5 | Re-login out of the submit path; pilot provider and order | §9, §11 |
| M6 | Durable integrity quarantine for every reader | §9 |
| M7 | Pinned runtime | §8 (agreed) |
| M8 | Windows MAX_PATH | §3 |
| M9 | Profile owned for the lane's life vs leaf-lock rule | §6 |
| M10 | Quota unknown; no daily cap in code | §5 |
