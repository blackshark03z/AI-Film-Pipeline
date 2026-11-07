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


def test_a_frame_counts_only_when_the_label_has_contrast_of_its_own():
    """P11-02: a flat target (0) with a negative control (-30) used to pass because the difference was 30 >= 25."""
    assert not DL.frame_shows_label(0.0, -30.0, 25.0)
    assert not DL.frame_shows_label(24.9, -30.0, 25.0)
    assert not DL.frame_shows_label(40.0, 30.0, 25.0)   # the control stands out nearly as much: not the label
    assert DL.frame_shows_label(60.0, 5.0, 25.0)
    assert DL.frame_shows_label(25.0, 0.0, 25.0)


@needs_ffmpeg
def test_one_body_frame_without_the_label_fails_the_whole_check(tmp_path):
    """P11-02: 4 of 5 sampled frames used to pass; now every sampled frame, first to last, must show the label."""
    import subprocess
    root, report = pipeline(tmp_path)
    master = root / "media" / "cut" / "mixed.mp4"
    planned = json.loads(Path(report).read_text(encoding="utf-8"))["planned"]
    title_s, end_s = float(planned["title_s"]), float(planned["total_s"]) - float(planned["body_end_s"])
    good = DL.label_evidence(master, title_s, end_s)
    assert good["ok"] and good["positive"] == good["checked"] == 5 and good["missing_at_s"] == []
    last = planned["body_end_s"] - 0.3
    cut = tmp_path / "last_frame_clean.mp4"
    done = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(master), "-vf",
                           f"drawbox=x=0:y=660:w=200:h=60:color=black:t=fill:enable='gte(t,{last - 0.2:.3f})'",
                           "-c:a", "copy", str(cut)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    bad = DL.label_evidence(cut, title_s, end_s)
    assert not bad["ok"] and bad["positive"] == 4 and len(bad["missing_at_s"]) == 1 and bad["missing_at_s"][0] > last - 0.3
    assert "missing at" in bad["detail"]


@needs_ffmpeg
def test_delivery_records_the_disclosure_policy_and_a_policy_change_refuses_acceptance(tmp_path):
    """P11-05: the manifest and 07_delivery.json carry ai_label; changing film.json afterwards makes the archive stale."""
    from film_pipeline.production import gate_checks as GC
    root, report = pipeline(tmp_path)
    done, body = deliver(root, report)
    assert done.returncode == 0 and body["ok"], body
    manifest = json.loads((root / "delivery" / "MANIFEST.json").read_text(encoding="utf-8"))
    item = json.loads((root / "07_delivery.json").read_text(encoding="utf-8"))["delivery"]
    assert manifest["ai_label"] == "always" and item["ai_label"] == "always"
    assert not [i for i in GC.master_issues(load_package(root)) if "ai_label" in i]
    header_path = root / "film.json"
    data = json.loads(header_path.read_text(encoding="utf-8"))
    data["disclosure"] = {"ai_label": "title_card"}
    header_path.write_text(json.dumps(data), encoding="utf-8")
    assert [i for i in GC.master_issues(load_package(root)) if "built with ai_label 'always'" in i]
    with pytest.raises(ValueError, match="cannot accept"):
        DL.accept_delivery(load_package(root), "Owner")
    assert "owner_acceptance" not in (root / "07_delivery.json").read_text(encoding="utf-8")


@needs_ffmpeg
def test_the_9x16_version_carries_its_own_label_and_deliver_checks_it(tmp_path):
    """P11-01: the 16:9 label (x 24-130) is cut off by the 9:16 crop, so the portrait is burned and sampled on its own."""
    root, report = pipeline(tmp_path)
    vr = json.loads((root / "versions" / "versions.json").read_text(encoding="utf-8"))
    item = next(v for v in vr["versions"] if v["name"] == "portrait_9x16")
    assert item["ai_label"]["text"] == "AI-generated" and item["ai_label"]["start_s"] > 0
    portrait = root / item["file"]
    assert DL.label_evidence(portrait, float(item["ai_label"]["start_s"]), 4.0, portrait=True)["ok"]
    done, body = deliver(root, report)
    assert done.returncode == 0 and body["ok"], body
    assert body["ai_label"]["portrait_evidence"]["ok"] and body["ai_label"]["portrait_evidence"]["positive"] >= 3


@needs_ffmpeg
def test_title_card_mode_burns_no_label_on_the_9x16_either(tmp_path):
    root, _ = pipeline(tmp_path, ai_label="title_card")
    vr = json.loads((root / "versions" / "versions.json").read_text(encoding="utf-8"))
    item = next(v for v in vr["versions"] if v["name"] == "portrait_9x16")
    assert item["ai_label"] is None
    assert not DL.label_evidence(root / item["file"], 3.0, 4.0, portrait=True)["ok"]


@needs_ffmpeg
def test_a_9x16_version_without_the_label_blocks_the_delivery(tmp_path):
    from film_pipeline.production import versions as VS
    root, report = pipeline(tmp_path)
    path = root / "versions" / "versions.json"
    vr = json.loads(path.read_text(encoding="utf-8"))
    item = next(v for v in vr["versions"] if v["name"] == "portrait_9x16")
    master = root / "media" / "cut" / "mixed.mp4"
    VS.render_portrait(master, item["segments"], root / item["file"], 720, 24.0)  # an old version: no label overlay
    item["sha256"] = VS.sha256_file(root / item["file"])
    path.write_text(json.dumps(vr), encoding="utf-8")
    done, body = deliver(root, report)
    assert done.returncode == 1 and "AI_LABEL_NOT_BURNED_9X16" in codes(body, "BLOCK")
    assert "AI_LABEL_NOT_BURNED" not in codes(body, "BLOCK")  # the 16:9 master is fine
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
