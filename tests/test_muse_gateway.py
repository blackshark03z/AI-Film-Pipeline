"""The manual Muse boundary must not manufacture sends, job IDs or accepted takes."""
import json
import subprocess
from types import SimpleNamespace

import pytest

from film_pipeline.production import muse_gateway as M, takes as T
from film_pipeline.production.money import money_ledger
from film_pipeline.providers.request import FrameRef, GenerationRequest
from film_pipeline.production.camera import CameraSetup


@pytest.fixture
def shot(tmp_path, monkeypatch):
    root = tmp_path / "film"
    root.mkdir()
    (root / "film.json").write_text('{"film_id":"probe","profile":"drama"}')
    (root / "04_shots.json").write_text('{"generations": []}')
    image = root / "start.png"
    image.write_bytes(b"test reference bytes")
    request = GenerationRequest(film_id="probe", generation_id="SC01_g1", take_id="SC01_g1_t1",
        prompt="One woman says: We closed an hour ago.",
        prompt_sha256=T.sha256_text("One woman says: We closed an hour ago."),
        duration_s=7, first_frame=FrameRef(path=str(image), sha256=T.sha256_file(image)),
        audio_mode="NATIVE_DIALOGUE", output=str(root / "unused.mp4"))
    payload = {"request": request.model_dump(), "shot_version": 1, "blockers": []}
    monkeypatch.setattr(M, "build_payload", lambda *a, **kw: payload)
    pkg = SimpleNamespace(root=root, header=SimpleNamespace(film_id="probe", rehearsal=False))
    return pkg, payload, image


def claim(pkg, folder):
    go = pkg.root / "backlog.md"
    go.write_text("OWNER_GO_LIVE: YES\n")
    return M.dispatch(pkg, folder, backlog=go)


@pytest.fixture
def clip(tmp_path):
    path = tmp_path / "download.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=24:d=0.5",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=0.5", "-c:v", "libx264", "-c:a", "aac",
                    "-shortest", str(path)], check=True, timeout=30)
    return path


def response(folder, clip):
    packet = json.loads((folder / "request.json").read_text())
    return {"request_id": packet["request_id"], "output_sha256": T.sha256_file(clip),
            "response_source": "https://muse.ai/thread/test", "observed_output": "test-output.mp4"}


def test_prepare_is_an_immutable_bundle_not_a_flow_send(shot):
    pkg, payload, image = shot
    folder = M.prepare(pkg, "SC01_g1")
    packet = json.loads((folder / "request.json").read_text())
    assert packet["request"]["prompt"] == payload["request"]["prompt"]
    assert (folder / packet["request"]["first_frame"]["path"]).read_bytes() == image.read_bytes()
    assert M.prepare(pkg, "SC01_g1") == folder
    assert not (pkg.root / "takes/intents").exists()
    assert not (folder / "state.json").exists()
    assert "UNKNOWN" in (folder / "relay.txt").read_text()


def test_dispatch_requires_go_live_and_cannot_repeat(shot):
    pkg, _, _ = shot
    folder = M.prepare(pkg, "SC01_g1")
    with pytest.raises(ValueError, match="OWNER_GO_LIVE"):
        M.dispatch(pkg, folder)
    claim(pkg, folder)
    with pytest.raises(ValueError, match="already"):
        claim(pkg, folder)


@pytest.mark.parametrize("change", ["source", "reference", "packet"])
def test_stale_or_altered_input_never_dispatches(shot, change):
    pkg, _, image = shot
    folder = M.prepare(pkg, "SC01_g1")
    if change == "source":
        (pkg.root / "04_shots.json").write_text('{}')
    elif change == "reference":
        image.write_bytes(b"different")
    else:
        data = json.loads((folder / "request.json").read_text())
        data["request"]["prompt"] = "Changed dialogue"
        (folder / "request.json").write_text(json.dumps(data))
    with pytest.raises(ValueError):
        claim(pkg, folder)
    assert not (folder / "state.json").exists()


def test_ingest_binds_download_not_a_fake_job_and_replays(shot, clip):
    pkg, _, _ = shot
    folder = M.prepare(pkg, "SC01_g1")
    claim(pkg, folder)
    first = M.ingest(pkg, folder, clip, response(folder, clip))
    second = M.ingest(pkg, folder, clip, response(folder, clip))
    assert first["take"] == second["take"]
    take = T.load_log(pkg.root, "probe").takes[0]
    assert take.status == "GENERATED" and take.provider == "muse" and not take.provider_job_id
    assert take.cost == {"amount": 1.0, "unit": "muse_requests", "provider": "muse"}
    assert money_ledger(T.load_log(pkg.root, "probe"), {})["credits"]["spent"] == 0
    state = json.loads((folder / "state.json").read_text())
    assert state["monetary_cost"] is None and state["binding"] == "operator_observed_download"
    assert state["media"]["audio_codec"] == "aac" and "DURATION_DIFFERS" in state["warnings"]


def test_wrong_receipt_or_corrupt_clip_never_registers(shot, clip):
    pkg, _, _ = shot
    folder = M.prepare(pkg, "SC01_g1")
    claim(pkg, folder)
    wrong = {**response(folder, clip), "request_id": "a" * 64}
    with pytest.raises(ValueError):
        M.ingest(pkg, folder, clip, wrong)
    clip.write_bytes(b"not a video")
    with pytest.raises(ValueError):
        M.ingest(pkg, folder, clip, response(folder, clip))
    assert not T.load_log(pkg.root, "probe").takes


def test_take_number_respects_flow_intents_and_existing_files(shot, clip):
    pkg, _, _ = shot
    folder = M.prepare(pkg, "SC01_g1")
    claim(pkg, folder)
    intents = pkg.root / "takes/intents"
    intents.mkdir(parents=True)
    (intents / "SC01_g1_t4.intent.json").write_text('{}')
    media = pkg.root / "media/takes"
    media.mkdir(parents=True)
    (media / "SC01_g1_t6.mp4").write_bytes(b"existing evidence")
    result = M.ingest(pkg, folder, clip, response(folder, clip))
    assert result["take"]["take_id"] == "SC01_g1_t7"
    assert (media / "SC01_g1_t6.mp4").read_bytes() == b"existing evidence"


def test_old_bytes_cannot_be_rebound_to_a_new_request(shot, clip):
    pkg, payload, _ = shot
    folder = M.prepare(pkg, "SC01_g1")
    claim(pkg, folder)
    M.ingest(pkg, folder, clip, response(folder, clip))
    payload["shot_version"] = 2
    newer = M.prepare(pkg, "SC01_g1")
    claim(pkg, newer)
    with pytest.raises(ValueError, match="already"):
        M.ingest(pkg, newer, clip, response(newer, clip))


def test_prompt_change_does_not_reset_one_dispatch_per_version(shot):
    pkg, payload, _ = shot
    folder = M.prepare(pkg, "SC01_g1")
    claim(pkg, folder)
    payload["request"]["prompt"] = "New wording"
    payload["request"]["prompt_sha256"] = T.sha256_text("New wording")
    with pytest.raises(ValueError):
        M.prepare(pkg, "SC01_g1")


def test_failed_prepare_can_resume_without_losing_evidence(shot, monkeypatch):
    pkg, _, _ = shot
    copy = M.shutil.copyfile
    monkeypatch.setattr(M.shutil, "copyfile", lambda *a, **kw: (_ for _ in ()).throw(OSError("interrupted")))
    with pytest.raises(OSError, match="interrupted"):
        M.prepare(pkg, "SC01_g1")
    monkeypatch.setattr(M.shutil, "copyfile", copy)
    folder = M.prepare(pkg, "SC01_g1")
    assert (folder / "handoff.zip").is_file()


def test_tampered_upload_archive_is_not_dispatched(shot):
    pkg, _, _ = shot
    folder = M.prepare(pkg, "SC01_g1")
    (folder / "handoff.zip").write_bytes(b"altered upload")
    with pytest.raises(ValueError, match="archive"):
        claim(pkg, folder)


def test_tampered_binding_cannot_write_outside_film(shot, clip):
    pkg, _, _ = shot
    folder = M.prepare(pkg, "SC01_g1")
    claim(pkg, folder)
    path = folder / "state.json"
    state = json.loads(path.read_text())
    state.update(status="BINDING", take_id="../../../outside")
    path.write_text(json.dumps(state))
    with pytest.raises(ValueError, match="take id"):
        M.ingest(pkg, folder, clip, response(folder, clip))
    assert not (pkg.root.parent / "outside.mp4").exists()


def test_prepared_variants_cannot_bypass_per_version_dispatch_limit(shot, clip):
    pkg, payload, _ = shot
    first = M.prepare(pkg, "SC01_g1")
    original = payload["request"]["prompt"]
    payload["request"]["prompt"] = "Other wording"
    payload["request"]["prompt_sha256"] = T.sha256_text("Other wording")
    second = M.prepare(pkg, "SC01_g1")
    payload["request"]["prompt"] = original
    payload["request"]["prompt_sha256"] = T.sha256_text(original)
    claim(pkg, first)
    M.ingest(pkg, first, clip, response(first, clip))
    payload["request"]["prompt"] = "Other wording"
    payload["request"]["prompt_sha256"] = T.sha256_text("Other wording")
    with pytest.raises(ValueError, match="version"):
        claim(pkg, second)


def test_interrupted_register_resumes_same_binding(shot, clip, monkeypatch):
    pkg, _, _ = shot
    folder = M.prepare(pkg, "SC01_g1")
    claim(pkg, folder)
    register = T.register_take
    monkeypatch.setattr(T, "register_take", lambda *a, **kw: (_ for _ in ()).throw(OSError("interrupted")))
    with pytest.raises(OSError):
        M.ingest(pkg, folder, clip, response(folder, clip))
    state = json.loads((folder / "state.json").read_text())
    assert state["status"] == "BINDING"
    monkeypatch.setattr(T, "register_take", register)
    assert M.ingest(pkg, folder, clip, response(folder, clip))["take"]["take_id"] == state["take_id"]
    assert len(T.load_log(pkg.root, "probe").takes) == 1


def test_camera_conditioning_preserves_dialogue_and_follows_static_plan():
    source = 'The given image is the first frame. A single unbroken 10s shot. She says: "I knew, Sam."'
    camera = CameraSetup(size="WIDE", angle="EYE_LEVEL", height="EYE", movement="STATIC",
                         lens_intent="WIDE_ESTABLISH", composition="Ruth left, Sam right")
    result = M.condition_camera_prompt(source, camera)
    assert 'She says: "I knew, Sam."' in result
    assert "first frame" not in result and "visual reference" in result
    assert "Camera locked off" in result and "no zoom" in result


def test_camera_conditioning_never_replaces_planned_camera_movement():
    camera = CameraSetup(size="CLOSE", angle="EYE_LEVEL", height="EYE", movement="PUSH_IN",
                         lens_intent="NORMAL", composition="one speaker")
    result = M.condition_camera_prompt("A single shot.", camera)
    assert "push in" in result and "locked off" not in result


def test_conditioned_bundle_binds_both_prompts_and_preserves_legacy(shot):
    pkg, payload, _ = shot
    camera = CameraSetup(size="WIDE", angle="EYE_LEVEL", height="EYE", movement="STATIC",
                         lens_intent="WIDE_ESTABLISH", composition="Ruth left, Sam right")
    pkg.typed = {"shots": SimpleNamespace(generations=[SimpleNamespace(generation_id="SC01_g1", camera=camera)])}
    legacy = M.prepare(pkg, "SC01_g1")
    conditioned = M.prepare(pkg, "SC01_g1", condition_camera=True)
    old = M._read(pkg, legacy)
    new = M._read(pkg, conditioned)
    assert old.schema_version == 1 and new.schema_version == 2
    assert new.source_prompt_sha256 == old.request.prompt_sha256
    assert new.request.prompt_sha256 != old.request.prompt_sha256
    assert payload["request"]["prompt"] == old.request.prompt
    claim(pkg, conditioned)
    camera.movement = "PUSH_IN"
    with pytest.raises(ValueError, match="stale"):
        M._read(pkg, conditioned)
