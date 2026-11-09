"""Generate stage through the package: the exact Flow send payload for one generation, an intent receipt, a hard go-live gate.

``build_payload`` derives everything from the package as it is *now* (it re-plans, so a stale prompt file can never be
sent): the prompt text and its hash, the start-frame still and its hash, the output name `<gid>_t<N>.mp4` (N = next take of
that generation), the exact argv for `tools/drama_flow_ui/flow_send.py` (start-frame route: the still goes into the
"Khung hinh" slot; with `--start-token` as `--start tok:<tail of the uploaded still> --start-file <png>`, without it as
`--upload-frames --start-file <png>` [`--end-file <png>`]: flow_send uploads the stills inside the send), the model and
expected credits.

Blockers keep a send from being safe; they are listed in the payload either way:

* package problems (`plan_package` BLOCKs, preflight not PASS)
* a chained generation whose previous generation has no ACCEPTED take of its current version (its end frame is the
  start frame, so an unreviewed or rejected take cannot hand off)
* the start-frame still is missing
* generability (only when the film opts in): a shot that reuses an accepted take, a RED shot without a valid Owner
  exception (version, prompt hash, expiry, attempts and credits), the per-version send cap, an AMBER second send while the
  first take waits for review
* live only: no budget in `film.json`, or the take would push credits past the cap (`budget.cap_factor`
  x estimate, counting every take already logged, rejected ones included)

``generate(dry_run=True)`` never touches Flow: it writes `takes/intents/<take>.intent.json` (idempotent for an unchanged
payload) and returns the payload. Without ``dry_run`` it refuses unless the backlog header says ``OWNER_GO_LIVE: YES`` **and**
there are no blockers; only then it calls the runner (default: `flow_send.py`), and a PASSED clip is registered in the take
log. The receipt is written *before* the send and updated with the result, so an interrupted send leaves evidence. Every
real send spends money.

Provider adapters (docs/production/PROVIDER_INDEPENDENCE.md, phase A): the payload carries a provider-neutral
``GenerationRequest`` and the route (`film.json` ``route``, a shot's own ``route`` overrides it; default Flow Omni 1.2
Flash TEST). The route's registry entry prices the send in its own unit and its preflight (`providers/route.py`) adds
ROUTE_* blockers and warnings. A Flow route goes through ``FlowUiAdapter`` (same argv, results and ledger as before);
an API route (MiniMax, an OpenAI-style gateway) submits, polls and downloads through its HTTP adapter and binds the take
by job id.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from film_pipeline.drama.generability import DRAFTS, rate_shot
from film_pipeline.production.plan import plan_package
from film_pipeline.production.money import (credit_ledger, money_ledger, receipt_amount, receipt_charged,
                                            receipt_result, receipt_unit)
from film_pipeline.production.planning import flow_credits
from film_pipeline.production.sections import shot_seconds
from film_pipeline.production.takes import (load_log, register_take, sha256_file, sha256_text, takes_dir)
from film_pipeline.providers.capability import DEFAULT_MODEL, DEFAULT_PROVIDER, ModelCapability, get_capability
from film_pipeline.providers.http_adapters import make_adapter
from film_pipeline.providers.flow_ui_adapter import FlowUiAdapter, default_runner  # noqa: F401 - re-exported
from film_pipeline.providers.request import FrameRef, GenerationRequest
from film_pipeline.providers.route import RouteSpec, resolve_route, route_defaults, route_issues

ROOT = Path(__file__).resolve().parents[3]
BACKLOG = ROOT / "docs" / "production" / "LOOP_BACKLOG.md"
FLOW_SEND = ROOT / "tools" / "drama_flow_ui" / "flow_send.py"  # == flow_ui_adapter.FLOW_SEND
ROUTE = "start_frame+Khung hinh"
ROUTE_END = "start_frame+end_frame+Khung hinh"
MODEL = "Omni 1.2 Flash 360p"
FLOW_MODEL = "Omni 1.2 Flash"  # the model name Flow's composer dropdown starts with
PLACEHOLDER_TOKEN = "tok:<TAIL_OF_UPLOADED_START_FRAME>"
PLACEHOLDER_END_TOKEN = "tok:<TAIL_OF_UPLOADED_END_FRAME>"
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


def _blocker(code: str, detail: str, live_only: bool = False) -> dict[str, Any]:
    return {"code": code, "detail": detail, "live_only": live_only}


def _problem_subject(problem: str) -> str | None:
    """The generation a per-shot plan problem is about, or None for a package-wide one."""
    m = re.match(r"^(\S+) preflight ", problem) or re.match(r"^PROMPT_TOO_LONG (\S+):", problem)
    return m.group(1) if m else None


def _frame_still(pkg: Any, generation_id: str, stills_dir: Path | None, blockers: list[dict[str, Any]],
                 kind: str = "start") -> Path:
    """The `kind` ("start" or "end") still of a generation. An explicit `--stills` directory wins. Otherwise the still
    recorded in 03_preprod.json must be approved and current; a generation with no record keeps the old behaviour
    (media/stills/<kind>_<gid>.png)."""
    from film_pipeline.production import stills as S
    root = Path(pkg.root)
    label, code, key = kind.upper(), kind.upper() + "_FRAME", generation_id if kind == "start" else S.end_key(generation_id)
    name = f"{kind}_{generation_id}"
    if stills_dir:
        still = Path(stills_dir) / f"{name}.png"
    elif key in pkg.typed["preprod"].stills:
        still = root / pkg.typed["preprod"].stills[key].file
        state, reason = S.state_of(pkg, key)
        if state != "APPROVED":
            blockers.append(_blocker(f"{code}_NOT_APPROVED", f"{generation_id}: {kind} still {state.lower()}: {reason} "
                                     f"(film.py stills --approve {key} --by NAME)"))
        return still
    else:
        still = root / "media" / "stills" / f"{name}.png"
    if not still.is_file():
        blockers.append(_blocker(f"{code}_MISSING", f"{still} not found (prompt in plan stills/{name}.txt; "
                                 f"film.py stills --register {key} --image PATH)"))
    return still


def _start_still(pkg: Any, generation_id: str, stills_dir: Path | None, blockers: list[dict[str, Any]]) -> Path:
    return _frame_still(pkg, generation_id, stills_dir, blockers, "start")


def build_payload(pkg: Any, generation_id: str, *, plan_out: Path | None = None, stills_dir: Path | None = None,
                  start_token: str | None = None, end_token: str | None = None,
                  today: date | None = None) -> dict[str, Any]:
    shots, pre = pkg.typed.get("shots"), pkg.typed.get("preprod")
    if shots is None or pre is None:
        raise ValueError("generate needs a valid 03_preprod.json and 04_shots.json")
    decl = next((g for g in shots.generations if g.generation_id == generation_id), None)
    if decl is None:
        raise ValueError(f"unknown generation {generation_id!r}")
    root = Path(pkg.root)
    plan_out = Path(plan_out) if plan_out else root / "media" / "plan"
    log = load_log(root, pkg.header.film_id)
    blockers: list[dict[str, Any]] = []

    # the end state of a generation counts as verified once a human accepted a take of its current version
    versions = {g.generation_id: g.version for g in shots.generations}
    verified = frozenset(t.generation_id for t in log.takes
                         if t.status == "ACCEPTED" and t.shot_version == versions.get(t.generation_id))
    result = plan_package(pkg, plan_out, storyboard=False, verified_handoffs=verified)
    # another shot's preflight or prompt length (e.g. one that waits for this take) is not a reason to hold this one back
    own = [p for p in result.problems if _problem_subject(p) in (None, generation_id)]
    blockers += [_blocker("PACKAGE_PROBLEM", p) for p in own]
    # an approval covers the shot decl the board was drawn from; a later decl change voids it (re-plan, re-approve)
    from film_pipeline.drama.storyboard import StoryboardGate
    board_shot, fingerprint = result.boards[generation_id]
    stale = StoryboardGate(plan_out / "storyboard").stale(board_shot, fingerprint)
    if stale:
        blockers.append(_blocker("STORYBOARD_STALE", f"{stale}: run film.py plan again and have the Owner re-approve "
                                 f"the board"))
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
    still = _start_still(pkg, generation_id, stills_dir, blockers)
    end_still = _frame_still(pkg, generation_id, stills_dir, blockers, "end") if decl.end_frame else None

    route = resolve_route(pkg.header, decl)
    cap = _capability(route)
    route = RouteSpec(provider=cap.provider, model=cap.model, tier=route.tier)  # canonical id, never an alias
    unit = cap.price.unit
    prices = {g.generation_id: _fallback_price(pkg.header, g) for g in shots.generations}
    sent = _sent_receipts(root, pkg.header.film_id, prices)
    # a send that did not end in a registered take still used its number (and probably its credits): never reuse it
    used = [len(log.for_generation(generation_id))] + [
        int(m.group(1)) for tid in sent if tid.startswith(f"{generation_id}_t") and (m := _RECEIPT_NUMBER.search(tid))]
    number = max(used) + 1
    take_id = f"{generation_id}_t{number}"
    out = root / "media" / "takes" / f"{take_id}.mp4"
    ledger = money_ledger(log, sent)
    spent = ledger.get(unit, {}).get("spent", 0.0)
    pending = [tid for tid, r in sent.items() if r.get("result") == "PENDING" and tid.startswith(f"{generation_id}_t")]
    if pending:
        blockers.append(_blocker("SEND_PENDING", f"{', '.join(pending)} was sent and never reported back; check Flow for the "
                                 f"clip and register or discard it by hand before another send", live_only=True))
    if out.exists() or out.with_suffix(".take.json").exists():
        blockers.append(_blocker("OUTPUT_EXISTS", f"{out} (or its manifest) already exists; it is evidence and is not "
                                 f"overwritten", live_only=True))
    cap_amount = pkg.header.budget.cap_for(unit)
    seconds = shot_seconds(decl, pkg.header)
    cost = _price(cap, seconds, route.tier)
    flow = cap.adapter == "flow_ui"
    if flow and start_token and decl.end_frame and not end_token:   # upload route (no start token) uploads the end still too
        blockers.append(_blocker("END_TOKEN_MISSING", "pass --end-token tok:<tail> of the end still uploaded to Flow",
                                 live_only=True))
    in_unit = "" if unit == "credits" else f" {unit}"
    day = (today or date.today()).isoformat()
    daily = route_defaults().daily_caps.get(unit)
    if daily is not None and not pkg.header.rehearsal:
        spent_today = _spent_on(sent, unit, day) + _spent_on_elsewhere(root, unit, day)
        if spent_today + cost > daily:
            blockers.append(_blocker("BUDGET_DAILY_EXCEEDED", f"{spent_today:g} spent on {day} + {cost:g} > daily cap "
                                     f"{daily:g}{in_unit}", live_only=True))
    if pkg.header.rehearsal:
        pass  # a rehearsal spends nothing: no budget to check (credits are recorded as 0)
    elif cap_amount is None and daily is not None and pkg.header.experiment:
        pass  # an experiment film without its own cap in this unit is held by the daily cap
    elif cap_amount is None:
        blockers.append(_blocker("BUDGET_NOT_SET", "film.json budget.credits_estimate is empty" if unit == "credits"
                                 else f"film.json budget.caps.{unit} is empty", live_only=True))
    elif spent + cost > cap_amount:
        blockers.append(_blocker("BUDGET_EXCEEDED", f"{spent:g} spent + {cost:g} > cap {cap_amount:g}{in_unit}",
                                 live_only=True))
    attempts = None
    if pre.preflight.generability:
        attempts = _generability_gate(decl, sent, log, sha256_text(prompt), cost, blockers, today or date.today(),
                                      route=route, unit=unit)
    request = GenerationRequest(
        film_id=pkg.header.film_id, generation_id=generation_id, take_id=take_id, prompt=prompt,
        prompt_sha256=sha256_text(prompt), duration_s=int(seconds), aspect=pkg.header.aspect, tier=route.tier,
        first_frame=FrameRef(path=str(still), sha256=sha256_file(still) if still.is_file() else ""),
        last_frame=(FrameRef(path=str(end_still), sha256=sha256_file(end_still) if end_still.is_file() else "")
                    if end_still is not None else None),
        audio_mode="NATIVE_DIALOGUE" if decl.dialogue else "AMBIENT" if decl.sfx else "SILENT", output=str(out))
    warnings: list[dict[str, Any]] = []
    for issue in route_issues(request, cap):
        if issue.severity == "BLOCK":
            blockers.append(_blocker(issue.code, issue.detail))
        else:
            warnings.append({"code": issue.code, "detail": issue.detail})
    if flow:
        argv, preconditions = FlowUiAdapter(cap).build_argv(request, prompt_file=prompt_file, start_token=start_token,
                                                            end_token=end_token)
        route_name = ROUTE_END if end_still is not None else ROUTE
    else:
        argv = []
        preconditions = [f"{cap.auth_env} is set in the environment (never written to a file)",
                         f"{cap.provider}/{cap.model} UNVERIFIED: {', '.join(cap.unverified) or 'nothing'}"]
        route_name = "api:" + "+".join(request.frame_roles)
    payload = {"film_id": pkg.header.film_id, "generation_id": generation_id, "take_id": take_id,
            "shot_version": decl.version, "prompt_file": str(prompt_file), "prompt_sha256": sha256_text(prompt),
            "prompt_words": len(prompt.split()), "start_frame": {"source": start_source, "file": str(still),
                                                                "exists": still.is_file(),
                                                                "sha256": sha256_file(still) if still.is_file() else ""},
            "route": route_name, "model": MODEL if flow else cap.display_name, "duration_s": int(seconds),
            "expected_credits": (0.0 if pkg.header.rehearsal else cost) if unit == "credits" else 0.0,
            "credits_spent": ledger["credits"]["spent"], "credit_cap": pkg.header.budget.credits_cap,
            "output": str(out), "argv": argv, "preconditions": preconditions, "blockers": blockers,
            "provider": cap.provider, "provider_model": cap.model, "tier": route.tier, "cost_unit": unit,
            "expected_cost": 0.0 if pkg.header.rehearsal else cost, "spent_in_unit": spent, "cap_in_unit": cap_amount,
            "warnings": warnings, "request": request.model_dump(mode="json")}
    if attempts is not None:
        payload["attempts"] = attempts
    if end_still is not None:
        payload["end_frame"] = {"file": str(end_still), "exists": end_still.is_file(),
                                "sha256": sha256_file(end_still) if end_still.is_file() else ""}
    return payload


def _spent_on(sent: dict[str, dict[str, Any]], unit: str, day: str) -> float:
    """What this film's receipts sent on ``day`` cost (or reserve) in ``unit``."""
    return sum(receipt_amount(r) for r in sent.values()
               if r.get("sent_on") == day and receipt_unit(r) == unit and receipt_charged(r))


def _spent_on_elsewhere(root: Path, unit: str, day: str) -> float:
    """The daily cap is per day, not per film: what the other films beside this one sent on ``day`` in ``unit``."""
    total = 0.0
    parent = Path(root).resolve().parent
    for other in sorted(parent.iterdir()) if parent.is_dir() else []:
        folder = takes_dir(other) / "intents"
        if other.resolve() == Path(root).resolve() or not folder.is_dir():
            continue
        for path in folder.glob("*.intent.json"):
            try:
                body = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if body.get("sent") and body.get("sent_on") == day and receipt_unit(body) == unit and receipt_charged(body):
                total += receipt_amount(body)
    return total


def _capability(route: RouteSpec) -> ModelCapability:
    try:
        return route.capability()
    except KeyError as exc:
        raise ValueError(f"route {route.provider}/{route.model} is not in the capability registry") from exc


def _price(cap: ModelCapability, seconds: float, tier: str) -> float:
    """The registry price of one send; a tier the model does not offer prices 0 (the route preflight blocks it)."""
    try:
        return cap.price_of(seconds, tier)
    except ValueError:
        return 0.0


def _fallback_price(header: Any, decl: Any) -> dict[str, Any]:
    """What an unreadable receipt of `decl` reserves: its route's price, unit and identity."""
    route = resolve_route(header, decl)
    try:
        cap = _capability(route)
    except ValueError:  # another shot's bad route is that shot's error (its own build_payload raises), not this one's
        return {"expected_credits": flow_credits(shot_seconds(decl, header))}
    amount = _price(cap, shot_seconds(decl, header), route.tier)
    flow = flow_credits(shot_seconds(decl, header))
    if cap.price.unit == "credits":
        return {"expected_credits": amount}
    return {"expected_credits": flow, "expected_cost": amount, "cost_unit": cap.price.unit, "provider": cap.provider,
            "provider_model": cap.model}


def _receipt_route(receipt: dict[str, Any]) -> tuple[str, str]:
    """(provider, model) of a receipt; one from before provider adapters is a Flow Omni 1.2 Flash send."""
    provider = str(receipt.get("provider") or DEFAULT_PROVIDER)
    model = str(receipt.get("provider_model") or (DEFAULT_MODEL if provider == DEFAULT_PROVIDER else ""))
    return provider, model


def _generability_gate(decl: Any, sent: dict[str, dict[str, Any]], log: Any, prompt_sha: str, cost: float,
                       blockers: list[dict[str, Any]], today: date, *, route: RouteSpec | None = None,
                       unit: str = "credits") -> dict[str, Any]:
    """Blockers from the generability rating (drama/generability.py) of the routed (provider, model); returns the
    payload's `attempts` block. A send counts once it was submitted (receipt sent, normalized result not NOT_SUBMITTED)
    on the same (provider, model); a version bump keeps the history. PROVIDER_FAILED (Flow's FLOW_FAILED: the provider
    rejected the clip, no output) and REJECTED_POLICY do not use up the cap: Owner 2026-11-09 "Không tính, sửa đi";
    their cost still counts in the ledger where the registry charges it."""
    route = route or RouteSpec()
    key = (route.provider, route.model)
    gid, level = decl.generation_id, rate_shot(decl, *key).level
    ours = {tid: r for tid, r in sent.items() if r.get("generation_id", tid.rsplit("_t", 1)[0]) == gid
            and _receipt_route(r) == key}
    mine = [r for r in ours.values() if receipt_result(r) not in NOT_AN_ATTEMPT]
    here = [r for r in mine if r.get("shot_version", 1) == decl.version]
    attempts = {"this_version": len(here), "all_versions": len(mine), "cap": DRAFTS[level], "level": level}
    reuse = (decl.accepted_take_reuse or "").strip()
    if reuse:
        blockers.append(_blocker("ACCEPTED_TAKE_REUSE", f"{gid} reuses the accepted take {reuse}; no new send"))
        return attempts
    exc = decl.generability_exception
    if level == "RED":
        if exc is None:
            blockers.append(_blocker("GENERABILITY_RED", f"{gid} v{decl.version} is RED and has no Owner "
                                     f"generability_exception"))
        else:
            if exc.shot_version != decl.version or exc.prompt_sha256 != prompt_sha:
                blockers.append(_blocker("EXCEPTION_MISMATCH", f"the exception is for v{exc.shot_version} prompt "
                                         f"{exc.prompt_sha256[:12]}; this is v{decl.version} prompt {prompt_sha[:12]}"))
            if today > exc.expires:
                blockers.append(_blocker("EXCEPTION_EXPIRED", f"the exception expired on {exc.expires}"))
            # FLOW_FAILED sends do not use an attempt but were charged: they still spend the exception's budget
            # (max_credits is in the route's unit)
            charged = [r for r in ours.values() if r.get("shot_version", 1) == decl.version
                       and receipt_unit(r) == unit and receipt_charged(r)]
            used = sum(receipt_amount(r) for r in charged)
            if len(here) >= exc.max_attempts or used + cost > exc.max_credits:
                blockers.append(_blocker("EXCEPTION_SPENT", f"{len(here)}/{exc.max_attempts} sends, {used:g} + {cost:g} "
                                         f"credits vs {exc.max_credits:g}"))
        return attempts
    if len(here) >= DRAFTS[level]:
        blockers.append(_blocker("SEND_CAP", f"{gid} v{decl.version} is {level}: {len(here)} of {DRAFTS[level]} send(s) used"))
    waiting = [t.take_id for t in log.for_generation(gid) if t.shot_version == decl.version and t.status == "GENERATED"]
    if level == "AMBER" and here and waiting:
        blockers.append(_blocker("AWAITING_REVIEW", f"{', '.join(waiting)} is not reviewed yet; accept or reject it "
                                 f"before the second AMBER send"))
    return attempts


# normalized results that do not use a generability send (nothing submitted, or the provider/moderation refused it)
NOT_AN_ATTEMPT = ("NOT_SUBMITTED", "PROVIDER_FAILED", "REJECTED_POLICY")
# Flow's raw vocabulary, kept for readers; the registry (providers/registry/flow.json error_map) is the source and a
# test pins the two together. Results the sender returns before pressing Enter on the prompt
# (tools/drama_flow_ui/flow_send.py): nothing was submitted -> NOT_SUBMITTED
PRE_SUBMIT_RESULTS = ("START_NOT_FOUND", "END_NOT_FOUND", "START_NOT_SET", "END_NOT_SET", "ATTACH_NOT_FOUND",
                      "SETTINGS_NOT_SET", "SEND_FAILED", "PRE_SUBMIT_ERROR")
# submitted, but Flow marked the job "Không thành công" and removed it: no clip -> PROVIDER_FAILED (charged, not a send)
FLOW_FAILED_RESULTS = ("FLOW_FAILED",)


def _sent_receipts(root: Path, film_id: str, prices: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Intent receipts of real sends (take id -> receipt). An unreadable receipt counts as a pending send, priced at
    its shot's price (`prices`: generation id -> Flow credits, or the `_fallback_price` fields of its route)."""
    out: dict[str, dict[str, Any]] = {}
    folder = takes_dir(root) / "intents"
    if not folder.is_dir():
        return out
    for path in sorted(folder.glob("*.intent.json")):
        take_id = path.name[:-len(".intent.json")]
        price = prices.get(take_id.rsplit("_t", 1)[0], flow_credits(8))
        price = price if isinstance(price, dict) else {"expected_credits": float(price)}
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # its unit is unknown: reserve the Flow credits it would have cost and, when the shot now routes to
            # another unit, that route's price as well (never silently move money from one unit to another)
            out[take_id] = {"sent": True, "result": "PENDING", "expected_credits": float(price["expected_credits"])}
            if "cost_unit" in price:
                out[f"{take_id}~{price['cost_unit']}"] = {"sent": True, "result": "PENDING", **price,
                                                          "expected_credits": 0.0}
            continue
        if body.get("sent") and body.get("film_id", film_id) == film_id:
            if receipt_unit(body) == "credits":
                # a Flow receipt without a price: its shot's Flow price
                fallback = float(price["expected_credits"])
                out[take_id] = {**body, "expected_credits": float(body.get("expected_credits") or fallback)}
                # P17-07: a Flow job that reconcile proved left no clip is a provider failure
                if _provider_no_clip(root, take_id) and str(body.get("result") or "") in NO_BIND_RESULTS:
                    out[take_id]["result"] = "FLOW_FAILED_NO_CLIP"
            else:
                same = price.get("cost_unit") == receipt_unit(body)
                out[take_id] = {**body, "expected_cost": float(body.get("expected_cost")
                                                               or (price.get("expected_cost", 0.0) if same else 0.0))}
    return out


# P17-07 (film05 SC02_g2, SC04_g1): Flow took the job, then no clip and no failed tile were left. flow_reconcile proves
# it (NOT_IN_GALLERY 10+ min after the send, `provider_no_clip`); the send is a provider failure like FLOW_FAILED:
# its credits count, the send cap is not used.
NO_BIND_RESULTS = ("UNBOUND", "AMBIGUOUS", "TIMEOUT", "BLOCKED", "NO_VIDEO_UNDER_TILE")


def _provider_no_clip(root: Path, take_id: str) -> bool:
    path = Path(root) / "media" / "takes" / f"{take_id}.reconcile.json"
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get("provider_no_clip"))
    except (OSError, ValueError):
        return False


def _write_receipt(root: Path, payload: dict[str, Any], **extra: Any) -> Path:
    path = takes_dir(root) / "intents" / f"{payload['take_id']}.intent.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    keep = ("film_id", "generation_id", "take_id", "shot_version", "prompt_sha256", "route", "model",
            "duration_s", "expected_credits", "credits_spent", "credit_cap", "provider", "provider_model", "tier",
            "cost_unit", "expected_cost")
    receipt = {k: payload[k] for k in keep}
    receipt["start_frame_sha256"] = payload["start_frame"]["sha256"]
    receipt["start_frame_source"] = payload["start_frame"]["source"]
    if "end_frame" in payload:
        receipt["end_frame_sha256"] = payload["end_frame"]["sha256"]
    receipt["blockers"] = [b["code"] for b in payload["blockers"]]
    receipt.update(extra)
    if receipt.get("sent") and receipt.get("cost_unit", "credits") != "credits":
        # the day of a send rules the daily cap; a later rewrite (the result) keeps the first day
        try:
            first = json.loads(path.read_text(encoding="utf-8")).get("sent_on") if path.is_file() else None
        except (OSError, ValueError):
            first = None
        receipt["sent_on"] = first or date.today().isoformat()
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def generate(pkg: Any, generation_id: str, *, dry_run: bool = True, plan_out: Path | None = None,
             stills_dir: Path | None = None, start_token: str | None = None, backlog: Path | None = None,
             runner: Runner | None = None, end_token: str | None = None,
             today: date | None = None, adapter: Any | None = None) -> dict[str, Any]:
    """``runner`` replaces flow_send on a Flow route; ``adapter`` replaces the HTTP adapter on an API route (tests and
    rehearsals: on a rehearsal package an explicit runner/adapter is a mock and records cost 0)."""
    payload = build_payload(pkg, generation_id, plan_out=plan_out, stills_dir=stills_dir, start_token=start_token,
                            end_token=end_token, today=today)
    root = Path(pkg.root)
    cap = get_capability(payload["provider"], payload["provider_model"])
    flow = cap.adapter == "flow_ui"
    live_blocked = [b for b in payload["blockers"] if not b["live_only"] or not dry_run]
    if dry_run:
        # a dry run reports the live-only blockers too, but they do not make the dry run itself fail
        receipt = _write_receipt(root, payload, dry_run=True, sent=False, owner_go_live=owner_go_live(backlog))
        return {"sent": False, "dry_run": True, "ready_to_send": not payload["blockers"], "payload": payload,
                "receipt": str(receipt)}
    # the go-live flag guards the provider; a rehearsal package with an explicit (mock) runner never reaches one
    mock = bool(pkg.header.rehearsal and (runner if flow else adapter) is not None)
    go = mock or owner_go_live(backlog)
    refusals = ([] if go else [_blocker("OWNER_GO_LIVE_NO", "the backlog header does not say OWNER_GO_LIVE: YES")])
    refusals += live_blocked
    if not flow:
        adapter = adapter or make_adapter(cap)
        health = adapter.health()
        if not health.routable:
            refusals.append(_blocker("PROVIDER_NOT_READY", f"{cap.provider}: {health.state} {health.diagnostic_code}",
                                     live_only=True))
    if refusals:
        receipt = _write_receipt(root, payload, dry_run=False, sent=False, owner_go_live=go,
                                 refused=[r["code"] for r in refusals])
        return {"sent": False, "dry_run": False, "refused": refusals, "payload": payload, "receipt": str(receipt)}
    receipt = _write_receipt(root, payload, dry_run=False, sent=True, owner_go_live=True, result="PENDING")
    if not flow:
        return _generate_api(pkg, payload, adapter, mock, receipt)
    out = Path(payload["output"])
    try:
        manifest = FlowUiAdapter(cap, runner=runner).send(payload["argv"], out)
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
                                 route=payload["route"], model=MODEL, credits=0.0 if mock else payload["expected_credits"],
                                 start_frame=Path(payload["start_frame"]["file"]), shot_version=payload["shot_version"])
        result["take"] = entry.model_dump(mode="json")
    result["manifest_result"] = outcome
    _write_receipt(root, payload, dry_run=False, sent=True, owner_go_live=True, result=outcome,
                   take_registered=bool(result.get("take")))
    return result


def _generate_api(pkg: Any, payload: dict[str, Any], adapter: Any, mock: bool, receipt: Path) -> dict[str, Any]:
    """An API route: submit, record the job id on the receipt at once (an interrupted poll leaves the binding), poll,
    download, register the take bound to its job id. The receipt's ``result`` is the normalized result; the provider's
    own outcome is ``provider_result``."""
    root = Path(pkg.root)
    request = GenerationRequest.model_validate(payload["request"])
    job: dict[str, str] = {}

    def submitted(job_id: str) -> None:
        job["id"] = job_id
        _write_receipt(root, payload, dry_run=False, sent=True, owner_go_live=True, result="PENDING",
                       provider_job_id=job_id)

    try:
        outcome = adapter.run(request, on_submitted=submitted)
    except BaseException:
        _write_receipt(root, payload, dry_run=False, sent=True, owner_go_live=True, result="PENDING",
                       provider_job_id=job.get("id", ""),
                       note="the adapter raised before reporting; poll the job id before resending")
        raise
    out = Path(payload["output"])
    result: dict[str, Any] = {"sent": True, "dry_run": False, "payload": payload, "manifest_result": outcome.result,
                              "provider_result": outcome.raw_result, "provider_job_id": outcome.provider_job_id,
                              "receipt": str(receipt)}
    final = outcome.result
    if final == "PASSED" and not (out.is_file() and outcome.sha256 and outcome.sha256 == sha256_file(out)):
        final = "AMBIGUOUS"  # the job says done but the bytes on disk are not the ones downloaded
    if final == "PASSED":
        entry, _ = register_take(root, pkg.header.film_id, payload["generation_id"], out,
                                 prompt_text=Path(payload["prompt_file"]).read_text(encoding="utf-8").strip(),
                                 route=payload["route"], model=payload["model"], credits=0.0,
                                 start_frame=Path(payload["start_frame"]["file"]), shot_version=payload["shot_version"],
                                 provider=payload["provider"], provider_job_id=outcome.provider_job_id,
                                 cost_unit=payload["cost_unit"], cost_amount=0.0 if mock else payload["expected_cost"])
        result["take"] = entry.model_dump(mode="json")
    result["manifest_result"] = final
    _write_receipt(root, payload, dry_run=False, sent=True, owner_go_live=True, result=final,
                   provider_result=outcome.raw_result, provider_job_id=outcome.provider_job_id,
                   take_registered=bool(result.get("take")), **({"note": outcome.detail} if outcome.detail else {}))
    return result
