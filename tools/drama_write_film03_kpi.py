"""Write docs/drama/film03/film03_kpi.json and the film02 comparison."""
import json
from pathlib import Path

from film_pipeline.drama.kpi import DefectRecord, FilmKPI

D = DefectRecord
kpi = FilmKPI(
    film_id="film03_front_desk", generations_planned=16,
    # 19 charged (16 accepted + 3 takes made without their start frame) and
    # about 12 provider blocks, refunded by Flow; the block count before the
    # session break is reconstructed from the rejected take records
    generations_sent=31, generations_blocked=12,
    generations_first_pass_accepted=13,
    # 19 charged x 12; blocked jobs refunded; images 0 credits
    credits_total=228, credits_investigation=36,
    usable_seconds=128, rerenders=3,
    defects=[
        D(generation_id="SC02_g2/SC03_g1/SC07_g2", category="TOOLING",
          stage_missed="flow_send picker click (scrollIntoView on a cdk "
                       "virtual list recycles <img> nodes: the click took a "
                       "neighbour, slot empty or film02's kitchen frame)",
          fixed_by="no programmatic scroll; wheel the list, click only where "
                   "elementFromPoint hits the token; --start-file pixel "
                   "check of the filled slot before paying"),
        D(generation_id="SC05_g2..SC07_g1", category="TOOLING",
          stage_missed="Custody (a failed job's one 'new' tile was an older "
                       "take's re-issued thumbnail; saved as four duplicates)",
          fixed_by="video kept only on a network prompt bind (UNBOUND "
                   "otherwise); manual accept needs a unique start-frame "
                   "match"),
        D(generation_id="SC03_g1/SC03_g2/SC06_g1/SC06_g2", category="PROVIDER_BLOCK",
          stage_missed="Provider moderation ('reputational risk / misrepresent "
                       "current events' on police + race subject)",
          fixed_by="video prompts drop race words (stills keep them); "
                   "repeated blocks pass with 'police' removed from the "
                   "prose (.soft.txt), dialogue unchanged"),
        D(generation_id="start_SC05_g1/start_SC06_g2", category="IDENTITY",
          stage_missed="Start-frame still (NORA rendered in uniform for "
                       "KESSLER)",
          fixed_by="tag_layout.check_still_identity gate on 0-credit stills"),
        D(generation_id="SC01_g1", category="SUBTITLE",
          stage_missed="Tag plan (three tags on a wide master: two faces too "
                       "small to recognise, tags over the first line)",
          fixed_by="each character tagged on his first close shot before "
                   "his line (intro needed_by)"),
        D(generation_id="stills", category="TOOLING",
          stage_missed="Batch script (PYTHONPATH with ':' on Windows: start "
                       "frames ran without characters)",
          fixed_by="PYTHONPATH 'src;tools'"),
    ],
    notes=["route: 0-credit stills (3 characters, 2 plates, 16 start frames) "
           "-> 16 x 8 s start-frame videos",
           "story: original script on the source SRT's motif (no names, "
           "events or lines copied)",
           "all 16 accepted takes match their start frame (mean grey diff "
           "4-18 at 64x36; other stills >= 40)",
           "SC02_g2 accepted by start-frame match (network bind missed; "
           "diff 14.1 vs next 52.0)"],
)
root = Path(__file__).resolve().parents[1]
data = kpi.model_dump(mode="json")
data["derived"] = {
    "first_pass_usable_rate": kpi.first_pass_usable_rate,
    "credits_per_usable_second": kpi.credits_per_usable_second,
    "rerenders_per_100s": kpi.rerenders_per_100s}
film02 = json.loads((root / "docs/drama/film02/film02_kpi.json")
                    .read_text(encoding="utf-8"))["derived"]
data["vs_film02"] = {k: {"film02": film02[k], "film03": v}
                     for k, v in data["derived"].items()}
(root / "docs/drama/film03/film03_kpi.json").write_text(
    json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(data["vs_film02"])
