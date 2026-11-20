"""Off-frame protection (2026-11-19 production defaults): film.json `defaults_version`, `preflight.offframe_protection`,
the shared leak check, its use in the PreSendCritic and in generate, and the guarantee that old films keep their prompts."""
import json
from pathlib import Path

import pytest

from film_pipeline.agentic import PreSendCritic
from film_pipeline.cli import scaffold
from film_pipeline.production import generate as G
from film_pipeline.production.interaction import offframe_leaks, protection_on, spoken_texts
from film_pipeline.production.package import FilmHeader, load_package, resolve_offframe_protection
from film_pipeline.production.plan import plan_package

from test_production_generate import backlog, codes, still
from test_production_interaction import off_frame

ROOT = Path(__file__).resolve().parents[1]
OLD_FILMS = ("film06_six_am", "film07_first_shift", "film08_chain_of_custody")
LISTS = ("safeguard_scenes", "clear_eyeline_scenes", "listener_unplaced_scenes", "de_personify_off_frame",
         "interperson_no_touch_ids")


def _configure(root, *, version=None, protection="absent", sfx=None):
    """Set film.json defaults_version, preflight.offframe_protection (True/False/None, "absent" = no key) and SC02_g1's sfx."""
    header = json.loads((root / "film.json").read_text(encoding="utf-8"))
    if version is not None:
        header["defaults_version"] = version
    (root / "film.json").write_text(json.dumps(header), encoding="utf-8")
    pre = json.loads((root / "03_preprod.json").read_text(encoding="utf-8"))
    if protection != "absent":
        pre["preflight"]["offframe_protection"] = protection
    (root / "03_preprod.json").write_text(json.dumps(pre, indent=2), encoding="utf-8")
    if sfx:
        shots = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
        next(g for g in shots["generations"] if g["generation_id"] == "SC02_g1")["sfx"] = sfx
        (root / "04_shots.json").write_text(json.dumps(shots, indent=2), encoding="utf-8")
    return root


def _video(root, gid="SC02_g1"):
    plan_package(load_package(root), root / "media" / "plan", storyboard=False)
    return (root / "media" / "plan" / "prompts" / f"{gid}.txt").read_text(encoding="utf-8").strip()


def _decl(pkg, gid="SC02_g1"):
    return next(g for g in pkg.typed["shots"].generations if g.generation_id == gid)


# --- defaults and resolution ---------------------------------------------------------------------------------------

def test_header_defaults_to_version_1_and_scaffold_writes_2(tmp_path):
    header = dict(film_id="f", title="t", profile="drama")
    assert FilmHeader(**header).defaults_version == 1
    with pytest.raises(ValueError):
        FilmHeader(**header, defaults_version=3)
    root = scaffold("newfilm", "drama", tmp_path, None)
    assert load_package(root).header.defaults_version == 2


@pytest.mark.parametrize("explicit, version, effective", [(None, 1, False), (None, 2, True), (False, 2, False),
                                                           (True, 1, True)])
def test_effective_protection_resolution(tmp_path, explicit, version, effective):
    assert resolve_offframe_protection(explicit, version) is effective
    root = _configure(off_frame(tmp_path), version=version, protection=explicit)
    pre = load_package(root).typed["preprod"]
    assert protection_on(pre) is effective
    if effective:  # spelled out once at load: every scene id in every list, object gaze neutral
        for name in LISTS:
            assert set(pre.scenes) <= set(getattr(pre.preflight, name)), name
        assert pre.preflight.object_gaze_neutral_eyeline is True
    else:
        assert all(getattr(pre.preflight, name) == [] for name in LISTS)
        assert pre.preflight.object_gaze_neutral_eyeline is False


# --- prompts and the leak check ------------------------------------------------------------------------------------

def test_protection_removes_the_off_frame_name_from_a_single_and_off_keeps_it(tmp_path):
    off = _video(_configure(off_frame(tmp_path / "off"), version=1))
    on = _video(_configure(off_frame(tmp_path / "on"), version=2))
    assert "young man" in off.lower()
    assert "THEO" not in on and "young man" not in on.lower() and "off-screen" in on
    pkg_off, pkg_on = load_package(tmp_path / "off" / "film"), load_package(tmp_path / "on" / "film")
    assert offframe_leaks(pkg_off.typed["preprod"], _decl(pkg_off), off) == ["the young man"]
    assert offframe_leaks(pkg_on.typed["preprod"], _decl(pkg_on), on) == []


def test_quoted_dialogue_is_not_a_leak(tmp_path):
    pkg = load_package(off_frame(tmp_path))
    pre, decl = pkg.typed["preprod"], _decl(pkg)
    assert offframe_leaks(pre, decl, "Close-up of the woman. Eyes on THEO.") == ["THEO", ]
    for quoted in ('MARA says: "THEO, wait."', "MARA says: “THEO, wait for the young man.”"):
        assert offframe_leaks(pre, decl, f"Close-up of the woman. {quoted} Quiet room.") == []
    # outside the quotes still counts
    assert offframe_leaks(pre, decl, 'MARA says: "wait." She looks at THEO.') == ["THEO"]
    # start-frame style writes the line unquoted, names turned into handles: cut it out by its script text
    assert offframe_leaks(pre, decl, "The woman says in English: the young man should wait. Quiet room.") == ["the young man"]
    assert offframe_leaks(pre, decl, "The woman says in English: the young man should wait. Quiet room.",
                          spoken=["THEO should wait."]) == []
    # only a shot with exactly one visible character is checked
    multi = decl.model_copy(update={"visible": ["MARA", "THEO"]})
    assert offframe_leaks(pre, multi, "Eyes on THEO.") == []


def test_spoken_texts_follow_the_shot_dialogue(tmp_path):
    pkg = load_package(off_frame(tmp_path))
    decl = _decl(pkg)
    assert decl.dialogue and len(spoken_texts(pkg, decl)) == len(decl.dialogue)


# --- generate and critic ---------------------------------------------------------------------------------------------

LEAKY_SFX = ["THEO shifts his weight beside the camera"]  # sfx is not scrubbed: a prompt part that still names the listener


def _dry_run(tmp_path, version):
    root = _configure(off_frame(tmp_path), version=version, sfx=LEAKY_SFX)
    pkg = load_package(root)
    plan_package(pkg, root / "media" / "plan", approve_storyboard="owner", storyboard=False)
    return G.generate(pkg, "SC02_g1", dry_run=True, stills_dir=still(tmp_path, "SC02_g1"), backlog=backlog(tmp_path))


def test_generate_dry_run_blocks_a_leak_only_when_protection_is_on(tmp_path):
    on = _dry_run(tmp_path / "on", version=2)["payload"]
    blocker = next(b for b in on["blockers"] if b["code"] == "CROSS_ATTENTION_LEAK")
    assert blocker["live_only"] is False and "the young man" in blocker["detail"]
    off = _dry_run(tmp_path / "off", version=1)["payload"]
    assert "CROSS_ATTENTION_LEAK" not in codes(off)


def test_generate_dry_run_of_a_clean_protected_single_has_no_leak_blocker(tmp_path):
    root = _configure(off_frame(tmp_path), version=2)
    pkg = load_package(root)
    plan_package(pkg, root / "media" / "plan", approve_storyboard="owner", storyboard=False)
    done = G.generate(pkg, "SC02_g1", dry_run=True, stills_dir=still(tmp_path, "SC02_g1"), backlog=backlog(tmp_path))
    assert "CROSS_ATTENTION_LEAK" not in codes(done["payload"])


@pytest.mark.parametrize("version, severity", [(2, "BLOCK"), (1, "WARN")])
def test_critic_leak_is_a_block_with_protection_and_a_warning_without(tmp_path, version, severity):
    root = _configure(off_frame(tmp_path), version=version, sfx=LEAKY_SFX)
    pkg = load_package(root)
    plan_dir = root / "media" / "plan"
    plan_package(pkg, plan_dir, storyboard=False)
    res = PreSendCritic().inspect(pkg, plan_dir=plan_dir, generation_id="SC02_g1")
    leak = [f for f in res["findings"] if f["code"] == "CROSS_ATTENTION_LEAK_RISK"]
    assert [f["severity"] for f in leak] == [severity]
    assert res["ok"] is False  # (the start still is not approved here either)


# --- old films keep their prompts --------------------------------------------------------------------------------------

@pytest.fixture(scope="module", params=OLD_FILMS)
def old_film_prompts(request, tmp_path_factory):
    root = ROOT / "films" / request.param
    if not (root / "takes" / "index.json").is_file():
        pytest.skip(f"{request.param} package not present")
    out = tmp_path_factory.mktemp(request.param)
    pkg = load_package(root)
    plan_package(pkg, out, takes_dir=root / "takes", storyboard=False)
    return root, pkg, {p.stem: p.read_text(encoding="utf-8") for p in (out / "prompts").glob("*.txt")}


def test_old_films_are_version_1_with_protection_off(old_film_prompts):
    _, pkg, _ = old_film_prompts
    assert pkg.header.defaults_version == 1 and not protection_on(pkg.typed["preprod"])


def test_old_films_prompt_hashes_match_their_accepted_takes(old_film_prompts):
    from film_pipeline.production.gate_checks import _prompt_rebind_issue
    from film_pipeline.production.takes import TakeEntry, sha256_text
    root, pkg, prompts = old_film_prompts
    version = {g.generation_id: g.version for g in pkg.typed["shots"].generations}
    index = json.loads((root / "takes" / "index.json").read_text(encoding="utf-8"))["takes"]
    accepted = [t for t in index if t["status"] == "ACCEPTED" and t.get("shot_version") == version.get(t["generation_id"])]
    assert accepted, "the film has accepted takes of the current shot version"
    stale = []
    for t in accepted:
        current = sha256_text(prompts[t["generation_id"]].strip())
        if current != t["prompt_sha256"] and _prompt_rebind_issue(root, TakeEntry.model_validate(t), current) != "":
            stale.append(t["take_id"])
    assert stale == []
