"""Opt-in delegation of the final audio mix/master to the external AutoEdit v2 post engine.

The engine is a separate project that is only ever run as a subprocess (``uv run --project <dir> post-engine render``);
nothing from it is imported. AFP exports a film_package (picture = the titled cut, stems = the ones ``build_stems``
just wrote) into a temp dir outside the film folder, the engine renders into another one, and only a passing
``final.mp4`` is copied atomically to the mixed master. Default AFP behaviour is unchanged when no engine is set.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

ENV_VAR = "AFP_POST_ENGINE_DIR"
ENGINE_TIMEOUT_S = 1800


def resolve_engine_dir(option: str | Path | None = None, env: dict[str, str] | None = None) -> Path | None:
    """The engine directory when delegation is on: the ``--engine`` option wins over ``AFP_POST_ENGINE_DIR``."""
    if option is not None and str(option).strip():
        return Path(option)
    value = (os.environ if env is None else env).get(ENV_VAR, "").strip()
    return Path(value) if value else None


def engine_command(engine_dir: Path, package: Path, out_dir: Path) -> list[str]:
    return ["uv", "run", "--project", str(engine_dir), "post-engine", "render", str(package), "--out", str(out_dir)]


def engine_revision(engine_dir: Path) -> str:
    try:
        done = subprocess.run(["git", "-C", str(engine_dir), "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=False)
    except OSError:
        return "unknown"
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else "unknown"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def picture_name(root: Path, cut: Path, stems_dir: Path) -> str:
    """``titled_cut`` for ``<root>/media/cut/titled_cut.mp4``; the exporter only reads that layout."""
    from film_pipeline.film_package_export import PICTURES
    root, cut = Path(root).resolve(), Path(cut).resolve()
    if cut.parent != root / "media" / "cut" or cut.suffix != ".mp4" or cut.stem not in PICTURES:
        raise ValueError(f"engine mix needs the cut under {root / 'media' / 'cut'} as one of "
                         f"{sorted(PICTURES)}.mp4, got {cut}")
    if Path(stems_dir).resolve() != root / "audio" / "stems":
        raise ValueError(f"engine mix needs the stems in {root / 'audio' / 'stems'}, got {stems_dir}")
    return cut.stem


def mix_info_from(built: dict[str, Any]) -> dict[str, Any]:
    """The part of audio/mix.json the exporter reads, from the stems just built (not from a stale file)."""
    return {"ambience": built["ambience"], "sfx": [row for row in built["sfx"] if row.get("asset")],
            "plan": {"music": built["music"]}}


def failed_checks(report: dict[str, Any]) -> list[str]:
    checks = (report.get("measurements") or {}).get("checks") or {}
    return sorted(name for name, ok in checks.items() if not ok)


def _read_report(folder: Path) -> dict[str, Any]:
    path = folder / "render_report.json"
    if not path.is_file():
        raise ValueError(f"post engine wrote no render_report.json in {folder}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"post engine render_report.json is not valid JSON: {exc}") from exc


def run_engine(engine_dir: Path, package: Path, out_dir: Path) -> tuple[Path, dict[str, Any]]:
    """Run the engine; returns (final.mp4, report). Raises ValueError unless exit 0, passed and the output exists."""
    command = engine_command(engine_dir, package, out_dir)
    try:
        done = subprocess.run(command, capture_output=True, text=True, check=False, timeout=ENGINE_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"post engine could not run: {exc}") from exc
    if done.returncode != 0:
        tail = (done.stderr or done.stdout or "").strip()[-500:]
        raise ValueError(f"post engine exit {done.returncode}: {tail}")
    out_dir = Path(out_dir)
    film_dirs = [p for p in out_dir.iterdir() if p.is_dir()] if out_dir.is_dir() else []
    if len(film_dirs) != 1:
        raise ValueError(f"post engine output: expected one film folder in {out_dir}, found {len(film_dirs)}")
    report = _read_report(film_dirs[0])
    if report.get("passed") is not True:
        failed = failed_checks(report)
        raise ValueError("post engine report passed=false" + (f"; failed checks: {', '.join(failed)}" if failed else ""))
    final = film_dirs[0] / "final.mp4"
    if not final.is_file():
        raise ValueError(f"post engine left no final.mp4 in {film_dirs[0]}")
    return final, report


def copy_atomic(source: Path, target: Path) -> None:
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
    os.close(fd)
    try:
        shutil.copyfile(source, name)
        os.replace(name, target)
    finally:
        Path(name).unlink(missing_ok=True)


def mix_via_engine(engine_dir: Path, root: Path, cut: Path, out: Path, stems_dir: Path,
                   built: dict[str, Any]) -> dict[str, Any]:
    """Export the package, render with the engine, copy ``final.mp4`` to ``out``; returns the ``engine`` section."""
    from film_pipeline.film_package_export import ExportError, export
    engine_dir = Path(engine_dir)
    picture = picture_name(root, cut, stems_dir)
    with tempfile.TemporaryDirectory(prefix="afp_pkg_") as pkg_tmp, \
            tempfile.TemporaryDirectory(prefix="afp_engine_") as out_tmp:
        package_path = Path(pkg_tmp) / "film_package.json"
        try:
            export(root, package_path, picture, mix_info_from(built))
        except ExportError as exc:
            raise ValueError(f"film_package export failed: {exc}") from exc
        final, report = run_engine(engine_dir, package_path, Path(out_tmp))
        copy_atomic(final, out)
        package_sha = _sha256(package_path)
    leveling = {"dialogue_leveling": report["dialogue_leveling"]} if "dialogue_leveling" in report else {}
    return {"dir": str(engine_dir), "revision": engine_revision(engine_dir), "package_sha256": package_sha,
            "report": {"passed": report["passed"], "measurements": report.get("measurements", {}), **leveling}}
