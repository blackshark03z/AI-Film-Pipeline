"""Advisory dialogue STT check: scoring, report rows and problems with an injected transcriber."""
import json
from pathlib import Path

from film_pipeline.production import dialogue_stt as D
from film_pipeline.production.package import load_package

from test_production_gate_checks import clone


def test_normalize():
    assert D.normalize("We'll count it, mine's!") == ["well", "count", "it", "mines"]
    assert D.normalize("ten-fifty") == ["ten", "fifty"]


def test_score_line_cases():
    assert D.score_line("Pour it out. We'll count it.", "pour it out will count it")["recall"] == 1.0
    assert D.score_line("Fourteen eighty. Exactly the fare.", "fourteen eighty exactly the fair")["recall"] == 1.0
    assert D.score_line("You're coming too?", "you're coming to")["recall"] == 1.0
    s = D.score_line("Last train. Last shift.", "last train last show")
    assert s["recall"] < 1 and s["missing"] == ["shift"]
    assert D.score_line("Last train.", "")["recall"] == 0


def _pkg(tmp_path):
    root = clone(tmp_path)

    (root / "titles").mkdir(exist_ok=True)
    (root / "audio").mkdir(exist_ok=True)
    wav = root / "audio" / "dialogue.wav"
    wav.write_bytes(b"RIFF")
    cues = [{"event_id": "SC01_g2", "line_no": 15, "character": "THEO", "text": "One ticket to Halden. Please.",
             "abs_start_s": 0.2, "abs_end_s": 2.0},
            {"event_id": "SC06_g2", "line_no": 70, "character": "ANNA", "text": "Last train. Last shift.",
             "abs_start_s": 3.0, "abs_end_s": 5.0}]
    (root / "titles" / "titles.json").write_text(json.dumps({"cues": cues}), encoding="utf-8")
    (root / "audio" / "mix.json").write_text(json.dumps({"stems": {"dialogue": str(wav)}}), encoding="utf-8")
    return load_package(root)


def test_check_rows_and_file(tmp_path):
    pkg = _pkg(tmp_path)
    rep = D.check(pkg, transcriber=lambda wav, spans: ["one ticket to halden please", "last train last show"])
    assert [r["verdict"] for r in rep["rows"]] == ["PASS", "WARN"]
    assert [p["code"] for p in rep["problems"]] == ["DIALOGUE_STT_MISMATCH"]
    assert "missing: shift" in rep["problems"][0]["detail"]
    assert rep["summary"]["pass"] == 1 and rep["summary"]["warn"] == 1
    assert (Path(pkg.root) / "qc" / "dialogue_stt.json").is_file()


def test_check_unavailable(tmp_path):
    rep = D.check(_pkg(tmp_path), transcriber=lambda wav, spans: None)
    assert rep["rows"] == [] and rep["problems"][0]["code"] == "STT_UNAVAILABLE" and rep["engine"] is None


def test_a_stem_miss_gets_a_second_opinion_on_the_raw_take(tmp_path, monkeypatch):
    # film04 SC06_g2: the mixed-down stem read "last show", the take itself "last shift"
    pkg = _pkg(tmp_path)
    titles = Path(pkg.root) / "titles" / "titles.json"
    data = json.loads(titles.read_text(encoding="utf-8"))
    data["cues"][1].update(start_s=1.9, end_s=4.5)
    titles.write_text(json.dumps(data), encoding="utf-8")
    take = Path(pkg.root) / "take.mp4"
    monkeypatch.setattr(D, "_take_source", lambda pkg, event_id: (take, 0.5))
    seen = []

    def fake(wav, spans):
        seen.append((Path(wav).name, spans))
        return ["last train last shift"] if Path(wav) == take else ["one ticket to halden please", "last train last show"]
    rep = D.check(pkg, transcriber=fake)
    row = rep["rows"][1]
    assert row["verdict"] == "PASS" and row["source"] == "take" and row["heard"] == "last train last shift"
    assert seen[1] == ("take.mp4", [[1.4, 6.0]]) and rep["problems"] == []
