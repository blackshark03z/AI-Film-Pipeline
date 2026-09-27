# SLICE-0008 editorial architecture decision

Decision recorded before implementation against `EditManifestV1`, the frozen editorial SoT, installed tools, and the one approved real SelectedTake. The schema is the canonical editorial record; runtime render metadata is derived evidence.

| Option | Availability | Strength | Weakness | Decision |
| --- | --- | --- | --- | --- |
| OPTION_A_MANIFEST_ONLY | Root `EditManifestV1` schema exists | Small, provider-neutral, exact intent | No actual media assembly proof | Select as canonical state, insufficient alone |
| OPTION_B_FFMPEG_CONCAT | FFmpeg 9.0.1 installed; AutoVideoPipeline has segment/concat examples | Fast remux when source streams and untrimmed boundaries are compatible | Stream copy cannot promise frame-accurate arbitrary trims or mixed-stream behavior | Select only for exact full-clip single-source remux |
| OPTION_C_FFMPEG_FILTERGRAPH | FFmpeg 9.0.1 has libx264/AAC | Precise source trims, explicit resolution/frame-rate/audio normalization and ordered concat | Re-encode cost and complexity | Select for trimmed or multi-clip rough cuts |
| OPTION_D_EDL | Text export possible, no current importer proof | Familiar simple interchange | Weak metadata, timecode constraints | Defer |
| OPTION_E_FCPXML_RESOLVE | No existing Film export or proven Resolve import path | Richer editor handoff | Version and import-edge complexity | Defer; may derive later |
| OPTION_F_OTIO | Python package absent; frozen SoT calls it optional | Portable timeline exchange | New dependency without current need | Defer |
| OPTION_G_RESOLVE_SCRIPTING | Resolve not on PATH; finishing truth remains Resolve | Direct editor integration | Runtime coupling and hard-to-test side effects | Defer |
| OPTION_H_REMOTION | Exists in AutoVideoPipeline, not this Film runtime | Programmable browser graphics | Browser/compositor/encoder overhead for immutable video clips | Reject for V1 rough cut |

## Smallest sufficient composition

`SelectedTake → EditManifestV1 → validated local source resolution → deterministic render plan → FFmpeg → validated rough-cut evidence`. `EditManifestV1` remains canonical, with no FFmpeg flags, absolute paths, or machine IDs in the manifest identity. The ID hashes project ID plus ordered clip intent (`order`, `shot_id`, `selected_take_id`, `asset_id`, `source_in_s`, `source_out_s`, `target_duration_s`, `notes`). Runtime validates exact SelectedTake, final `QCReport=pass`, Asset, GenerationAttempt and ShotSpec links and current bytes before rendering.

Orders must be exactly `1..N` as supplied; malformed order is rejected, never silently sorted. Source intervals are half-open `[source_in_s, source_out_s)`, with absent out meaning the media end. `target_duration_s` is validation intent, not retiming. No implicit speed change. Bounds must stay within actual media duration; floating container timestamps receive a documented `0.05s` validation tolerance, not permission to read past media. A target must agree with the resolved trim within `0.05s` or render is refused.

For the real full-source one-clip cut, stream-copy remux preserves both existing H.264 video and AAC audio without image/audio re-encode. For trims or multiple clips, a compact filtergraph trims each input, resets timestamps, normalizes to an explicit output profile (first clip's resolution and frame rate; yuv420p, H.264; audio at 48 kHz stereo AAC when every source has usable audio), and concatenates in manifest order. A mixture of audio-bearing and silent clips is rejected in V1 instead of silently dropping or fabricating a stream. Source audio is preserved when present. The output is an implementation rough cut, not the final master.

`RESOLVE_HANDOFF = EDIT_MANIFEST_ONLY`. No EDL/FCPXML/OTIO or destructive Resolve action is justified by one take. No PickupRequest is created because no missing editorial requirement is evidenced. Editorial reproducibility means the same canonical manifest resolves to the same ordered sources, trims, and declared render policy; encoder output bytes are validated and hashed but not claimed identical across FFmpeg versions/platforms.
