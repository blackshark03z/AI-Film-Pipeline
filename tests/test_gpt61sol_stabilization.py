from __future__ import annotations

import hashlib
import json
import math
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from film_pipeline.agentic import (
    AccountLeasePool,
    CapabilityRouter,
    CausalRepairRouter,
    PreSendCritic,
    SceneIncrementalConformer,
    WaveDAGScheduler,
)
from film_pipeline.drama import post as drama_post
from film_pipeline.film_package_export import build_package, validate_package
from film_pipeline.film_package_export import validate as export_validate
from film_pipeline.production import (
    dailies_triage,
    deliver as DL,
    finish as fn_mod,
    foley,
    gate_checks,
    generate as gen_mod,
    money as money_mod,
    muse_gateway,
    recovery,
    render_cache,
    report as report_mod,
    takes as T,
    titles as ti_mod,
)
from film_pipeline.production.edit import AudioCut, EditEvent, EditSection, TextLine, Transition, render_cut
from film_pipeline.production.package import load_package
from film_pipeline.production.plan import plan_package
from film_pipeline.production.runtime import composer_lock, film_lock
from film_pipeline.providers import flow_ui_adapter
from film_pipeline.production import dialogue_stt

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
FFMPEG = shutil.which("ffmpeg")


def _needs_ffmpeg(fn):
    return pytest.mark.skipif(not FFMPEG, reason="ffmpeg not available")(fn)


def _synth_clip(out: Path, *, duration_s: float = 1.5, color: str = "navy", freq: int = 440,
                silent: bool = False, size: str = "1280x720", testsrc: bool = False) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    audio_in = f"anullsrc=r=48000:cl=stereo:d={duration_s:.3f}" if silent else f"sine=f={freq}:r=48000:d={duration_s:.3f}"
    video_in = (
        f"testsrc2=size={size}:rate=24:duration={duration_s:.3f}"
        if testsrc
        else f"color=c={color}:s={size}:r=24:d={duration_s:.3f}"
    )
    cmd = [
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", video_in,
        "-f", "lavfi", "-i", audio_in,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "2", "-ar", "48000",
        "-shortest", str(out),
    ]
    subprocess.run(cmd, check=True, timeout=120)
    return out


def _copy_film03_subset(tmp_path: Path, count: int | None = 3) -> Path:
    root = tmp_path / "film"
    root.mkdir(parents=True, exist_ok=True)
    for name in ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json"):
        shutil.copyfile(FILM03 / name, root / name)
    if count is not None:
        shots = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
        shots["generations"] = shots["generations"][:count]
        for g in shots["generations"]:
            g["previous_generation_id"] = None
        (root / "04_shots.json").write_text(json.dumps(shots, indent=2), encoding="utf-8")
    return root


def _accept_clip(root: Path, film_id: str, gid: str, clip: Path, *, prompt_text: str = "p", shot_version: int = 1,
                 credits: float = 6.0) -> str:
    entry, _ = T.register_take(
        root, film_id, gid, clip, prompt_text=prompt_text, route="flow", model="omni-1.2-flash",
        credits=credits, shot_version=shot_version,
    )
    log = T.load_log(root, film_id)
    rev_dir = root / "takes" / "reviews"
    rev_dir.mkdir(parents=True, exist_ok=True)
    rev_rel = f"takes/reviews/{entry.take_id}.json"
    (root / rev_rel).write_text("{}", encoding="utf-8")
    for t in log.takes:
        if t.take_id == entry.take_id:
            t.status = "ACCEPTED"
            t.review_file = rev_rel
    T.save_log(root, log)
    return entry.take_id


# ---------------------------------------------------------------------------
# P1 #1: Hash-bound negative reconciliation (no boolean-only shortcut)
# ---------------------------------------------------------------------------

def test_p1_01_stale_reconcile_without_matching_intent_hash_stays_unresolved(tmp_path):
    root = _copy_film03_subset(tmp_path, 1)
    pkg = load_package(root)
    gid = pkg.typed["shots"].generations[0].generation_id
    prompt_sha = T.sha256_text("test prompt")
    intent_path = root / "takes" / "intents" / f"{gid}_t1.intent.json"
    intent_path.parent.mkdir(parents=True, exist_ok=True)
    intent_path.write_text(
        json.dumps({
            "take_id": f"{gid}_t1",
            "generation_id": gid,
            "prompt_sha256": prompt_sha,
            "sent": True,
            "dry_run": False,
            "result": "PENDING",
            "expected_credits": 6.0,
            "provider": "flow",
        }) + "\n",
        encoding="utf-8",
    )
    native_path = root / "media" / "takes" / f"{gid}_t1.take.json"
    native_path.parent.mkdir(parents=True, exist_ok=True)
    native_path.write_text(json.dumps({"result": "FAILED_NO_CLIP"}), encoding="utf-8")
    native_sha = hashlib.sha256(native_path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

    reconcile_path = root / "media" / "takes" / f"{gid}_t1.reconcile.json"
    reconcile_path.write_text(
        json.dumps({
            "resolution": "PROVIDER_NO_CLIP",
            "provider_no_clip": True,
            "scan_verified": True,
            "prompt_sha256": prompt_sha,
            "native_sha256": native_sha,
            "intent_sha256": "0" * 64,  # stale/mismatched hash
        }),
        encoding="utf-8",
    )
    receipts = gen_mod._sent_receipts(root, pkg.header.film_id, {})
    assert receipts[f"{gid}_t1"]["result"] == "PENDING"
    assert not hasattr(gen_mod, "_provider_no_clip")

    # Matching LF-normalized hash + native hash + prompt hash resolves cleanly to FLOW_FAILED_NO_CLIP
    lf_sha = hashlib.sha256(intent_path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    reconcile_path.write_text(
        json.dumps({
            "resolution": "PROVIDER_NO_CLIP",
            "provider_no_clip": True,
            "scan_verified": True,
            "prompt_sha256": prompt_sha,
            "native_sha256": native_sha,
            "intent_sha256": lf_sha,
        }),
        encoding="utf-8",
    )
    resolved = gen_mod._sent_receipts(root, pkg.header.film_id, {})
    assert resolved[f"{gid}_t1"]["result"] == "FLOW_FAILED_NO_CLIP"


# ---------------------------------------------------------------------------
# P1 #2: report._production includes unregistered charged receipts
# ---------------------------------------------------------------------------

def test_p1_02_report_includes_unregistered_charged_receipts(tmp_path):
    root = _copy_film03_subset(tmp_path, 1)
    pkg = load_package(root)
    gid = pkg.typed["shots"].generations[0].generation_id
    intent_path = root / "takes" / "intents" / f"{gid}_t1.intent.json"
    intent_path.parent.mkdir(parents=True, exist_ok=True)
    intent_path.write_text(
        json.dumps({
            "take_id": f"{gid}_t1",
            "generation_id": gid,
            "sent": True,
            "dry_run": False,
            "result": "PASSED",
            "expected_credits": 10.0,
            "provider": "flow",
            "model": "omni-1.2-flash",
            "take_registered": False,
        }),
        encoding="utf-8",
    )
    prod = report_mod._production(load_package(root))
    assert prod["credits_spent"] == 10.0
    assert prod["logged_credits"] == 0.0
    assert prod["unregistered_charged_credits"] == 10.0


# ---------------------------------------------------------------------------
# P1 #3: Finish invalidation (attributions, mp3, render_cache _RENDER_IMPL_SHA)
# ---------------------------------------------------------------------------

def test_p1_03_finish_invalidation_and_render_cache_revision(tmp_path, monkeypatch):
    src = tmp_path / "src.txt"
    src.write_text("v1", encoding="utf-8")
    k1 = render_cache.key_for(sources=[src], settings={"x": 1})
    monkeypatch.setattr(render_cache, "_RENDER_IMPL_SHA", "modified-renderer-rev")
    k2 = render_cache.key_for(sources=[src], settings={"x": 1})
    assert k1 != k2

    root = _copy_film03_subset(tmp_path, 1)
    (root / "audio").mkdir(parents=True, exist_ok=True)
    assets_json = root / "audio" / "assets.json"
    mp3 = tmp_path / "outside.mp3"
    mp3.write_bytes(b"ID3v1-first")
    assets_json.write_text(
        json.dumps({"assets": [{"path": str(mp3), "kind": "sfx", "license": "CC-BY", "status": "cleared", "attribution": "Artist A"}]}),
        encoding="utf-8",
    )
    t_fp1 = fn_mod._fingerprint(root, "titles")
    m_fp1 = fn_mod._fingerprint(root, "mix")

    assets_json.write_text(
        json.dumps({"assets": [{"path": str(mp3), "kind": "sfx", "license": "CC-BY", "status": "cleared", "attribution": "Artist B"}]}),
        encoding="utf-8",
    )
    t_fp2 = fn_mod._fingerprint(root, "titles")
    assert t_fp2 != t_fp1

    mp3.write_bytes(b"ID3v1-replaced")
    m_fp2 = fn_mod._fingerprint(root, "mix")
    assert m_fp2 != m_fp1


# ---------------------------------------------------------------------------
# P1 #4 & #5: Deliver versions binding & title_card pixel check
# ---------------------------------------------------------------------------

@_needs_ffmpeg
def test_p1_04_05_deliver_versions_binding_and_title_card_pixel_check(tmp_path):
    root = _copy_film03_subset(tmp_path, 2)
    pkg = load_package(root)
    header = json.loads((root / "film.json").read_text(encoding="utf-8"))
    header["disclosure"] = {"ai_label": "title_card"}
    (root / "film.json").write_text(json.dumps(header, indent=2), encoding="utf-8")

    shots = pkg.typed["shots"].generations
    clips_dir = root / "media" / "takes"
    events = []
    for i, g in enumerate(shots):
        clip = _synth_clip(
            clips_dir / f"{g.generation_id}_t1.mp4",
            duration_s=1.2,
            freq=440 + i * 110,
            testsrc=True,
        )
        tid = _accept_clip(root, pkg.header.film_id, g.generation_id, clip)
        events.append(EditEvent(event_id=f"ev{i+1}", take_id=tid))

    labelled = [TextLine(text="The Front Desk", size=64), TextLine(text="Generated with AI", size=26)]
    unlabelled = [TextLine(text="The Front Desk", size=64), TextLine(text="A Drama Short", size=26)]
    edl = EditSection(events=events, title=labelled, title_s=2.5, end=[TextLine(text="The End", size=48)], end_s=1.0)
    (root / "05_edit.json").write_text(edl.model_dump_json(), encoding="utf-8")

    # Render legitimate titled cut, normalize loudness, build versions & QC
    cut_mp4 = root / "media" / "cut" / "mixed.mp4"
    rep_real = render_cut(load_package(root), edl, cut_mp4, clips_dir=clips_dir, title_lines=[(t.text, t.size) for t in labelled])
    cut_json = cut_mp4.with_suffix(".cut.json")
    cut_json.write_text(json.dumps(rep_real, indent=2), encoding="utf-8")
    drama_post.normalize_loudness(cut_mp4)

    from film_pipeline.production import master_qc as mq_mod, versions as vs_mod
    mq_mod.write_record(load_package(root), mq_mod.check_master(cut_mp4, pkg=load_package(root), cut_report=cut_json))
    vs_mod.build(load_package(root), cut_mp4, cut_json, generators="Google Flow")

    res_ok = DL.deliver(load_package(root), cut_mp4, cut_json, generators="Google Flow")
    assert res_ok["ok"] is True, res_ok["findings"]
    assert res_ok["ai_label"] == {"mode": "title_card"}

    # Finding #4: tamper cut_report_sha256 / master_16x9 mismatch in versions.json -> VERSIONS_STALE BLOCK
    v_path = root / "versions" / "versions.json"
    v_orig = json.loads(v_path.read_text(encoding="utf-8"))
    v_bad = json.loads(json.dumps(v_orig))
    v_bad["versions"][0]["sha256"] = "deadbeef" * 8
    v_path.write_text(json.dumps(v_bad), encoding="utf-8")
    res_stale = DL.deliver(load_package(root), cut_mp4, cut_json, generators="Google Flow")
    assert "VERSIONS_STALE" in {f["code"] for f in res_stale["findings"] if f["severity"] == "BLOCK"}
    v_path.write_text(json.dumps(v_orig), encoding="utf-8")

    # Finding #5: swap master video to one whose title card omitted the AI line -> AI_TITLE_CARD_NOT_BURNED
    bad_mp4 = root / "media" / "cut" / "no_ai_card.mp4"
    rep_bad = render_cut(load_package(root), edl, bad_mp4, clips_dir=clips_dir,
                         title_lines=[(t.text, t.size) for t in unlabelled])
    shutil.copyfile(bad_mp4, cut_mp4)
    cut_json.write_text(json.dumps(rep_bad, indent=2), encoding="utf-8")
    drama_post.normalize_loudness(cut_mp4)
    mq_mod.write_record(load_package(root), mq_mod.check_master(cut_mp4, pkg=load_package(root), cut_report=cut_json))
    vs_mod.build(load_package(root), cut_mp4, cut_json, generators="Google Flow")
    res_missing_card = DL.deliver(load_package(root), cut_mp4, cut_json, generators="Google Flow")
    bad_codes = {f["code"] for f in res_missing_card["findings"] if f["severity"] == "BLOCK"}
    assert "AI_TITLE_CARD_NOT_BURNED" in bad_codes
    assert "AI_TITLE_CARD_NOT_BURNED_9X16" in bad_codes


# ---------------------------------------------------------------------------
# P1 #6: Cold wheel resource fallbacks & dialogue_stt._stem relative path
# ---------------------------------------------------------------------------

def test_p1_06_packaged_resource_fallbacks_work_without_repo_root(tmp_path, monkeypatch):
    monkeypatch.setattr(foley, "DEFAULT_CATALOG", tmp_path / "missing" / "sfx_catalog.json")
    cat = foley.load_catalog()
    assert len(cat["entries"]) > 0

    monkeypatch.setattr(export_validate, "SCHEMA_PATH", tmp_path / "missing" / "schema.json")
    schema = export_validate._load_schema()
    assert "properties" in schema

    monkeypatch.setattr(flow_ui_adapter, "FLOW_SEND", tmp_path / "missing" / "flow_send.py")
    monkeypatch.setattr(flow_ui_adapter, "_REPO_FLOW_DIR", tmp_path / "missing_dir")
    assert flow_ui_adapter._resolved_flow_dir() == flow_ui_adapter._PKG_FLOW_DIR
    assert (flow_ui_adapter._resolved_flow_dir() / "flow_send.py").is_file()

    # dialogue_stt._stem resolves relative to film root first (independent of cwd/ROOT)
    film_dir = tmp_path / "myfilm"
    (film_dir / "audio" / "stems").mkdir(parents=True)
    stem_wav = film_dir / "audio" / "stems" / "dialogue.wav"
    stem_wav.write_bytes(b"RIFF0000WAVE")
    (film_dir / "audio" / "mix.json").write_text(
        json.dumps({"stems": {"dialogue": "audio/stems/dialogue.wav"}}), encoding="utf-8"
    )
    assert dialogue_stt._stem(film_dir) == stem_wav


# ---------------------------------------------------------------------------
# P1 #7 & #8: AccountLeasePool BEGIN IMMEDIATE, unique active, idempotency & token
# ---------------------------------------------------------------------------

def test_p1_07_08_lease_pool_atomicity_idempotency_token_and_quarantine(tmp_path):
    db = tmp_path / "pool.sqlite3"
    pool = AccountLeasePool(db, min_reserve_credits=10.0, cooldown_s=5.0)
    pool.register_account("a1", 50.0)
    lease = pool.acquire("SC01_g1", cost_credits=6.0, now=100.0, film_id="f1", shot_version=1)
    assert lease is not None and lease["lease_token"]

    # Wrong token refused
    with pytest.raises(ValueError, match="lease_token"):
        pool.release("SC01_g1", film_id="f1", shot_version=1, lease_token="wrong", credits_spent=6.0, now=101.0)

    # Double release is idempotent (only deducts once: 50 -> 44)
    pool.release("SC01_g1", film_id="f1", shot_version=1, lease_token=lease["lease_token"], credits_spent=6.0, now=101.0)
    pool.release("SC01_g1", film_id="f1", shot_version=1, lease_token=lease["lease_token"], credits_spent=6.0, now=102.0)
    snap = pool.snapshot()
    assert snap["accounts"][0]["credits"] == 44.0

    # Quarantining while ACTIVE preserves lease as QUARANTINED_PENDING_RECONCILE
    pool.register_account("a2", 50.0)
    l2 = pool.acquire("SC01_g2", cost_credits=6.0, now=200.0, film_id="f1", shot_version=1)
    assert l2 is not None
    acct = l2["account_id"]
    pool.quarantine_account(acct, "verify")
    assert pool.acquire("SC01_g2", cost_credits=6.0, now=210.0, film_id="f1", shot_version=1) is None

    # DB partial unique constraint prevents two ACTIVE leases on the same account
    with sqlite3.connect(db) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO leases (lease_key, film_id, generation_id, shot_version, account_id, lease_token, leased_at, state, settled_credits) "
                "VALUES ('k1', 'f1', 'gX', 1, 'a2', 'tok1', 1.0, 'ACTIVE', 0.0)"
            )
            conn.execute(
                "INSERT INTO leases (lease_key, film_id, generation_id, shot_version, account_id, lease_token, leased_at, state, settled_credits) "
                "VALUES ('k2', 'f1', 'gY', 1, 'a2', 'tok2', 1.0, 'ACTIVE', 0.0)"
            )


# ---------------------------------------------------------------------------
# P1 #9 & #10: Pending Muse claim blocks send + atomic temp staging recovery
# ---------------------------------------------------------------------------

@_needs_ffmpeg
def test_p1_09_10_muse_pending_blocks_generate_and_temp_staging_recovers(tmp_path, monkeypatch):
    root = _copy_film03_subset(tmp_path, count=None)
    pkg = load_package(root)
    plan_package(pkg, root / "media" / "plan", storyboard=True, approve_storyboard="owner")
    gid = next(g.generation_id for g in pkg.typed["shots"].generations if not g.previous_generation_id)
    # Approve start still
    from film_pipeline.production import stills as st_mod
    from PIL import Image
    still_src = tmp_path / "start.png"
    Image.new("RGB", (1280, 720), (30, 40, 50)).save(still_src)
    st_mod.register_still(load_package(root), gid, still_src, source="test")
    st_mod.approve_still(load_package(root), gid, "Owner")

    backlog = tmp_path / "backlog.md"
    backlog.write_text("OWNER_GO_LIVE: YES\n", encoding="utf-8")
    folder = muse_gateway.prepare(load_package(root), gid)
    muse_gateway.dispatch(load_package(root), folder, backlog=backlog)

    # Finding #9: pending Muse handoff shows in recovery.pending_receipts & blocks generate.build_payload
    pend = recovery.pending_receipts(load_package(root))
    assert any(p.get("provider") == "muse" and p.get("generation_id") == gid for p in pend)
    payload = gen_mod.build_payload(load_package(root), gid, stills_dir=root / "media" / "stills")
    assert any(b["code"] == "SEND_PENDING" for b in payload["blockers"])

    # Finding #10: crash during copy writes to temp sibling without corrupting final output; retry succeeds cleanly
    clip = _synth_clip(tmp_path / "muse_dl.mp4", duration_s=1.0, color="green")
    digest = T.sha256_file(clip)
    state = json.loads((folder / "state.json").read_text(encoding="utf-8"))
    resp = {
        "request_id": state["request_id"],
        "response_source": "https://muse.ai/runs/1",
        "output_sha256": digest,
        "observed_output": "green 1.0s synthetic clip",
    }

    real_copyfileobj = shutil.copyfileobj

    def crash_mid_copy(src, dst, *a, **kw):
        dst.write(b"partial-bytes")
        raise RuntimeError("simulated crash during copy")

    monkeypatch.setattr(muse_gateway.shutil, "copyfileobj", crash_mid_copy)
    with pytest.raises(RuntimeError, match="simulated crash"):
        muse_gateway.ingest(load_package(root), folder, clip, resp)
    final_out = root / "media" / "takes" / f"{gid}_t1.mp4"
    assert not final_out.exists()

    # Retry succeeds atomically and binds take
    monkeypatch.setattr(muse_gateway.shutil, "copyfileobj", real_copyfileobj)
    ing = muse_gateway.ingest(load_package(root), folder, clip, resp)
    assert ing["created"] is True
    assert T.sha256_file(final_out) == digest


# ---------------------------------------------------------------------------
# P1 #11: Incremental conform checks source hashes & output hash & EDL subset
# ---------------------------------------------------------------------------

@_needs_ffmpeg
def test_p1_11_incremental_conform_verifies_output_hash_and_edl_trims(tmp_path):
    root = _copy_film03_subset(tmp_path, 2)
    shots = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
    for g in shots["generations"]:
        g["scene_id"] = "SC01"
    (root / "04_shots.json").write_text(json.dumps(shots, indent=2), encoding="utf-8")

    pkg = load_package(root)
    cdir = root / "media" / "takes"
    tids = []
    for i, g in enumerate(pkg.typed["shots"].generations):
        c = _synth_clip(cdir / f"{g.generation_id}_t1.mp4", duration_s=2.0, color=("red" if i == 0 else "blue"))
        tids.append(_accept_clip(root, pkg.header.film_id, g.generation_id, c))

    edl = EditSection(
        events=[
            EditEvent(event_id="e1", take_id=tids[0], src_in_s=0.0, src_out_s=1.0),
            EditEvent(event_id="e2", take_id=tids[1], src_in_s=0.0, src_out_s=1.0,
                      transition=Transition(type="DISSOLVE", duration_s=0.5)),
        ],
        title=[TextLine(text="T", size=40), TextLine(text="Generated with AI", size=24)],
        title_s=1.0,
        end_s=0.5,
    )
    (root / "05_edit.json").write_text(edl.model_dump_json(), encoding="utf-8")

    conf = SceneIncrementalConformer()
    built = conf.conform_ready_scenes(load_package(root), render=True)
    assert len(built["rendered"]) == 1
    mkv = Path(built["rendered"][0]["output"])
    assert built["rendered"][0]["output_sha256"]
    # Duration matches trimmed dissolve (~1.5s, NOT 4.0s untrimmed)
    dur = drama_post.probe_video_duration(mkv)
    assert 1.3 <= dur <= 1.7

    # 1-byte corrupted MKV is NEVER reported FRESH
    mkv.write_bytes(b"X")
    st_bad = conf.scene_status(load_package(root))
    assert "SC01" not in st_bad["fresh_scenes"]
    assert "SC01" in st_bad["ready_scenes"]


# ---------------------------------------------------------------------------
# P1 #12: film_package_export clamps dissolve overlap cleanly without schema fail
# ---------------------------------------------------------------------------

@_needs_ffmpeg
def test_p1_12_film_package_export_dissolve_overlap_clamped(tmp_path):
    root = _copy_film03_subset(tmp_path, 2)
    pkg = load_package(root)
    cdir = root / "media" / "takes"
    tids = []
    for i, g in enumerate(pkg.typed["shots"].generations):
        c = _synth_clip(cdir / f"{g.generation_id}_t1.mp4", duration_s=1.5, freq=440 + i * 100)
        tids.append(_accept_clip(root, pkg.header.film_id, g.generation_id, c))

    edl = EditSection(
        events=[
            EditEvent(event_id="e1", take_id=tids[0], src_in_s=0.0, src_out_s=1.2),
            EditEvent(event_id="e2", take_id=tids[1], src_in_s=0.0, src_out_s=1.2,
                      transition=Transition(type="DISSOLVE", duration_s=0.5)),
        ],
        title=[TextLine(text="Title", size=40), TextLine(text="Generated with AI", size=24)],
        title_s=1.0,
        end=[TextLine(text="End", size=40)],
        end_s=1.0,
    )
    (root / "05_edit.json").write_text(edl.model_dump_json(), encoding="utf-8")
    rough = root / "media" / "cut" / "rough_cut.mp4"
    rep = render_cut(load_package(root), edl, rough, clips_dir=cdir)
    cut_json = rough.with_suffix(".cut.json")
    cut_json.write_text(json.dumps(rep, indent=2), encoding="utf-8")
    stem = root / "audio" / "stems" / "dialogue.wav"
    stem.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(rough), "-vn", "-c:a", "pcm_s16le", str(stem)],
        check=True,
        timeout=60,
    )
    from film_pipeline.production.lock import lock_picture
    lock_picture(load_package(root), "Tester", clips_dir=cdir)

    exp, warns = build_package(root, "rough_cut")
    assert any("clamped out_frame" in w for w in warns)
    validate_package(exp, check_media=True)


# ---------------------------------------------------------------------------
# P2 #13, #14, #15: PreSendCritic cold plan, CausalRepair, Scheduler, Router
# ---------------------------------------------------------------------------

def test_p2_13_14_15_critic_causal_scheduler_and_router(tmp_path):
    root = _copy_film03_subset(tmp_path, 2)
    pkg = load_package(root)

    # Finding #13: Cold plan returns PLAN_MISSING BLOCK instead of AttributeError
    critic_res = PreSendCritic().inspect(pkg, plan_dir=tmp_path / "cold_plan")
    assert critic_res["ok"] is False
    block_codes = {f["code"] for f in critic_res["findings"] if f["severity"] == "BLOCK"}
    assert "PLAN_MISSING" in block_codes
    assert block_codes <= {"PLAN_MISSING", "START_STILL_NOT_READY"}

    # Finding #14: CausalRepair handles PROMPT/START_FRAME, empty->CLASSIFY, and cross-version count
    router = CausalRepairRouter(max_attempts=2)
    assert router.route("g1", "")["action"] == "CLASSIFY"
    assert router.route("g1", "")["auto_retry_allowed"] is False
    assert router.route("g1", "PROMPT", failed_attempts=1)["action"] == "rewrite_prompt_plain_single_action"

    c1 = tmp_path / "c1.mp4"
    c2 = tmp_path / "c2.mp4"
    c1.write_bytes(b"v1-fail")
    c2.write_bytes(b"v2-fail")
    gid = pkg.typed["shots"].generations[0].generation_id
    T.register_take(root, pkg.header.film_id, gid, c1, prompt_text="p", route="flow", model="m", credits=6.0, shot_version=1)
    log = T.load_log(root, pkg.header.film_id)
    log.takes[-1].status = "REJECTED"
    log.takes[-1].cause = "PROMPT"
    T.save_log(root, log)

    shots_raw = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
    shots_raw["generations"][0]["version"] = 2
    (root / "04_shots.json").write_text(json.dumps(shots_raw, indent=2), encoding="utf-8")
    T.register_take(root, pkg.header.film_id, gid, c2, prompt_text="p", route="flow", model="m", credits=6.0, shot_version=2)
    log2 = T.load_log(root, pkg.header.film_id)
    log2.takes[-1].status = "REJECTED"
    log2.takes[-1].cause = "PROMPT"
    T.save_log(root, log2)

    diag = router.diagnose_take_log(load_package(root))
    assert len(diag) == 1
    assert diag[0]["total_rejected_across_versions"] == 2
    assert diag[0]["action"] == "ESCALATE_TO_TECH_LEAD"

    # Finding #15: shot_seconds pricing (6s -> 6.0, 12s -> 14.0), Scheduler excludes pending sends, CP2 approval
    cr = CapabilityRouter()
    assert cr.route_shot(SimpleNamespace(generation_id="g6", visible=["A"], duration_s=6.0))["estimated_credits"] == 6.0
    assert cr.route_shot(SimpleNamespace(generation_id="g12", visible=["A"], duration_s=12.0))["estimated_credits"] == 14.0

    # Pending receipt keeps generation out of ready_frontier
    gid1 = pkg.typed["shots"].generations[0].generation_id
    gid2 = pkg.typed["shots"].generations[1].generation_id
    intent_p = root / "takes" / "intents" / f"{gid1}_t1.intent.json"
    intent_p.parent.mkdir(parents=True, exist_ok=True)
    intent_p.write_text(json.dumps({"take_id": f"{gid1}_t1", "generation_id": gid1, "sent": True, "dry_run": False, "result": "PENDING"}), encoding="utf-8")
    waves = WaveDAGScheduler(load_package(root)).plan_waves()
    assert gid1 in waves["pending_sends"]
    assert gid1 not in waves["ready_frontier"]
    assert gid2 in waves["ready_frontier"]


# ---------------------------------------------------------------------------
# P2 #18, #19, #20: Non-finite LedgerAdjustment, Triage tail, Reframe event_id
# ---------------------------------------------------------------------------

def test_p2_18_20_money_nonfinite_and_reframe_event_mapping(tmp_path):
    with pytest.raises(ValidationError):
        money_mod.LedgerAdjustment(adjustment_id="a1", delta=float("nan"), reason="r", evidence="e", by="o")

    root = _copy_film03_subset(tmp_path, 1)
    first = money_mod.record_adjustment(root, -6.0, "refund", "ev1", "owner", adjustment_id="adj-1")
    dup = money_mod.record_adjustment(root, -6.0, "refund", "ev1", "owner", adjustment_id="adj-1")
    assert first.adjustment_id == dup.adjustment_id == "adj-1"
    with pytest.raises(ValueError, match="conflicting adjustment_id"):
        money_mod.record_adjustment(root, -12.0, "other", "ev1", "owner", adjustment_id="adj-1")

    # Finding #20: reframe on renamed + repeated EDL events
    pkg = load_package(root)
    gid = pkg.typed["shots"].generations[0].generation_id
    fake_clip = tmp_path / "take.mp4"
    fake_clip.write_bytes(b"video")
    entry, _ = T.register_take(root, pkg.header.film_id, gid, fake_clip, prompt_text="p", route="flow", model="m", credits=6.0)
    edl = EditSection(
        events=[
            EditEvent(event_id="E12_FIRST", take_id=entry.take_id, src_in_s=0.0, src_out_s=1.0),
            EditEvent(event_id="E13_REPEAT", take_id=entry.take_id, src_in_s=0.0, src_out_s=1.0),
        ]
    )
    (root / "05_edit.json").write_text(edl.model_dump_json(), encoding="utf-8")
    box = {"x": 0.05, "y": 0.05, "w": 0.9, "h": 0.9}
    T._merge_reframe(root, gid, box, take_id=entry.take_id)
    raw_ref = json.loads((root / "titles" / "reframe.json").read_text(encoding="utf-8"))
    assert "E12_FIRST" in raw_ref["events"] and "E13_REPEAT" in raw_ref["events"]
    assert gid not in raw_ref["events"]

    # Also test resolve_reframes_for_section expands generation-keyed entries written before 05_edit.json existed
    expanded = ti_mod.resolve_reframes_for_section(root, edl, {gid: box})
    assert set(expanded) == {"E12_FIRST", "E13_REPEAT"}
    assert ti_mod.reframe_problems(edl, ti_mod.ReframePlan(events=expanded)) == []


@_needs_ffmpeg
def test_p2_19_triage_samples_tail_of_15s_clip_and_checks_hash(tmp_path):
    root = _copy_film03_subset(tmp_path, 1)
    pkg = load_package(root)
    gid = pkg.typed["shots"].generations[0].generation_id
    clip = _synth_clip(root / "media" / "takes" / "long15s.mp4", duration_s=15.0, color="navy", size="320x180")
    tid = _accept_clip(root, pkg.header.film_id, gid, clip)
    tri = dailies_triage.triage_take(load_package(root), tid)
    assert tri["hash_verified"] is True
    assert len(tri["output_sha256"]) == 64
    assert 2 <= tri["metrics"]["frames_sampled"] <= 12

    # Inject frame change ONLY at t=14.9s; verify _gray_frames catches the tail change
    base_clip = _synth_clip(tmp_path / "solid.mp4", duration_s=14.0, color="black", size="320x180")
    tail_clip = _synth_clip(tmp_path / "white_tail.mp4", duration_s=1.0, color="white", size="320x180")
    merged = tmp_path / "tail_spike.mp4"
    lst = tmp_path / "list.txt"
    lst.write_text(f"file '{base_clip.as_posix()}'\nfile '{tail_clip.as_posix()}'\n", encoding="utf-8")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(merged)], check=True)
    frames = dailies_triage._gray_frames(merged, max_frames=12, duration_s=15.0)
    assert sum(frames[-1]) / len(frames[-1]) > 180.0


# ---------------------------------------------------------------------------
# Tech Lead Concurrency, Corrupt JSON, Silent Loudness, Boundary FFmpeg, Doctor
# ---------------------------------------------------------------------------

def test_tl_parallel_multi_account_generate_no_film_busy(tmp_path, monkeypatch):
    root = _copy_film03_subset(tmp_path, count=None)
    header = json.loads((root / "film.json").read_text(encoding="utf-8"))
    header.setdefault("budget", {})["credits_estimate"] = 200
    (root / "film.json").write_text(json.dumps(header, indent=2), encoding="utf-8")
    pkg = load_package(root)
    plan_package(pkg, root / "media" / "plan", storyboard=True, approve_storyboard="owner")
    from PIL import Image
    from film_pipeline.production import stills as st_mod
    gids = [g.generation_id for g in pkg.typed["shots"].generations if not g.previous_generation_id][:2]
    for gid in gids:
        s = tmp_path / f"{gid}.png"
        Image.new("RGB", (64, 36), (10, 20, 30)).save(s)
        st_mod.register_still(load_package(root), gid, s, source="test")
        st_mod.approve_still(load_package(root), gid, "Owner")

    backlog = tmp_path / "backlog.md"
    backlog.write_text("OWNER_GO_LIVE: YES\n", encoding="utf-8")
    monkeypatch.setenv("AFP_FREE_GIB_MIN", "0")

    barrier = threading.Barrier(2, timeout=5.0)
    results: dict[str, dict] = {}
    errors: list[BaseException] = []

    def make_runner(out_bytes: bytes):
        def _run(argv: list[str], out: Path) -> dict:
            barrier.wait()  # Proves Phase B runs simultaneously on two accounts without holding film_lock
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(out_bytes)
            return {"result": "PASSED", "returncode": 0}
        return _run

    def worker(gid: str, acct: str, proj: str, cdp: str, tag: bytes):
        try:
            res = gen_mod.generate(
                load_package(root), gid, dry_run=False, stills_dir=root / "media" / "stills", backlog=backlog,
                runner=make_runner(tag), account_scope=acct, cdp_scope=proj, cdp_endpoint=cdp,
            )
            results[gid] = res
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    t1 = threading.Thread(target=worker, args=(gids[0], "acct_alpha", "proj-alpha", "http://127.0.0.1:9331", b"clip-1"))
    t2 = threading.Thread(target=worker, args=(gids[1], "acct_beta", "proj-beta", "http://127.0.0.1:9332", b"clip-2"))
    t1.start()
    t2.start()
    t1.join(timeout=15.0)
    t2.join(timeout=15.0)

    assert not errors
    assert results[gids[0]]["sent"] is True, results[gids[0]]
    assert results[gids[1]]["sent"] is True, results[gids[1]]
    assert results[gids[0]]["payload"]["account"] == "acct_alpha"
    assert results[gids[1]]["payload"]["account"] == "acct_beta"
    receipt_0 = json.loads(Path(results[gids[0]]["receipt"]).read_text(encoding="utf-8"))
    assert receipt_0["sent_on"]
    assert receipt_0["account"] == "acct_alpha"
    send_log = [json.loads(line) for line in (root / "takes" / "send_log.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert {row.get("account") for row in send_log} == {"acct_alpha", "acct_beta"}


@_needs_ffmpeg
def test_tl_silent_normalize_loudness_and_corrupt_json_guards(tmp_path):
    # Silent clip does not fail with loudnorm measured_I=-inf
    silent = _synth_clip(tmp_path / "silent.mp4", duration_s=1.0, silent=True, size="320x180")
    metrics = drama_post.normalize_loudness(silent)
    assert (not math.isfinite(metrics["integrated_lufs"])) or metrics["integrated_lufs"] <= -69.0

    # Corrupt QC & corrupt MANIFEST return structured blockers instead of uncaught ValidationError
    root = _copy_film03_subset(tmp_path, 1)
    (root / "qc").mkdir(parents=True, exist_ok=True)
    (root / "qc" / "master_qc.json").write_text("{corrupt", encoding="utf-8")
    issues = gate_checks.master_issues(load_package(root))
    assert any("corrupt qc/master_qc.json" in i for i in issues)

    arch = tmp_path / "bad_arch"
    arch.mkdir()
    (arch / "MANIFEST.json").write_text("{not-json", encoding="utf-8")
    ver = DL.verify_archive(arch)
    assert ver["ok"] is False and ver["problems"][0]["code"] == "MANIFEST_CORRUPT"


@_needs_ffmpeg
def test_tl_boundary_fractional_dissolve_jl_cut_and_cli_doctor(tmp_path):
    # Test boundary fractional trims + 0.5s dissolve + J/L split + portrait build + CLI doctor
    root = _copy_film03_subset(tmp_path, 2)
    pkg = load_package(root)
    cdir = root / "media" / "takes"
    tids = []
    for i, g in enumerate(pkg.typed["shots"].generations):
        c = _synth_clip(cdir / f"{g.generation_id}_t1.mp4", duration_s=2.4, freq=440 + i * 220)
        tids.append(_accept_clip(root, pkg.header.film_id, g.generation_id, c))

    edl = EditSection(
        events=[
            EditEvent(event_id="ev1", take_id=tids[0], src_in_s=0.1, src_out_s=1.35),
            EditEvent(event_id="ev2", take_id=tids[1], src_in_s=0.15, src_out_s=1.4,
                      transition=Transition(type="DISSOLVE", duration_s=0.5),
                      audio=AudioCut(j_cut_s=0.1, l_cut_s=0.1)),
        ],
        title=[TextLine(text="Boundary", size=48), TextLine(text="Generated with AI", size=24)],
        title_s=1.0,
        end=[TextLine(text="Done", size=40)],
        end_s=0.5,
    )
    (root / "05_edit.json").write_text(edl.model_dump_json(), encoding="utf-8")
    cut_mp4 = root / "media" / "cut" / "titled_cut.mp4"
    rep = render_cut(load_package(root), edl, cut_mp4, clips_dir=cdir)
    cut_json = cut_mp4.with_suffix(".cut.json")
    cut_json.write_text(json.dumps(rep, indent=2), encoding="utf-8")
    assert drama_post.probe_video_duration(cut_mp4) > 3.0

    done = subprocess.run(
        [sys.executable, "-m", "film_pipeline", "doctor", "--film", str(root), "--operation", "send"],
        capture_output=True, text=True, check=False, cwd=ROOT,
    )
    assert done.returncode == 0, done.stderr
    doc = json.loads(done.stdout)
    assert doc["ok"] is True and doc["readonly"] is True
    assert doc["resources"]["sfx_catalog"]["ok"] is True
    assert doc["resources"]["film_package_schema"]["ok"] is True
    assert doc["ffmpeg_filters"]["xfade"] is True
