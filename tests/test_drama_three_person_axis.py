"""film08: three people on one set; only two hold the axis pair.

The centre person (HOLLIS) has no axis partner, so shot headers read
"close-up of HOLLIS looking none", and masters said "wide two-shot" while
three people were in frame.
"""
from film_pipeline.drama.axis import AxisBook, axis_record
from film_pipeline.drama.coverage import CoverageShot
from film_pipeline.production.interaction import ListenerAnchor
from film_pipeline.production.plan import _anchored_eyeline

BOOK = AxisBook.for_pair("SC01", "NAOMI", "ELI")


def _shot(coverage, subject, visible, eyelines=None):
    return CoverageShot(shot_id="SC01_S1", coverage=coverage, shot_size="CLOSE", subject=subject,
                        axis=axis_record(BOOK, "SC01_S1", visible, eyelines=eyelines))


def test_centre_single_takes_its_eyeline_from_the_shot():
    assert _shot("SINGLE", "HOLLIS", ["HOLLIS"], {"HOLLIS": "screen-right"}).describe(BOOK) == \
        "close-up of HOLLIS looking screen-right"


def test_unsided_single_without_eyeline_never_says_looking_none():
    text = _shot("SINGLE", "HOLLIS", ["HOLLIS"]).describe(BOOK)
    assert text == "close-up of HOLLIS" and "none" not in text
    assert _shot("REACTION", "HOLLIS", ["HOLLIS"]).describe(BOOK) == "silent close-up of HOLLIS"


def test_axis_pair_single_unchanged():
    assert _shot("SINGLE", "NAOMI", ["NAOMI"]).describe(BOOK) == "close-up of NAOMI looking screen-right"


def test_master_names_the_third_person():
    text = _shot("MASTER", "", ["NAOMI", "HOLLIS", "ELI"]).describe(BOOK)
    assert text == "wide shot, NAOMI left, ELI right, with HOLLIS also in frame"
    assert _shot("MASTER", "", ["NAOMI", "ELI"]).describe(BOOK) == "wide two-shot, NAOMI left, ELI right"


def test_eyeline_override_ignores_people_not_in_shot():
    rec = axis_record(BOOK, "S", ["HOLLIS"], eyelines={"ELI": "screen-left"})
    assert rec.eyelines == {"HOLLIS": "none"}


class _Decl:
    def __init__(self, subject, gaze, anchors):
        self.subject, self.gaze_target, self.listener_anchors = subject, gaze, anchors


def test_anchored_eyeline_follows_off_frame_side():
    off = lambda side: ListenerAnchor(mode="OFF_FRAME", side=side, placement="x stands off frame")
    assert _anchored_eyeline(_Decl("HOLLIS", "ELI", {"ELI": off("RIGHT")})) == {"HOLLIS": "screen-right"}
    assert _anchored_eyeline(_Decl("HOLLIS", "NAOMI", {"NAOMI": off("LEFT")})) == {"HOLLIS": "screen-left"}
    assert _anchored_eyeline(_Decl("HOLLIS", "NAOMI", {"NAOMI": off("BEHIND_CAMERA")})) == {}
    assert _anchored_eyeline(_Decl("HOLLIS", "ledger", {})) == {}


FILM08 = __import__("pathlib").Path(__file__).resolve().parents[1] / "films" / "film08_chain_of_custody"


@__import__("pytest").mark.skipif(not (FILM08 / "04_shots.json").is_file(), reason="film08 package not present")
def test_film08_prompts_have_one_consistent_eyeline(tmp_path):
    """Object-gaze shots dropped the lens eyeline; the centre person's singles name a side; masters name all three."""
    from film_pipeline.production.package import load_package
    from film_pipeline.production.plan import plan_package
    plan_package(load_package(FILM08), tmp_path, storyboard=False)
    prompts = {p.stem: p.read_text(encoding="utf-8") for p in (tmp_path / "prompts").glob("*.txt")}
    assert not [k for k, t in prompts.items() if "looking none" in t]
    for gid in ("SC09_g24", "SC10_g01", "SC11_g16"):
        assert "eyes go just past the lens" not in prompts[gid] and " looks at the " in prompts[gid], gid
    assert "with the older man also in frame" in prompts["SC01_g01"]
    assert not [k for k, t in prompts.items() if t.count("eyes go just past the lens") > 1]


def test_board_draws_the_unsided_centre_person(tmp_path):
    """film08 SC01_g03: HOLLIS's singles rendered as empty boards (only sided people were drawn)."""
    from PIL import Image
    from film_pipeline.drama.coverage import SceneUnit
    from film_pipeline.drama.storyboard import render_schematic_frame
    shot = _shot("SINGLE", "HOLLIS", ["HOLLIS"], {"HOLLIS": "screen-left"})
    unit = SceneUnit(scene_id="SC01", duration_s=6.0, shots=[shot], axis_book=BOOK)
    out = render_schematic_frame(unit, shot, tmp_path / "f.png", width=640)
    im = Image.open(out).convert("RGB")
    assert im.getpixel((320, 230)) != (238, 236, 230)  # a figure at frame centre, not background
