import json
import io
import runpy
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import pytest

from film_pipeline.production import finish as F
from film_pipeline.production import preflight as P
from film_pipeline.production.runtime import atomic_json


def test_actual_cli_emit_supports_finish_capture_and_unicode():
    cli = runpy.run_path(str(Path(__file__).resolve().parents[1] / "tools/film.py"))
    output = io.StringIO()
    with redirect_stdout(output):
        cli["_emit"]({"step": "hoàn thiện"})
    assert json.loads(output.getvalue()) == {"step": "hoàn thiện"}


def test_finish_rejects_unlocked_edit_without_running_commands(tmp_path, monkeypatch):
    pkg = SimpleNamespace(root=tmp_path)
    monkeypatch.setattr(F, "evaluate_gates", lambda p: [])
    monkeypatch.setattr(F, "lock_status", lambda p: {"locked": False})
    result = F.finish(pkg, command=lambda a: pytest.fail("no command before lock"), dry_run=True)
    assert not result["ok"] and "locked EDL" in result["blocked"][0]
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("stop_at", ["grade", "titles", "mix", "mastercheck", "versions", "dialoguecheck", "deliver"])
@pytest.mark.parametrize("phase", ["before", "after"])
def test_finish_resumes_after_interruption_and_rechecks_cached_outputs(tmp_path, monkeypatch, stop_at, phase):
    pkg = SimpleNamespace(root=tmp_path)
    gates = [SimpleNamespace(gate=str(i), status="PASS" if i < 6 else "OWNER_PENDING") for i in range(1, 7)]
    monkeypatch.setattr(F, "evaluate_gates", lambda p: gates)
    monkeypatch.setattr(F, "lock_status", lambda p: {"locked": True, "fresh": True})
    monkeypatch.setattr(F, "_accepted_unchanged", lambda *a: False)
    monkeypatch.setattr(P, "check", lambda p: {"ok": True, "stt_python": None})
    monkeypatch.setattr(F.D, "verify_archive", lambda p: {"ok": True, "release_ready": True})
    calls = []
    interrupted = True
    def write(name, data):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, dict) or isinstance(data, list):
            atomic_json(path, data)
        else:
            path.write_bytes(data)
    def command(argv):
        nonlocal interrupted
        step = argv[0]
        calls.append(step)
        if step == stop_at and interrupted and phase == "before":
            interrupted = False
            raise RuntimeError("power lost during finishing")
        if step == "generators":
            write("generators.json", [])
        elif step == "grade":
            assert "--settings" not in argv
            write("color/color.json", {"plan": {"tolerance": 6}})
        elif step == "titles":
            for name in ("titles", "credits"):
                write(f"titles/{name}.json", {})
            write("titles/test.en.srt", b"caption")
            for name in ("titled_cut", "titled_cut.clean"):
                write(f"media/cut/{name}.mp4", b"verified-video")
                write(f"media/cut/{name}.cut.json", {})
        elif step == "mix":
            write("audio/mix.json", {"stems": {}})
            write("media/cut/mixed.mp4", b"mixed-video")
        elif step == "mastercheck":
            write("qc/master_qc.json", {})
        elif step == "versions":
            write("versions/portrait.mp4", b"portrait")
            write("versions/versions.json", {"versions": [{"file": "versions/portrait.mp4"}]})
            write("versions/metadata.json", {})
        elif step == "dialoguecheck":
            write("qc/dialogue_stt.json", {})
        elif step == "deliver":
            write("media/deliveries/v1/MANIFEST.json", {})
            write("07_delivery.json", {"delivery": {"manifest": "media/deliveries/v1/MANIFEST.json"}})
        if step == stop_at and interrupted:
            interrupted = False
            raise RuntimeError("power lost during finishing")
        print('{"ok":true}')
        return 0
    write("generators.json", [])
    with pytest.raises(RuntimeError, match="power lost"):
        F.finish(pkg, command=command)
    calls.clear()
    result = F.finish(pkg, command=command)
    order = ["grade", "titles", "mix", "mastercheck", "versions", "dialoguecheck", "deliver"]
    assert result["ok"] and calls == order[order.index(stop_at):]
    assert result["owner_acceptance_written"] is False
    before = (tmp_path / "media/finish-state.json").read_bytes()
    calls.clear()
    assert F.finish(pkg, command=command)["ok"] and calls == []
    assert (tmp_path / "media/finish-state.json").read_bytes() == before
    (tmp_path / "media/cut/titled_cut.clean.mp4").write_bytes(b"corrupted")
    assert F.finish(pkg, command=command)["ok"]
    assert calls[0] == "titles" and "grade" not in calls
    calls.clear()
    write("audio/mix_plan.json", {"duck_db": 14})
    assert F.finish(pkg, command=command)["ok"]
    assert calls[0] == "mix" and "titles" not in calls
    calls.clear()
    write("color/color_plan.json", {"tolerance": 8})
    assert F.finish(pkg, command=command)["ok"]
    assert calls[0] == "grade"
    calls.clear()
    write("titles/reframe.json", {"reframes": {}})
    assert F.finish(pkg, command=command)["ok"]
    assert calls[0] == "titles"
    calls.clear()
    monkeypatch.setattr(F, "_CODE_SHA", "new qualified finishing implementation")
    assert F.finish(pkg, command=command)["ok"] and calls[0] == "grade"


def test_preflight_blocks_low_space_without_contacting_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(P.shutil, "disk_usage", lambda p: SimpleNamespace(free=2 * 2**30))
    monkeypatch.setattr(P.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="tool version"))
    monkeypatch.setattr(P.urllib.request, "urlopen", lambda *a, **k: pytest.fail("offline check must not contact Flow"))
    result = P.check(tmp_path)
    assert not result["ok"] and len(result["issues"]) >= 2
    assert result["provider_session"] == "NOT_PROBED"
