from __future__ import annotations

import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from film_pipeline import cli as cli_mod
from film_pipeline.agentic import WaveDAGScheduler, suggest_setup_anchors
from film_pipeline.drama import post as drama_post
from film_pipeline.production import (
    continuity as cont_mod,
    deliver as DL,
    ffjoin,
    finish as fn_mod,
    generate as gen_mod,
    preflight,
    render_cache,
    stills as S,
    takes as T,
    versions as vs_mod,
)
from film_pipeline.production.edit import AudioCut, EditEvent, EditSection, TextLine, Transition, render_cut
from film_pipeline.production.package import load_package
from film_pipeline.production.plan import plan_package
from film_pipeline.production.qc_model import TAKE_GROUPS, answer_group

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
TOOL = ROOT / "tools" / "film.py"
needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg not installed")


def _synth_clip(out: Path, *, duration_s: float = 1.6, freq: int = 440, color: str = "navy") -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc2=size=320x180:rate=24:duration={duration_s:.3f}",
            "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000:duration={duration_s:.3f}",
            "-af", "volume=0.3",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ac", "2", "-ar", "48000", "-shortest", str(out),
        ],
        check=True,
        timeout=120,
    )
    return out


def _accept_take(root: Path, film_id: str, gid: str, clip: Path, *, reviewer: str = "human:Alice") -> str:
    pkg = load_package(root)
    entry, _ = T.register_take(
        root, film_id, gid, clip, prompt_text=f"prompt {gid}", route="flow", model="m", credits=6.0
    )
    decl = next(g for g in pkg.typed["shots"].generations if g.generation_id == gid)
    rel_qs = T._relation_questions(pkg.typed["preprod"], decl, T.script_dialogue(pkg))
    checks = [
        {"group": grp, "result": "PASS", "level": "FULL_MOTION", "reviewer": reviewer, "evidence": f"reviewed {entry.take_id}"}
        for grp in TAKE_GROUPS
    ]
    for q in rel_qs:
        target_grp = answer_group(q["id"])
        for c in checks:
            if c["group"] == target_grp:
                c.setdefault("answers", {})[q["id"]] = "verified ok"
    sheet = {
        "take_id": entry.take_id,
        "generation_id": gid,
        "output_sha256": entry.output_sha256,
        "required_answers": [q["id"] for q in rel_qs],
        "checks": checks,
    }
    res = T.ingest_review(root, film_id, sheet, pkg=pkg)
    assert res["status"] == "ACCEPTED", res
    return entry.take_id


def _copy_film03_subset(tmp_path: Path, gids: list[str] | None = None) -> Path:
    root = tmp_path / "film"
    root.mkdir(parents=True, exist_ok=True)
    for name in ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json"):
        shutil.copyfile(FILM03 / name, root / name)
    if gids is not None:
        shots = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
        wanted = set(gids)
        shots["generations"] = [g for g in shots["generations"] if g["generation_id"] in wanted]
        for g in shots["generations"]:
            g["previous_generation_id"] = None
        (root / "04_shots.json").write_text(json.dumps(shots, indent=2), encoding="utf-8")
    return root


def _run_cli(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        capture_output=True, text=True, encoding="utf-8", cwd=cwd,
    )


@needs_ffmpeg
def test_default_package_delivers_16x9_only_and_finish_skips_clean_copy_and_portrait(tmp_path, monkeypatch):
    # 1. Default film.json omits portrait_9x16 -> False -> 16:9 only through CLI and finish()
    root = _copy_film03_subset(tmp_path, ["SC02_g1", "SC03_g1", "SC04_g2"])
    pkg = load_package(root)
    assert pkg.header.portrait_9x16 is False

    plan_package(pkg, root / "media" / "plan", storyboard=True, approve_storyboard="Alice")
    img = tmp_path / "still.png"
    Image.new("RGB", (64, 36), (40, 80, 120)).save(img)
    for gid in ("SC02_g1", "SC03_g1", "SC04_g2"):
        S.register_still(load_package(root), gid, img, source="test")
        S.approve_still(load_package(root), gid, "Alice")

    takes_dir = root / "media" / "takes"
    tids = [
        _accept_take(root, pkg.header.film_id, gid, _synth_clip(takes_dir / f"{gid}_t1.mp4", freq=440 + idx * 100))
        for idx, gid in enumerate(("SC02_g1", "SC03_g1", "SC04_g2"))
    ]
    edl = EditSection(
        events=[EditEvent(event_id=f"e{i+1}", take_id=tid) for i, tid in enumerate(tids)],
        title=[TextLine(text="The Front Desk", size=64), TextLine(text="Generated with AI", size=26)],
        title_s=2.0,
        end=[TextLine(text="All characters are fictional.", size=30)],
        end_s=1.0,
    )
    (root / "05_edit.json").write_text(edl.model_dump_json(), encoding="utf-8")
    (root / "generators.json").write_text(
        json.dumps([{"role": "video+audio", "name": "Google", "model": "Flow Omni 1.2 Flash", "settings": "360p"}]),
        encoding="utf-8",
    )
    rights = json.loads((root / "03_preprod.json").read_text(encoding="utf-8"))
    for r in rights.get("rights", []):
        r["status"] = "cleared"
    (root / "03_preprod.json").write_text(json.dumps(rights, indent=2), encoding="utf-8")

    # Bypass heavy STT subprocess check and synthetic 3-shot Gate 2/3 completeness while running real finish() CLI steps
    from film_pipeline.production import dialogue_stt as ds_mod

    def _fake_stt(p):
        out = Path(p.root) / "qc" / "dialogue_stt.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"ok": True, "summary": {"lines": 0, "pass": 0, "warn": 0}}) + "\n", encoding="utf-8")
        return {"ok": True, "summary": {"lines": 0, "pass": 0, "warn": 0}}

    monkeypatch.setattr(ds_mod, "check", _fake_stt)
    monkeypatch.setattr(preflight, "check", lambda p, **k: {"ok": True, "issues": [], "warnings": [], "stt_python": None})
    monkeypatch.setattr(
        fn_mod,
        "evaluate_gates",
        lambda p: [SimpleNamespace(gate=str(i), status="PASS" if i < 6 else "OWNER_PENDING") for i in range(1, 7)],
    )
    # Lock picture via CLI
    assert cli_mod.main(["lock", "--film", str(root), "--lock", "--by", "Alice", "--reason", "lock"]) == 0

    dry = fn_mod.finish(load_package(root), command=cli_mod.main, dry_run=True)
    assert dry["ok"] is True and dry["portrait_9x16"] is False

    res = fn_mod.finish(load_package(root), command=cli_mod.main)
    assert res["ok"] is True, res
    assert not (root / "media" / "cut" / "titled_cut.clean.mp4").exists()
    assert not list((root / "versions").glob("*_9x16.mp4"))

    vr = json.loads((root / "versions" / "versions.json").read_text(encoding="utf-8"))
    assert vr["summary"]["portrait_enabled"] is False
    assert [v["name"] for v in vr["versions"]] == ["master_16x9"]

    arch = DL.current_archive(root)
    ver = DL.verify_archive(arch)
    assert ver["ok"] is True, ver
    manifest = DL.ArchiveManifest.model_validate_json((arch / "MANIFEST.json").read_text(encoding="utf-8"))
    assert set(manifest.masters) == {"master_16x9"}
    assert not (arch / "disclosure_9x16.json").exists()
    assert not list((arch / "masters").glob("*_9x16.mp4"))

    # 2. Opt-in --portrait still renders & delivers 9:16 cleanly
    assert cli_mod.main(["versions", "--film", str(root), "--portrait",
                         "--cut-report", str(root / "media" / "cut" / "titled_cut.cut.json"),
                         "--generators-file", str(root / "generators.json")]) == 0
    assert (root / "versions" / f"{pkg.header.film_id}_9x16.mp4").is_file()
    assert cli_mod.main(["deliver", "--film", str(root), "--portrait",
                         "--cut-report", str(root / "media" / "cut" / "titled_cut.cut.json"),
                         "--generators-file", str(root / "generators.json")]) == 0
    arch2 = DL.current_archive(root)
    manifest2 = DL.ArchiveManifest.model_validate_json((arch2 / "MANIFEST.json").read_text(encoding="utf-8"))
    assert set(manifest2.masters) == {"master_16x9", "portrait_9x16"}


@needs_ffmpeg
def test_parallel_chunk_render_and_threadsafe_cache_and_nvenc(tmp_path, monkeypatch):
    # 1. Thread-safe render_cache.save under concurrent workers on identical key
    cache_dir = tmp_path / "cache"
    src_file = tmp_path / "chunk.mkv"
    src_file.write_bytes(b"identical-chunk-payload" * 100)
    with ThreadPoolExecutor(max_workers=6) as pool:
        outs = list(pool.map(lambda _: render_cache.save(cache_dir, "k" * 64, src_file, ".mkv"), range(6)))
    assert all(p == cache_dir / f"{'k'*64}.mkv" for p in outs)
    assert render_cache.cached(cache_dir, "k" * 64, ".mkv") is not None

    # 2. Parallel fine + hard render (>12 events) and skip of second assemble on unannotated chunks
    root = _copy_film03_subset(tmp_path, ["SC02_g1"])
    header = json.loads((root / "film.json").read_text(encoding="utf-8"))
    header["disclosure"] = {"ai_label": "title_card"}
    (root / "film.json").write_text(json.dumps(header, indent=2), encoding="utf-8")
    clip = _synth_clip(root / "media" / "takes" / "SC02_g1_t1.mp4", duration_s=1.2, freq=440)
    tid = _accept_take(root, "film03_front_desk", "SC02_g1", clip)

    assemble_calls = []
    real_assemble = drama_post.assemble

    def spy_assemble(*args, **kwargs):
        assemble_calls.append(kwargs.get("_body_only", False))
        return real_assemble(*args, **kwargs)

    monkeypatch.setattr(drama_post, "assemble", spy_assemble)

    fine_events = [
        EditEvent(
            event_id=f"e{i}",
            take_id=tid,
            src_in_s=0.1,
            src_out_s=0.35,
            transition=Transition() if i == 0 else Transition(type="DISSOLVE", duration_s=0.05),
            audio=AudioCut() if i == 0 else AudioCut(j_cut_s=0.02, l_cut_s=0.02),
        )
        for i in range(13)
    ]
    fine_sec = EditSection(
        events=fine_events,
        title=[TextLine(text="Test", size=48), TextLine(text="Generated with AI", size=24)],
        title_s=1.0,
        end=[TextLine(text="End", size=40)],
        end_s=0.5,
    )
    fine_out = tmp_path / "out" / "fine.mp4"
    rep = render_cut(load_package(root), fine_sec, fine_out, jobs=3, cache_dir=tmp_path / "rcache")
    assert len(rep["rendered_events"]) == 13
    assert drama_post.probe_video_duration(fine_out) == pytest.approx(1.0 + 13 * 0.25 - 12 * 0.05 + 0.5, abs=0.35)
    # No second _body_only assemble calls because cues=[], overlays=[], and label_text=""!
    assert True not in assemble_calls

    hard_events = [EditEvent(event_id=f"h{i}", take_id=tid, src_out_s=0.25) for i in range(13)]
    hard_sec = EditSection(events=hard_events, title_s=1.0, end_s=0.5)
    hard_out = tmp_path / "out" / "hard.mp4"
    rep_h = render_cut(load_package(root), hard_sec, hard_out, jobs=3, cache_dir=tmp_path / "rcache_hard")
    assert len(rep_h["rendered_events"]) == 13
    assert drama_post.probe_video_duration(hard_out) == pytest.approx(1.0 + 13 * 0.25 + 0.5, abs=0.35)

    # 3. Hardware NVENC render if available on this machine
    if ffjoin.nvenc_available():
        nv_out = tmp_path / "out" / "fine_nvenc.mp4"
        render_cut(load_package(root), fine_sec, nv_out, jobs=2, hwaccel=True, cache_dir=tmp_path / "rcache_nv")
        assert nv_out.is_file() and drama_post.probe_video_duration(nv_out) > 2.0


def test_bind_matching_stills_and_setup_anchor_dag_unblocking(tmp_path):
    root = _copy_film03_subset(tmp_path)
    # Create a linear 10-shot chain g0 -> g1 -> ... -> g9 and duplicate g0 choreography/prompt into g9
    shots = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
    gens = shots["generations"][:10]
    for i, g in enumerate(gens):
        g["previous_generation_id"] = None if i == 0 else gens[i - 1]["generation_id"]
        g["end_frame"] = False
    # Make gens[1] share the exact prompt shape/state as gens[0] in a test pair so bind_matching_stills matches
    gens[1]["scene_id"] = gens[0]["scene_id"]
    gens[1]["coverage"] = gens[0]["coverage"]
    gens[1]["subject"] = gens[0]["subject"]
    gens[1]["foreground"] = gens[0]["foreground"]
    gens[1]["visible"] = list(gens[0]["visible"])
    gens[1]["start_state"] = gens[0]["start_state"]
    gens[1]["listener_anchors"] = dict(gens[0].get("listener_anchors", {}))
    gens[1]["gaze_target"] = gens[0].get("gaze_target", "")
    shots["generations"] = gens
    (root / "04_shots.json").write_text(json.dumps(shots, indent=2), encoding="utf-8")

    # Approve g0 still and verify bind_matching_stills binds onto identical prompt g1 (refuses REHEARSAL-BOT)
    img = tmp_path / "s.png"
    Image.new("RGB", (64, 36), (10, 40, 80)).save(img)
    g0, g1, g3 = gens[0]["generation_id"], gens[1]["generation_id"], gens[3]["generation_id"]
    S.register_still(load_package(root), g0, img, source="test")
    S.approve_still(load_package(root), g0, "Alice")

    with pytest.raises(ValueError, match="REHEARSAL-BOT"):
        S.bind_matching_stills(load_package(root), by="REHEARSAL-BOT")

    bound = S.bind_matching_stills(load_package(root), by="Alice")
    assert any(b["generation_id"] == g1 and b["donor"] == g0 for b in bound["bound"])
    assert S.state_of(load_package(root), g1)[0] == "APPROVED"

    # Initial DAG critical depth == 10
    pkg_before = load_package(root)
    before_waves = WaveDAGScheduler(pkg_before).plan_waves()
    assert before_waves["critical_path_depth"] == 10
    assert len(before_waves["ready_frontier"]) == 1

    # Optimistic lookahead=1 with GENERATED g0 clip populates speculative_frontier without changing ready_frontier
    clip0 = root / "media" / "takes" / f"{g0}_t1.mp4"
    clip0.parent.mkdir(parents=True, exist_ok=True)
    clip0.write_bytes(b"fake-clip-bytes")
    T.register_take(root, "film03_front_desk", g0, clip0, prompt_text="p", route="flow", model="m", credits=6.0)
    spec_waves = WaveDAGScheduler(load_package(root), optimistic_lookahead=1).plan_waves()
    assert spec_waves["ready_frontier"] == [g0]
    assert g1 in spec_waves["speculative_frontier"]

    # setup-anchors max_chain_depth=3 flattens depth from 10 to <= 3
    anc = suggest_setup_anchors(load_package(root), max_chain_depth=3, apply=True)
    assert anc["critical_path_before"] == 10
    assert anc["critical_path_after"] <= 3
    assert anc["wave0_after"] > anc["wave0_before"]
    assert WaveDAGScheduler(load_package(root)).plan_waves()["critical_path_depth"] <= 3

    # Independent still shot g3 does NOT block on HANDOFF_PREVIOUS_NOT_ACCEPTED once still & storyboard approved
    plan_package(load_package(root), root / "media" / "plan", storyboard=True, approve_storyboard="Alice")
    S.register_still(load_package(root), g3, img, source="anchor")
    S.approve_still(load_package(root), g3, "Alice")
    payload = gen_mod.build_payload(load_package(root), g3)
    blocker_codes = {b["code"] for b in payload["blockers"]}
    assert "HANDOFF_PREVIOUS_NOT_ACCEPTED" not in blocker_codes
    assert payload["start_frame"]["source"] == "approved setup-anchor start still"

    # Continuity OBJECT_HANDOFF check still enforces prop handoff across previous_generation_id on g3
    pre = json.loads((root / "03_preprod.json").read_text(encoding="utf-8"))
    shots_cur = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
    g2_end = gens[2]["end_state"]
    broken_state = f"{g3}_broken_start"
    pre["states"][broken_state] = json.loads(json.dumps(pre["states"][g2_end]))
    pre["states"][broken_state]["props"]["__synthetic_prop__"] = "on table"
    shots_cur["generations"][3]["start_state"] = broken_state
    (root / "03_preprod.json").write_text(json.dumps(pre, indent=2), encoding="utf-8")
    (root / "04_shots.json").write_text(json.dumps(shots_cur, indent=2), encoding="utf-8")
    pkg_cont = load_package(root)
    c_issues = cont_mod.continuity_issues(pkg_cont.typed["preprod"], pkg_cont.typed["shots"])
    assert any(i.check == "OBJECT_HANDOFF" and g3 in i.detail for i in c_issues)


@needs_ffmpeg
def test_review_ui_and_batch_review_ingest(tmp_path):
    gids = ["SC02_g1", "SC03_g1", "SC04_g2"]
    root = _copy_film03_subset(tmp_path, gids)
    pkg = load_package(root)
    cdir = root / "media" / "takes"
    entries = []
    for idx, gid in enumerate(gids):
        clip = _synth_clip(cdir / f"{gid}_t1.mp4", duration_s=1.0, freq=440 + idx * 110)
        entry, _ = T.register_take(root, pkg.header.film_id, gid, clip, prompt_text=f"p {gid}", route="flow", model="m", credits=6.0)
        entries.append(entry)

    assert cli_mod.main(["review-ui", "--film", str(root), "--triage"]) == 0
    html_path = root / "media" / "review_ui" / "index.html"
    assert html_path.is_file()
    html_text = html_path.read_text(encoding="utf-8")
    for entry in entries:
        assert entry.take_id in html_text
        assert entry.output_sha256 in html_text

    # Ingest batch review list JSON through CLI `review --ingest`
    pkg = load_package(root)
    batch = []
    for entry in entries:
        decl = next(g for g in pkg.typed["shots"].generations if g.generation_id == entry.generation_id)
        rel_qs = T._relation_questions(pkg.typed["preprod"], decl, T.script_dialogue(pkg))
        checks = [
            {"group": grp, "result": "PASS", "level": "FULL_MOTION", "reviewer": "human:Alice", "evidence": f"batch {entry.take_id}"}
            for grp in TAKE_GROUPS
        ]
        for q in rel_qs:
            tg = answer_group(q["id"])
            for c in checks:
                if c["group"] == tg:
                    c.setdefault("answers", {})[q["id"]] = "verified"
        batch.append({
            "take_id": entry.take_id,
            "generation_id": entry.generation_id,
            "output_sha256": entry.output_sha256,
            "required_answers": [q["id"] for q in rel_qs],
            "checks": checks,
        })
    batch_file = tmp_path / "batch_reviews.json"
    batch_file.write_text(json.dumps(batch, indent=2), encoding="utf-8")
    assert cli_mod.main(["review", "--film", str(root), "--ingest", str(batch_file)]) == 0

    log = T.load_log(root, pkg.header.film_id)
    assert all(log.get(e.take_id).status == "ACCEPTED" for e in entries)
