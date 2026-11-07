"""Delivery archive and restore check (categories 56 legal clearance, 87 data management, 151 packaging, 153 platform compliance).

``deliver`` gathers everything a release needs into ``<film>/delivery/`` and refuses to call it complete when a compliance
check fails. Nothing is published or uploaded.

* ``masters/`` - the 16:9 master and the 9:16 version, each stream-copied with the AI-disclosure tags (``drama.disclosure``),
  optionally C2PA-signed, each with its ``disclosure*.json`` whose ``content_sha256`` is the hash of the delivered file.
* ``sidecars/`` SRTs, ``thumbs/``, ``metadata.json``, ``qc/`` (master QC record and the cut report), ``rights/rights.json``
  (the pre-production rights ledger, the sound asset ledger and the attributions owed).
* ``package/`` - the package JSON, script, take log, reviews, colour/titles/mix/lock records, so the film can be read
  without the working tree. The take clips themselves are not copied (they are large): ``external_dependencies`` lists each
  one the EDL uses with its hash and whether it was on disk, so a restore says exactly what a re-render would need.
* ``MANIFEST.json`` - every file with size and sha256, the dependencies, the picture-lock state and the findings.

BLOCK findings (the disclosure fails ``check_release``, no AI label burned into the opening title, master QC missing / stale /
failing, the 9:16 version missing, C2PA requested and failing) stop the delivery: nothing replaces an earlier ``delivery/``.
WARN findings (picture not locked, rights not cleared) are recorded and make ``release_ready`` false. A delivery that
replaces another moves the old one to ``delivery.superseded-<UTC stamp>/``; it is never deleted.

``verify_archive`` is the restore check (``film.py status --package``): hashes of every listed file, unlisted files, the
package loading from ``package/``, the disclosure of each master, and the dependencies the archive does not hold.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import Field

from film_pipeline.core import ContractModel

LABEL_WORD = re.compile(r"\bAI\b")
BODY_LABEL = "AI-generated"  # the small bottom-left label drama.post.assemble burns over the body (film.json disclosure.ai_label)
MANIFEST = "MANIFEST.json"
PACKAGE_GLOBS = ("film.json", "script.fountain", "0[1-6]_*.json", "takes/*.json", "color/*.json", "titles/*.json",
                 "audio/*.json", "lock/*.json", "lock/history/*.json", "qc/*.json", "versions/*.json")
HUMAN_CONTRIBUTION = ["Story, direction, take selection and editing of the generated material"]
JURISDICTION = ["EU AI Act Art. 50 (applies from 2026-08-02): visible label and machine-readable marking"]


class FileEntry(ContractModel):
    path: str
    size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    role: str


class Dependency(ContractModel):
    path: str  # relative to the film root
    sha256: str
    kind: str = "take"
    present_at_delivery: bool


class ArchiveManifest(ContractModel):
    film_id: str
    title: str
    created: str
    release_ready: bool
    picture_lock: dict[str, Any] = Field(default_factory=dict)
    masters: dict[str, str] = Field(default_factory=dict)  # name -> path inside the archive
    files: list[FileEntry] = Field(default_factory=list)
    external_dependencies: list[Dependency] = Field(default_factory=list)
    findings: list[dict[str, Any]] = Field(default_factory=list)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _finding(code: str, severity: str, detail: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "detail": detail}


# ------------------------------------------------------------------ disclosure

def split_generators(text: str) -> list[Any]:
    """'Google Flow Omni 1.1 Flash; Other Tool 2' -> role-less GeneratorRecords (first word is the provider)."""
    from film_pipeline.production.generators import split_generators as split
    return split(text)


def visible_label(section: Any) -> Any:
    """The AI label the opening title card really carries: the first title line that names AI, else an empty label."""
    from film_pipeline.drama.disclosure import VisibleLabel
    for line in section.title:
        if LABEL_WORD.search(line.text):
            return VisibleLabel(text=line.text, start_s=0.0, duration_s=float(section.title_s))
    return VisibleLabel(text="", start_s=0.0, duration_s=0.0)


def build_disclosure(pkg: Any, section: Any, generators: Any) -> Any:
    """`generators` is the `--generators` text or the records of a `--generators-file`."""
    from film_pipeline.drama.disclosure import Disclosure
    from film_pipeline.production import titles as ti
    from film_pipeline.production.generators import as_records
    label = visible_label(section)
    if pkg.header.disclosure.ai_label == "always":  # the opening card names AI and a small label stays on for the whole body
        label = label.model_copy(update={"watermark_text": BODY_LABEL, "watermark_always_on": True})
    return Disclosure(film_id=pkg.header.film_id, title=pkg.header.title, created=date.today().isoformat(),
                      generators=as_records(generators), post_tools=["ffmpeg"],
                      synthetic_persons=bool(ti.cast_names(pkg)), human_contribution=HUMAN_CONTRIBUTION,
                      visible_label=label, jurisdiction_notes=JURISDICTION)


def label_evidence(master: Path, title_s: float, end_s: float, *, samples: int = 5, min_contrast: float = 25.0) -> dict[str, Any]:
    """Look for the burned-in body label in sampled frames of the 16:9 master.

    At each sample the label's glyph pixels (as `drama.post.ai_label_png` draws them) are compared with the ring around them;
    the same comparison 400 px to the right is the control. A frame counts when the glyphs stand out by `min_contrast` luma
    levels more than the control does. The label is present when 60 % of the sampled frames count."""
    import subprocess
    import tempfile
    from PIL import Image, ImageFilter
    from film_pipeline.drama.post import H, W, ai_label_png, probe_video_duration
    total = probe_video_duration(master)
    lo, hi = title_s + 0.3, total - end_s - 0.3
    if hi <= lo:
        return {"checked": 0, "positive": 0, "ok": False, "detail": "the body is too short to sample"}
    times = [lo + (hi - lo) * (i + 0.5) / samples for i in range(samples)]
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        alpha = Image.open(ai_label_png(work / "label.png", BODY_LABEL)).split()[3]
        glyph = alpha.point(lambda v: 255 if v > 100 else 0)
        ring_img = glyph.filter(ImageFilter.MaxFilter(7))
        box = glyph.getbbox()
        if box is None:
            return {"checked": 0, "positive": 0, "ok": False, "detail": "the label renders no pixels"}
        x0, y0, x1, y1 = box[0] - 4, box[1] - 4, box[2] + 4, box[3] + 4
        pixels = [(x, y) for y in range(max(0, y0), min(H, y1)) for x in range(max(0, x0), min(W, x1))]
        on = [p for p in pixels if glyph.getpixel(p)]
        ring = [p for p in pixels if ring_img.getpixel(p) and not glyph.getpixel(p)]
        shift = 400

        def contrast(frame: Any, dx: int) -> float:
            mean = lambda ps: sum(frame.getpixel((x + dx, y)) for x, y in ps) / len(ps)  # noqa: E731
            return mean(on) - mean(ring)

        positive = 0
        for n, t in enumerate(times):
            png = work / f"f{n}.png"
            done = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(master), "-frames:v", "1", str(png)],
                                  capture_output=True, text=True)
            if done.returncode != 0 or not png.is_file():
                raise ValueError(f"could not extract a frame at {t:.1f} s: {done.stderr.strip()[:200]}")
            frame = Image.open(png).convert("L").resize((W, H))
            positive += contrast(frame, 0) - contrast(frame, shift) >= min_contrast
    need = -(-samples * 6 // 10)
    return {"checked": samples, "positive": positive, "ok": positive >= need, "detail": f"{positive} of {samples} sampled frames show the label"}


def mark_master(src: Path, dst: Path, disclosure: Any, disclosure_json: Path, *, c2pa: tuple[Path, Path] | None = None) -> Any:
    """Embed the disclosure tags (stream copy), sign C2PA when asked, and write the record bound to the delivered bytes."""
    from film_pipeline.drama import disclosure as D
    if c2pa is None:
        D.embed_metadata(src, dst, disclosure)
    else:
        tagged = dst.with_name(dst.stem + ".tagged.mp4")
        D.embed_metadata(src, tagged, disclosure)
        try:
            D.sign_c2pa(tagged, dst, disclosure, c2pa[0], c2pa[1])
        finally:
            tagged.unlink(missing_ok=True)
    return D.write_disclosure(disclosure, dst, disclosure_json)


# ------------------------------------------------------------------ gathering

def copy_package(root: Path, out: Path) -> list[str]:
    done: list[str] = []
    for pattern in PACKAGE_GLOBS:
        for src in sorted(Path(root).glob(pattern)):
            if src.is_file():
                dst = out / src.relative_to(root)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
                done.append(str(src.relative_to(root)).replace("\\", "/"))
    return done


def rights_record(pkg: Any) -> tuple[dict[str, Any], list[dict[str, str]]]:
    from film_pipeline.production import sound_rights as sr
    pre = pkg.typed.get("preprod")
    entries = [e.model_dump(mode="json") for e in pre.rights] if pre is not None else []
    from film_pipeline.production.planning import legal
    findings = [_finding("RIGHTS_PENDING", "WARN", text) for text in legal(pkg)["owner_decisions"]]
    for issue in sr.check_assets(pkg)["issues"]:
        findings.append(_finding("SOUND_RIGHTS_OPEN", "WARN", f"{issue['code']} {issue['asset']}: {issue['detail']}"))
    record = {"preprod": entries, "sound_assets": sr.load_ledger(Path(pkg.root)).model_dump(mode="json"),
              "attributions_owed": sr.attributions(pkg)}
    return record, findings


def dependencies(pkg: Any) -> list[Dependency]:
    from film_pipeline.production import takes as T
    section = pkg.typed.get("edit")
    if section is None:
        return []
    log = T.load_log(Path(pkg.root), pkg.header.film_id)
    out = []
    for event in section.events:
        if event.kind == "TAKE":
            try:
                entry = log.get(event.take_id)
            except KeyError:
                continue
            rel = f"media/takes/{entry.output_file}"
            out.append(Dependency(path=rel, sha256=entry.output_sha256, present_at_delivery=(Path(pkg.root) / rel).is_file()))
    return out


def inventory(out: Path) -> list[FileEntry]:
    entries = []
    for path in sorted(p for p in out.rglob("*") if p.is_file() and p.name != MANIFEST):
        rel = path.relative_to(out).as_posix()
        entries.append(FileEntry(path=rel, size=path.stat().st_size, sha256=sha256_file(path), role=rel.split("/", 1)[0]))
    return entries


# ------------------------------------------------------------------ deliver

def deliver(pkg: Any, master: Path, cut_report: Path, *, generators: Any = "", c2pa: tuple[Path, Path] | None = None) -> dict[str, Any]:
    """Build ``delivery/``; returns the report (``ok`` false and nothing replaced when a BLOCK finding stands)."""
    from film_pipeline.drama import disclosure as D
    from film_pipeline.production import master_qc as mq
    from film_pipeline.production import titles as ti
    from film_pipeline.production import versions as vs
    from film_pipeline.production.lock import lock_status
    from film_pipeline.production.mix import stamp_post_item
    root = Path(pkg.root)
    section = pkg.typed.get("edit")
    if section is None:
        raise ValueError("deliver needs a valid 05_edit.json")
    film_id = pkg.header.film_id
    findings: list[dict[str, str]] = []
    master = Path(master)

    # ---- inputs that must exist and agree
    qc_path = root / "qc" / "master_qc.json"
    master_sha = sha256_file(master)
    if not qc_path.is_file():
        findings.append(_finding("QC_MISSING", "BLOCK", "no qc/master_qc.json: run film.py mastercheck on the master"))
    else:
        record = mq.MasterQc.model_validate_json(qc_path.read_text(encoding="utf-8"))
        if record.sha256 != master_sha:
            findings.append(_finding("QC_STALE", "BLOCK", "qc/master_qc.json was made on other bytes than this master: run mastercheck again"))
        elif not record.ok:
            findings.append(_finding("QC_FAILED", "BLOCK", "the master QC record has a failing group"))
    versions_report = vs.versions_dir(root) / "versions.json"
    portrait = None
    if versions_report.is_file():
        vr = json.loads(versions_report.read_text(encoding="utf-8"))
        item = next((v for v in vr["versions"] if v["name"] == "portrait_9x16"), None)
        portrait = root / item["file"] if item else None
        if not vr.get("ok"):
            findings.append(_finding("VERSIONS_FAILED", "BLOCK", "versions/versions.json has a BLOCK finding"))
        elif item and portrait.is_file() and sha256_file(portrait) != item["sha256"]:
            findings.append(_finding("VERSIONS_STALE", "BLOCK", "the 9:16 file changed after film.py versions: run it again"))
    if portrait is None or not portrait.is_file():
        findings.append(_finding("VERSIONS_MISSING", "BLOCK", "no 9:16 version: run film.py versions"))
        portrait = None
    disclosure = build_disclosure(pkg, section, generators)
    if not disclosure.visible_label.text:
        findings.append(_finding("AI_LABEL_MISSING", "BLOCK",
                                 "the opening title card carries no AI label: add a title line naming AI (05_edit.json `title`)"))
    if not disclosure.generators:
        findings.append(_finding("GENERATORS_MISSING", "BLOCK",
                                 "no generator named for the disclosure (--generators or --generators-file)"))
    label_mode = pkg.header.disclosure.ai_label
    label_check: dict[str, Any] = {"mode": label_mode}
    if label_mode == "always":  # the setting promises a label on the whole body: the master has to show it
        try:
            label_check["evidence"] = label_evidence(master, float(section.title_s), float(section.end_s))
        except Exception as exc:  # noqa: BLE001 - an unreadable master is a finding, not a crash
            label_check["evidence"] = {"checked": 0, "positive": 0, "ok": False, "detail": str(exc)[:200]}
        if not label_check["evidence"]["ok"]:
            findings.append(_finding("AI_LABEL_NOT_BURNED", "BLOCK",
                                     f"film.json disclosure.ai_label is 'always' but the master does not show the label over "
                                     f"the body ({label_check['evidence']['detail']}): render with film.py titles --render"))

    # ---- stage the archive
    stage = root / "delivery.staging"
    if stage.exists():
        shutil.rmtree(stage)
    masters: dict[str, str] = {}
    if not any(f["severity"] == "BLOCK" for f in findings):
        marks = {"master_16x9": (master, f"masters/{film_id}_16x9.mp4", "disclosure_16x9.json")}
        if portrait is not None:
            marks["portrait_9x16"] = (portrait, f"masters/{film_id}_9x16.mp4", "disclosure_9x16.json")
        for name, (src, rel, disc) in marks.items():
            dst = stage / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                mark_master(src, dst, disclosure, stage / disc, c2pa=c2pa)
            except Exception as exc:  # noqa: BLE001 - embed / sign failures are findings, not crashes
                findings.append(_finding("C2PA_FAILED" if c2pa else "MARKING_FAILED", "BLOCK", f"{name}: {exc}"))
                continue
            masters[name] = rel
            for problem in D.check_release(dst, stage / disc):
                findings.append(_finding("COMPLIANCE", "BLOCK", f"{name}: {problem}"))
    blocked = any(f["severity"] == "BLOCK" for f in findings)
    status = lock_status(pkg)
    if not (status.get("locked") and status.get("fresh")):
        findings.append(_finding("PICTURE_NOT_LOCKED", "WARN", f"picture is not locked and fresh: {status.get('reason') or 'no lock'}"))
    rights, found = rights_record(pkg)
    findings += found
    if pkg.header.rehearsal:  # a WARN keeps release_ready false and travels in the manifest
        findings.append(_finding("REHEARSAL_SYNTHETIC", "WARN", "REHEARSAL — synthetic: mock footage, no provider, never releasable"))
    if blocked:
        shutil.rmtree(stage, ignore_errors=True)
        return {"film_id": film_id, "ok": False, "release_ready": False, "findings": findings, "archive": None,
                "summary": {"blocks": sum(f["severity"] == "BLOCK" for f in findings), "warnings": sum(f["severity"] == "WARN" for f in findings)}}

    for src in sorted(ti.titles_dir(root).glob("*.srt")):
        (stage / "sidecars").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, stage / "sidecars" / src.name)
    thumbs = vs.versions_dir(root) / "thumbs"
    for src in sorted(thumbs.glob("*.jpg")) if thumbs.is_dir() else []:
        (stage / "thumbs").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, stage / "thumbs" / src.name)
    shutil.copyfile(vs.versions_dir(root) / "metadata.json", stage / "metadata.json")
    (stage / "qc").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(qc_path, stage / "qc" / "master_qc.json")
    if Path(cut_report).is_file():
        shutil.copyfile(cut_report, stage / "qc" / Path(cut_report).name)
    (stage / "rights").mkdir(parents=True, exist_ok=True)
    (stage / "rights" / "rights.json").write_text(json.dumps(rights, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    copied = copy_package(root, stage / "package")
    release_ready = not any(f["severity"] in ("BLOCK", "WARN") for f in findings)
    manifest = ArchiveManifest(film_id=film_id, title=pkg.header.title, created=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               release_ready=release_ready,
                               picture_lock={k: status.get(k) for k in ("locked", "fresh", "lock_edl_sha256", "locked_by") if k in status},
                               masters=masters, files=inventory(stage), external_dependencies=dependencies(pkg), findings=findings)
    (stage / MANIFEST).write_text(json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ---- swap in; an earlier delivery is kept
    final = root / "delivery"
    superseded = None
    if final.exists():
        superseded = root / f"delivery.superseded-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
        final.rename(superseded)
    stage.rename(final)
    manifest_sha = sha256_file(final / MANIFEST)
    stamp_post_item(pkg, "delivery", {"manifest": "delivery/MANIFEST.json", "manifest_sha256": manifest_sha,
                                      "release_ready": release_ready, "files": len(manifest.files)}, filename="07_delivery.json")
    return {"film_id": film_id, "ok": True, "release_ready": release_ready, "archive": "delivery", "manifest_sha256": manifest_sha,
            **({"stamp": "REHEARSAL — synthetic"} if pkg.header.rehearsal else {}),
            "superseded": superseded.name if superseded else None, "package_files": copied, "findings": findings,
            "ai_label": label_check,
            "external_dependencies": {"count": len(manifest.external_dependencies),
                                      "present": sum(d.present_at_delivery for d in manifest.external_dependencies)},
            "summary": {"files": len(manifest.files), "blocks": 0, "warnings": sum(f["severity"] == "WARN" for f in findings)}}


# ------------------------------------------------------------------ Owner acceptance

def accept_delivery(pkg: Any, by: str) -> dict[str, Any]:
    """Record the Owner's acceptance of the *current* archive (bound to its manifest hash; a new ``deliver`` drops it).

    Raises ValueError, writing nothing, unless gates 1-5 PASS, the delivery verifies, and ``release_ready`` is true: an
    acceptance never papers over a missing review, an open rights decision or a stale archive.
    """
    from datetime import datetime, timezone
    from film_pipeline.production import gate_checks
    from film_pipeline.production.gates import evaluate_gates
    if not by.strip():
        raise ValueError("an acceptance needs the name of the person who accepts")
    root = Path(pkg.root)
    if pkg.header.rehearsal:
        raise ValueError("cannot accept: this is a rehearsal package (REHEARSAL — synthetic); it is never releasable")
    from film_pipeline.production.rehearsal import refuse_bot
    refuse_bot(root, by)
    not_pass = [f"gate {r.gate} {r.name} is {r.status}: {r.issues[0] if r.issues else ''}"
                for r in evaluate_gates(pkg) if r.gate in "12345" and r.status != "PASS"]
    refusals = not_pass + gate_checks.master_issues(pkg)
    item = gate_checks._delivery_item(pkg)
    if not refusals and item.get("release_ready") is not True:
        refusals.append("release_ready is false: resolve the WARN findings (rights, picture lock) and deliver again")
    if refusals:
        raise ValueError("cannot accept: " + "; ".join(refusals[:6]))
    path = root / "07_delivery.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["delivery"]["owner_acceptance"] = {"by": by.strip(), "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                            "manifest_sha256": item["manifest_sha256"]}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"accepted_by": by.strip(), "manifest_sha256": item["manifest_sha256"]}


# ------------------------------------------------------------------ restore check

def verify_archive(archive: Path) -> dict[str, Any]:
    """Check a delivery directory wherever it was copied to. ``ok`` = every listed file present with its hash, the package
    loads, every master's disclosure passes ``check_release``."""
    from film_pipeline.drama import disclosure as D
    from film_pipeline.production.package import PackageError, load_package
    archive = Path(archive)
    path = archive / MANIFEST
    if not path.is_file():
        return {"ok": False, "error": f"{MANIFEST} not found in {archive}"}
    manifest = ArchiveManifest.model_validate_json(path.read_text(encoding="utf-8"))
    missing, mismatched = [], []
    for entry in manifest.files:
        file = archive / entry.path
        if not file.is_file():
            missing.append(entry.path)
        elif file.stat().st_size != entry.size or sha256_file(file) != entry.sha256:
            mismatched.append(entry.path)
    listed = {e.path for e in manifest.files} | {MANIFEST}
    unlisted = sorted(p.relative_to(archive).as_posix() for p in archive.rglob("*") if p.is_file()
                      and p.relative_to(archive).as_posix() not in listed)
    problems: list[dict[str, str]] = []
    package_info: dict[str, Any] = {"loaded": False}
    if (archive / "package" / "film.json").is_file():
        try:
            pkg = load_package(archive / "package")
            package_info = {"loaded": True, "film_id": pkg.header.film_id, "missing_stages": pkg.missing_stages, "issues": pkg.issues}
            if pkg.header.film_id != manifest.film_id:
                problems.append(_finding("PACKAGE_MISMATCH", "BLOCK", "package/film.json is another film than the manifest"))
        except PackageError as exc:
            problems.append(_finding("PACKAGE_UNREADABLE", "BLOCK", str(exc)))
    else:
        problems.append(_finding("PACKAGE_MISSING", "BLOCK", "package/film.json is not in the archive"))
    release: dict[str, list[str]] = {}
    for name, rel in manifest.masters.items():
        disc = archive / ("disclosure_16x9.json" if name == "master_16x9" else "disclosure_9x16.json")
        release[name] = D.check_release(archive / rel, disc) if (archive / rel).is_file() else [f"release file missing: {rel}"]
    for name, found in release.items():
        problems += [_finding("COMPLIANCE", "BLOCK", f"{name}: {p}") for p in found]
    absent = [d.model_dump(mode="json") for d in manifest.external_dependencies]
    ok = not (missing or mismatched) and not any(p["severity"] == "BLOCK" for p in problems)
    return {"ok": ok, "film_id": manifest.film_id, "release_ready": manifest.release_ready, "files": len(manifest.files),
            "missing_files": missing, "hash_mismatch": mismatched, "unlisted_files": unlisted, "package": package_info,
            "problems": problems,
            "missing_dependencies": absent,
            "note": "take clips are not archived: the masters restore as they are; re-rendering needs the listed dependencies by hash"}
