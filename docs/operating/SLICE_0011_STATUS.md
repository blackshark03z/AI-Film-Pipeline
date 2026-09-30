# SLICE-0011 execution status

## Authority and current state

- Accepted baseline: `a3496592950c1270cda96fab2cb10711baee33fa`; initial tree clean. Slice-0010 evidence is closed and untouched.
- Working branch: `codex/slice-0011-reference-i2v-continuity`.
- Provider authority ceiling: one reference upload, one reference-video submit per shot, two submits total; no retry, Seedance, billing change or provider switch.
- Current external-effect counters: reference upload reservations **1**, reference-video submits **0**. One upload path was invoked on 2026-09-30, but its provider outcome is unknown. The local receipt remains `RESERVED` with no verified Flow media ID. The same upload must never be retried from this state.
- Any genuine provider-state ambiguity stops at `OWNER_AMBIGUITY_GATE`; no autonomous recovery after that gate.

## Reference and read-only qualification

- The suggested `stable-reference.png` is a geometric RPC probe, not a person; unsuitable for character identity review.
- Candidate `D:/Story Auto/evidence/goal54/fixtures/r1_character.png` is a 1280×720 PNG with SHA-256 `31ca872d7b608dee61db0f0bdc753e4acaf659c428706ff7da88dfee98c3e531`. `D:/Story Auto/story-auto/tools/goal54_make_reference_fixture.py` draws the fictional illustrated adult character deterministically with Pillow and explicitly states that it avoids copyright and personal-data ambiguity. It was used as a prior I2V research fixture. No real-person image is involved.
- Read-only Flow RPC catalog preflight on project `f6b40e79-d6f8-4354-80ae-c863260e96f5` succeeded: 2 existing catalog records; observed qualified fingerprint `78ca7a1c3048b2c86802981696ca7e196752a661a027d3f11b8b5edece84e049`. This qualifies the current catalog/session surface only; it does not prove a new upload or generation outcome.
- Story Auto reuse source is the private `maseQ`/`MZZa6b`/`Zzl0ze`/`as29s` batchexecute path behind a normal authenticated browser session. Film will not import `story_auto.*` at runtime or claim a public API.

## Milestones

1. Persist the exact reference as ordinary `Asset(origin=reference)` with no fabricated generation lineage; bind two distinct ShotSpecs to one character, identity/look version and Asset/SHA.
2. Compile and route with one real `image_input`, exact reference SHA, and a bounded versioned Flow I2V profile. Reject T2V-only or textual fallback.
3. Port the minimum private RPC contract and session transport; validate drift read-only and test one-upload reuse, one-submit-per-shot, ambiguity stops and restart readback before any provider write.
4. One upload was reserved and attempted; execution stopped at `OWNER_AMBIGUITY_GATE` before any video submission. Resume only through the Owner's existing ambiguity procedure. Do not retry upload or submit from the current state.
5. Prepare one reference-vs-A, reference-vs-B and A-vs-B packet; ask Owner for explicit APPROVE/REJECT. Do not select takes before approval.
6. If approved, persist two final QC reports/takes, assemble a two-clip cut and EditJobInputV0 package, run regression/independent review and commit a clean candidate.

## Design constraints confirmed

- The frozen AssetV1 schema already permits `origin=reference`; only Film runtime model/SQLite storage require alignment. Generated output receipt/binding behavior must stay strict.
- Story Auto's per-attempt `FlowRpcGenerator.run()` cannot be reused whole because it would upload once for each shot. Film needs one shared hash-bound operational upload receipt and two separate generation jobs.
- Story Auto's upload readback compares decoded pixels, so original PNG SHA and provider-returned media SHA are distinct facts. Never claim provider bytes equal the local reference without byte proof.
- Final observed character continuity is a human gate; VLM findings are advisory.

## 2026-09-30 Owner ambiguity handoff

- The real preflight read 2 records from project `f6b40e79-d6f8-4354-80ae-c863260e96f5` and matched catalog fingerprint `78ca7a1c3048b2c86802981696ca7e196752a661a027d3f11b8b5edece84e049` immediately before the upload stage.
- The Film reference Asset ID is `asset_70834935ccb760367645411d115c0c24243f4dd921182ef4b9502cad382062ff`; its local PNG SHA-256 is `31ca872d7b608dee61db0f0bdc753e4acaf659c428706ff7da88dfee98c3e531`.
- Durable upload reservation: `refup_1521a9ea3a8582852abbe2b97bf8de4df2ddba6cb689df67c04e06b26021e3ce`, `upload_attempts=1`, `state=RESERVED`, `media_id=NULL`, `provider_media_sha256=NULL`. This means one upload attempt was budgeted; it does **not** prove the POST reached Flow or that upload succeeded.
- Durable counts at stop: 1 reference Asset (no generated lineage), 0 GenerationAttempts, 0 ProviderJobs, 0 Flow reference-video submits, 0 output Assets. No Shot A/B generation was invoked.
- The CLI recorded only the safe stop code `OwnerAmbiguityGate: reference upload reserved; provider outcome requires Owner`. The precise failing phase and remote side effect are not known from local persisted evidence. No provider readback, retry, replacement, or alternate transport was performed after this gate.
- The session is project-access verified, but the signed-in Google account name is not technically read back by this private RPC path. `hoangbsea` is Owner-attested from the login step, not a verified account assertion in the upload receipt.
- Next action is the Owner's ambiguity procedure. The local one-upload guard remains consumed until an Owner-authorized, evidence-backed resolution is supplied; normal `upload` will fail closed.
