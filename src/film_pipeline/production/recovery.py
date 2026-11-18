"""Resolve one existing send. Reconciliation never submits or creatively accepts a take."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from film_pipeline.production.runtime import atomic_json, film_writer, flow_target_problem, run_async
from film_pipeline.production import takes as T
from film_pipeline.production.money import receipt_result, unresolved_sends

ROOT = Path(__file__).resolve().parents[3]
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*_t[0-9]+")


def _matches_json_file_sha(path: Path, expected: str) -> bool:
    """Match SHA-256 against exact bytes on disk or LF-normalized bytes (for Git CRLF checkouts)."""
    if not expected or not path.is_file():
        return False
    if T.sha256_file(path) == expected:
        return True
    raw = path.read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    return lf != raw and hashlib.sha256(lf).hexdigest() == expected


def _matches_scope(receipt: dict, scope: str | None, acct: str | None) -> bool:
    r_proj = str(receipt.get("project") or "").strip()
    r_acct = str(receipt.get("account") or "").strip()
    if not r_proj and not r_acct:
        return True
    if acct is not None:
        if r_acct:
            return r_acct == acct
        return True if scope is None else r_proj == scope
    if scope is not None:
        return True if not r_proj else r_proj == scope
    return True


def pending_receipts(pkg, *, cdp_scope: str | None = None, account_scope: str | None = None) -> list[dict]:
    from film_pipeline.production.generate import _sent_receipts, _fallback_price
    from film_pipeline.production.muse_gateway import pending_muse_claims
    shots = pkg.typed.get("shots")
    prices = {s.generation_id: _fallback_price(pkg.header, s) for s in shots.generations} if shots else {}
    sent = _sent_receipts(Path(pkg.root), pkg.header.film_id, prices)
    scope = (cdp_scope or "").strip() or None
    acct = (account_scope or "").strip() or None
    unresolved = {**unresolved_sends(T.load_log(Path(pkg.root), pkg.header.film_id), sent), **pending_muse_claims(Path(pkg.root))}
    items = unresolved.items()
    if scope is not None or acct is not None:
        items = [(tid, r) for tid, r in items if _matches_scope(r, scope, acct)]
    return [{"take_id": tid, "result": r.get("result", "PENDING"), "provider": r.get("provider", "flow"),
             "cost_unit": r.get("cost_unit", "credits"),
             "reserved_cost": None if r.get("provider") == "muse" else r.get("expected_cost", r.get("expected_credits", 0)),
             **({"generation_id": r["generation_id"]} if r.get("generation_id") else {})}
            for tid, r in items]


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
        if (result.get("resolution") == "QUALIFIED_PREPARING" and _matches_json_file_sha(intent, result.get("intent_sha256", ""))
                and receipt.get("submit_protocol") == "inprocess-checkpoint-v1" and receipt.get("dispatch_phase") == "PREPARING"):
            return {**receipt, "result": "PRE_SUBMIT_ERROR CONTROLLER_NOT_DISPATCHED", "reconciled": True}
        if (result.get("resolution") == "PROVIDER_NO_CLIP" and _matches_json_file_sha(intent, result.get("intent_sha256", ""))
                and _matches_json_file_sha(native, result.get("native_sha256", "")) and result.get("prompt_sha256") == receipt.get("prompt_sha256")
                and result.get("provider_no_clip") is True and result.get("scan_verified") is True):
            return {**receipt, "result": "FLOW_FAILED_NO_CLIP", "reconciled": True}
        if (_matches_json_file_sha(intent, result.get("intent_sha256", "")) and result.get("native_sha256")
                and _matches_json_file_sha(native, result["native_sha256"])):
            evidence = json.loads(native.read_text(encoding="utf-8"))
            outcome = {**receipt, "result": evidence.get("result")}
            if evidence.get("prompt_sha256") == receipt.get("prompt_sha256") and receipt_result(outcome) in {"NOT_SUBMITTED", "PROVIDER_FAILED"}:
                return {**outcome, "reconciled": True}
        if (result.get("result") == "BOUND" and result.get("registered") is True
                and _matches_json_file_sha(intent, result.get("intent_sha256", ""))
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
    from film_pipeline.providers.flow_ui_adapter import flow_tool
    root = Path(pkg.root)
    tool = flow_tool("flow_reconcile")
    args = tool.build_parser().parse_args(["--receipts", str(root / "takes/intents"), "--takes-index", str(root / "takes/index.json"),
                                         "--ids", take_id, "--out-dir", str(out.parent), "--download"])
    results = run_async(lambda: tool.run(args), timeout=480)
    if take_id not in results:
        raise ValueError("Flow reconciliation returned no evidence; original send remains pending")
    return results[take_id]


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
    if receipt.get("submit_protocol") == "inprocess-checkpoint-v1" and receipt.get("dispatch_phase") == "PREPARING":
        if native.is_file() and json.loads(native.read_text(encoding="utf-8")).get("submission_phase") in {"SUBMITTING", "SUBMITTED"}:
            raise ValueError("dispatch journal contradicts the native submission checkpoint")
        atomic_json(result_path, {"resolution": "QUALIFIED_PREPARING", "intent_sha256": T.sha256_file(path)})
        return {"resolved": True, "result": "PRE_SUBMIT_ERROR CONTROLLER_NOT_DISPATCHED", "submitted_again": False}
    native_bound = None
    if native.is_file():
        evidence = json.loads(native.read_text(encoding="utf-8"))
        if (evidence.get("result") == "PASSED" and evidence.get("media_id")
                and evidence.get("binding") == "RECONCILE_PROMPT_MATCH"):
            if (evidence.get("prompt_sha256") != receipt["prompt_sha256"] or evidence.get("file") != out.name
                    or not out.is_file() or evidence.get("sha256") != T.sha256_file(out)
                    or (receipt.get("project") and evidence.get("project") != receipt["project"])):
                raise ValueError("native download provenance/hash does not identify this send")
            native_bound = {"result": "BOUND", "download": "SAVED", "media_id": evidence["media_id"],
                            "sha256": evidence["sha256"], "prompt_sha256": receipt["prompt_sha256"],
                            "native_sha256": T.sha256_file(native), "resolution_source": "NATIVE_PASSED"}
        outcome = {**receipt, "result": evidence.get("result")}
        if (evidence.get("prompt_sha256") == receipt["prompt_sha256"]
                and receipt_result(outcome) in {"NOT_SUBMITTED", "PROVIDER_FAILED"}
                and not (receipt.get("dispatch_phase") == "SUBMITTING" and evidence.get("submission_phase") == "PREPARING")):
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
    if not (reusable or native_bound):   # a scan is next: only on the profile (and project) that made the send
        mismatch = flow_target_problem(receipt)
        if mismatch:
            raise ValueError(mismatch)
    result = prior if reusable else native_bound or (runner or _native_runner)(pkg, take_id, prompt, out)
    if result.get("provider_no_clip") and result.get("result") == "NOT_IN_GALLERY":
        from film_pipeline.providers.flow_ui_adapter import flow_tool
        context = json.loads(native.read_text(encoding="utf-8")) if native.is_file() else {}
        if (result.get("scan_verified") is True and result.get("native_sha256") == T.sha256_file(native)
                and result.get("prompt_sha256") == receipt["prompt_sha256"] and result.get("project") == context.get("project")
                and context.get("project") and (not receipt.get("project") or receipt["project"] == context["project"])
                and flow_tool("flow_reconcile").settled(native)):
            atomic_json(result_path, {**result, "resolution": "PROVIDER_NO_CLIP", "intent_sha256": T.sha256_file(path)})
            return {"resolved": True, "result": "FLOW_FAILED_NO_CLIP", "submitted_again": False}
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
