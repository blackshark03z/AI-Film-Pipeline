import json
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.production import generate as G
from film_pipeline.production import takes as T
from film_pipeline.production.package import load_package
from film_pipeline.production.plan import plan_package

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
TOOL = ROOT / "tools" / "film.py"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")


def film(tmp_path, estimate=None, approve=True):
    root = tmp_path / "film"
    root.mkdir(parents=True)
    for name in FILES:
        (root / name).write_text((FILM03 / name).read_text(encoding="utf-8"), encoding="utf-8")
    if estimate is not None:
        header = json.loads((root / "film.json").read_text(encoding="utf-8"))
        header["budget"]["credits_estimate"] = estimate
        (root / "film.json").write_text(json.dumps(header), encoding="utf-8")
    pkg = load_package(root)
    if approve:  # the human storyboard approval `film.py plan --approve-storyboard` records in media/plan
        plan_package(pkg, root / "media" / "plan", approve_storyboard="owner")
    return pkg


def backlog(tmp_path, line="OWNER_GO_LIVE: NO"):
    path = tmp_path / "backlog.md"
    path.write_text(f"# Loop backlog\n\n{line}\n<!-- OWNER_GO_LIVE: YES would be a comment -->\n", encoding="utf-8")
    return path


def still(tmp_path, gid="SC01_g1"):
    folder = tmp_path / "stills"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"start_{gid}.png").write_bytes(b"png-bytes")
    return folder


def accept(pkg, gid, n=1, version=1, credits=12.0):
    log = T.load_log(pkg.root, pkg.header.film_id)
    log.takes.append(T.TakeEntry(take_id=f"{gid}_t{n}", generation_id=gid, prompt_sha256="a" * 64, route="r", model="m",
                                 credits=credits, output_file="x.mp4", output_sha256="b" * 64, status="ACCEPTED",
                                 shot_version=version))
    T.save_log(pkg.root, log)


def codes(payload):
    return [b["code"] for b in payload["blockers"]]


class FakeRunner:
    def __init__(self, result="PASSED"):
        self.calls, self.result = [], result

    def __call__(self, argv, out):
        self.calls.append(argv)
        if self.result == "PASSED":
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"fake-video-bytes")
        return {"result": self.result}


def test_go_live_is_only_a_literal_yes_line(tmp_path):
    assert not G.owner_go_live(backlog(tmp_path))
    assert G.owner_go_live(backlog(tmp_path, "OWNER_GO_LIVE: YES"))
    assert not G.owner_go_live(tmp_path / "missing.md")
    comment = tmp_path / "c.md"
    comment.write_text("<!-- OWNER_GO_LIVE: YES -->\n", encoding="utf-8")
    assert not G.owner_go_live(comment)  # a commented mention is not the header line
    assert not G.owner_go_live()  # the real backlog is NO while the Owner has not flipped it


def test_dry_run_builds_the_exact_payload_and_sends_nothing(tmp_path):
    pkg = film(tmp_path)
    runner = FakeRunner()
    done = G.generate(pkg, "SC01_g1", dry_run=True, stills_dir=still(tmp_path), backlog=backlog(tmp_path))
    p = done["payload"]
    prompt = (Path(p["prompt_file"])).read_text(encoding="utf-8").strip()
    assert not done["sent"] and done["dry_run"] and not runner.calls
    assert p["prompt_sha256"] == T.sha256_text(prompt) and p["prompt_words"] == len(prompt.split())
    assert p["take_id"] == "SC01_g1_t1" and p["output"].endswith("SC01_g1_t1.mp4")
    assert p["route"] == "start_frame+Khung hinh" and p["model"] == "Omni Flash 360p" and p["expected_credits"] == 12
    assert p["argv"][2:5] == [p["prompt_file"], p["output"], "--start"] and "--start-file" in p["argv"]
    assert p["start_frame"]["exists"] and p["start_frame"]["sha256"] == T.sha256_text("png-bytes")
    assert not (Path(p["output"])).exists()  # nothing rendered


def test_dry_run_reports_live_only_blockers_but_is_not_ready(tmp_path):
    done = G.generate(film(tmp_path), "SC01_g1", dry_run=True, stills_dir=still(tmp_path), backlog=backlog(tmp_path))
    assert codes(done["payload"]) == ["START_TOKEN_MISSING", "BUDGET_NOT_SET"] and not done["ready_to_send"]
    assert all(b["live_only"] for b in done["payload"]["blockers"])
    ready = G.generate(film(tmp_path / "b", estimate=100), "SC01_g1", dry_run=True,
                       stills_dir=still(tmp_path / "b"), start_token="tok:abc", backlog=backlog(tmp_path))
    assert ready["ready_to_send"] and ready["payload"]["blockers"] == [] and ready["payload"]["credit_cap"] == 150


def test_unapproved_storyboard_blocks_the_send(tmp_path):
    done = G.generate(film(tmp_path, 100, approve=False), "SC01_g1", dry_run=True, stills_dir=still(tmp_path),
                      start_token="tok:abc", backlog=backlog(tmp_path))
    assert set(codes(done["payload"])) == {"PACKAGE_PROBLEM"} and not done["ready_to_send"]
    assert any("SC01_g1 preflight BLOCKED" in b["detail"] for b in done["payload"]["blockers"])


def test_missing_start_frame_is_a_blocker(tmp_path):
    done = G.generate(film(tmp_path, 100), "SC01_g1", dry_run=True, stills_dir=tmp_path / "nowhere",
                      start_token="tok:abc", backlog=backlog(tmp_path))
    assert codes(done["payload"]) == ["START_FRAME_MISSING"] and not done["payload"]["start_frame"]["exists"]


def test_intent_receipt_is_written_and_stable(tmp_path):
    pkg = film(tmp_path, 100)
    kw = dict(dry_run=True, stills_dir=still(tmp_path), start_token="tok:abc", backlog=backlog(tmp_path))
    first = G.generate(pkg, "SC01_g1", **kw)
    path = Path(first["receipt"])
    text = path.read_text(encoding="utf-8")
    receipt = json.loads(text)
    assert path.name == "SC01_g1_t1.intent.json" and receipt["dry_run"] and not receipt["sent"]
    assert receipt["prompt_sha256"] == first["payload"]["prompt_sha256"] and receipt["blockers"] == []
    G.generate(pkg, "SC01_g1", **kw)
    assert path.read_text(encoding="utf-8") == text  # an unchanged payload rewrites the same receipt


def test_chained_generation_needs_the_previous_take_accepted(tmp_path):
    pkg = film(tmp_path, 100)
    kw = dict(dry_run=True, stills_dir=still(tmp_path, "SC01_g2"), start_token="tok:abc", backlog=backlog(tmp_path))
    blocked = G.generate(pkg, "SC01_g2", **kw)
    assert codes(blocked["payload"]) == ["HANDOFF_PREVIOUS_NOT_ACCEPTED"]
    accept(pkg, "SC01_g1")
    ok = G.generate(pkg, "SC01_g2", **kw)
    assert ok["payload"]["blockers"] == [] and ok["payload"]["start_frame"]["source"] == "end frame of SC01_g1_t1"
    # a take of another shot version does not count for the current version
    pkg2 = film(tmp_path / "v", 100)
    accept(pkg2, "SC01_g1", version=2)
    stale = G.generate(pkg2, "SC01_g2", dry_run=True, stills_dir=still(tmp_path / "v", "SC01_g2"), start_token="tok:a",
                       backlog=backlog(tmp_path))
    assert codes(stale["payload"]) == ["HANDOFF_PREVIOUS_NOT_ACCEPTED"]


def test_take_numbers_follow_the_log(tmp_path):
    pkg = film(tmp_path, 100)
    accept(pkg, "SC01_g1")
    done = G.generate(pkg, "SC01_g1", dry_run=True, stills_dir=still(tmp_path), backlog=backlog(tmp_path))
    assert done["payload"]["take_id"] == "SC01_g1_t2" and done["payload"]["credits_spent"] == 12


def test_unknown_generation_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="unknown generation"):
        G.generate(film(tmp_path), "SC99_g1", dry_run=True)


def test_live_refuses_without_owner_go_and_never_calls_the_runner(tmp_path):
    runner = FakeRunner()
    done = G.generate(film(tmp_path, 100), "SC01_g1", dry_run=False, stills_dir=still(tmp_path), start_token="tok:abc",
                      backlog=backlog(tmp_path), runner=runner)
    assert not done["sent"] and [r["code"] for r in done["refused"]] == ["OWNER_GO_LIVE_NO"] and not runner.calls
    receipt = json.loads(Path(done["receipt"]).read_text(encoding="utf-8"))
    assert receipt["refused"] == ["OWNER_GO_LIVE_NO"] and not receipt["sent"] and not receipt["owner_go_live"]


def test_live_refuses_on_budget_token_or_blockers_even_with_go(tmp_path):
    go = backlog(tmp_path, "OWNER_GO_LIVE: YES")
    runner = FakeRunner()
    no_budget = G.generate(film(tmp_path), "SC01_g1", dry_run=False, stills_dir=still(tmp_path), start_token="tok:a",
                           backlog=go, runner=runner)
    assert [r["code"] for r in no_budget["refused"]] == ["BUDGET_NOT_SET"]
    no_token = G.generate(film(tmp_path / "t", 100), "SC01_g1", dry_run=False, stills_dir=still(tmp_path / "t"),
                          backlog=go, runner=runner)
    assert [r["code"] for r in no_token["refused"]] == ["START_TOKEN_MISSING"]
    pkg = film(tmp_path / "c", 20)  # cap 30: one 12-credit take fits, two do not
    accept(pkg, "SC01_g1", credits=24.0)
    over = G.generate(pkg, "SC01_g1", dry_run=False, stills_dir=still(tmp_path / "c"), start_token="tok:a", backlog=go,
                      runner=runner)
    assert [r["code"] for r in over["refused"]] == ["BUDGET_EXCEEDED"] and not runner.calls


def test_live_with_go_sends_once_and_registers_the_take(tmp_path):
    pkg = film(tmp_path, 100)
    runner = FakeRunner()
    done = G.generate(pkg, "SC01_g1", dry_run=False, stills_dir=still(tmp_path), start_token="tok:abc",
                      backlog=backlog(tmp_path, "OWNER_GO_LIVE: YES"), runner=runner)
    assert done["sent"] and len(runner.calls) == 1 and done["manifest_result"] == "PASSED"
    assert "tok:abc" in runner.calls[0] and runner.calls[0][runner.calls[0].index("--start") + 1] == "tok:abc"
    logged = T.load_log(pkg.root, pkg.header.film_id).get("SC01_g1_t1")
    assert logged.status == "GENERATED" and logged.prompt_sha256 == done["payload"]["prompt_sha256"]
    assert logged.start_frame_sha256 == done["payload"]["start_frame"]["sha256"] and logged.credits == 12
    receipt = json.loads(Path(done["receipt"]).read_text(encoding="utf-8"))
    assert receipt["sent"] and receipt["result"] == "PASSED" and receipt["take_registered"]


def test_a_failed_send_registers_no_take_but_keeps_the_receipt(tmp_path):
    pkg = film(tmp_path, 100)
    done = G.generate(pkg, "SC01_g1", dry_run=False, stills_dir=still(tmp_path), start_token="tok:abc",
                      backlog=backlog(tmp_path, "OWNER_GO_LIVE: YES"), runner=FakeRunner("BLOCKED"))
    assert done["sent"] and "take" not in done and T.load_log(pkg.root, pkg.header.film_id).takes == []
    receipt = json.loads(Path(done["receipt"]).read_text(encoding="utf-8"))
    assert receipt["result"] == "BLOCKED" and not receipt["take_registered"]


def test_cli_dry_run_and_refused_live(tmp_path):
    pkg = film(tmp_path, 100)
    base = [sys.executable, str(TOOL), "generate", "--film", str(pkg.root), "--gid", "SC01_g1",
            "--stills", str(still(tmp_path)), "--start-token", "tok:abc", "--backlog", str(backlog(tmp_path))]
    dry = subprocess.run([*base, "--dry-run"], capture_output=True, text=True, encoding="utf-8")
    body = json.loads(dry.stdout)
    assert dry.returncode == 0 and body["dry_run"] and body["ready_to_send"] and not body["sent"]
    live = subprocess.run(base, capture_output=True, text=True, encoding="utf-8")
    refused = json.loads(live.stdout)
    assert live.returncode == 1 and not refused["sent"] and refused["refused"][0]["code"] == "OWNER_GO_LIVE_NO"
    bad = subprocess.run([sys.executable, str(TOOL), "generate", "--film", str(pkg.root), "--gid", "NOPE", "--dry-run"],
                         capture_output=True, text=True, encoding="utf-8")
    assert bad.returncode == 2


def test_an_accepted_take_verifies_the_end_state_the_next_shot_depends_on(tmp_path):
    # film03 SC03_g1 needs the letter's end state from SC02_g2 verified (CROSS_CUT_DEPENDENCY); an accepted take does it
    kw = dict(dry_run=True, start_token="tok:abc", backlog=backlog(tmp_path))
    pkg = film(tmp_path, 100)
    before = G.generate(pkg, "SC03_g1", stills_dir=still(tmp_path, "SC03_g1"), **kw)
    assert any("SC03_g1 preflight BLOCKED" in b["detail"] for b in before["payload"]["blockers"])
    accept(pkg, "SC02_g2")
    after = G.generate(pkg, "SC03_g1", stills_dir=still(tmp_path, "SC03_g1"), **kw)
    assert after["payload"]["blockers"] == [] and after["ready_to_send"]


def test_other_shots_waiting_on_their_predecessor_do_not_block_this_one(tmp_path):
    done = G.generate(film(tmp_path, 100), "SC01_g1", dry_run=True, stills_dir=still(tmp_path), start_token="tok:abc",
                      backlog=backlog(tmp_path))
    assert done["payload"]["blockers"] == []  # SC03_g1's own preflight is BLOCKED until SC02_g2 is accepted


# ------------------------------------------------------------------ Codex review fixes


def test_go_live_needs_one_exact_line(tmp_path):
    for text in ("OWNER_GO_LIVE:\nYES\n", "OWNER_GO_LIVE: YES, but not yet\n", "OWNER_GO_LIVE:  YES\n",
                 "OWNER_GO_LIVE: YES\nOWNER_GO_LIVE: NO\n", "OWNER_GO_LIVE: YESTERDAY\n", "  OWNER_GO_LIVE: YES\n"):
        path = tmp_path / "b.md"
        path.write_text(text, encoding="utf-8")
        assert not G.owner_go_live(path), text
    path = tmp_path / "ok.md"
    path.write_bytes(b"# x\r\nOWNER_GO_LIVE: YES \r\n")
    assert G.owner_go_live(path)


GO = "OWNER_GO_LIVE: YES"


def live(pkg, tmp_path, runner, **kw):
    return G.generate(pkg, "SC01_g1", dry_run=False, stills_dir=still(tmp_path), start_token="tok:abc",
                      backlog=backlog(tmp_path, GO), runner=runner, **kw)


def test_a_failed_send_keeps_its_take_number_and_its_credits(tmp_path):
    pkg = film(tmp_path, 20)   # cap 30: two 12-credit sends fit, three do not
    first = live(pkg, tmp_path, FakeRunner("TIMEOUT"))
    assert first["sent"] and first["payload"]["take_id"] == "SC01_g1_t1"
    second = live(pkg, tmp_path, FakeRunner("TIMEOUT"))
    assert second["payload"]["take_id"] == "SC01_g1_t2" and second["payload"]["credits_spent"] == 12
    assert (Path(first["receipt"]).parent / "SC01_g1_t1.intent.json").is_file()   # evidence of t1 is not overwritten
    third = live(pkg, tmp_path, FakeRunner())
    assert not third["sent"] and [r["code"] for r in third["refused"]] == ["BUDGET_EXCEEDED"]
    assert third["payload"]["credits_spent"] == 24


def test_an_interrupted_send_blocks_the_next_one(tmp_path):
    pkg = film(tmp_path, 100)

    class Dies:
        calls = 0

        def __call__(self, argv, out):
            self.calls += 1
            raise RuntimeError("process died")

    with pytest.raises(RuntimeError):
        live(pkg, tmp_path, Dies())
    receipt = json.loads((T.takes_dir(pkg.root) / "intents" / "SC01_g1_t1.intent.json").read_text(encoding="utf-8"))
    assert receipt["sent"] and receipt["result"] == "PENDING"
    runner = FakeRunner()
    again = live(pkg, tmp_path, runner)
    assert not again["sent"] and not runner.calls
    assert [r["code"] for r in again["refused"]] == ["SEND_PENDING"] and again["payload"]["take_id"] == "SC01_g1_t2"


def test_a_pending_receipt_on_disk_blocks_even_without_an_exception(tmp_path):
    pkg = film(tmp_path, 100)
    folder = T.takes_dir(pkg.root) / "intents"
    folder.mkdir(parents=True)
    (folder / "SC01_g1_t1.intent.json").write_text("{not json", encoding="utf-8")   # killed mid-write
    again = live(pkg, tmp_path, FakeRunner())
    assert [r["code"] for r in again["refused"]] == ["SEND_PENDING"]


def test_a_failing_sender_does_not_register_an_old_clip(tmp_path):
    pkg = film(tmp_path, 100)

    class Crashes:
        def __call__(self, argv, out):
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"old-bytes")
            return {"result": "PASSED", "returncode": 1}

    done = live(pkg, tmp_path, Crashes())
    assert done["manifest_result"] == "SENDER_EXIT_1" and "take" not in done
    assert T.load_log(pkg.root, pkg.header.film_id).takes == []

    class WrongHash:
        def __call__(self, argv, out):
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"new-bytes")
            return {"result": "PASSED", "returncode": 0, "sha256": "0" * 64}

    other = live(pkg, tmp_path, WrongHash())
    assert other["manifest_result"] == "MANIFEST_HASH_MISMATCH" and "take" not in other


def test_an_existing_output_is_never_overwritten(tmp_path):
    pkg = film(tmp_path, 100)
    out = pkg.root / "media" / "takes" / "SC01_g1_t1.mp4"
    out.parent.mkdir(parents=True)
    out.write_bytes(b"evidence")
    runner = FakeRunner()
    done = live(pkg, tmp_path, runner)
    assert [r["code"] for r in done["refused"]] == ["OUTPUT_EXISTS"] and not runner.calls and out.read_bytes() == b"evidence"
