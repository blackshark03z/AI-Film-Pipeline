"""Resolve one existing send. Reconciliation never submits or creatively accepts a take."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from film_pipeline.production.runtime import atomic_json, film_writer
from film_pipeline.production import takes as T
from film_pipeline.production.money import receipt_result, unresolved_sends

ROOT = Path(__file__).resolve().parents[3]
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*_t[0-9]+")


def pending_receipts(pkg) -> list[dict]:
    from film_pipeline.production.generate import _sent_receipts, _fallback_price
    shots = pkg.typed.get("shots")
    prices = {s.generation_id: _fallback_price(pkg.header, s) for s in shots.generations} if shots else {}
    sent = _sent_receipts(Path(pkg.root), pkg.header.film_id, prices)
    return [{"take_id": tid, "result": r.get("result", "PENDING"), "provider": r.get("provider", "flow"),
             "cost_unit": r.get("cost_unit", "credits"),
             "reserved_cost": r.get("expected_cost", r.get("expected_credits", 0))}
            for tid, r in unresolved_sends(T.load_log(Path(pkg.root), pkg.header.film_id), sent).items()]


def sent_prompt(root: Path, take_id: str, receipt: dict) -> str:
    snapshot = root / "takes" / "intents" / f"{take_id}.prompt.txt"
    path = snapshot if snapshot.is_file() else root / "media" / "plan" / "prompts" / f"{receipt['generation_id']}.txt"
    if not path.is_file():
        raise ValueError("sent prompt snapshot is missing; cannot safely reconcile")
    text = path.read_text(encoding="utf-8").strip()
    if T.sha256_text(text) != receipt.get("prompt_sha256"):
        raise ValueError("sent prompt hash differs; cannot safely reconcile")
    return text


def _resolution_path(root: Path, take_id: str) -> Path:
    return root / "media" / "takes" / f"{take_id}.reconcile.json"


def resolved_receipt(root: Path, take_id: str, receipt: dict) -> dict:
    """Overlay proven resolution without rewriting historical intent payloads."""
    path = _resolution_path(root, take_id)
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        intent = root / "takes" / "intents" / f"{take_id}.intent.json"
        clip = root / "media" / "takes" / f"{take_id}.mp4"
        native = clip.with_suffix(".take.json")
        if (result.get("intent_sha256") == T.sha256_file(intent) and result.get("native_sha256")
                and result["native_sha256"] == T.sha256_file(native)):
            evidence = json.loads(native.read_text(encoding="utf-8"))
            outcome = {**receipt, "result": evidence.get("result")}
            if evidence.get("prompt_sha256") == receipt.get("prompt_sha256") and receipt_result(outcome) in {"NOT_SUBMITTED", "PROVIDER_FAILED"}:
                return {**outcome, "reconciled": True}
        if (result.get("result") == "BOUND" and result.get("registered") is True
                and result.get("intent_sha256") == T.sha256_file(intent)
                and result.get("prompt_sha256") == receipt.get("prompt_sha256")
                and result.get("sha256") == T.sha256_file(clip)):
            entry = next((t for t in T.load_log(root, receipt["film_id"]).takes if t.output_file == clip.name), None)
            if (entry and entry.output_sha256 == result["sha256"] and entry.prompt_sha256 == receipt["prompt_sha256"]
                    and entry.generation_id == receipt["generation_id"] and entry.shot_version == receipt["shot_version"]):
                return {**receipt, "result": "PASSED", "take_registered": True, "reconciled": True}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass
    return receipt


def _native_runner(pkg, take_id: str, prompt: str, out: Path) -> dict:
    root = Path(pkg.root)
    command = [sys.executable, str(ROOT / "tools/drama_flow_ui/flow_reconcile.py"),
               "--receipts", str(root / "takes/intents"), "--takes-index", str(root / "takes/index.json"),
               "--ids", take_id, "--out-dir", str(out.parent), "--download"]
    done = subprocess.run(command, capture_output=True, text=True, timeout=480)
    if done.returncode:
        raise ValueError("Flow reconciliation failed; original send remains pending: " + done.stderr[-300:])
    path = _resolution_path(root, take_id)
    if not path.is_file():
        raise ValueError("Flow reconciliation returned no evidence; original send remains pending")
    return json.loads(path.read_text(encoding="utf-8"))


@film_writer(flow=True)
def reconcile(pkg: Any, take_id: str, *, runner=None) -> dict:
    if not _ID.fullmatch(take_id):
        raise ValueError("invalid take id")
    root = Path(pkg.root)
    path = root / "takes/intents" / f"{take_id}.intent.json"
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("film_id") != pkg.header.film_id or receipt.get("take_id") != take_id or not receipt.get("sent"):
        raise ValueError("take receipt does not identify a submitted send of this film")
    if receipt.get("provider", "flow") != "flow":
        raise ValueError("this command reconciles existing Flow sends only")
    prompt = sent_prompt(root, take_id, receipt)
    resolved = resolved_receipt(root, take_id, receipt)
    if resolved.get("reconciled"):
        entry = next((t for t in T.load_log(root, receipt["film_id"]).takes if t.output_file == f"{take_id}.mp4"), None)
        return {"resolved": True, "reused": True, "result": resolved["result"],
                **({"take": entry.model_dump(mode="json")} if entry else {})}
    out = root / "media/takes" / f"{take_id}.mp4"
    result_path = _resolution_path(root, take_id)
    native = out.with_suffix(".take.json")
    if native.is_file():
        evidence = json.loads(native.read_text(encoding="utf-8"))
        outcome = {**receipt, "result": evidence.get("result")}
        if evidence.get("prompt_sha256") == receipt["prompt_sha256"] and receipt_result(outcome) in {"NOT_SUBMITTED", "PROVIDER_FAILED"}:
            atomic_json(result_path, {"receipt_id": take_id, "result": evidence["result"],
                                     "intent_sha256": T.sha256_file(path), "native_sha256": T.sha256_file(native)})
            return {"resolved": True, "result": evidence["result"], "submitted_again": False}
    try:
        prior = json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else {}
    except (OSError, ValueError):
        prior = {}
    if not isinstance(prior, dict):
        prior = {}
    reusable = (prior.get("result") == "BOUND" and prior.get("download") == "SAVED" and out.is_file()
                and prior.get("intent_sha256") == T.sha256_file(path)
                and prior.get("sha256") == T.sha256_file(out) and prior.get("prompt_sha256") == receipt["prompt_sha256"])
    result = prior if reusable else (runner or _native_runner)(pkg, take_id, prompt, out)
    if result.get("result") != "BOUND" or result.get("download") != "SAVED":
        return {"resolved": False, "take_id": take_id, "result": result.get("result", "UNKNOWN"),
                "next_action": "Reconcile this existing send again; do not resubmit an uncertain job"}
    if not result.get("media_id") or not out.is_file() or result.get("sha256") != T.sha256_file(out):
        raise ValueError("download binding/hash evidence is missing or mismatched")
    if result.get("prompt_sha256") != receipt["prompt_sha256"]:
        raise ValueError("download prompt hash does not identify the original send")
    # Persist download proof first, so a crash before registration can reuse the exact verified bytes.
    proof = {**result, "receipt_id": take_id, "intent_sha256": T.sha256_file(path), "registered": False}
    atomic_json(result_path, proof)
    entry, created = T.register_take(root, pkg.header.film_id, receipt["generation_id"], out, prompt_text=prompt,
                                    route=receipt["route"], model=receipt["model"],
                                    credits=float(receipt.get("expected_credits", 0)),
                                    shot_version=int(receipt["shot_version"]))
    if (entry.output_file != out.name or entry.prompt_sha256 != receipt["prompt_sha256"]
            or entry.shot_version != receipt["shot_version"]):
        raise ValueError("registered take conflicts with this send")
    # Input images may have changed since the send; retain their receipted provenance, not today's image bytes.
    if entry.start_frame_sha256 and entry.start_frame_sha256 != receipt.get("start_frame_sha256", ""):
        raise ValueError("registered take has different input-frame provenance")
    if not entry.start_frame_sha256 and receipt.get("start_frame_sha256"):
        log = T.load_log(root, pkg.header.film_id)
        log.get(entry.take_id).start_frame_sha256 = receipt.get("start_frame_sha256", "")
        T.save_log(root, log)
        entry = log.get(entry.take_id)
    atomic_json(result_path, {**proof, "registered": True, "take_id": entry.take_id})
    return {"resolved": True, "reused": not created, "take": entry.model_dump(mode="json")}
