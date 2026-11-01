"""Write docs/drama/film02/film02_kpi.json and the film01 comparison."""
import json
from pathlib import Path

from film_pipeline.drama.kpi import DefectRecord, FilmKPI

D = DefectRecord
kpi = FilmKPI(
    film_id="film02_spare_key", generations_planned=6,
    # 6 accepted + SC02_g2 first try ("Không thành công", provider failure)
    generations_sent=7, generations_blocked=1,
    generations_first_pass_accepted=6,
    # conservative: the failed try counted as charged (7 x 12); images are
    # 0 credits (Nano Banana 2.1 in Flow)
    credits_total=84, credits_investigation=0,
    usable_seconds=48, rerenders=0,
    defects=[
        D(generation_id="SC03_g1", category="IDENTITY",
          stage_missed="Start-frame still prompt (prop on an out-of-frame "
                       "character drew a stranger)",
          fixed_by="still_prompt drops props on unseen people, 'Only X in "
                   "frame' for singles; caught on the 0-credit still"),
        D(generation_id="plates", category="SET",
          stage_missed="Plate generation (second time of day rendered as a "
                       "different room)",
          fixed_by="second plate rendered from the first plate attached"),
        D(generation_id="SC02_g2", category="PROVIDER_BLOCK",
          stage_missed="Provider (generic failure, no policy text)",
          fixed_by="one retry; flow_send recovers the start slot the failed "
                   "job left filled"),
        D(generation_id="preflight", category="TIMING",
          stage_missed="Scene bible (heading 'THAT MORNING (FLASHBACK)' "
                       "not grouped; return from flashback compared with the "
                       "flashback)",
          fixed_by="_tod_group reads words in the heading; LINEAR cut "
                   "anchors on the latest earlier story moment"),
        D(generation_id="prompt", category="SHOT_SCALE",
          stage_missed="Prompt compile (three-person master called a "
                       "two-shot)",
          fixed_by="coverage.describe: 'wide shot' for 3+ people"),
        D(generation_id="flow_send", category="TOOLING",
          stage_missed="Flow send step (image URLs not /asb/, gallery "
                       "scrolls in a container, picker items below the "
                       "fold)",
          fixed_by="token regex covers flow-content images, scroll every "
                   "container to top, scrollIntoView picker items"),
    ],
    notes=["route: 0-credit stills (3 characters, 2 plates, 6 start frames) "
           "-> 6 x 8 s start-frame videos",
           "usable_seconds: 3 scenes x 16 s, all first-pass takes",
           "prompt budget raised to 215 words on the start-frame route; "
           "all six followed their phase timing (speech inside the ACTION "
           "window)"],
)
root = Path(__file__).resolve().parents[1]
data = kpi.model_dump(mode="json")
data["derived"] = {
    "first_pass_usable_rate": kpi.first_pass_usable_rate,
    "credits_per_usable_second": kpi.credits_per_usable_second,
    "rerenders_per_100s": kpi.rerenders_per_100s}
film01 = json.loads((root / "docs/drama/film01_kpi.json")
                    .read_text(encoding="utf-8"))["derived"]
data["vs_film01"] = {k: {"film01": film01[k], "film02": v}
                     for k, v in data["derived"].items()}
(root / "docs/drama/film02/film02_kpi.json").write_text(
    json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(data["vs_film01"])
