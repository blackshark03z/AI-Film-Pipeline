# SLICE-0008 editorial evidence

## Boundary and decision

- Baseline: `9ed65e6000518daa8270cdffa38470e3300d724c` (SLICE-0007 closed). The exact SLICE-0008 work package is `CURRENT_SLICE.md`; the prior package is preserved as `SLICE_0007_WORK_PACKAGE.md`.
- The A–H solution comparison and selected composition were recorded in `SLICE_0008_EDITORIAL_ARCHITECTURE.md` before implementation. `EditManifestV1` is canonical; FFmpeg is a local derived rough-cut renderer. Resolve handoff is `EDIT_MANIFEST_ONLY`.
- No Flow, Seedance or other AI generation occurred. No QC decision was reopened, and no PickupRequest was created.

## Real approved source and persisted manifest

Fresh SQLite reads from ignored local `projects/flow_canary/slice0006/attempt_05/runtime.sqlite` resolve:

| Link | Exact identity |
| --- | --- |
| ShotSpec | `FLOW_CANARY_001` |
| GenerationAttempt | `attempt_600664fc7042d7e7c7321afe521b758f64da312f70d679552b027eb1b145a6b5` |
| ProviderJob | `job_62eab53994a2b8b1bde875b67f0068da97798a02f8aa75f8765d042edb07f0ea` |
| Asset | `asset_c45abad93f33adbf43a6da62f3a04091b1cb712314ef209e6d84bea31a653c01` |
| Source Asset SHA-256 | `c5014f1438dd8b4e1fbcd85df85fc5216bf91985b2164d0afbe5c3a0695abacf` |
| Final QCReport | `qcr_058bc4ede5bb77c9b0683c5788d76ad18c424a340328a4ce8d53382401c25904`, decision `pass` |
| SelectedTake | `take_a4f85e57ca88fe9629eb0c377ca6751711116c2f61425d9595d75ba09898647b` |
| EditManifest | `edit_52750848b473f76fd6e14f4007fa30b73a25082017e2d0fa191efcb44526ecc5` |

The manifest has exactly one clip at order 1, full source interval, target 8.0 seconds. The source file exists, is nonempty, matches its persisted SHA-256, and probes as 8.0 seconds, 1280×720, H.264/AAC at 24 fps. The manifest and clip rows are append-only in the same SQLite runtime DB. A new store instance reads them back and rechecks the exact SelectedTake, final passing QCReport, Asset, GenerationAttempt, ShotSpec, current source bytes, and trim bounds.

## Real rough cut

- Local ignored artifact: `projects/flow_canary/slice0008/rough_cuts/rough_cut_edit_52750848b473f76fd6e14f4007fa30b73a25082017e2d0fa191efcb44526ecc5.mp4`.
- Render receipt: `rough_16ebe466ebd8c2f458280422cb210e276d321f925d086188a76f908fe829f1d8`.
- Output SHA-256: `82b4c10f6facfc9e3e2c7bbd1e5a9bebea16795587d6ea66c0c8ae8f17537e54`.
- Media: 8.0 seconds, 1280×720, 24 fps, H.264 video, AAC audio. Method: single full-clip stream-copy remux, preserving the source audio. FFprobe and complete FFmpeg decode passed.
- The persisted render receipt stores the manifest ID, source Asset/SelectedTake IDs and hashes, output SHA-256, duration, dimensions, codecs, audio policy, FFmpeg version and render-plan fingerprint. A fresh store instance rechecks all source and output links, the plan fingerprint, media metadata and full decode. Re-running the entrypoint reads the same receipt without rendering a second artifact.
- The SQLite DB and MP4 remain ignored local runtime artifacts; the code, work package and safe evidence are committed. The rough cut is not a final master.

## Deterministic fixture proof

Three local FFmpeg color clips with AAC audio and differing dimensions/frame rates prove explicit normalization, ordered concat, source trims and 1.5-second accumulated timeline duration. Decoded midpoint RGB samples prove red → green → blue, and a reversed manifest produces a different render identity and starts blue. Invalid order, duplicate order, empty trim, out-of-bounds trim, implicit retime, missing file, wrong hash, missing SelectedTake, unapproved Asset and changed persisted source bytes are rejected. A separate fixture persists a passing-QC SelectedTake manifest and render, then reads both through a new SQLite store. A valid but wrong-duration media file is rejected at render-receipt persistence even when its hash and metadata are presented, so fresh readback revalidates output duration against manifest intervals. These fixtures prove multi-clip mechanics; the real approved project has only one clip.

Focused editorial tests: 4 passed. Full regression: 130 passed. No root schema or frozen SoT file changed. No credentials, cookie values, signed URLs or authorization headers are included in tracked evidence.

Independent reviewer examined implementation correctness and all eight solution options. One initial readback gap (output duration was not rechecked against manifest intervals after initial rendering) was fixed and covered by a regression test. Final independent review reported no remaining material finding.
