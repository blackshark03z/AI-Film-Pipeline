"""P13-05: a shot can pin its end state with an approved end still, sent in Flow's end-frame slot."""
import json
from pathlib import Path

from film_pipeline.drama import ContinuityState
from film_pipeline.production import generate as G
from film_pipeline.production import stills as S
from film_pipeline.production import takes as T
from film_pipeline.production.gate_checks import PLAN_META
from film_pipeline.production.package import load_package
from film_pipeline.production.plan import END_FRAME_PREFIX, START_FRAME_PREFIX, START_PREFIX, plan_package, word_budget

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")
GID = "SC01_g2"        # film03: the letter ends folded on the desk
STILL = ("Edit the given image, the first frame of this shot. Change only this: the letter folded, on the desk. "
         "Pose at the end of the shot: she lays a folded letter on the desk. "  # the last phase: hands match the end
         "Keep everything else the same: framing, people, faces, clothes, light.")
NOT_END = ("SC01_g1", "SC03_g1")


def film(tmp_path, end_frame=(GID,), handles=None, approve=True, style="full"):
    root = tmp_path / "film"
    root.mkdir(parents=True)
    for name in FILES:
        (root / name).write_text((FILM03 / name).read_text(encoding="utf-8"), encoding="utf-8")
    shots = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
    for g in shots["generations"]:
        if g["generation_id"] in end_frame:
            g["end_frame"] = True
    (root / "04_shots.json").write_text(json.dumps(shots), encoding="utf-8")
    pre = json.loads((root / "03_preprod.json").read_text(encoding="utf-8"))
    pre["preflight"]["prompt_style"] = style
    for name, handle in (handles or {}).items():
        pre["characters"][name]["handle"] = handle
    (root / "03_preprod.json").write_text(json.dumps(pre), encoding="utf-8")
    header = json.loads((root / "film.json").read_text(encoding="utf-8"))
    header["budget"]["credits_estimate"] = 100
    (root / "film.json").write_text(json.dumps(header), encoding="utf-8")
    pkg = load_package(root)
    if approve:
        plan_package(pkg, root / "media" / "plan", approve_storyboard="owner")
    return pkg


def backlog(tmp_path):
    path = tmp_path / "backlog.md"
    path.write_text("# Loop backlog\n\nOWNER_GO_LIVE: NO\n", encoding="utf-8")
    return path


def stills(tmp_path, *names):
    folder = tmp_path / "stills"
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / f"{name}.png").write_bytes(f"png-{name}".encode())
    return folder


def accept(pkg, gid, n=1, version=1):
    log = T.load_log(pkg.root, pkg.header.film_id)
    log.takes.append(T.TakeEntry(take_id=f"{gid}_t{n}", generation_id=gid, prompt_sha256="a" * 64, route="r", model="m",
                                 credits=12.0, output_file="x.mp4", output_sha256="b" * 64, status="ACCEPTED",
                                 shot_version=version))
    T.save_log(pkg.root, log)


def codes(payload):
    return [b["code"] for b in payload["blockers"]]


def ready(tmp_path):
    pkg = film(tmp_path)
    accept(pkg, "SC01_g1")      # SC01_g2 starts from the end of SC01_g1
    return pkg


# -- continuity ---------------------------------------------------------------------------------------------------

def test_change_clauses_list_changed_props_then_changed_positions():
    start = ContinuityState(positions={"MAI": "at the desk", "HUNG": "by the door"},
                            props={"letter:": "in MAI's hand", "cup": "on the desk"})
    end = ContinuityState(positions={"MAI": "at the desk", "HUNG": "at the window"},
                          props={"letter:": "on the floor", "cup": "on the desk", "key": "in the lock"})
    assert end.change_clauses(start) == ["letter on the floor", "key in the lock", "HUNG at the window"]
    assert end.change_clauses(end) == []
    assert end.describe_change(start) == "Ends with letter on the floor; key in the lock, held to the last frame."
    assert start.describe_change(start) == ""


# -- plan ---------------------------------------------------------------------------------------------------------

def test_plan_writes_the_end_still_prompt_and_the_two_frame_prefix(tmp_path):
    pkg = film(tmp_path, style="start_frame", approve=False)
    out = Path(pkg.root) / "media" / "plan"
    result = plan_package(pkg, out, storyboard=False)
    assert (out / "stills" / f"end_{GID}.txt").read_text(encoding="utf-8") == STILL + "\n"
    assert not list(out.glob("stills/end_SC0[2-8]*")) and not (out / "stills" / "end_SC01_g1.txt").exists()
    prompt = (out / "prompts" / f"{GID}.txt").read_text(encoding="utf-8")
    assert prompt.startswith(END_FRAME_PREFIX) and not prompt.startswith(START_FRAME_PREFIX)
    assert (out / "prompts" / "SC01_g1.txt").read_text(encoding="utf-8").startswith(START_FRAME_PREFIX)
    gens = result.record["generations"]
    assert (out / "prompts" / "SC03_g1.txt").read_text(encoding="utf-8").startswith(START_FRAME_PREFIX)
    assert gens[GID]["end_still_words"] == len(STILL.split())
    assert all("end_still_words" not in v for g, v in gens.items() if g != GID)
    budget = json.loads((out / PLAN_META).read_text(encoding="utf-8"))["word_budget"][GID]
    assert budget["sections"]["prefix"] == len(END_FRAME_PREFIX.split())
    assert sum(budget["sections"].values()) == budget["words"]


def test_end_pose_replaces_the_last_phase_in_the_end_still(tmp_path):
    # film04 SC01_g1 v4: the HOLD phase ("the shutter does not move") is motion talk an image cannot show
    pkg = film(tmp_path, style="start_frame", approve=False)
    shots = json.loads((Path(pkg.root) / "04_shots.json").read_text(encoding="utf-8"))
    for g in shots["generations"]:
        if g["generation_id"] == GID:
            g["end_pose"] = "she stands at the desk, both hands flat beside the letter"
    (Path(pkg.root) / "04_shots.json").write_text(json.dumps(shots), encoding="utf-8")
    out = Path(pkg.root) / "media" / "plan"
    plan_package(load_package(pkg.root), out, storyboard=False)
    text = (out / "stills" / f"end_{GID}.txt").read_text(encoding="utf-8")
    assert "Pose at the end of the shot: she stands at the desk, both hands flat beside the letter. Keep" in text
    assert "lays a folded letter" not in text


def test_other_prompt_styles_keep_their_prefix(tmp_path):
    pkg = film(tmp_path, approve=False)          # prompt_style "full": the end frame changes the prompt prefix only in "start_frame"
    out = Path(pkg.root) / "media" / "plan"
    plan_package(pkg, out, storyboard=False)
    assert (out / "prompts" / f"{GID}.txt").read_text(encoding="utf-8").startswith(START_PREFIX)
    assert (out / "stills" / f"end_{GID}.txt").is_file()


def test_word_budget_counts_the_prefix_actually_used():
    assert word_budget({}, END_FRAME_PREFIX)["prefix"] == len(END_FRAME_PREFIX.split()) == 9


def test_end_still_uses_character_handles(tmp_path):
    # SC04_g2: ORTIZ ends by the trash bin, holding the smoothed letter
    pkg = film(tmp_path, end_frame=("SC04_g2",), handles={"ORTIZ": "the older man"}, approve=False)
    out = Path(pkg.root) / "media" / "plan"
    plan_package(pkg, out, storyboard=False)
    text = (out / "stills" / "end_SC04_g2.txt").read_text(encoding="utf-8")
    assert "ORTIZ" not in text and "the older man by the trash bin" in text


def test_end_frame_that_changes_nothing_is_a_plan_problem(tmp_path):
    pkg = film(tmp_path, end_frame=("SC03_g1",), approve=False)       # film03 SC03_g1: end state == start state
    out = Path(pkg.root) / "media" / "plan"
    result = plan_package(pkg, out, storyboard=False)
    gen = result.record["generations"]["SC03_g1"]
    issue = next(i for i in gen["issues"] if i["check"] == "END_FRAME")
    assert issue["severity"] == "BLOCK" and issue["detail"] == "end_frame set but the end state changes nothing"
    assert gen["verdict"] == "BLOCKED" and "end_still_words" not in gen
    assert "SC03_g1 preflight BLOCKED" in result.problems
    assert not (out / "stills" / "end_SC03_g1.txt").exists()
    assert "end:SC03_g1" not in S.still_prompts(pkg)


def test_a_film_without_end_frame_keeps_its_plan_output(tmp_path):
    pkg = film(tmp_path, end_frame=(), approve=False)
    out = Path(pkg.root) / "media" / "plan"
    result = plan_package(pkg, out, storyboard=False)
    assert all("end_still_words" not in v for v in result.record["generations"].values())
    assert not list((out / "stills").glob("end_*"))
    assert all(not k.startswith("end:") for k in S.still_prompts(pkg))


# -- generate -----------------------------------------------------------------------------------------------------

def test_end_frame_shot_needs_an_end_still_and_a_token(tmp_path):
    pkg = ready(tmp_path)
    payload = G.build_payload(pkg, GID, stills_dir=stills(tmp_path, f"start_{GID}"), start_token="tok:abc")
    assert codes(payload) == ["END_FRAME_MISSING", "END_TOKEN_MISSING"]
    assert next(b for b in payload["blockers"] if b["code"] == "END_TOKEN_MISSING")["live_only"]
    assert not payload["end_frame"]["exists"] and payload["end_frame"]["sha256"] == ""


def test_end_frame_payload_argv_route_and_receipt(tmp_path):
    pkg = ready(tmp_path)
    folder = stills(tmp_path, f"start_{GID}", f"end_{GID}")
    done = G.generate(pkg, GID, dry_run=True, stills_dir=folder, start_token="tok:abc", end_token="tok:xyz",
                      backlog=backlog(tmp_path))
    p = done["payload"]
    assert done["ready_to_send"] and p["blockers"] == []
    assert p["route"] == "start_frame+end_frame+Khung hinh"
    i = p["argv"].index("--end")
    assert p["argv"][i:] == ["--end", "tok:xyz", "--end-file", str(folder / f"end_{GID}.png")]
    assert p["argv"][p["argv"].index("--start"):i] == ["--start", "tok:abc", "--start-file",
                                                       str(folder / f"start_{GID}.png"), "--model",
                                                       "Omni 1.2 Flash", "--duration", "8"]
    assert p["end_frame"] == {"file": str(folder / f"end_{GID}.png"), "exists": True,
                              "sha256": T.sha256_text(f"png-end_{GID}")}
    assert any("end still is uploaded" in c for c in p["preconditions"])
    receipt = json.loads(Path(done["receipt"]).read_text(encoding="utf-8"))
    assert receipt["end_frame_sha256"] == p["end_frame"]["sha256"] and receipt["route"] == p["route"]
    bare = G.build_payload(pkg, GID, stills_dir=folder, start_token="tok:abc")   # no token: a placeholder in the argv
    assert bare["argv"][bare["argv"].index("--end") + 1] == G.PLACEHOLDER_END_TOKEN


def test_the_end_still_of_the_package_record_must_be_approved(tmp_path):
    from PIL import Image
    pkg = ready(tmp_path)
    key = S.end_key(GID)
    png = tmp_path / "e.png"
    Image.new("RGB", (8, 8), (40, 40, 40)).save(png)
    assert "END_FRAME_MISSING" in codes(G.build_payload(pkg, GID, stills_dir=None))
    S.register_still(load_package(pkg.root), key, png)
    assert "END_FRAME_NOT_APPROVED" in codes(G.build_payload(load_package(pkg.root), GID, stills_dir=None))
    S.approve_still(load_package(pkg.root), key, "Owner")
    payload = G.build_payload(load_package(pkg.root), GID, stills_dir=None)
    assert not {"END_FRAME_MISSING", "END_FRAME_NOT_APPROVED"} & set(codes(payload))
    assert payload["end_frame"]["file"].endswith(f"end_{GID}.png") and payload["end_frame"]["exists"]


def test_shots_without_end_frame_keep_payload_argv_and_receipt(tmp_path):
    pkg = film(tmp_path)
    folder = stills(tmp_path, "start_SC01_g1", f"end_{GID}")
    done = G.generate(pkg, "SC01_g1", dry_run=True, stills_dir=folder, start_token="tok:abc", end_token="tok:xyz",
                      backlog=backlog(tmp_path))
    p = done["payload"]
    assert "end_frame" not in p and "--end" not in p["argv"] and "--end-file" not in p["argv"]
    assert p["route"] == "start_frame+Khung hinh" and len(p["argv"]) == 12
    assert p["preconditions"] == ["Flow composer is on Omni 1.2 Flash, 360p, video mode (flow_send sets model and duration)",
                                  "the start still is uploaded to the Flow gallery (its tail is --start-token)",
                                  "GPM / Flow browser stays open; no cookies or captchas touched"]
    assert p["blockers"] == []                       # END_TOKEN_MISSING and END_FRAME_* concern end_frame shots only
    assert "end_frame_sha256" not in json.loads(Path(done["receipt"]).read_text(encoding="utf-8"))
