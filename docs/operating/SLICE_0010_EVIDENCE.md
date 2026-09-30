# SLICE-0010 evidence — two-shot production proven

## Authority and source

- Accepted baseline: `38402664e61a803ddab99e29e418605d086acac3`; initial Git tree clean.
- Authority: at most one fresh Flow Generate for `FLOW_CANARY_002`; no Seedance generation, billing change, purchase, subscription, or anti-bot bypass.
- Current result: `PROVEN` after explicit Owner `APPROVE`, passing final Shot 2 QC, a verified ordered two-clip rough cut, and a verified two-media Film producer package.
- No frozen Film SoT or root schema changed. Runtime database, credentials, project creation receipts, review media and downloaded video remain local under ignored paths.

## Reuse and planned sequence

The existing `ShotSpecV1`, prompt compiler, router, immutable path store, Flow/Veo transport, dispatch journal, exact passive output binding, official acquisition, QC kernel, rough-cut renderer, and `EditJobInputV0` exporter are reused. The only new creative input is `fixtures/flow_canary_shot2.json`. No canonical scene, graph, or orchestration entity was added.

Fresh readback of the accepted Shot 1 database and bytes verified:

| Item | Identity |
| --- | --- |
| ShotSpec | `FLOW_CANARY_001`, scene `FLOW_CANARY` |
| GenerationAttempt | `attempt_600664fc7042d7e7c7321afe521b758f64da312f70d679552b027eb1b145a6b5` |
| ProviderJob | `job_62eab53994a2b8b1bde875b67f0068da97798a02f8aa75f8765d042edb07f0ea`, succeeded, dispatch count 1 |
| Asset | `asset_c45abad93f33adbf43a6da62f3a04091b1cb712314ef209e6d84bea31a653c01` |
| Asset SHA-256 | `c5014f1438dd8b4e1fbcd85df85fc5216bf91985b2164d0afbe5c3a0695abacf`, current bytes matched |
| SelectedTake | `take_a4f85e57ca88fe9629eb0c377ca6751711116c2f61425d9595d75ba09898647b`, final passing QC read back |

Shot 2 is `FLOW_CANARY_002` in scene `FLOW_CANARY`, with `previous_shot_id=FLOW_CANARY_001`. ShotSpec hash: `67f44a94a6147c793210f8206cd643f914ebd0da1835755d1922415fd91b96be`. Pure sequence validation passes for exact predecessor, scene, spec versions, explicit environment fields, shared character versions and overlapping structured state. The free-form critical invariants are preserved as creative requirements, not parsed as semantic proof.

The existing compiler produced PromptPlan `plan_53c75edc2d07f701efd3bd085d874e2d2c589c929d10aa86d3ab205c0593743d`; routing selected Flow/Veo `route_d325474343e8b24720562e3a16da4e36430ef4c066d65fd3f9eae4bb621228c1`. Capability snapshot hash: `9e962dc554ff06d2876057796cb3e5b22030db296f1e66fe70c7e17fb1546d86`. Duration control is unsupported and degraded to textual intent.

## Flow effect and exact attribution

The Owner completed normal login in an isolated visible browser. The candidate session's read-only project discovery included Shot 1's exact project. One dedicated project was then created for an empty output correlation domain: `f6b40e79-d6f8-4354-80ae-c863260e96f5`. Its provider preflight was `READY / PROJECT_READBACK_READY`; Veo 3.1 Fast video mode, x1, enabled Generate with the exact preview prompt, and a stable passive baseline of zero identities were checked before reservation. No billing change was made.

The initial local run froze one Shot 2 GenerationAttempt and ProviderJob, then stopped before reservation because the preexisting database guard counted Shot 1's consumed job globally. The database readback showed Shot 2 `dispatch_count=0`, no dispatch facts and no Generate. The guard was narrowed to one consumed job **per shot**, preserving one-shot at-most-once semantics. The same frozen Shot 2 job was revalidated against the same project, empty baseline and prompt before its only reservation.

| Item | Readback |
| --- | --- |
| GenerationAttempt | `attempt_b8f17f205dd88555aa6908c95d628207be998295664b974057d4f4f92b64fffb` |
| ProviderJob | `job_e11a3cfc99c3a23e6e0efa8f7e618b062b6d03ccdf65f6e691f20d00b2caaa93` |
| Project binding hash | `5a5ab6209edfe035ba43202364902b686e1171885c03547ad162a6a4f254367c` |
| Dispatch | `dispatch_count=1`; one trusted normal Flow Generate click |
| Delivery semantics | `AT_MOST_ONCE_WITH_POSSIBLE_LOSS`; `submission_state=SUBMISSION_RESERVED` |
| Output identity | `response-tuple:78203d6c-16b9-4cae-a66c-a1f7de58275f:f6b40e79-d6f8-4354-80ae-c863260e96f5:977e16db-a6ea-4e51-81d9-14c2b7803aa9` |
| Asset | `asset_41994c57b392a2cb92ef7de44d663ee03f5f8358c07c18ac89162e6770a1061b` |
| Asset SHA-256 | `751b51622215f2ef23309bc568a7f84e81706308bac43e5ce9e562374fbdc057` |
| Official video | `projects/flow_canary/slice0010/outputs/c21af6d3f997d0b30c85c45e.mp4`; 4,384,591 bytes; 8.0s; 1280×720 |

The original bounded poll ended `RUNNING`, without authorizing a second submit. A fresh read-only project load found one exact passive output identity and corresponding tile, created one immutable binding, officially downloaded the output, and read back its complete ShotSpec → PromptPlan → RoutingDecision → GenerationAttempt → ProviderJob → Asset lineage. The current file hash and media probe match the persisted Asset. The journal contains `RESERVED`, `PROMPT_VERIFIED`, `CLICK_ARMED`, `TRUSTED_CLICK_OBSERVED`, `PROMPT_ACCEPTANCE_TRANSITION`, `REMOTE_IDENTITY_OBSERVED`, `IDENTITY_BOUND`, `DOWNLOAD_STARTED`, `DOWNLOAD_VALIDATED`, `ASSET_PERSISTED`. It contains no qualified provider-native Generate acceptance; a trusted click and observed output do not establish provider-native idempotency.

## QC and Owner gate

Deterministic technical QC passed, including full video decode. The pending review report was `qcr_49f23de86c288d40fe21414d21582b45ada2a8579b4cbb47fb679ccbe3177579`. An initial `gemini-3.8-flash` advisory returned unavailable or malformed output without controlling QC. A subsequent `gemini-2.5-flash` sampled-frame advisory produced seven findings, all advisory. Those findings examine Shot 2 only; the paired visual-world comparison remained with the Owner. No model confidence establishes temporal absence of people or exact geography.

Owner review material is local:

- `projects/flow_canary/slice0010/review/REVIEW_PACKET.md` (SHA-256 `7765485b0d83449d1a1bc2807453588eb4f31aabba8abc1f4fd0ec29dc408b78`)
- `projects/flow_canary/slice0010/review/shot1_vs_shot2_23cbb95a96372e2f3b7b7342b9c8e742764131ab18d496fc6b0a2f6c54a62277.jpg`
- Exact Shot 1 and Shot 2 videos linked from that packet, plus five representative frames from each shot.

The Owner explicitly answered **APPROVE** to the paired review question covering Shot 2 visual quality, continuity with Shot 1, and editorial usability. Human decision `human_f8e9c4a420eaabe4c0c542f293143b69330619aa7fe31cdd0b720f1ab25acc58` produced final passing report `qcr_45f3427566a3dca15b46410821349951055047b7343445e5bc15e4e613d57eda` and exactly one Shot 2 SelectedTake `take_971a99fe03f6b4924d943ecd4a2a04fdc006a55972949daa0c8417ed054287c0`. Selection authority is `human_with_vlm_assist`: the VLM was advisory; the Owner decided. Repeating finalization returned the same identities. Fresh QC and Asset readback passed. The existing Shot 1 SelectedTake and Asset were reread unchanged.

The observed review supports plausible empty, rainy, reflective visual-world continuity and a wide-to-insert cut. The independent reviewer noted that the contact sheet cannot establish exact physical geography. Structural sequence compatibility, observed visual review, and Owner approval remain distinct evidence.

## Two-shot assembly and Film producer handoff

- Ordered EditManifest: `edit_2a8fab758efc4615714d2efb093f897dbb37e19f246e51707e8d0d4cf2dccdb4`, with `FLOW_CANARY_001` then `FLOW_CANARY_002` and their exact approved SelectedTakes. Both clips resolve through passing QC, Asset, GenerationAttempt, and ShotSpec.
- Rough-cut receipt: `rough_6ab8123068b424bafc8e92c352f43d46291b5b594c0d15419aa77531fd1859f4`; file `projects/flow_canary/slice0010/rough_cut/rough_cut_edit_2a8fab758efc4615714d2efb093f897dbb37e19f246e51707e8d0d4cf2dccdb4.mp4`; SHA-256 `2c2d2461e71c4f806dadb4d083b67af611f3bc16ff04d4ce906a94a2c5cabba4`; 16.0 s, 1280×720, H.264 video, AAC audio, source-audio preservation policy, full decode passed. Manifest and render receipts read back from persisted state.
- `EditJobInputV0 0.1.0` package: `projects/flow_canary/slice0010/autoedit_package`; job `editjob_52c1efae93afb39d3027736e746268979619574598a71a34de9ed2462044a8d8`; package `editpkg_dc504b1f0c96ac8873eb9536c788a5ca8dd81bb97ff6e9246ea92dd7137f178c`. It has two real, SHA-verified, root-relative referenced media entries, an ordered `EditManifestV1` suggestion, and Film provenance for both shots. Producer package validation and media readback passed with the explicit `film_workspace` root bound to `projects/flow_canary`.
- Before rendering, the slice-specific assembly readback requires the exact frozen Shot 2 spec, exact predecessor, paired Shot 1 evidence in the pending QC report, and the explicit Owner approval successor. An ordinary single-shot passing SelectedTake is rejected by a focused synthetic test.

## Validation and review

- Focused SLICE-0010 tests: 13 passed. Full suite: 167 passed. `compileall src tests` and `git diff --check` passed.
- Independent review found two material approval/assembly bypasses; both were closed. It confirmed that one accepted older real shot plus this one new real shot legitimately proves the first two-shot vertical, while exact geography remains unproven. The dispatch journal and one-per-shot reservation preserve the one-submit bound.
- No new canonical scene entity, frozen SoT change, AutoEdit implementation change, Seedance generation, billing change, or second Flow Generate.
