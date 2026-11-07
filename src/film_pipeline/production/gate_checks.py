"""Validators for gates 3, 4 and 6 of a drama Production Package (P10-01).

Each gate has two functions: ``*_issues`` (a defect -> BLOCK) and ``*_pending`` (nothing is wrong, but a human has to decide
-> OWNER_PENDING). A gate is PASS only when both are empty, i.e. when the evidence on disk says so; missing evidence is a BLOCK,
never a pass.

* Gate 3 (visual_spatial) reads the plan record that ``film.py plan`` wrote (``media/plan/gate3.json`` + ``plan_meta.json``).
  A plan older than the stage files it was made from is stale. Only a *pending* storyboard is an Owner matter.
* Gate 4 (production_asset) reads the take log and the stored reviews: every generation needs a take of the current shot version
  that a human review accepted, with the logged bytes. Takes nobody has judged yet are pending, not good.
* Gate 6 (final_master) reads the master QC record, the delivery archive and the picture lock. A clean delivery is still pending
  until the Owner's acceptance (written by ``film.py deliver --accept``) is bound to the current archive manifest.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

PLAN_DIR = ("media", "plan")
PLAN_META = "plan_meta.json"
# the stage files a plan is made from (a change to any of them makes the plan stale)
PLAN_INPUTS = ("script.fountain", "02_direction.json", "03_preprod.json", "04_shots.json")
_PLAN_KEYS = ("feasibility", "temporal", "continuity", "camera", "comprehension")
_COVERED_BY_RECORD = ("FEASIBILITY", "TEMPORAL", "CONTINUITY", "CAMERA", "COMPREHENSION")


def file_sha(path: Path) -> str:
    """sha256 of a file with line endings normalised, so a plan survives a CRLF/LF checkout."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _preprod_sha(path: Path) -> str:
    """03_preprod.json without its `stills` record: registering or approving a start still is not a planning change."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return file_sha(path)
    if not isinstance(raw, dict):
        return file_sha(path)
    raw.pop("stills", None)  # always canonical JSON, so adding the first still does not change the hash
    return hashlib.sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def plan_inputs_sha(root: Path) -> dict[str, str]:
    return {name: (_preprod_sha if name == "03_preprod.json" else file_sha)(Path(root) / name)
            for name in PLAN_INPUTS if (Path(root) / name).is_file()}


def plan_dir(root: Path) -> Path:
    return Path(root).joinpath(*PLAN_DIR)


# --------------------------------------------------------------------------- gate 3

def _load_plan(pkg: Any) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    base = plan_dir(pkg.root)
    record_path, meta_path = base / "gate3.json", base / PLAN_META
    if not record_path.is_file():
        return None, None, ["no plan record (media/plan/gate3.json): run film.py plan"]
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else None
    except (OSError, ValueError) as exc:
        return None, None, [f"plan record unreadable: {exc}"]
    if meta is None:
        return record, None, [f"{PLAN_META} missing next to gate3.json: run film.py plan again"]
    stale = [n for n, sha in plan_inputs_sha(pkg.root).items() if meta.get("planned_from", {}).get(n) != sha]
    if stale:
        return record, meta, [f"the plan is stale, {', '.join(stale)} changed after film.py plan: run it again"]
    return record, meta, []


def _is_pending_storyboard(issue: dict[str, Any]) -> bool:
    return issue.get("check") == "STORYBOARD" and str(issue.get("detail", "")).endswith("storyboard PENDING")


def plan_issues(pkg: Any) -> list[str]:
    record, meta, problems = _load_plan(pkg)
    if problems or record is None or meta is None:
        return problems
    out: list[str] = []
    for key in _PLAN_KEYS:
        out += [f"{key.upper()} {i['check']}: {i['detail']}" for i in record.get(key, []) if i.get("severity") == "BLOCK"]
    for gid, gen in record.get("generations", {}).items():
        out += [f"{gid} {i['check']}: {i['detail']}" for i in gen.get("issues", [])
                if i.get("severity") == "BLOCK" and not _is_pending_storyboard(i)]
    out += [p for p in meta.get("problems", []) if " preflight " not in p and not p.startswith(_COVERED_BY_RECORD)]
    if not record.get("generations"):
        out.append("the plan record holds no generations")
    return list(dict.fromkeys(out))


def plan_pending(pkg: Any) -> list[str]:
    record, _, problems = _load_plan(pkg)
    if problems or record is None:
        return []
    frames = [f"{gid} {i['detail'].split(':')[0]}" for gid, gen in record.get("generations", {}).items()
              for i in gen.get("issues", []) if _is_pending_storyboard(i)]
    return [f"storyboard not approved: {len(frames)} frame(s) wait for a reviewer "
            "(film.py plan --approve-storyboard NAME after looking at them)"] if frames else []


# --------------------------------------------------------------------------- gate 4

def _review(root: Path, entry: Any) -> Any | None:
    from film_pipeline.production.qc_model import TakeQc
    from film_pipeline.production.takes import takes_dir
    if not entry.review_file:
        return None
    path = takes_dir(root) / entry.review_file
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw.get("qc"), dict):  # a legacy pointer at the wrapped dailies sheet: the review is its `qc` block
        raw = dict(raw["qc"])
    claimed = raw.pop("output_sha256", None)
    return TakeQc.model_validate(raw), claimed


def take_issues(pkg: Any) -> list[str]:
    return _take_state(pkg)[0]


def take_pending(pkg: Any) -> list[str]:
    return _take_state(pkg)[1]


def _take_state(pkg: Any) -> tuple[list[str], list[str]]:
    from film_pipeline.production.takes import load_log
    root = Path(pkg.root)
    log = load_log(root, pkg.header.film_id)
    blocks: list[str] = []
    pending: list[str] = []
    for decl in pkg.typed["shots"].generations:
        gid = decl.generation_id
        takes = [t for t in log.for_generation(gid) if t.shot_version == decl.version]
        stale = [t.take_id for t in log.for_generation(gid) if t.shot_version != decl.version]
        if not takes:
            blocks.append(f"{gid}: no take of shot version {decl.version}" + (f" (older: {', '.join(stale)})" if stale else ""))
            continue
        accepted = [t for t in takes if t.status == "ACCEPTED"]
        if not accepted:
            waiting = [t.take_id for t in takes if t.status in ("GENERATED", "INCOMPLETE")]
            if waiting:
                pending.append(f"{gid}: take {', '.join(waiting)} waits for a human review")
            else:
                blocks.append(f"{gid}: every take is rejected ({', '.join(t.take_id for t in takes)}): retake or pickup")
            continue
        for entry in accepted:
            found = _review(root, entry)
            if found is None:
                blocks.append(f"{entry.take_id}: ACCEPTED in the log without a stored review")
                continue
            review, claimed = found
            if claimed != entry.output_sha256:
                blocks.append(f"{entry.take_id}: the review is not bound to the logged bytes")
            if review.verdict().status != "ACCEPTED":
                blocks.append(f"{entry.take_id}: the stored review does not accept it ({'; '.join(review.verdict().reasons)})")
            clip = root / "media" / "takes" / entry.output_file
            if not clip.is_file():  # the accepted bytes cannot be checked: that is a defect, not a pass
                blocks.append(f"{entry.take_id}: the accepted clip is missing (media/takes/{entry.output_file}), its bytes cannot be checked")
            else:
                from film_pipeline.production.takes import sha256_file
                if sha256_file(clip) != entry.output_sha256:
                    blocks.append(f"{entry.take_id}: the clip on disk changed after it was logged")
            prompt_file = plan_dir(root) / "prompts" / f"{gid}.txt"
            if prompt_file.is_file():  # the take was judged against the prompt it was made from; a changed prompt makes it stale
                from film_pipeline.production.takes import sha256_text
                current = sha256_text(prompt_file.read_text(encoding="utf-8").strip())
                if current != entry.prompt_sha256:
                    blocks.append(f"{entry.take_id}: the prompt changed after this take was generated (shot version {decl.version} "
                                  f"is unchanged): retake it or bump the shot version")
    return blocks, pending


# --------------------------------------------------------------------------- gate 6

def _delivery_item(pkg: Any) -> dict[str, Any]:
    raw = pkg.stages.get("delivery") or {}
    item = raw.get("delivery") if isinstance(raw, dict) else None
    return item if isinstance(item, dict) else {}


def master_issues(pkg: Any) -> list[str]:
    from film_pipeline.production import master_qc as mq
    from film_pipeline.production.deliver import MANIFEST, sha256_file, verify_archive
    from film_pipeline.production.lock import picture_lock_issues
    root = Path(pkg.root)
    out: list[str] = []
    qc_path = root / "qc" / "master_qc.json"
    if not qc_path.is_file():
        out.append("no qc/master_qc.json: run film.py mastercheck on the master")
    else:
        record = mq.MasterQc.model_validate_json(qc_path.read_text(encoding="utf-8"))
        if not record.ok:
            out.append("the master QC record has a failing group")
    out += [f"picture lock: {i}" for i in picture_lock_issues(pkg)]
    item = _delivery_item(pkg)
    archive = root / "delivery"
    if not item or not (archive / MANIFEST).is_file():
        out.append("no delivery archive (delivery/MANIFEST.json): run film.py deliver")
        return out
    if item.get("manifest_sha256") != sha256_file(archive / MANIFEST):
        out.append("delivery/MANIFEST.json changed after 07_delivery.json recorded it")
    verified = verify_archive(archive)
    if not verified.get("ok"):
        why = [f"missing {m}" for m in verified.get("missing_files", [])] + [f"hash {m}" for m in verified.get("hash_mismatch", [])]
        why += [p["detail"] for p in verified.get("problems", []) if p.get("severity") == "BLOCK"]
        out.append("the delivery archive does not verify: " + ("; ".join(why[:6]) or verified.get("error", "unknown")))
    archived_qc = archive / "qc" / "master_qc.json"
    if qc_path.is_file() and archived_qc.is_file() and sha256_file(archived_qc) != sha256_file(qc_path):
        out.append("master QC was re-run after the delivery: deliver again so the archive carries the current QC")
    return out


def master_pending(pkg: Any) -> list[str]:
    item = _delivery_item(pkg)
    out: list[str] = []
    if item.get("release_ready") is False:
        out.append("release_ready is false (rights pending or WARN findings): see delivery/MANIFEST.json findings")
    accepted = item.get("owner_acceptance")
    if not accepted or accepted.get("manifest_sha256") != item.get("manifest_sha256") or not str(accepted.get("by", "")).strip():
        out.append("the Owner has not accepted this delivery (film.py deliver --accept NAME, once gates 1-5 pass)")
    return out
