"""010C: append late-observed protocol facts (unwatermarked URLs, credit
economy, video-mode default duration) to the L4/L5 evidence artifacts."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_010c_dola_fullstack"
sys.path.insert(0, str(ROOT / "tools"))


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()

    protocol_path = PKG / "V2_010C_CURRENT_PROTOCOL.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["late_observed_facts"] = {
        "appended_at": now,
        "video_mode_default_duration": "the composer 動画を作成 mode "
            "dispatches at the 10s default even when the prompt text says "
            "5-second (observed: F2A prompt said 5-second, output 10.08s)",
        "credit_economy": {
            "observed_costs": {"5s_video": 1, "10s_video": 2,
                               "image_generation": "UNKNOWN (non-video)"},
            "evidence": "provider refusal message on F2B: 2 credits needed "
                        "for the 10s-class parameters, 1 remaining today "
                        "(consistent with 4/day: M2 5s=1 + F2A 10s=2 → 1 "
                        "left)",
            "refusal_is_pre_generation": "the provider refuses BEFORE any "
                                         "generation; no video credits are "
                                         "spent on a refusal"},
        "unwatermarked_outputs": {
            "fact": "the creation video object carries unwatermarked URL "
                    "variants (245 'unwatermarked' mentions in the F2A "
                    "capture); the 010C adapter took video.download_url "
                    "(watermarked 'Dola AI' corner mark)",
            "consequence": "production adapter should expose the "
                           "unwatermarked variant selection (same creation "
                           "id, same lineage); Owner decides which variant "
                           "enters the canonical pipeline"},
        "direction_advisory_f2a": "worker advisory: F2A reads as a "
                                  "camera-facing approach rather than the "
                                  "frozen frame-left lateral travel; Owner "
                                  "visual read is authoritative"}
    protocol_path.write_text(json.dumps(protocol, indent=1,
                                        ensure_ascii=False), encoding="utf-8")

    diff_path = PKG / "V2_010C_PROTOCOL_DIFF.json"
    diff = json.loads(diff_path.read_text(encoding="utf-8"))
    diff["late_observed"] = {
        "appended_at": now,
        "credit_refusal_f2b": "explicit provider refusal (2 credits needed, "
                              "1 remaining) — deterministic, non-ambiguous, "
                              "no latch",
        "f2b_disposition": "STOPPED_PROVIDER_CREDIT_REFUSAL; no retry per "
                           "F2B=ONE authority; Owner may re-authorize a 5s-"
                           "class F2B in a fresh scope"}
    diff_path.write_text(json.dumps(diff, indent=1, ensure_ascii=False),
                         encoding="utf-8")
    print("late facts appended")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
