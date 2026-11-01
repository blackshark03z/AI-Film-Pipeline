"""Write docs/drama/film01_kpi.json (figures from FILM01_LESSONS.md)."""
import json
from pathlib import Path

from film_pipeline.drama.kpi import DefectRecord, FilmKPI

D = DefectRecord
kpi = FilmKPI(
    film_id="film01_first_day", generations_planned=10,
    # 10 first-pass text-only sends + 4 SC03 rework sends
    generations_sent=14,
    # SC01_g2: 4 earlier blocks + probes T3, T5 (flow_block_rootcause.json)
    generations_blocked=6,
    generations_first_pass_accepted=8,
    credits_total=228, credits_investigation=60,
    usable_seconds=80, rerenders=4,
    defects=[
        D(generation_id="SC01_g2", category="PROVIDER_BLOCK",
          stage_missed="Provider route choice",
          fixed_by="preflight TEXT_ONLY route; refs on that route BLOCK"),
        D(generation_id="SC03_g1", category="IDENTITY",
          stage_missed="Prompt compile (look re-described per scene)",
          fixed_by="bible.CharacterLook locked text + preflight LOOK"),
        D(generation_id="SC03_g2", category="PROP_LOGIC",
          stage_missed="Script + generation split",
          fixed_by="ContinuityState + check_cross_cut + HandoffQC gating"),
        D(generation_id="SC03_g2", category="IDENTITY",
          stage_missed="Prompt compile (start-state character had no look)",
          fixed_by="preflight LOOK covers characters named by start state"),
        D(generation_id="film01_post", category="SUBTITLE",
          stage_missed="Post (cue timing from audio alone)",
          fixed_by="cues clamped to the speaking shot of the plan"),
        D(generation_id="film01_post", category="AUDIO",
          stage_missed="Post (single-pass loudnorm)",
          fixed_by="2-pass loudnorm + limiter"),
        D(generation_id="flow_send", category="TOOLING",
          stage_missed="Flow send step (overlay; stale tile downloaded)",
          fixed_by="dismiss overlays, SEND_FAILED, take is new only if sha "
                   "differs"),
    ],
    notes=["credits_total 228 = 60 investigation + 168 route "
           "(14 sends x 12)",
           "usable_seconds: 5 scenes x 16 s of accepted clips"],
)
out = Path(__file__).resolve().parents[1] / "docs/drama/film01_kpi.json"
data = kpi.model_dump(mode="json")
data["derived"] = {
    "first_pass_usable_rate": kpi.first_pass_usable_rate,
    "credits_per_usable_second": kpi.credits_per_usable_second,
    "rerenders_per_100s": kpi.rerenders_per_100s}
out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(data["derived"])
