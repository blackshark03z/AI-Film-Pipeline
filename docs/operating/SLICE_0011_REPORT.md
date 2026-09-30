# SLICE-0011 candidate report — Owner ambiguity stop

RESULT: `OWNER_AMBIGUITY_GATE` (not PROVEN)

SLICE: `SLICE-0011`

BASELINE_SHA: `a3496592950c1270cda96fab2cb10711baee33fa`

REUSE: Story Auto's qualified private `maseQ`/`MZZa6b`/`Zzl0ze`/`as29s` contract and browser-session semantics were adapted without a `story_auto.*` runtime import. Film's existing AssetV1, ShotSpecV1, PromptPlan, RoutingDecision, GenerationAttempt, ProviderJob, SQLite lineage, dispatch journal, QC, SelectedTake, EditManifest, and EditJobInputV0 primitives remain the intended path. New canonical entities: none. Frozen schema changes: none.

REFERENCE: fictional illustrated adult character drawn by `D:/Story Auto/story-auto/tools/goal54_make_reference_fixture.py`; source `D:/Story Auto/evidence/goal54/fixtures/r1_character.png`; ordinary Film Asset ID `asset_70834935ccb760367645411d115c0c24243f4dd921182ef4b9502cad382062ff`; SHA-256 `31ca872d7b608dee61db0f0bdc753e4acaf659c428706ff7da88dfee98c3e531`; PNG 1280×720; provenance is deterministic synthetic fixture, no identifiable real person. The reference Asset has no fabricated generation lineage.

CHARACTER: `CHAR_CONTINUITY_001`, `ID_V1`, `LOOK_V1`.

SHOT_A: `CHAR_CONTINUITY_A`; ShotSpec hash `669ccf59247ccedc0e42a95f8753c36238bfd159a4836c70fbf7a3845372cf11`; PromptPlan `plan_a2f37382087ce23cd5ec313e5767e058d4627eb4305b76ef0b07db93679ad4a7`; mapped `image_input` binds the exact reference Asset/SHA; GenerationAttempt/ProviderJob/output Asset: none; dispatch count: 0.

SHOT_B: `CHAR_CONTINUITY_B`; ShotSpec hash `f3bada08b65c1a33438adf5357329eaf5eaa32eb96ace58d22b0c506ad8ef4ba`; PromptPlan `plan_8a18fc8e76227c727028896da2a1a5c739c590b4b9f28dafc6b272c632fbd66e`; same mapped `image_input`; GenerationAttempt/ProviderJob/output Asset: none; dispatch count: 0.

PROVIDER: bounded profile `flow-rpc-reference-video-2026-09-20.1`; private observed reference-video transport, 8 seconds/16:9/one PNG. T2V path was not used. Project `f6b40e79-d6f8-4354-80ae-c863260e96f5` and catalog fingerprint `78ca7a1c3048b2c86802981696ca7e196752a661a027d3f11b8b5edece84e049` were read-only qualified immediately before the upload stage. The active Google account name is not technically verified by the RPC path; `hoangbsea` is Owner-attested from login.

EXTERNAL_EFFECTS: one durable reference-upload reservation, with one attempted upload path; whether an HTTP POST reached Flow or succeeded is **unknown**. Reservation ID `refup_1521a9ea3a8582852abbe2b97bf8de4df2ddba6cb689df67c04e06b26021e3ce`; `upload_attempts=1`, `state=RESERVED`, `media_id=NULL`, provider media SHA `NULL`. Flow generation submissions: 0; Seedance generations: 0; billing changes: 0. No second upload, provider readback after the gate, provider switch, or workaround occurred.

QC / SELECTED_TAKES / ASSEMBLY / AUTOEDIT_HANDOFF: not reached. No visual or human approval is claimed. No AutoEdit change.

REGRESSION: focused 17 passed; full 186 passed; compileall passed; `git diff --check` passed. Independent read-only review found no remaining prewrite code blocker after fixes, while noting live behavior and Owner acceptance remain unverified.

SOT_FILES_CHANGED: none. SECRETS_COMMITTED: none. Live runtime SQLite and reference copy remain ignored local files.

NEXT: Owner must apply the existing ambiguity procedure and provide an evidence-backed resolution for the reserved upload. The controller must not retry upload or start either generation from this state. If the upload is proven and a verified provider media ID/readback can be safely bound under Owner direction, resume this exact reference lineage; otherwise stop without manufacturing a new upload authorization.
