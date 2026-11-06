"""Generate stage through the package: the exact Flow send payload for one generation, an intent receipt, a hard go-live gate.

``build_payload`` derives everything from the package as it is *now* (it re-plans, so a stale prompt file can never be
sent): the prompt text and its hash, the start-frame still and its hash, the output name `<gid>_t<N>.mp4` (N = next take of
that generation), the exact argv for `tools/drama_flow_ui/flow_send.py` (start-frame route: the still goes into the
"Khung hinh" slot with `--start tok:<tail of the uploaded still> --start-file <png>`), the model and expected credits.

Blockers keep a send from being safe; they are listed in the payload either way:

* package problems (`plan_package` BLOCKs, preflight not PASS)
* a chained generation whose previous generation has no ACCEPTED take of its current version (its end frame is the
  start frame, so an unreviewed or rejected take cannot hand off)
* the start-frame still is missing
* live only: no `--start-token`, no budget in `film.json`, or the take would push credits past the cap (`budget.cap_factor`
  x estimate, counting every take already logged, rejected ones included)

``generate(dry_run=True)`` never touches Flow: it writes `takes/intents/<take>.intent.json` (idempotent for an unchanged
payload) and returns the payload. Without ``dry_run`` it refuses unless the backlog header says ``OWNER_GO_LIVE: YES`` **and**
there are no blockers; only then it calls the runner (default: `flow_send.py`), and a PASSED clip is registered in the take
log. The receipt is written *before* the send and updated with the result, so an interrupted send leaves evidence. Every
real send spends credits; the video model is always Omni Flash at 360p.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from film_pipeline.production.plan import plan_package
from film_pipeline.production.planning import CREDITS_PER_GENERATION
from film_pipeline.production.takes import (load_log, register_take, sha256_file, sha256_text, takes_dir)

ROOT = Path(__file__).resolve().parents[3]
BACKLOG = ROOT / "docs" / "production" / "LOOP_BACKLOG.md"
FLOW_SEND = ROOT / "tools" / "drama_flow_ui" / "flow_send.py"
ROUTE = "start_frame+Khung hinh"
MODEL = "Omni Flash 360p"
PLACEHOLDER_TOKEN = "tok:<TAIL_OF_UPLOADED_START_FRAME>"
_GO = re.compile(r"^OWNER_GO_LIVE: (YES|NO)[ \t\r]*$", re.MULTILINE)
_RECEIPT_NUMBER = re.compile(r"_t(\d+)$")

Runner = Callable[[list[str], Path], dict[str, Any]]


def owner_go_live(backlog: Path | None = None) -> bool:
    """True only if the backlog header carries a literal `OWNER_GO_LIVE: YES`; a missing file or line means NO."""
    path = Path(backlog) if backlog else BACKLOG
    try:
        found = _GO.findall(path.read_text(encoding="utf-8"))
    except OSError:
        return False
    return found == ["YES"]   # exactly one header line, and it says YES


def default_runner(argv: list[str], out: Path) -> dict[str, Any]:  # pragma: no cover - spends credits; P3-05 only
    """Run the sender and return its manifest plus `returncode`; `generate` refuses a manifest that does not belong to
    this send (the output must not exist before the send, so an old manifest cannot be mistaken for a new one)."""
    done = subprocess.run(argv, check=False)
    manifest = out.with_suffix(".take.json")
    body = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {"result": "NO_MANIFEST"}
    return {**body, "returncode": done.returncode}


def _blocker(code: str, detail: str, live_only: bool = False) -> dict[str, Any]:
    return {"code": code, "detail": detail, "live_only": live_only}


def build_payload(pkg: Any, generation_id: str, *, plan_out: Path | None = None, stills_dir: Path | None = None,
                  start_token: str | None = None) -> dict[str, Any]:
    shots, pre = pkg.typed.get("shots"), pkg.typed.get("preprod")
    if shots is None or pre is None:
        raise ValueError("generate needs a valid 03_preprod.json and 04_shots.json")
    decl = next((g for g in shots.generations if g.generation_id == generation_id), None)
    if decl is None:
        raise ValueError(f"unknown generation {generation_id!r}")
    root = Path(pkg.root)
    plan_out = Path(plan_out) if plan_out else root / "media" / "plan"
    stills_dir = Path(stills_dir) if stills_dir else root / "media" / "stills"
    log = load_log(root, pkg.header.film_id)
    blockers: list[dict[str, Any]] = []

    # the end state of a generation counts as verified once a human accepted a take of its current version
    versions = {g.generation_id: g.version for g in shots.generations}
    verified = frozenset(t.generation_id for t in log.takes
                         if t.status == "ACCEPTED" and t.shot_version == versions.get(t.generation_id))
    result = plan_package(pkg, plan_out, storyboard=False, verified_handoffs=verified)
    # another shot's preflight (e.g. one that waits for this take) is not a reason to hold this one back
    own = [p for p in result.problems
           if not (re.match(r"^(\S+) preflight ", p) and re.match(r"^(\S+)", p).group(1) != generation_id)]
    blockers += [_blocker("PACKAGE_PROBLEM", p) for p in own]
    prompt_file = plan_out / "prompts" / f"{generation_id}.txt"
    prompt = prompt_file.read_text(encoding="utf-8").strip()

    if decl.previous_generation_id:
        prev = next(g for g in shots.generations if g.generation_id == decl.previous_generation_id)
        accepted = [t for t in log.for_generation(prev.generation_id)
                    if t.status == "ACCEPTED" and t.shot_version == prev.version]
        if not accepted:
            blockers.append(_blocker("HANDOFF_PREVIOUS_NOT_ACCEPTED",
                                     f"{prev.generation_id} v{prev.version} has no ACCEPTED take; its end frame is "
                                     f"this shot's start frame"))
        start_source = f"end frame of {accepted[-1].take_id}" if accepted else f"end frame of {prev.generation_id}"
    else:
        start_source = "approved start still"
    still = stills_dir / f"start_{generation_id}.png"
    if not still.is_file():
        blockers.append(_blocker("START_FRAME_MISSING", f"{still} not found (prompt in plan stills/start_{generation_id}.txt)"))

    sent = _sent_receipts(root, pkg.header.film_id)
    logged = {t.take_id for t in log.takes}
    # a send that did not end in a registered take still used its number (and probably its credits): never reuse it
    used = [len(log.for_generation(generation_id))] + [
        int(m.group(1)) for tid in sent if tid.startswith(f"{generation_id}_t") and (m := _RECEIPT_NUMBER.search(tid))]
    number = max(used) + 1
    take_id = f"{generation_id}_t{number}"
    out = root / "media" / "takes" / f"{take_id}.mp4"
    spent = sum(t.credits for t in log.takes) + sum(r["expected_credits"] for tid, r in sent.items() if tid not in logged)
    pending = [tid for tid, r in sent.items() if r.get("result") == "PENDING" and tid.startswith(f"{generation_id}_t")]
    if pending:
        blockers.append(_blocker("SEND_PENDING", f"{', '.join(pending)} was sent and never reported back; check Flow for the "
                                 f"clip and register or discard it by hand before another send", live_only=True))
    if out.exists() or out.with_suffix(".take.json").exists():
        blockers.append(_blocker("OUTPUT_EXISTS", f"{out} (or its manifest) already exists; it is evidence and is not "
                                 f"overwritten", live_only=True))
    cap = pkg.header.budget.credits_cap
    if not start_token:
        blockers.append(_blocker("START_TOKEN_MISSING", "pass --start-token tok:<tail> of the start still uploaded to Flow",
                                 live_only=True))
    if cap is None:
        blockers.append(_blocker("BUDGET_NOT_SET", "film.json budget.credits_estimate is empty", live_only=True))
    elif spent + CREDITS_PER_GENERATION > cap:
        blockers.append(_blocker("BUDGET_EXCEEDED", f"{spent:g} spent + {CREDITS_PER_GENERATION:g} > cap {cap:g}",
                                 live_only=True))
    argv = [sys.executable, str(FLOW_SEND), str(prompt_file), str(out), "--start", start_token or PLACEHOLDER_TOKEN,
            "--start-file", str(still)]
    return {"film_id": pkg.header.film_id, "generation_id": generation_id, "take_id": take_id,
            "shot_version": decl.version, "prompt_file": str(prompt_file), "prompt_sha256": sha256_text(prompt),
            "prompt_words": len(prompt.split()), "start_frame": {"source": start_source, "file": str(still),
                                                                "exists": still.is_file(),
                                                                "sha256": sha256_file(still) if still.is_file() else ""},
            "route": ROUTE, "model": MODEL, "expected_credits": CREDITS_PER_GENERATION, "credits_spent": spent,
            "credit_cap": cap, "output": str(out), "argv": argv,
            "preconditions": ["Flow composer is on Omni Flash, 360p, video mode",
                              "the start still is uploaded to the Flow gallery (its tail is --start-token)",
                              "GPM / Flow browser stays open; no cookies or captchas touched"],
            "blockers": blockers}


def _sent_receipts(root: Path, film_id: str) -> dict[str, dict[str, Any]]:
    """Intent receipts of real sends (take id -> receipt). An unreadable receipt counts as a pending send."""
    out: dict[str, dict[str, Any]] = {}
    folder = takes_dir(root) / "intents"
    if not folder.is_dir():
        return out
    for path in sorted(folder.glob("*.intent.json")):
        take_id = path.name[:-len(".intent.json")]
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            out[take_id] = {"sent": True, "result": "PENDING", "expected_credits": CREDITS_PER_GENERATION}
            continue
        if body.get("sent") and body.get("film_id", film_id) == film_id:
            out[take_id] = {**body, "expected_credits": float(body.get("expected_credits") or CREDITS_PER_GENERATION)}
    return out


def _write_receipt(root: Path, payload: dict[str, Any], **extra: Any) -> Path:
    path = takes_dir(root) / "intents" / f"{payload['take_id']}.intent.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    keep = ("film_id", "generation_id", "take_id", "shot_version", "prompt_sha256", "route", "model",
            "expected_credits", "credits_spent", "credit_cap")
    receipt = {k: payload[k] for k in keep}
    receipt["start_frame_sha256"] = payload["start_frame"]["sha256"]
    receipt["start_frame_source"] = payload["start_frame"]["source"]
    receipt["blockers"] = [b["code"] for b in payload["blockers"]]
    receipt.update(extra)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def generate(pkg: Any, generation_id: str, *, dry_run: bool = True, plan_out: Path | None = None,
             stills_dir: Path | None = None, start_token: str | None = None, backlog: Path | None = None,
             runner: Runner | None = None) -> dict[str, Any]:
    payload = build_payload(pkg, generation_id, plan_out=plan_out, stills_dir=stills_dir, start_token=start_token)
    root = Path(pkg.root)
    live_blocked = [b for b in payload["blockers"] if not b["live_only"] or not dry_run]
    if dry_run:
        # a dry run reports the live-only blockers too, but they do not make the dry run itself fail
        receipt = _write_receipt(root, payload, dry_run=True, sent=False, owner_go_live=owner_go_live(backlog))
        return {"sent": False, "dry_run": True, "ready_to_send": not payload["blockers"], "payload": payload,
                "receipt": str(receipt)}
    go = owner_go_live(backlog)
    refusals = ([] if go else [_blocker("OWNER_GO_LIVE_NO", "the backlog header does not say OWNER_GO_LIVE: YES")])
    refusals += live_blocked
    if refusals:
        receipt = _write_receipt(root, payload, dry_run=False, sent=False, owner_go_live=go,
                                 refused=[r["code"] for r in refusals])
        return {"sent": False, "dry_run": False, "refused": refusals, "payload": payload, "receipt": str(receipt)}
    receipt = _write_receipt(root, payload, dry_run=False, sent=True, owner_go_live=True, result="PENDING")
    out = Path(payload["output"])
    try:
        manifest = (runner or default_runner)(payload["argv"], out)
    except BaseException:
        _write_receipt(root, payload, dry_run=False, sent=True, owner_go_live=True, result="PENDING",
                       note="the sender raised before reporting; check Flow before resending")
        raise
    result: dict[str, Any] = {"sent": True, "dry_run": False, "payload": payload, "manifest_result": manifest.get("result"),
                              "receipt": str(receipt)}
    outcome = str(manifest.get("result"))
    if outcome == "PASSED" and manifest.get("returncode", 0) != 0:
        outcome = f"SENDER_EXIT_{manifest.get('returncode')}"
    elif outcome == "PASSED" and manifest.get("sha256") and out.is_file() and manifest["sha256"] != sha256_file(out):
        outcome = "MANIFEST_HASH_MISMATCH"
    if outcome == "PASSED" and out.is_file():
        entry, _ = register_take(root, pkg.header.film_id, generation_id, out,
                                 prompt_text=Path(payload["prompt_file"]).read_text(encoding="utf-8").strip(),
                                 route=ROUTE, model=MODEL, credits=CREDITS_PER_GENERATION,
                                 start_frame=Path(payload["start_frame"]["file"]), shot_version=payload["shot_version"])
        result["take"] = entry.model_dump(mode="json")
    result["manifest_result"] = outcome
    _write_receipt(root, payload, dry_run=False, sent=True, owner_go_live=True, result=outcome,
                   take_registered=bool(result.get("take")))
    return result
