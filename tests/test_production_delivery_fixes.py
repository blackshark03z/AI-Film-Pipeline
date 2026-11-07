"""P10-03: structured generators (role + settings) and the AI label setting that the master is checked against."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from film_pipeline.production import deliver as DL
from film_pipeline.production import generators as G
from film_pipeline.production import titles as TI
from film_pipeline.production.edit import EditEvent, EditSection, TextLine
from film_pipeline.production.package import FilmHeader, load_package
from test_production_deliver import codes, deliver, needs_ffmpeg, pipeline
from test_production_versions import FILM03, run

FLOW = {"role": "video+audio", "name": "Google", "model": "Flow Omni 1.1 Flash", "settings": "360p, Khung hinh"}
IMAGE = {"role": "image", "name": "Google", "model": "Nano Banana 2.1", "settings": ""}


def gen_file(tmp_path, data):
    path = tmp_path / "generators.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ----------------------------------------------------------------------------- generators

def test_file_form_keeps_role_and_settings_and_the_string_form_is_role_less(tmp_path):
    records = G.load_generators_file(gen_file(tmp_path, [FLOW, IMAGE]))
    assert [(g.provider, g.model, g.role, g.settings) for g in records] == [
        ("Google", "Flow Omni 1.1 Flash", "video+audio", "360p, Khung hinh"), ("Google", "Nano Banana 2.1", "image", "")]
    plain = G.split_generators("Google Flow Omni 1.1 Flash; Other Tool")
    assert [g.role for g in plain] == ["", ""] and G.split_generators("  ") == []
    assert G.generators_line("Google Flow Omni 1.1 Flash") == "Google Flow Omni 1.1 Flash"  # the string form prints as before
    assert G.generators_line(records) == "Google Flow Omni 1.1 Flash (video+audio); Google Nano Banana 2.1 (image)"
    assert G.generators_line(None) == "" and G.generators_line([]) == ""


@pytest.mark.parametrize("data, message", [
    ({"role": "image"}, "non-empty JSON list"), ([], "non-empty JSON list"), (["x"], "not an object"),
    ([{**FLOW, "role": "camera"}], "role must be one of"), ([{**FLOW, "role": ""}], "role must be one of"),
    ([{**FLOW, "name": " "}], "needs a name"), ([{**FLOW, "color": "red"}], "unknown keys")])
def test_a_bad_generators_file_is_refused_with_the_reason(tmp_path, data, message):
    with pytest.raises(ValueError, match=message):
        G.load_generators_file(gen_file(tmp_path, data))


def test_missing_or_unreadable_generators_file(tmp_path):
    with pytest.raises(ValueError, match="generators file"):
        G.load_generators_file(tmp_path / "none.json")
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="generators file"):
        G.load_generators_file(tmp_path / "bad.json")


def test_credits_and_disclosure_name_the_role_of_each_generator(tmp_path):
    records = G.load_generators_file(gen_file(tmp_path, [FLOW, IMAGE]))
    pkg = load_package(FILM03)
    en = [t for t, _ in TI.credits_lines(pkg, "en", generators=records)[0]]
    vi = [t for t, _ in TI.credits_lines(pkg, "vi", generators=records)[0]]
    assert any(t.endswith("Google Flow Omni 1.1 Flash (video+audio); Google Nano Banana 2.1 (image)") for t in en)
    assert any("(image)" in t for t in vi)
    old = [t for t, _ in TI.credits_lines(pkg, "en", generators="Google Flow Omni 1.1 Flash")[0]]
    assert "Generated with AI: Google Flow Omni 1.1 Flash" in old
    disclosure = DL.build_disclosure(pkg, EditSection(events=[EditEvent(event_id="a", take_id="SC02_g1_t1")],
                                                      title=[TextLine(text="Generated with AI")]), records)
    assert [(g.role, g.settings) for g in disclosure.generators] == [("video+audio", "360p, Khung hinh"), ("image", "")]


# ----------------------------------------------------------------------------- the AI label setting

def header(**extra):
    return FilmHeader.model_validate({"film_id": "f", "title": "T", "profile": "drama", **extra})


def test_ai_label_defaults_to_always_and_accepts_only_the_two_modes():
    assert header().disclosure.ai_label == "always"
    assert header(disclosure={"ai_label": "title_card"}).disclosure.ai_label == "title_card"
    with pytest.raises(ValidationError):
        header(disclosure={"ai_label": "never"})
    assert load_package(FILM03).header.disclosure.ai_label == "always"  # the shipped films keep the strong setting


def test_disclosure_marks_the_label_always_on_only_in_always_mode():
    section = EditSection(events=[EditEvent(event_id="a", take_id="SC02_g1_t1")], title=[TextLine(text="Generated with AI")])
    pkg = load_package(FILM03)
    on = DL.build_disclosure(pkg, section, "Google Flow").visible_label
    assert on.watermark_always_on and on.watermark_text == "AI-generated" and on.text == "Generated with AI"
    off_pkg = load_package(FILM03).model_copy(update={"header": header(disclosure={"ai_label": "title_card"})})
    off = DL.build_disclosure(off_pkg, section, "Google Flow").visible_label
    assert not off.watermark_always_on and off.watermark_text == "" and off.text == "Generated with AI"


# ----------------------------------------------------------------------------- the master really carries it

@needs_ffmpeg
def test_default_render_burns_the_label_and_deliver_sees_it(tmp_path):
    root, report = pipeline(tmp_path)
    done, body = deliver(root, report)
    assert done.returncode == 0 and body["ok"], body
    check = body["ai_label"]
    assert check["mode"] == "always" and check["evidence"]["ok"] and check["evidence"]["positive"] >= 3
    disc = json.loads((root / "delivery" / "disclosure_16x9.json").read_text(encoding="utf-8"))
    assert disc["visible_label"]["watermark_always_on"] is True


@needs_ffmpeg
def test_title_card_mode_leaves_the_body_clean_and_the_detector_does_not_invent_a_label(tmp_path):
    root, report = pipeline(tmp_path, ai_label="title_card")
    master = root / "media" / "cut" / "mixed.mp4"
    assert not DL.label_evidence(master, 3.0, 4.0)["ok"]  # nothing burned: the detector says so
    done, body = deliver(root, report)
    assert done.returncode == 0 and body["ok"] and body["ai_label"] == {"mode": "title_card"}, body
    assert "AI_LABEL_NOT_BURNED" not in codes(body)


@needs_ffmpeg
def test_always_setting_with_a_master_that_has_no_label_blocks_the_delivery(tmp_path):
    root, report = pipeline(tmp_path, ai_label="title_card")  # rendered without the body label ...
    header_path = root / "film.json"
    data = json.loads(header_path.read_text(encoding="utf-8"))
    data["disclosure"] = {"ai_label": "always"}  # ... then the setting is raised to "always"
    header_path.write_text(json.dumps(data), encoding="utf-8")
    done, body = deliver(root, report)
    assert done.returncode == 1 and not body["ok"] and "AI_LABEL_NOT_BURNED" in codes(body, "BLOCK")
    assert not (root / "delivery").exists()


@needs_ffmpeg
def test_deliver_takes_a_generators_file_and_refuses_both_forms(tmp_path):
    root, report = pipeline(tmp_path)
    path = gen_file(tmp_path, [FLOW, IMAGE])
    done = run("deliver", "--film", str(root), "--cut-report", report, "--generators-file", str(path))
    assert done.returncode == 0, done.stdout
    disc = json.loads((root / "delivery" / "disclosure_16x9.json").read_text(encoding="utf-8"))
    assert [(g["role"], g["settings"]) for g in disc["generators"]] == [("video+audio", "360p, Khung hinh"), ("image", "")]
    both = run("deliver", "--film", str(root), "--cut-report", report, "--generators", "X Y", "--generators-file", str(path))
    assert both.returncode == 1 and "not both" in json.loads(both.stdout)["error"]
    bad = run("deliver", "--film", str(root), "--cut-report", report, "--generators-file", str(tmp_path / "none.json"))
    assert bad.returncode == 1 and "generators file" in json.loads(bad.stdout)["error"]
