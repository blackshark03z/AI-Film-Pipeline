from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from film_pipeline.agentic import (
    AccountLeasePool,
    CapabilityRouter,
    CausalRepairRouter,
    PreSendCritic,
    SceneIncrementalConformer,
    WaveDAGScheduler,
)
from film_pipeline.production import takes as T
from film_pipeline.production.package import load_package
from film_pipeline.production.plan import plan_package

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
FILM08 = ROOT / "films" / "film08_chain_of_custody"
TOOL = ROOT / "tools" / "film.py"


def _copy_film03(tmp_path: Path) -> Path:
    root = tmp_path / "film"
    root.mkdir(parents=True)
    for name in ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json"):
        shutil.copyfile(FILM03 / name, root / name)
    return root


def _accept_gen(root: Path, film_id: str, gid: str, clip: Path, *, shot_version: int = 1) -> None:
    T.register_take(root, film_id, gid, clip, prompt_text=f"prompt for {gid}", route="flow", model="m", credits=6.0, shot_version=shot_version)
    log = T.load_log(root, film_id)
    for t in log.takes:
        if t.generation_id == gid and t.shot_version == shot_version:
            t.status = "ACCEPTED"
    T.save_log(root, log)


def test_wave_dag_scheduler_partitions_waves(tmp_path):
    root = _copy_film03(tmp_path)
    shots = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
    gens = shots["generations"][:3]
    g0, g1, g2 = gens[0]["generation_id"], gens[1]["generation_id"], gens[2]["generation_id"]
    gens[0]["previous_generation_id"] = None
    gens[1]["previous_generation_id"] = g0
    gens[2]["previous_generation_id"] = g1
    shots["generations"] = gens
    (root / "04_shots.json").write_text(json.dumps(shots, indent=2), encoding="utf-8")

    # Initial waves before accepting g0
    plan0 = WaveDAGScheduler(load_package(root)).plan_waves()
    assert plan0["remaining_count"] == 3
    assert plan0["ready_frontier"] == [g0]
    assert [x["generation_id"] for x in plan0["waves"]["1"]] == [g1]
    assert [x["generation_id"] for x in plan0["waves"]["2"]] == [g2]
    assert plan0["critical_path_depth"] == 3

    # Accept g0 -> g1 becomes Wave 0 ready frontier, g2 shifts to Wave 1
    clip0 = tmp_path / f"{g0}_t1.mp4"
    clip0.write_bytes(b"fake-mp4-g0")
    _accept_gen(root, "film03_front_desk", g0, clip0, shot_version=gens[0].get("version", 1))
    plan1 = WaveDAGScheduler(load_package(root)).plan_waves()
    assert plan1["accepted_count"] == 1
    assert plan1["ready_frontier"] == [g1]
    assert [x["generation_id"] for x in plan1["waves"]["1"]] == [g2]
    assert plan1["critical_path_depth"] == 2


def test_account_lease_pool_atomic_reserve_cooldown_and_quarantine(tmp_path):
    db_path = tmp_path / "agentic_leases.sqlite3"
    pool = AccountLeasePool(db_path, min_reserve_credits=20.0, cooldown_s=60.0)
    pool.register_account("acct_low", 24.0)   # 24 - 6 = 18 < 20 reserve -> ineligible
    pool.register_account("acct_a", 100.0)
    pool.register_account("acct_b", 80.0)

    l1 = pool.acquire("SC01_g1", cost_credits=6.0, now=1000.0)
    assert l1 is not None and l1["account_id"] == "acct_a"

    l2 = pool.acquire("SC01_g2", cost_credits=6.0, now=1000.0)
    assert l2 is not None and l2["account_id"] == "acct_b"

    # Both eligible accounts busy, acct_low below reserve
    assert pool.acquire("SC01_g3", cost_credits=6.0, now=1000.0) is None

    # Quarantine acct_a without halting healthy acct_b; unresolved lease stays quarantined against double-dispatch
    q = pool.quarantine_account("acct_a", "unusual activity")
    assert q["status"] == "COOLDOWN_QUARANTINE"

    # Release SC01_g2 and advance past cooldown_s -> unresolved SC01_g1 still blocked until proven NOT_SUBMITTED
    pool.release("SC01_g2", credits_spent=6.0, now=1010.0)
    assert pool.acquire("SC01_g1", cost_credits=6.0, now=1020.0) is None
    assert pool.acquire("SC01_g1", cost_credits=6.0, now=1075.0) is None
    # After reconciliation confirms NOT_SUBMITTED, explicitly release acct_a's quarantined lease -> acct_b picks it up
    pool.quarantine_account("acct_a", "proven NOT_SUBMITTED", release_active_leases=True)
    l1_re = pool.acquire("SC01_g1", cost_credits=6.0, now=1075.0)
    assert l1_re is not None and l1_re["account_id"] == "acct_b"
    snap = pool.snapshot()
    acct_b = next(a for a in snap["accounts"] if a["account_id"] == "acct_b")
    assert acct_b["credits"] == 74.0


def test_pre_send_critic_catches_leakage_prohibition_and_still(tmp_path):
    root = _copy_film03(tmp_path)
    pkg = load_package(root)
    plan_dir = tmp_path / "plan"
    plan_package(pkg, plan_dir, storyboard=False)

    shots = pkg.typed["shots"].generations
    single_shot = next(g for g in shots if g.coverage == "SINGLE" and len(g.visible) == 1)
    multi_shot = next((g for g in shots if len(g.visible) >= 2), None)
    assert multi_shot is not None

    # Inject off-frame token into SINGLE prompt and 'No touching.' conflict into multi shot prompt
    off_char = next(c for c in pkg.typed["preprod"].characters if c not in single_shot.visible)
    sp_file = plan_dir / "prompts" / f"{single_shot.generation_id}.txt"
    sp_file.write_text(sp_file.read_text(encoding="utf-8") + f" Eyes stay on {off_char}.", encoding="utf-8")

    shots_raw = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
    for g in shots_raw["generations"]:
        if g["generation_id"] == multi_shot.generation_id:
            g["choreography"]["once_actions"] = ["Hollis lays the badge on the counter"]
    (root / "04_shots.json").write_text(json.dumps(shots_raw, indent=2), encoding="utf-8")
    mp_file = plan_dir / "prompts" / f"{multi_shot.generation_id}.txt"
    mp_file.write_text(mp_file.read_text(encoding="utf-8") + " No touching.", encoding="utf-8")

    res = PreSendCritic().inspect(load_package(root), plan_dir=plan_dir)
    codes = {(f["generation_id"], f["code"]) for f in res["findings"]}
    assert (single_shot.generation_id, "CROSS_ATTENTION_LEAK_RISK") in codes
    assert (multi_shot.generation_id, "PROHIBITION_ACTION_CONFLICT") in codes
    head = next(g for g in shots if not g.previous_generation_id)
    assert (head.generation_id, "START_STILL_NOT_READY") in codes
    assert res["ok"] is False


def test_causal_repair_router_bounds_retries_and_halts_on_refusal():
    router = CausalRepairRouter(max_attempts=2)
    r1 = router.route("SC09_g03", "OFF_FRAME_INTRUSION", failed_attempts=1)
    assert r1["action"] == "enable_de_personify_off_frame"
    assert r1["auto_retry_allowed"] is True and r1["escalate"] is False

    r2 = router.route("SC09_g03", "OFF_FRAME_INTRUSION", failed_attempts=2)
    assert r2["action"] == "ESCALATE_TO_TECH_LEAD"
    assert r2["auto_retry_allowed"] is False and r2["escalate"] is True

    r_refusal = router.route("SC10_g01", "PROVIDER_CONTENT_REFUSAL", failed_attempts=1)
    assert r_refusal["action"] == "HALT_HUMAN_DECISION"
    assert r_refusal["halted"] is True and r_refusal["auto_retry_allowed"] is False


def test_scene_incremental_conformer_cache_and_invalidation(tmp_path):
    if not shutil.which("ffmpeg"):
        return
    root = _copy_film03(tmp_path)
    shots = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
    by_scene: dict[str, list[dict]] = {}
    for g in shots["generations"]:
        by_scene.setdefault(g["scene_id"], []).append(g)
    scenes = list(by_scene)[:2]
    sc1, sc2 = scenes[0], scenes[1]
    sc1_gen = {**by_scene[sc1][0], "previous_generation_id": None}
    sc2_gen = {**by_scene[sc2][0], "previous_generation_id": None}
    shots["generations"] = [sc1_gen, sc2_gen]
    (root / "04_shots.json").write_text(json.dumps(shots, indent=2), encoding="utf-8")

    takes_dir = root / "media" / "takes"
    takes_dir.mkdir(parents=True, exist_ok=True)
    clip = takes_dir / f"{sc1_gen['generation_id']}_t1.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=1",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo:duration=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(clip),
    ], check=True)
    _accept_gen(root, "film03_front_desk", sc1_gen["generation_id"], clip, shot_version=sc1_gen.get("version", 1))

    conf = SceneIncrementalConformer()
    dry = conf.conform_ready_scenes(load_package(root), render=False)
    assert sc1 in dry["ready_scenes"] and sc2 in dry["incomplete_scenes"]

    built = conf.conform_ready_scenes(load_package(root), render=True)
    assert len(built["rendered"]) == 1
    assert (root / "media" / "scenes" / f"{sc1}.mkv").is_file()

    fresh = conf.scene_status(load_package(root))
    assert sc1 in fresh["fresh_scenes"]

    # Mutate shared color config -> cache invalidates to READY_TO_CONFORM
    (root / "color").mkdir(exist_ok=True)
    (root / "color" / "color_plan.json").write_text('{"look": "eq=brightness=0.05"}\n', encoding="utf-8")
    stale = conf.scene_status(load_package(root))
    assert sc1 in stale["ready_scenes"]


def test_capability_router_and_film08_agentic_plan_readonly_cli():
    cr = CapabilityRouter()
    probe = cr.route_shot(SimpleNamespace(generation_id="g1", visible=["A"]), blocking_probe=True)
    muse = cr.route_shot(SimpleNamespace(generation_id="g2", visible=[]), multi_location_cast_anchor=True, strict_face_lock_from_still=False)
    flow = cr.route_shot(SimpleNamespace(generation_id="g3", visible=["HOLLIS"]))
    low = cr.route_shot(SimpleNamespace(generation_id="g4", visible=["HOLLIS"]), budget_remaining=2.0)
    assert probe["lane"] == "vilao_probe"
    assert muse["lane"] == "muse_gateway"
    assert flow["lane"] == "flow_omni_flash" and flow["budget_blocked"] is False
    assert low["lane"] == "flow_omni_flash" and low["budget_blocked"] is True

    if not FILM08.is_dir():
        return
    cli = subprocess.run(
        [sys.executable, str(TOOL), "agentic-plan", "--film", str(FILM08)],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert cli.returncode == 0, cli.stderr
    data = json.loads(cli.stdout)
    assert data["readonly"] is True
    assert data["waves"]["accepted_count"] == 300
    assert data["waves"]["remaining_count"] == 0
    assert data["waves"]["ready_frontier"] == []
    assert data["checkpoints"]["CP1_brief_cast_budget"]["status"] == "APPROVED"
    assert data["checkpoints"]["CP2_pilot_scene_reel"]["status"] == "READY_FOR_PILOT_REVIEW"
    assert data["checkpoints"]["CP3_master_acceptance"]["status"] == "OWNER_PENDING"
    assert data["incremental_conform"]["total_scenes"] == 12
