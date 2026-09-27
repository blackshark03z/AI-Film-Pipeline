# SLICE-0007 Owner approval and closure evidence

## Frozen authority

- Continuation work package: `SLICE_0007_OWNER_APPROVAL_WORK_PACKAGE.md`, Owner supplied and preserved byte-for-byte.
- Accepted candidate: `ad7624a2da578c57a64d43316feabaf95cb0a71d` on `slice-0007-qc-kernel`.
- Owner decision: explicit `APPROVE` of the real take. Authority is `human`; source is `owner_explicit_review`. Selection authority is `human_with_vlm_assist` because the approved review packet contained Gemini advisory findings. No confidence value or claimed viewing timestamp was added to the human evidence.
- No Flow Generate, Seedance Generate, media regeneration, or repair execution occurred in this continuation.

## Exact starting state and append-only transition

The existing SQLite lineage was freshly read before any write. It contained the exact Asset SHA-256 `c5014f1438dd8b4e1fbcd85df85fc5216bf91985b2164d0afbe5c3a0695abacf`, the prior report `qcr_fa1ef8247c17b733d2a010a7f090dc847404d3f9954b9163bbc521d4b8e9c86d` at `needs_human_review`, 20 QC evidence rows, and no human decision, SelectedTake, or RepairDecision. The original SLICE-0006 ProviderJob remained at `dispatch_count=1`; this continuation made no dispatch.

The finalization read the prior report and its exact evidence IDs, appended three human gate evidence records, persisted an explicit human decision, and derived a new immutable `QCReportV1` successor. It did not mutate the prior report or its evidence. The final report links to the prior report ID in its runtime record and reuses every prior evidence ID.

| Record | Exact identity / state |
| --- | --- |
| Human decision | `human_90e9295215e77bf416b1e78b1a15ad60b174f997f8b60923cd7261c4c54083a0`; `APPROVE`, `authority=human`, `source=owner_explicit_review` |
| Prior QCReport | `qcr_fa1ef8247c17b733d2a010a7f090dc847404d3f9954b9163bbc521d4b8e9c86d`; still `needs_human_review` |
| Final QCReport | `qcr_058bc4ede5bb77c9b0683c5788d76ad18c424a340328a4ce8d53382401c25904`; `pass`; 23 evidence IDs |
| SelectedTake | `take_a4f85e57ca88fe9629eb0c377ca6751711116c2f61425d9595d75ba09898647b`; `human_with_vlm_assist` |
| ShotSpec | `FLOW_CANARY_001` |
| GenerationAttempt | `attempt_600664fc7042d7e7c7321afe521b758f64da312f70d679552b027eb1b145a6b5` |
| Asset | `asset_c45abad93f33adbf43a6da62f3a04091b1cb712314ef209e6d84bea31a653c01`; byte hash verified |

## Fresh readback and idempotency

After committing the records, a fresh SQLite connection rederived both reports and the SelectedTake, verified the exact Asset bytes and all referenced review artifacts, and checked the exact Shot/Attempt/Asset/final-report links. Reapplying the same approval command produced the same human decision, final report and SelectedTake IDs. Counts remained 23 evidence, 1 human decision, 2 reports, **1** SelectedTake, **0** RepairDecisions. The original pending report remains readable. The code refuses a different SelectedTake for the same shot and rejects an Asset byte change before selection.

The deterministic focused suite now includes the Owner approval successor, historical evidence retention, exact link, fresh readback, rerun idempotency, wrong-SHA refusal, and legacy human-decision identity compatibility. Full regression: **126 passed**. The lightweight independent review confirmed the real lineage and identified legacy identity and generic-review source-provenance risks. Both were fixed and covered by focused tests. The reviewer found no remaining material issue before candidate freeze.

The SQLite database and MP4 remain local under ignored `projects/`; the candidate includes only secret-free lineage IDs, checksums, evidence and tests. No frozen Film SoT or root schema changed.
