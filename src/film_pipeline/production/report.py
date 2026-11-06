"""Status report and learnings ledger (categories 92 logging, 157-158 project and resource management, 165 risk, 168 reporting).

``status_report(pkg)`` answers "which gate is the film at, what is missing, what has it cost" from the files of the package
and nothing else: gates, stage completeness, credits spent against the estimate and the cap, usable seconds and the credits
per usable second, the retake rate and the open retake decisions, open P0 / P1 QC findings (take reviews and the master QC),
the dirty post items against the picture lock, rights blockers, the delivery state and one **next action**. A section that
cannot be computed is listed in ``errors`` instead of being left out silently, and a number is only reported when its source
exists (no cut report -> no ``cut_s``).

``ledger.json`` keeps the film's learnings. A learning is an ``observation`` until the same finding is recorded with evidence
from a second film; only then it is ``replicated``. The kind is derived, never declared, so one film cannot promote its own
observation. ``all_films`` puts the reports of every package in a directory side by side.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from film_pipeline.core import ContractModel

LEDGER = "ledger.json"
POST_ITEMS = ("titles", "mix", "master_qc", "versions")      # items of 06_post.json a finished film has
OPTIONAL_ITEMS = ("color",)
OPEN_RETAKE = ("CLASSIFY", "RETRY", "CHANGE_APPROACH", "ESCALATE")


# ------------------------------------------------------------------ learnings ledger

class Evidence(ContractModel):
    film_id: str = Field(min_length=1)
    ref: str = Field(min_length=3)           # where it can be checked: a file, a commit, a take id
    at: str = ""


class Learning(ContractModel):
    learning_id: str = Field(pattern=r"^L\d{3,}$")
    text: str = Field(min_length=8)
    area: str = Field(default="", description="stage or category the learning is about")
    evidence: list[Evidence] = Field(min_length=1)

    @property
    def films(self) -> list[str]:
        return sorted({e.film_id for e in self.evidence})

    @property
    def kind(self) -> Literal["observation", "replicated"]:
        return "replicated" if len(self.films) >= 2 else "observation"


class Ledger(ContractModel):
    film_id: str
    learnings: list[Learning] = Field(default_factory=list)


def ledger_path(root: Path) -> Path:
    return Path(root) / LEDGER


def load_ledger(root: Path, film_id: str = "") -> Ledger:
    path = ledger_path(root)
    if not path.is_file():
        return Ledger(film_id=film_id)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw == {}:                       # the empty placeholder `new` scaffolds
        return Ledger(film_id=film_id)
    return Ledger.model_validate(raw)


def save_ledger(root: Path, ledger: Ledger) -> Path:
    path = ledger_path(root)
    path.write_text(json.dumps(ledger.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_learning(root: Path, film_id: str, text: str, ref: str, *, area: str = "") -> Learning:
    ledger = load_ledger(root, film_id)
    if any(item.text.strip().lower() == text.strip().lower() for item in ledger.learnings):
        raise ValueError("this learning is already in the ledger: use --replicate with evidence from another film")
    entry = Learning(learning_id=f"L{len(ledger.learnings) + 1:03d}", text=text.strip(), area=area,
                     evidence=[Evidence(film_id=film_id, ref=ref, at=_stamp())])
    ledger.learnings.append(entry)
    save_ledger(root, ledger)
    return entry


def add_evidence(root: Path, learning_id: str, film_id: str, ref: str) -> Learning:
    """Evidence for an existing learning from ``film_id``. Another reference from a film that is already there is kept but
    does not make the learning replicated: replication needs a different film."""
    ledger = load_ledger(root)
    found = next((x for x in ledger.learnings if x.learning_id == learning_id), None)
    if found is None:
        raise ValueError(f"no learning {learning_id} in {ledger_path(root)}")
    found.evidence.append(Evidence(film_id=film_id, ref=ref, at=_stamp()))
    save_ledger(root, ledger)
    return found


def ledger_view(root: Path, film_id: str = "") -> dict[str, Any]:
    ledger = load_ledger(root, film_id)
    rows = [{"id": x.learning_id, "kind": x.kind, "films": x.films, "area": x.area, "text": x.text,
             "evidence": [e.model_dump(mode="json") for e in x.evidence]} for x in ledger.learnings]
    return {"film_id": ledger.film_id or film_id, "learnings": rows,
            "counts": {"observation": sum(r["kind"] == "observation" for r in rows),
                       "replicated": sum(r["kind"] == "replicated" for r in rows)}}


# ------------------------------------------------------------------ report sections

def _gates(pkg: Any) -> dict[str, Any]:
    from film_pipeline.production.gates import evaluate_gates
    results = evaluate_gates(pkg)
    return {r.gate: {"name": r.name, "status": r.status, "issues": len(r.issues), "first": r.issues[:2]} for r in results}


def _credits(pkg: Any, spent: float, expected: float | None) -> dict[str, Any]:
    budget = pkg.header.budget
    estimate, cap = budget.credits_estimate, budget.credits_cap
    return {"spent": round(spent, 2), "estimate": estimate, "cap": cap, "planned_expected": expected,
            "pct_of_estimate": round(100 * spent / estimate, 1) if estimate else None,
            "over_estimate": bool(estimate and spent > estimate), "over_cap": bool(cap and spent > cap)}


def _production(pkg: Any) -> dict[str, Any]:
    from film_pipeline.production import takes as T
    from film_pipeline.production.retake import retake_report
    shots = pkg.typed.get("shots")
    log = T.load_log(Path(pkg.root), pkg.header.film_id)
    by_status: dict[str, int] = {}
    for t in log.takes:
        by_status[t.status] = by_status.get(t.status, 0) + 1
    spent = sum(t.credits for t in log.takes)
    out: dict[str, Any] = {"takes": len(log.takes), "by_status": by_status, "credits_spent": spent,
                           "retake_rate": round(by_status.get("REJECTED", 0) / len(log.takes), 3) if log.takes else None}
    if shots is None:
        return out
    report = retake_report(log, shots)
    accepted = report["counts"]["DONE"]
    rendered = len(report["plan"])
    first_pass = sum(1 for row in report["plan"] if row["action"] == "DONE" and len(row["takes"]) == 1)
    usable = accepted * pkg.header.generation_s
    out.update(generations=len(shots.generations), rendered=rendered, accepted=accepted, first_pass=first_pass,
               first_pass_rate=round(first_pass / rendered, 3) if rendered else None, usable_s=usable,
               usable_s_basis=f"accepted generations x {pkg.header.generation_s} s",
               credits_per_usable_s=round(spent / usable, 2) if usable else None, retake_counts=report["counts"],
               open_retakes=[{"generation_id": r["generation_id"], "action": r["action"], "reason": r["reason"]}
                             for r in report["plan"] if r["action"] in OPEN_RETAKE],
               awaiting_review=[r["generation_id"] for r in report["plan"] if r["action"] == "AWAITING_REVIEW"],
               not_rendered=sorted(set(g.generation_id for g in shots.generations) - {r["generation_id"] for r in report["plan"]}))
    return out


def _qc(pkg: Any, production: dict[str, Any]) -> dict[str, Any]:
    from film_pipeline.production import master_qc as mq
    from film_pipeline.production.qc_model import TakeQc
    root = Path(pkg.root)
    open_p0, open_p1 = [], []
    reviews = root / "takes" / "reviews"
    done = {r["generation_id"] for r in production.get("open_retakes", [])} | set(production.get("awaiting_review", []))
    for path in sorted(reviews.glob("*.qc.json")) if reviews.is_dir() else []:
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw.pop("output_sha256", None)
        take = TakeQc.model_validate(raw)
        verdict = take.verdict()
        if take.generation_id in done or verdict.status == "REJECTED":
            if verdict.p0:
                open_p0.append({"take_id": take.take_id, "groups": verdict.p0})
            if verdict.p1_unwaived:
                open_p1.append({"take_id": take.take_id, "groups": verdict.p1_unwaived})
    master = None
    path = root / "qc" / "master_qc.json"
    if path.is_file():
        record = mq.MasterQc.model_validate_json(path.read_text(encoding="utf-8"))
        master = {"ok": record.ok, "p0": sum(f.severity == "P0" for f in record.findings),
                  "blocks": sum(f.severity == "BLOCK" for f in record.findings),
                  "warnings": sum(f.severity == "WARN" for f in record.findings)}
    return {"take_p0": open_p0, "take_p1_unwaived": open_p1, "master": master}


def _post(pkg: Any) -> dict[str, Any]:
    from film_pipeline.production.lock import dirty_items, items, lock_status
    present = {name: stage for stage, name, _ in items(pkg)}
    status = lock_status(pkg)
    out: dict[str, Any] = {"picture_lock": {k: status.get(k) for k in ("locked", "fresh", "reason") if k in status},
                           "items": sorted(present), "missing": [n for n in POST_ITEMS if n not in present],
                           "optional_missing": [n for n in OPTIONAL_ITEMS if n not in present]}
    if pkg.typed.get("edit") is not None:
        found = dirty_items(pkg)
        out["dirty"] = [f"{d['stage']}:{d['item']}" for d in found["dirty"]]
    else:
        out["dirty"] = []
    return out


def _rights(pkg: Any) -> dict[str, Any]:
    from film_pipeline.production import sound_rights as sr
    from film_pipeline.production.planning import legal
    pending = legal(pkg)["owner_decisions"]
    sounds = [f"{i['code']} {i['asset']}" for i in sr.check_assets(pkg)["issues"]] if pkg.typed.get("edit") is not None else []
    return {"pending": pending, "sound": sounds, "blockers": len(pending) + len(sounds)}


def _delivery(pkg: Any) -> dict[str, Any]:
    path = Path(pkg.root) / "delivery" / "MANIFEST.json"
    if not path.is_file():
        return {"delivered": False}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"delivered": True, "release_ready": data.get("release_ready"), "files": len(data.get("files", [])),
            "created": data.get("created"), "open_findings": [f"{f['code']}" for f in data.get("findings", [])]}


def _cut(pkg: Any) -> dict[str, Any] | None:
    cuts = sorted((Path(pkg.root) / "media" / "cut").glob("*.cut.json"), key=lambda p: p.stat().st_mtime) if (Path(pkg.root) / "media" / "cut").is_dir() else []
    if not cuts:
        return None
    planned = json.loads(cuts[-1].read_text(encoding="utf-8")).get("planned", {})
    return {"report": cuts[-1].name, "cut_s": planned.get("total_s")} if planned else None


# ------------------------------------------------------------------ next action

def next_action(report: dict[str, Any]) -> str:
    gates, production = report["gates"], report.get("production", {})
    for gid, g in gates.items():
        if g["status"] == "BLOCK" and int(gid) <= 3:
            return f"Resolve Gate {gid} ({g['name']}): {g['first'][0] if g['first'] else 'see validate'}"
    for gid, g in gates.items():
        if g["status"] == "OWNER_PENDING":
            return f"Owner decision needed at Gate {gid} ({g['name']}): {g['first'][0] if g['first'] else 'see validate'}"
    if production.get("not_rendered") and not production.get("takes"):
        return f"Generate is paused (OWNER_GO_LIVE): {len(production['not_rendered'])} shots wait for the Owner's go-live"
    if production.get("open_retakes"):
        row = production["open_retakes"][0]
        return f"Retake decision for {row['generation_id']}: {row['action']} - {row['reason']}"
    if production.get("awaiting_review"):
        return f"Review takes of {', '.join(production['awaiting_review'][:4])}"
    if production.get("not_rendered"):
        return f"Render {len(production['not_rendered'])} more shots (next: {production['not_rendered'][0]}) once the Owner allows Generate"
    if not report["edit"]["present"]:
        return "Write 05_edit.json from the accepted takes"
    post = report["post"]
    if not post["picture_lock"].get("locked"):
        return "Lock the picture (film.py lock --lock --by <name>)"
    if post["dirty"]:
        return f"Rebuild what the cut left behind: {', '.join(post['dirty'][:4])}"
    if post["missing"]:
        return f"Produce the missing post items: {', '.join(post['missing'])} (titles -> mix -> mastercheck -> versions)"
    if not report["delivery"]["delivered"]:
        return "Run film.py deliver"
    if not report["delivery"]["release_ready"]:
        why = [*report["rights"]["pending"][:2], *report["rights"]["sound"][:2]] or report["delivery"].get("open_findings", [])
        return f"Clear what keeps the delivery from release_ready: {'; '.join(why) or 'see delivery/MANIFEST.json'}"
    return "Nothing open on the pipeline side: waiting for the Owner's acceptance"


# ------------------------------------------------------------------ report

def status_report(pkg: Any) -> dict[str, Any]:
    """The whole-film report. Each section runs on its own: a failure becomes an entry of ``errors``."""
    errors: list[str] = []

    def section(name: str, fn, default):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - the report must say what it could not compute
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
            return default

    report: dict[str, Any] = {"film_id": pkg.header.film_id, "title": pkg.header.title, "profile": pkg.header.profile,
                              "stages": {"present": sorted(pkg.stages), "missing": pkg.missing_stages,
                                         "empty": sorted(k for k, v in pkg.stages.items() if not v)},
                              "package_issues": pkg.issues}
    report["gates"] = section("gates", lambda: _gates(pkg), {})
    production = section("production", lambda: _production(pkg), {})
    report["production"] = production
    expected = None
    if pkg.header.profile == "drama" and "preprod" in pkg.typed and "shots" in pkg.typed:
        def planned() -> dict[str, Any]:
            from film_pipeline.production.planning import planning_report
            plan = planning_report(pkg)
            return {"expected": plan["budget"]["expected_credits"], "owner_decisions": plan["legal"]["owner_decisions"]}
        info = section("planning", planned, {})
        expected = info.get("expected")
        report["owner_decisions"] = info.get("owner_decisions", [])
    report["credits"] = section("credits", lambda: _credits(pkg, production.get("credits_spent", 0.0), expected), {})
    report["edit"] = {"present": pkg.typed.get("edit") is not None}
    report["qc"] = section("qc", lambda: _qc(pkg, production), {})
    report["post"] = section("post", lambda: _post(pkg), {"picture_lock": {}, "dirty": [], "missing": list(POST_ITEMS), "items": []})
    report["rights"] = section("rights", lambda: _rights(pkg), {"pending": [], "sound": [], "blockers": 0})
    report["delivery"] = section("delivery", lambda: _delivery(pkg), {"delivered": False})
    report["cut"] = section("cut", lambda: _cut(pkg), None)
    report["learnings"] = ledger_view(Path(pkg.root), pkg.header.film_id)["counts"]
    report["errors"] = errors
    report["next_action"] = next_action(report)
    return report


def all_films(films_dir: Path) -> list[dict[str, Any]]:
    """One row per package under ``films_dir``: where each film is and what it cost."""
    from film_pipeline.production.package import PackageError, load_package
    rows = []
    for path in sorted(Path(films_dir).iterdir()):
        if not (path / "film.json").is_file():
            continue
        try:
            pkg = load_package(path)
            r = status_report(pkg)
        except PackageError as exc:
            rows.append({"film": path.name, "error": str(exc)})
            continue
        gates = {k: v["status"] for k, v in r["gates"].items()}
        prod = r["production"]
        rows.append({"film": r["film_id"], "profile": r["profile"], "gates": gates,
                     "credits_spent": r["credits"].get("spent"), "estimate": r["credits"].get("estimate"),
                     "usable_s": prod.get("usable_s"), "credits_per_usable_s": prod.get("credits_per_usable_s"),
                     "retake_rate": prod.get("retake_rate"), "delivered": r["delivery"]["delivered"],
                     "next_action": r["next_action"], "errors": len(r["errors"])})
    return rows
