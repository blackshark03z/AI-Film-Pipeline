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
import math
import os
import re
from contextlib import ExitStack, contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from film_pipeline.drama.generability import DRAFTS, rate_shot
from film_pipeline.production.interaction import offframe_leaks, protection_on, spoken_texts
from film_pipeline.production.plan import plan_package
from film_pipeline.production.money import (credit_ledger, load_adjustments, money_ledger, receipt_amount, receipt_charged,
                                            unresolved_sends, receipt_result, receipt_unit)
from film_pipeline.production.halt import is_halted, read_halt, set_halt
from film_pipeline.production import leases as L
from film_pipeline.production.planning import flow_credits
from film_pipeline.production.sections import shot_seconds
from film_pipeline.production.takes import (load_log, register_take, sha256_file, sha256_text, takes_dir)
from film_pipeline.production.runtime import (atomic_json, atomic_text, composer_lock, film_lock, film_writer,
                                              flow_cdp, flow_project)
from film_pipeline.providers.capability import DEFAULT_MODEL, DEFAULT_PROVIDER, ModelCapability, get_capability
from film_pipeline.providers.http_adapters import make_adapter
from film_pipeline.providers.flow_ui_adapter import FlowUiAdapter, default_runner, controller_runner  # noqa: F401 - re-exported
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


def _halt_blocker() -> dict[str, Any] | None:
    """PRODUCTION_HALT blocker while the machine-wide halt is set (Owner rule: no sending on any account)."""
    halt = read_halt()
    if halt is None:
        return None
    return _blocker("PRODUCTION_HALT", f"production halted: {halt.get('reason', '')} "
                    f"(afp-film halt clear --by ... --reason ...)", live_only=True)


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


_PLAN_CACHE: dict[tuple[Any, ...], tuple[Any, dict[str, str]]] = {}


def _cached_plan_package(pkg: Any, root: Path, plan_out: Path, verified: frozenset[str],
                         generation_id: str) -> Any:
    """Reuse an in-process ``plan_package`` result when package inputs and rendered prompt files match."""
    from film_pipeline.production.gate_checks import plan_inputs_sha

    key = (
        str(root.resolve()),
        str(plan_out.resolve()),
        tuple(sorted(plan_inputs_sha(root).items())),
        verified,
        id(plan_package),
    )
    cached = _PLAN_CACHE.get(key)
    prompt_path = plan_out / "prompts" / f"{generation_id}.txt"
    gate3_path = plan_out / "gate3.json"
    if cached is not None:
        result, prompt_shas = cached
        expected_sha = prompt_shas.get(generation_id)
        if expected_sha and prompt_path.is_file() and gate3_path.is_file() and sha256_file(prompt_path) == expected_sha:
            return result
        _PLAN_CACHE.pop(key, None)
    result = plan_package(pkg, plan_out, storyboard=False, verified_handoffs=verified)
    prompts_dir = plan_out / "prompts"
    prompt_shas = {p.stem: sha256_file(p) for p in prompts_dir.glob("*.txt")} if prompts_dir.is_dir() else {}
    _PLAN_CACHE[key] = (result, prompt_shas)
    return result


def build_payload(pkg: Any, generation_id: str, *, plan_out: Path | None = None, stills_dir: Path | None = None,
                  start_token: str | None = None, end_token: str | None = None,
                  today: date | None = None, cdp_scope: str | None = None,
                  account_scope: str | None = None) -> dict[str, Any]:
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
    result = _cached_plan_package(pkg, root, plan_out, verified, generation_id)
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
    if protection_on(pre):  # off-frame protection: a single's prompt must not name the people who are out of frame
        leaked = offframe_leaks(pre, decl, prompt, spoken_texts(pkg, decl))
        if leaked:
            blockers.append(_blocker("CROSS_ATTENTION_LEAK", f"{generation_id}: the prompt names off-frame character(s) "
                                     f"{', '.join(leaked)} outside the dialogue; the video model draws them into the frame"))

    if decl.previous_generation_id and not decl.independent_still:
        prev = next(g for g in shots.generations if g.generation_id == decl.previous_generation_id)
        accepted = [t for t in log.for_generation(prev.generation_id)
                    if t.status == "ACCEPTED" and t.shot_version == prev.version]
        if not accepted:
            blockers.append(_blocker("HANDOFF_PREVIOUS_NOT_ACCEPTED",
                                     f"{prev.generation_id} v{prev.version} has no ACCEPTED take; its end frame is "
                                     f"this shot's start frame"))
        start_source = f"end frame of {accepted[-1].take_id}" if accepted else f"end frame of {prev.generation_id}"
    elif decl.independent_still:
        start_source = "approved setup-anchor start still"
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
    # P18-02: a take named after its clip stem (an imported SC01_g1_t2.mp4 as the first take) holds that number too
    names = list(sent) + [n for t in log.for_generation(generation_id) for n in (t.take_id, Path(t.output_file).stem)]
    used = [len(log.for_generation(generation_id))] + [
        int(m.group(1)) for tid in names if tid.startswith(f"{generation_id}_t") and (m := _RECEIPT_NUMBER.search(tid))]
    number = max(used) + 1
    take_id = f"{generation_id}_t{number}"
    out = root / "media" / "takes" / f"{take_id}.mp4"
    ledger = money_ledger(log, sent, load_adjustments(root).adjustments)
    spent = ledger.get(unit, {}).get("spent", 0.0)
    from film_pipeline.production.muse_gateway import pending_muse_claims
    scope = (os.environ.get("AFP_FLOW_PROJECT", "").strip() if cdp_scope is None else cdp_scope.strip()) or None
    acct = (os.environ.get("AFP_FLOW_ACCOUNT", "").strip() if account_scope is None else account_scope.strip()) or None
    pending = {**unresolved_sends(log, sent), **pending_muse_claims(root)}
    if scope is not None or acct is not None:
        filtered = {}
        for tid, r in pending.items():
            same_gen = r.get("generation_id", tid.rsplit("_t", 1)[0]) == generation_id
            r_acct = str(r.get("account") or "").strip()
            r_proj = str(r.get("project") or "").strip()
            if same_gen:
                filtered[tid] = r
            elif not r_acct and not r_proj:
                filtered[tid] = r
            elif (acct and r_acct == acct) or (scope and r_proj == scope):
                filtered[tid] = r
        pending = filtered
    if pending:
        blockers.append(_blocker("SEND_PENDING", f"{', '.join(pending)} still needs reconciliation; run film.py reconcile "
                                 f"for the existing send before another submission", live_only=True))
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
    # The daily caps (machine-wide per unit, per provider) are the broker's: it reserves against them atomically at
    # admission (S1); the spend sent before S1 is imported into the broker first (leases.import_legacy_spend).
    daily = route_defaults().daily_caps.get(unit)
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
            "expected_cost": 0.0 if pkg.header.rehearsal else cost, "spent_in_unit": spent,
            "cap_in_unit": "unlimited" if cap_amount is not None and math.isinf(cap_amount) else cap_amount,
            "day": day,
            "warnings": warnings, "request": request.model_dump(mode="json")}
    if acct:
        payload["account"] = acct
    if scope:
        payload["project"] = scope
    if attempts is not None:
        payload["attempts"] = attempts
    if end_still is not None:
        payload["end_frame"] = {"file": str(end_still), "exists": end_still.is_file(),
                                "sha256": sha256_file(end_still) if end_still.is_file() else ""}
    return payload


def film_budget(pkg: Any, unit: str) -> dict[str, Any]:
    """The film-side numbers a broker admission in ``unit`` reserves against (read them under film_lock): the film's
    cap (None: none set, inf: unlimited), what its money ledger already spent in ``unit``, and every take id the
    ledger knows with the amount it verifiably counts for that take in ``unit`` (a registered take's cost, a charged
    unresolved receipt; 0 otherwise): the broker credits a take's reservation with no more than that. A rehearsal
    spends nothing: its cap is 0."""
    root = Path(pkg.root)
    if pkg.header.rehearsal:
        return {"film_cap": 0.0, "film_baseline": 0.0, "film_counted": {}, "rehearsal": True,
                "experiment": bool(pkg.header.experiment)}
    shots = pkg.typed["shots"]
    prices = {g.generation_id: _fallback_price(pkg.header, g) for g in shots.generations}
    sent = _sent_receipts(root, pkg.header.film_id, prices)
    log = load_log(root, pkg.header.film_id)
    ledger = money_ledger(log, sent, load_adjustments(root).adjustments)
    counted: dict[str, float] = {tid.split("~", 1)[0]: 0.0 for tid in sent}
    counted.update({t.take_id: 0.0 for t in log.takes})
    for t in log.takes:
        cost = t.cost if hasattr(t, "cost") else {"amount": t.credits, "unit": "credits"}
        if cost["unit"] == unit:
            counted[t.take_id] += float(cost["amount"])
    for tid, amount in ledger.get(unit, {}).get("unresolved", {}).items():
        counted[tid.split("~", 1)[0]] = counted.get(tid.split("~", 1)[0], 0.0) + float(amount)
    return {"film_cap": pkg.header.budget.cap_for(unit), "film_baseline": float(ledger.get(unit, {}).get("spent", 0.0)),
            "film_counted": counted, "rehearsal": False, "experiment": bool(pkg.header.experiment)}


def _film_budget(pkg: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """``film_budget`` for this send (its gates already refused BUDGET_NOT_SET / BUDGET_EXCEEDED in build_payload)."""
    if pkg.header.rehearsal:
        return {"film_cap": None, "film_baseline": 0.0, "film_counted": {}}
    return film_budget(pkg, payload["cost_unit"])


def _daily_blockers(pool: Any, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Read-only (dry runs): would the broker's daily caps refuse this send today?"""
    unit, cost, day = payload["cost_unit"], float(payload["expected_cost"]), payload["day"]
    in_unit = "" if unit == "credits" else f" {unit}"
    out = []
    pcap = pool.provider_caps.get(payload["provider"], {}).get(unit)
    if pcap is not None:
        used = pool.daily_usage(unit, day, provider=payload["provider"])
        if used + cost > pcap:
            out.append(_blocker("PROVIDER_DAILY_EXCEEDED", f"{payload['provider']}: {used:g} spent on {day} + {cost:g} "
                                f"> daily cap {pcap:g}{in_unit}", live_only=True))
    mcap = pool.machine_caps.get(unit)
    if mcap is not None:
        used = pool.daily_usage(unit, day)
        if used + cost > mcap:
            out.append(_blocker("BUDGET_DAILY_EXCEEDED", f"{used:g} spent on {day} + {cost:g} > daily cap "
                                f"{mcap:g}{in_unit}", live_only=True))
    return out


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
            if not isinstance(body, dict):
                raise ValueError("unreadable intent object")
            if receipt_result(body) == "AMBIGUOUS":
                from film_pipeline.production.recovery import resolved_receipt
                body = resolved_receipt(Path(root), take_id, body)
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
            else:
                same = price.get("cost_unit") == receipt_unit(body)
                out[take_id] = {**body, "expected_cost": float(body.get("expected_cost")
                                                               or (price.get("expected_cost", 0.0) if same else 0.0))}
    return out


def _write_receipt(root: Path, payload: dict[str, Any], **extra: Any) -> Path:
    path = takes_dir(root) / "intents" / f"{payload['take_id']}.intent.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    keep = ("film_id", "generation_id", "take_id", "shot_version", "prompt_sha256", "prompt_file", "route", "model",
            "duration_s", "expected_credits", "credits_spent", "credit_cap", "provider", "provider_model", "tier",
            "cost_unit", "expected_cost")
    receipt = {k: payload[k] for k in keep}
    receipt.update({k: payload[k] for k in ("submit_protocol", "dispatch_phase", "project", "cdp", "account", "lease_key",
                                            "lease_holder", "lease_db", "broker") if k in payload})
    receipt["start_frame_sha256"] = payload["start_frame"]["sha256"]
    receipt["start_frame_source"] = payload["start_frame"]["source"]
    if "end_frame" in payload:
        receipt["end_frame_sha256"] = payload["end_frame"]["sha256"]
    receipt["blockers"] = [b["code"] for b in payload["blockers"]]
    receipt.update(extra)
    if receipt.get("sent"):
        # The day of a send rules the daily cap; a later rewrite keeps the first day recorded.
        try:
            first = json.loads(path.read_text(encoding="utf-8")).get("sent_on") if path.is_file() else None
        except (OSError, ValueError):
            first = None
        receipt["sent_on"] = first or date.today().isoformat()
    atomic_json(path, receipt)
    return path


AUTO_RESEND = 1                         # P18-03: automatic resends after a provider failure, per generate call
PROVIDER_FAILURES_BEFORE_RESTAGE = 3    # OWNER_POLICY.md: after 3 provider failures on one shot, restage


def _is_flow_route(pkg: Any, generation_id: str) -> bool:
    shots = pkg.typed.get("shots") if hasattr(pkg, "typed") else None
    decl = next((g for g in shots.generations if g.generation_id == generation_id), None) if shots else None
    if decl is None:
        return False
    route = resolve_route(pkg.header, decl)
    return _capability(route).adapter == "flow_ui"


def generate(pkg: Any, generation_id: str, *, dry_run: bool = True, plan_out: Path | None = None,
             stills_dir: Path | None = None, start_token: str | None = None, backlog: Path | None = None,
             runner: Runner | None = None, end_token: str | None = None,
             today: date | None = None, adapter: Any | None = None, auto_resend: int = AUTO_RESEND,
             cdp_scope: str | None = None, account_scope: str | None = None,
             cdp_endpoint: str | None = None) -> dict[str, Any]:
    """``runner`` replaces flow_send on a Flow route; ``adapter`` replaces the HTTP adapter on an API route (tests and
    rehearsals: on a rehearsal package an explicit runner/adapter is a mock and records cost 0).

    P18-03: a Flow send that ends PROVIDER_FAILED (FLOW_FAILED, or a job proven vanished inside the send) is sent again
    up to ``auto_resend`` times -- same shot version, same prompt, no board re-approval -- while the shot version has
    fewer than PROVIDER_FAILURES_BEFORE_RESTAGE provider failures (OWNER_POLICY: 3 on one shot -> restage). The resend
    is an ordinary send through every gate (go-live, budget, cap). Each send is logged in takes/send_log.jsonl.

    S1 (STUDIO_ARCHITECTURE §5-§6): every live send is admitted by the broker in one short transaction (halt, epoch,
    the account's batch lease, and reservations against the account quota, the film budget, the provider's and the
    machine's daily caps); the broker re-checks halt, epoch and lease right before the Enter. ``film_lock`` and the broker
    transaction are leaf locks (F2): neither is ever taken while the other is held."""
    root = Path(pkg.root)
    if dry_run:
        with film_lock(root, timeout_s=15.0):
            payload = build_payload(pkg, generation_id, plan_out=plan_out, stills_dir=stills_dir, start_token=start_token,
                                    end_token=end_token, today=today, cdp_scope=cdp_scope, account_scope=account_scope)
        # read-only broker checks, outside film_lock (F2)
        halted = _halt_blocker()
        if halted is not None:
            payload["blockers"].append(halted)
        if not pkg.header.rehearsal:
            pool = L.machine_pool()
            L.import_legacy_spend(pool, root)   # the pre-S1 spend is in the broker's daily usage (idempotent)
            payload["blockers"].extend(_daily_blockers(pool, payload))
        if _is_flow_route(pkg, generation_id) and not (pkg.header.rehearsal and runner is not None):
            # a dry run only reports whether a live send could lease an account; it never takes a lease
            ok, why = L.machine_pool().availability(cost_credits=float(payload["expected_credits"]),
                                                    account_id=L.pinned_account(account_scope),
                                                    provider=payload["provider"])
            if not ok:
                payload["warnings"].append({"code": L.BLOCKER, "detail": f"a live send would be refused: {why}"})
        with film_lock(root, timeout_s=15.0):
            receipt = _write_unsent_receipt(root, payload, dry_run=True, sent=False,
                                            owner_go_live=owner_go_live(backlog))
        return {"sent": False, "dry_run": True, "ready_to_send": not payload["blockers"], "payload": payload,
                "receipt": str(receipt)}

    resend = False
    with ExitStack() as outer:
        if _is_flow_route(pkg, generation_id):
            outer.enter_context(composer_lock(cdp_endpoint))

        # Phase A0 (film_lock, short): the payload, every refusal that needs no broker, the film's budget numbers.
        with film_lock(root, timeout_s=15.0):
            payload = build_payload(pkg, generation_id, plan_out=plan_out, stills_dir=stills_dir, start_token=start_token,
                                    end_token=end_token, today=today, cdp_scope=cdp_scope, account_scope=account_scope)
            cap = get_capability(payload["provider"], payload["provider_model"])
            flow = cap.adapter == "flow_ui"
            live_blocked = list(payload["blockers"])
            mock = bool(pkg.header.rehearsal and (runner if flow else adapter) is not None)
            go = mock or owner_go_live(backlog)
            refusals = ([] if go else [_blocker("OWNER_GO_LIVE_NO", "the backlog header does not say OWNER_GO_LIVE: YES")])
            refusals += live_blocked
            halted = None if mock else _halt_blocker()
            if halted is not None:
                refusals.append(halted)
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
            budget = _film_budget(pkg, payload)

        # Admission: one short broker transaction, outside film_lock (F2). A mock leases from the rehearsal package's
        # own pool; an API route reserves without an account.
        pool, lease, refused = _admit(pkg, payload, budget, flow=flow, mock=mock, account_scope=account_scope,
                                      cdp_endpoint=cdp_endpoint, cdp_scope=cdp_scope)
        if lease is None:
            with film_lock(root, timeout_s=15.0):
                receipt = _write_unsent_receipt(root, payload, dry_run=False, sent=False, owner_go_live=go,
                                                refused=[refused["code"]])
            return {"sent": False, "dry_run": False, "refused": [refused], "payload": payload, "receipt": str(receipt)}
        try:
            payload.update(broker=True, lease_key=lease["lease_key"], lease_holder=lease["holder"],
                           lease_db=str(pool.db_path))
            if flow:   # the journal names the Flow profile (CDP endpoint) and, when pinned, the project this send targets
                lease_cdp, lease_proj = str(lease.get("cdp_endpoint") or ""), str(lease.get("project") or "")
                payload["cdp"] = flow_cdp(cdp_endpoint or lease_cdp or None)
                effective_proj = (cdp_scope if cdp_scope is not None else (lease_proj or flow_project())).strip()
                if effective_proj:
                    payload["project"] = effective_proj
                # the lease's profile: its composer lock, and AFP_FLOW_CDP/AFP_FLOW_PROJECT for the in-process sender
                outer.enter_context(composer_lock(payload["cdp"]))
                outer.enter_context(_flow_target_env(lease_cdp if not cdp_endpoint else "",
                                                     lease_proj if cdp_scope is None else ""))
                payload.update(account=lease["account_id"])
            if flow and runner is None and not mock:   # probes the browser: never under film_lock
                from film_pipeline.production.preflight import check
                environment = check(root, probe_flow=True, operation="send")
                if not environment["ok"]:
                    _drop_lease(pool, lease)
                    return {"sent": False, "dry_run": False, "refused": [_blocker("ENVIRONMENT_NOT_READY", issue)
                            for issue in environment["issues"]], "payload": payload, "environment": environment}
            # Phase A1 (film_lock, short): the immutable prompt snapshot and the PENDING receipt
            with film_lock(root, timeout_s=15.0):
                taken = _receipt_sent(root, payload["take_id"])
                if not taken:
                    snapshot = takes_dir(root) / "intents" / f"{payload['take_id']}.prompt.txt"
                    prompt = Path(payload["prompt_file"]).read_text(encoding="utf-8").strip()
                    if sha256_text(prompt) != payload["prompt_sha256"]:
                        raise ValueError("prompt changed during preflight; no send was made")
                    if snapshot.exists() and snapshot.read_text(encoding="utf-8").strip() != prompt:
                        raise ValueError("immutable sent prompt snapshot conflicts; no send was made")
                    if not snapshot.exists():
                        atomic_text(snapshot, prompt + "\n")
                    old_prompt = payload["prompt_file"]
                    payload["prompt_file"] = str(snapshot)
                    payload["argv"] = [str(snapshot) if arg == old_prompt else arg for arg in payload["argv"]]
                    effective_acct = (account_scope if account_scope is not None
                                      else os.environ.get("AFP_FLOW_ACCOUNT", "")).strip()
                    if effective_acct and not flow:
                        payload["account"] = effective_acct
                    if flow and (runner is None or getattr(runner, "takes_before_submit", False)):
                        payload.update(submit_protocol="inprocess-checkpoint-v1", dispatch_phase="PREPARING")
                    receipt = _write_receipt(root, payload, dry_run=False, sent=True, owner_go_live=True,
                                             result="PENDING")
            if taken:   # another send of this film took the same take number since Phase A0: never overwrite it
                _drop_lease(pool, lease)
                return {"sent": False, "dry_run": False, "payload": payload,
                        "refused": [_blocker("TAKE_NUMBER_TAKEN", f"{payload['take_id']} was sent by another caller "
                                             f"meanwhile; run generate again", live_only=True)]}
        except BaseException:
            _drop_lease(pool, lease)   # nothing was submitted: give the account back, no charge, no cooldown
            raise

        # Phase B (outside film_lock so parallel CDP accounts do not hit FILM_BUSY during provider I/O)
        if not flow:
            return _generate_api(pkg, payload, adapter, mock, receipt, pool, lease)
        try:
            result, resend = _send_flow(pkg, payload, cap, runner, mock, receipt, auto_resend, pool, lease)
        except BaseException as exc:
            # crash or unknown outcome: the lease stays held (uncertain) until `afp-film lease settle` after reconcile;
            # the one exception: the durable dispatch phase is still PREPARING, i.e. the sender never reached the Enter
            # (a dead controller cannot issue a later one), so nothing was submitted and the account is given back.
            # The broker has the last word: a child it saw pass the pre-Enter check (SUBMITTING) is never released.
            if not lease.get("finished"):
                why = f"send raised {type(exc).__name__}: {exc}"[:300]
                if payload.get("dispatch_phase") == "PREPARING":
                    _drop_lease(pool, lease, reason=why)
                else:
                    _hold_lease(pool, lease, why)
            raise
    if resend:   # an ordinary send through every gate; it acquires its own lease
        result["auto_resend"] = generate(pkg, generation_id, dry_run=False, plan_out=plan_out, stills_dir=stills_dir,
                                         start_token=start_token, backlog=backlog, runner=runner, end_token=end_token,
                                         today=today, adapter=adapter, auto_resend=auto_resend - 1,
                                         cdp_scope=cdp_scope, account_scope=account_scope, cdp_endpoint=cdp_endpoint)
    return result


def _receipt_sent(root: Path, take_id: str) -> bool:
    """Whether ``take_id`` already has the receipt of a real send (read under film_lock)."""
    path = takes_dir(root) / "intents" / f"{take_id}.intent.json"
    if not path.is_file():
        return False
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True   # unreadable: treat it as a send (never overwrite evidence)
    return bool(isinstance(body, dict) and body.get("sent"))


def _write_unsent_receipt(root: Path, payload: dict[str, Any], **extra: Any) -> Path:
    """A dry-run or refused receipt written after film_lock was released and taken again: never over the receipt of a
    real send of the same take number (another caller may have claimed it meanwhile)."""
    if _receipt_sent(root, payload["take_id"]):
        return takes_dir(root) / "intents" / f"{payload['take_id']}.intent.json"
    return _write_receipt(root, payload, **extra)


# admission refusals that keep their own code; any other (no account, lease held, epoch, batch) is NO_ACCOUNT_LEASE
ADMISSION_CODES = ("PRODUCTION_HALT", "BUDGET_EXCEEDED", "BUDGET_DAILY_EXCEEDED", "PROVIDER_DAILY_EXCEEDED", "NO_PRICE")


def _admit(pkg: Any, payload: dict[str, Any], budget: dict[str, Any], *, flow: bool, mock: bool,
           account_scope: str | None, cdp_endpoint: str | None,
           cdp_scope: str | None) -> tuple[Any, dict[str, Any] | None, dict[str, Any]]:
    """The broker admission of this send: a batch of one child (the take) under key ``<film_id>:<take_id>@<package>``
    and a fresh holder. A Flow send leases an account (pinned by ``account_scope`` / AFP_FLOW_ACCOUNT, else the broker's
    choice); an API send reserves without one. Returns (broker, lease, refusal blocker). An explicit ``cdp_endpoint``
    or ``cdp_scope`` that contradicts the account's registered profile/project refuses the lease."""
    from film_pipeline.agentic.broker import AdmitRequest, Child, new_holder
    from film_pipeline.production.runtime import normalize_cdp
    root = Path(pkg.root)
    pinned = L.pinned_account(account_scope) if flow else None
    legacy_root = None
    if mock:
        pool, name = L.rehearsal_pool(root, pinned)
        pinned = name if flow else None
    else:
        pool = L.machine_pool()
        legacy_root = L.import_legacy_spend(pool, root)   # reads receipts: outside both leaf locks
    unit = payload["cost_unit"]
    request = AdmitRequest(
        lease_key=L.lease_key(payload["film_id"], payload["take_id"], root),
        children=[Child(payload["take_id"], _expected_amount(payload), take_id=payload["take_id"],
                        shot_key=f"{payload['generation_id']}:v{payload['shot_version']}")],
        unit=unit, provider=None if mock else payload["provider"], job_kind="video", film_id=payload["film_id"],
        film_key=L.film_scope(payload["film_id"], root), generation_id=payload["generation_id"],
        shot_version=payload["shot_version"], holder=new_holder(), account_id=pinned, needs_account=flow,
        film_cap=budget["film_cap"], film_baseline=budget["film_baseline"], film_counted=budget["film_counted"],
        legacy_root=legacy_root, day=payload.get("day"))
    out = pool.admit(request)
    if not out["ok"]:
        code = out["code"] if out["code"] in ADMISSION_CODES else L.BLOCKER
        return pool, None, _blocker(code, out["reason"], live_only=True)
    lease = out["lease"]
    conflict = ""
    if flow and cdp_endpoint and lease["cdp_endpoint"] and \
            normalize_cdp(cdp_endpoint) != normalize_cdp(lease["cdp_endpoint"]):
        conflict = f"account {lease['account_id']} uses profile {lease['cdp_endpoint']}, this send targets {cdp_endpoint}"
    elif flow and cdp_scope and lease["project"] and cdp_scope.strip() != lease["project"]:
        conflict = f"account {lease['account_id']} uses project {lease['project']}, this send targets {cdp_scope}"
    if conflict:
        _drop_lease(pool, lease)
        return pool, None, _blocker(L.BLOCKER, conflict, live_only=True)
    return pool, lease, {}


def _expected_amount(payload: dict[str, Any]) -> float | None:
    """The send's price in its own unit (None: no price, the broker refuses it)."""
    value = payload["expected_credits"] if payload["cost_unit"] == "credits" else payload.get("expected_cost")
    return None if value is None else float(value)


def _drop_lease(pool: Any, lease: dict[str, Any] | None, *, reason: str = "") -> None:
    """Give back a lease whose send was never submitted: nothing spent, no cooldown. A child the broker saw pass the
    pre-Enter check (SUBMITTING) is never released here: it is held for reconcile instead. A lease this caller no
    longer holds (the broker closed it, or another token) is left as it is."""
    if lease is None or lease.get("finished"):
        return
    try:
        out = pool.release_unsent(lease["lease_key"], lease_token=lease["lease_token"])
        if out["uncertain"]:
            pool.hold_child(lease["lease_key"], lease_token=lease["lease_token"],
                            reason=reason or "the broker saw the child pass the pre-Enter check")
    except (KeyError, ValueError):
        pass
    lease["finished"] = True


def _hold_lease(pool: Any, lease: dict[str, Any], reason: str) -> None:
    """The send's outcome is unknown: hold the lease (and its account) until reconcile + `lease settle`."""
    try:
        pool.hold_child(lease["lease_key"], lease_token=lease["lease_token"], reason=reason)
    except (KeyError, ValueError):
        pass
    lease["finished"] = True


def _finish_lease(pool: Any, lease: dict[str, Any], payload: dict[str, Any], outcome: str, normalized: str) -> None:
    """Settle the lease from the send's outcome (after film_lock is released): an account warning has already
    quarantined the account and held the lease; an unknown outcome keeps the lease held until reconcile + `lease
    settle`; otherwise the child is settled, spending the expected amount when the outcome is charged (the money
    ledger's rule)."""
    if lease.get("finished"):
        return
    if normalized == "AMBIGUOUS":
        _hold_lease(pool, lease, outcome)
        return
    spent = float(_expected_amount(payload) or 0.0) if receipt_charged({**payload, "result": outcome}) else 0.0
    pool.finish_child(lease["lease_key"], lease_token=lease["lease_token"], child_key=payload["take_id"],
                      outcome=normalized, spent=spent)
    lease["finished"] = True


@contextmanager
def _flow_target_env(cdp: str, project: str):
    """Point the in-process Flow sender (AFP_FLOW_CDP / AFP_FLOW_PROJECT) at the lease's profile for this send."""
    saved = {k: os.environ.get(k) for k in ("AFP_FLOW_CDP", "AFP_FLOW_PROJECT")}
    try:
        if cdp:
            os.environ["AFP_FLOW_CDP"] = cdp
        if project:
            os.environ["AFP_FLOW_PROJECT"] = project
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _send_flow(pkg: Any, payload: dict[str, Any], cap: Any, runner: Runner | None, mock: bool, receipt: Path,
               auto_resend: int, pool: Any, lease: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Phase B (the Flow send), Phase C (register the take, final receipt, send log), then the lease settlement."""
    from film_pipeline.agentic.broker import NotSent
    root = Path(pkg.root)
    generation_id = payload["generation_id"]
    out = Path(payload["output"])

    def before_submit(context):
        # right before the Enter, in one broker transaction: the halt (a warning on another account may have set it),
        # the epoch and the lease; losing any of them ends the child NOT_SENT and nothing is submitted
        check = pool.before_enter(lease["lease_key"], lease_token=lease["lease_token"], child_key=payload["take_id"])
        if not check["go"]:
            raise NotSent(check["code"], check["reason"])
        with film_lock(root, timeout_s=15.0):
            payload.update(dispatch_phase="SUBMITTING", project=context.get("project") or payload.get("project", ""))
            _write_receipt(root, payload, dry_run=False, sent=True, owner_go_live=True, result="PENDING")

    if runner is None:
        native_runner = lambda argv, output: controller_runner(argv, output, before_submit)  # noqa: E731
    elif getattr(runner, "takes_before_submit", False):   # the rehearsal mock: writes the SUBMITTING receipt like the sender
        native_runner = lambda argv, output: runner(argv, output, before_submit)  # noqa: E731
    else:
        native_runner = runner
    # On exception keep the last durable phase; a dead controller cannot issue a later Enter.
    manifest = FlowUiAdapter(cap, runner=native_runner).send(payload["argv"], out)

    outcome = str(manifest.get("result"))
    if "FLOW_ACCOUNT_WARNING" in outcome:
        # Owner rule: any account warning stops ALL sending at once (before Phase C); never auto-resend. The broker
        # quarantines the account and holds its lease in the transaction that records its halt event.
        set_halt(outcome, source="generate", account=str(payload.get("account", "")),
                 film_id=pkg.header.film_id, take_id=payload["take_id"], db=getattr(pool, "db_path", None))
        if lease.get("account_id"):
            pool.account_warning(lease["account_id"], outcome, film_id=pkg.header.film_id, take_id=payload["take_id"])
            lease["finished"] = True

    # Phase C (short exclusive metadata lock): register take, write final receipt, and append send log.
    with film_lock(root, timeout_s=15.0):
        result: dict[str, Any] = {"sent": True, "dry_run": False, "payload": payload, "manifest_result": manifest.get("result"),
                                  "receipt": str(receipt)}
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
        normalized = cap.normalize(outcome)
        incident = normalized == "PROVIDER_FAILED"
        failures = _provider_failures(root, pkg.header.film_id, generation_id, payload["shot_version"]) if incident else 0
        resend = (incident and auto_resend > 0 and failures < PROVIDER_FAILURES_BEFORE_RESTAGE
                  and not is_halted())
        log_send(root, payload, manifest, outcome, normalized, auto_resend=resend, provider_failures=failures)
        if incident and not resend and failures >= PROVIDER_FAILURES_BEFORE_RESTAGE:
            result["restage_needed"] = (f"{generation_id} v{payload['shot_version']}: {failures} provider failures; "
                                        f"restage or simplify the prompt and record why (OWNER_POLICY)")
    _finish_lease(pool, lease, payload, outcome, normalized)   # the broker settlement: after film_lock (F2)
    return result, resend


def _provider_failures(root: Path, film_id: str, generation_id: str, version: int) -> int:
    """Sends of this shot version whose normalized result is PROVIDER_FAILED (the one just written included)."""
    sent = _sent_receipts(root, film_id, {})
    return sum(1 for tid, r in sent.items() if r.get("generation_id", tid.rsplit("_t", 1)[0]) == generation_id
               and r.get("shot_version", 1) == version and receipt_result(r) == "PROVIDER_FAILED")


def log_send(root: Path, payload: dict[str, Any], manifest: dict[str, Any], outcome: str, normalized: str,
             **extra: Any) -> Path:
    """P18-03 reliability log: one JSON line per Flow send in takes/send_log.jsonl (time, receipt, result, binding,
    elapsed); ``incident`` marks a provider failure. Nothing secret: no token, URL or prompt text."""
    path = takes_dir(root) / "send_log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = {"at": datetime.now().astimezone().isoformat(timespec="seconds"), "take_id": payload["take_id"],
            "generation_id": payload["generation_id"], "shot_version": payload["shot_version"],
            "provider": payload["provider"], "model": payload["provider_model"], "result": outcome,
            "normalized": normalized, "incident": normalized == "PROVIDER_FAILED",
            "binding": manifest.get("binding", ""), "bound_in_send": outcome == "PASSED",
            "elapsed_s": manifest.get("elapsed_s"), "started": manifest.get("started", ""),
            "finished": manifest.get("finished", ""), "cdp": payload.get("cdp", ""),
            "project": payload.get("project", ""), "account": payload.get("account", ""), **extra}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    return path


def _generate_api(pkg: Any, payload: dict[str, Any], adapter: Any, mock: bool, receipt: Path, pool: Any,
                  lease: dict[str, Any]) -> dict[str, Any]:
    """An API route: submit, record the job id on the receipt at once (an interrupted poll leaves the binding), poll,
    download, register the take bound to its job id. The receipt's ``result`` is the normalized result; the provider's
    own outcome is ``provider_result``. The broker re-checks halt and lease right before the submit and settles the
    reservation from the outcome after film_lock is released (F2)."""
    from film_pipeline.agentic.broker import NotSent
    root = Path(pkg.root)
    request = GenerationRequest.model_validate(payload["request"])
    job: dict[str, str] = {}

    def submitted(job_id: str) -> None:
        with film_lock(root, timeout_s=15.0):
            job["id"] = job_id
            _write_receipt(root, payload, dry_run=False, sent=True, owner_go_live=True, result="PENDING",
                           provider_job_id=job_id)

    check = pool.before_enter(lease["lease_key"], lease_token=lease["lease_token"], child_key=payload["take_id"])
    if not check["go"]:   # the broker closed the child NOT_SENT: nothing was submitted, nothing is charged
        lease["finished"] = True
        with film_lock(root, timeout_s=15.0):
            _write_receipt(root, payload, dry_run=False, sent=True, owner_go_live=True,
                           result=f"PRE_SUBMIT_ERROR NOT_SENT {check['code']}",
                           note=f"{check['reason']}; nothing was submitted"[:300])
        raise NotSent(check["code"], check["reason"])
    try:
        outcome = adapter.run(request, on_submitted=submitted)
    except BaseException as exc:
        with film_lock(root, timeout_s=15.0):
            _write_receipt(root, payload, dry_run=False, sent=True, owner_go_live=True, result="PENDING",
                           provider_job_id=job.get("id", ""),
                           note="the adapter raised before reporting; poll the job id before resending")
        _hold_lease(pool, lease, f"the adapter raised {type(exc).__name__}"[:300])
        raise
    out = Path(payload["output"])
    with film_lock(root, timeout_s=15.0):
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
    _finish_lease(pool, lease, payload, final, final)   # the broker settlement: after film_lock (F2)
    return result
