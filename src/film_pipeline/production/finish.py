"""Resume the existing local finishing commands from verified content, never Owner acceptance."""
from __future__ import annotations

import hashlib
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path

from film_pipeline.production import deliver as D
from film_pipeline.production.gates import evaluate_gates
from film_pipeline.production.lock import lock_status
from film_pipeline.production.package import load_package
from film_pipeline.production.runtime import atomic_json, film_writer
from film_pipeline.production import post_engine, preflight

_source_root = Path(__file__).resolve().parents[1]
_code_paths = sorted([*(_source_root / "production").glob("*.py"), *(_source_root / "drama").glob("*.py"),
                      _source_root.parents[1] / "tools/film.py"])
_CODE_SHA = hashlib.sha256(b"".join(p.read_bytes() for p in _code_paths)).hexdigest()


def _hashes(paths) -> dict:
    return {str(p): D.sha256_file(p) for p in sorted(set(paths)) if p.is_file()}


def _work_file(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path if (root / path).is_file() or not path.is_file() else path


def _outputs(root: Path, name: str) -> list[Path]:
    fixed = {"generators": ["generators.json"], "grade": ["color/color.json"],
             "titles": ["titles/titles.json", "titles/credits.json",
                        "media/cut/titled_cut.mp4", "media/cut/titled_cut.cut.json", "media/cut/titled_cut.clean.mp4",
                        "media/cut/titled_cut.clean.cut.json"],
             "mix": ["audio/mix.json", "media/cut/mixed.mp4"], "mastercheck": ["qc/master_qc.json"],
             "versions": ["versions/versions.json", "versions/metadata.json"],
             "dialoguecheck": ["qc/dialogue_stt.json"], "deliver": ["07_delivery.json"]}
    paths = [root / n for n in fixed[name]]
    if name == "titles":
        paths.extend((root / "titles").glob("*.srt"))
    if name == "mix" and (root / "audio/mix.json").is_file():
        for value in json.loads((root / "audio/mix.json").read_text(encoding="utf-8")).get("stems", {}).values():
            if isinstance(value, str):
                p = Path(value)
                paths.append(_work_file(root, value))
    if name == "versions" and (root / "versions/versions.json").is_file():
        report = json.loads((root / "versions/versions.json").read_text(encoding="utf-8"))
        paths.extend(_work_file(root, item["file"]) for item in report["versions"])
        paths.extend((root / "versions/thumbs").glob("*.jpg"))
    if name == "deliver":
        paths.append(D.current_archive(root) / D.MANIFEST)
    return paths


def _fingerprint(root: Path, name: str) -> str:
    files = [root / n for n in ("film.json", "script.fountain", "takes/index.json", "lock/picture.lock.json")]
    files.extend(root.glob("0[1-5]_*.json"))
    dependencies = {
        "generators": [], "grade": ["color/color_plan.json"],
        "titles": ["color/color.json", "generators.json", "titles/portrait_focus.json", "titles/reframe.json", "titles/cues.json"],
        "mix": ["media/cut/titled_cut.mp4", "media/cut/titled_cut.cut.json", "audio/assets.json", "audio/mix_plan.json"],
        "mastercheck": ["media/cut/mixed.mp4", "media/cut/titled_cut.cut.json"],
        "versions": ["media/cut/mixed.mp4", "media/cut/titled_cut.clean.mp4", "media/cut/titled_cut.cut.json",
                     "titles/titles.json", "titles/portrait_focus.json", "generators.json"],
        "dialoguecheck": ["audio/stems/dialogue.wav", "titles/titles.json"],
        "deliver": ["media/cut/mixed.mp4", "media/cut/titled_cut.cut.json", "generators.json"],
    }
    files.extend(root / n for n in dependencies[name])
    if name == "mix":
        files.extend((root / "audio").rglob("*.wav"))
    if name == "deliver":
        files.extend(p for pattern in D.PACKAGE_GLOBS for p in root.glob(pattern))
        files.extend((root / "titles").glob("*.srt"))
        if (root / "versions/versions.json").is_file():
            files.extend(_work_file(root, v["file"]) for v in json.loads((root / "versions/versions.json").read_text(encoding="utf-8"))["versions"])
    payload = {"step": name, "files": _hashes(files), "pipeline_code": _CODE_SHA}
    engine = post_engine.resolve_engine_dir() if name == "mix" else None
    if engine is not None:  # a mix mastered by the engine is not the same output as AFP's own mix
        payload["post_engine"] = {"dir": str(engine), "revision": post_engine.engine_revision(engine)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _fresh(root: Path, name: str, state: dict) -> bool:
    item = state.get(name, {})
    try:
        paths = _outputs(root, name)
        if not paths or any(not p.is_file() for p in paths):
            return False
        if item.get("inputs") != _fingerprint(root, name) or item.get("outputs") != _hashes(paths):
            return False
        return name != "deliver" or D.verify_archive(D.current_archive(root))["ok"]
    except (OSError, ValueError, KeyError):
        return False


def _accepted_unchanged(pkg, gates) -> bool:
    if not all(g.status == "PASS" for g in gates):
        return False
    root, archive = Path(pkg.root), D.current_archive(pkg.root)
    verified = D.verify_archive(archive)
    if not verified["ok"]:
        return False
    manifest = D.ArchiveManifest.model_validate_json((archive / D.MANIFEST).read_text(encoding="utf-8"))
    for item in manifest.files:
        if not item.path.startswith("package/"):
            continue
        rel = item.path.removeprefix("package/")
        # Later learning/qualification reports do not change the delivered picture or its Owner decision.
        if rel.startswith("qc/") and rel != "qc/master_qc.json":
            continue
        current = root / rel
        if not current.is_file() or D.sha256_file(current) != item.sha256:
            return False
    for record, output, field in [(root / "audio/mix.json", root / "media/cut/mixed.mp4", "output_sha256")]:
        if not output.is_file() or json.loads(record.read_text(encoding="utf-8")).get(field) != D.sha256_file(output):
            return False
    for version in json.loads((root / "versions/versions.json").read_text(encoding="utf-8"))["versions"]:
        path = _work_file(root, version["file"])
        if not path.is_file() or D.sha256_file(path) != version["sha256"]:
            return False
    return True


@film_writer()
def finish(pkg, *, command, dry_run: bool = False) -> dict:
    root = Path(pkg.root).resolve()
    gates = evaluate_gates(pkg)
    blocked = [f"gate {g.gate}: {g.status}" for g in gates if g.gate in "1234" and g.status != "PASS"]
    picture = lock_status(pkg)
    if not picture.get("locked") or not picture.get("fresh"):
        blocked.append("finish requires a fresh locked EDL")
    if blocked:
        return {"ok": False, "blocked": blocked, "steps": [], "dry_run": dry_run}
    if _accepted_unchanged(pkg, gates):
        return {"ok": True, "dry_run": dry_run, "reused": True, "steps": [],
                "archive": str(D.current_archive(root)), "owner_acceptance_preserved": True}
    env = preflight.check(root)
    state_path = root / "media/finish-state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
    except ValueError:
        state = {}
    generators = ["--generators-file", str(root / "generators.json")]
    steps = [("generators", ["generators", "--init"])] if not (root / "generators.json").is_file() else []
    engine = post_engine.resolve_engine_dir()
    mix_argv = ["mix", "--cut", str(root / "media/cut/titled_cut.mp4"), "--stems", str(root / "audio/stems")]
    if engine is not None:
        mix_argv += ["--engine", str(engine)]
    steps += [("grade", ["grade"]), ("titles", ["titles", "--render", "--color", "--clean-copy", *generators]),
              ("mix", mix_argv),
              ("mastercheck", ["mastercheck", "--cut-report", str(root / "media/cut/titled_cut.cut.json")]),
              ("versions", ["versions", "--cut-report", str(root / "media/cut/titled_cut.cut.json"), *generators]),
              ("dialoguecheck", ["dialoguecheck"]),
              ("deliver", ["deliver", "--cut-report", str(root / "media/cut/titled_cut.cut.json"), *generators])]
    planned = [{"step": name, "run": not _fresh(root, name, state)} for name, _ in steps]
    if dry_run:
        return {"ok": env["ok"], "dry_run": True, "steps": planned, "environment": env}
    if not env["ok"]:
        return {"ok": False, "blocked": env["issues"], "steps": planned, "environment": env}
    results, dirty = [], False
    old_stt = os.environ.get("AFP_STT_PYTHON")
    try:
        if env["stt_python"]:
            os.environ["AFP_STT_PYTHON"] = env["stt_python"]
        for name, argv in steps:
            if not dirty and _fresh(root, name, state):
                results.append({"step": name, "reused": True})
                continue
            dirty = True
            stream = io.StringIO()
            with redirect_stdout(stream):
                code = command([argv[0], "--film", str(root), *argv[1:]])
            try:
                result = json.loads(stream.getvalue())
            except ValueError:
                result = {"error": stream.getvalue()[-500:] or "no command result"}
            if code:
                return {"ok": False, "steps": results, "failed_step": name, "exit_code": code, "result": result}
            outputs = _outputs(root, name)
            if any(not p.is_file() for p in outputs):
                return {"ok": False, "steps": results, "failed_step": name, "error": "command left missing outputs"}
            state[name] = {"inputs": _fingerprint(root, name), "outputs": _hashes(outputs)}
            atomic_json(state_path, state)
            results.append({"step": name, "reused": False})
    finally:
        if old_stt is None:
            os.environ.pop("AFP_STT_PYTHON", None)
        else:
            os.environ["AFP_STT_PYTHON"] = old_stt
    verified = D.verify_archive(D.current_archive(root))
    return {"ok": verified["ok"], "steps": results, "archive": str(D.current_archive(root)),
            "release_ready": verified["release_ready"], "owner_acceptance_written": False,
            "environment": env}
