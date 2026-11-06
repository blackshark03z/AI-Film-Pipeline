"""Generic film CLI over a Production Package (`films/<film_id>/`): new, validate, status."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.production.gates import evaluate_gates, summary  # noqa: E402
from film_pipeline.production.package import (  # noqa: E402
    SCRIPT_FILE, STAGE_FILES, FilmHeader, PackageError, load_package, save_header,
)


def _emit(payload: dict) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def scaffold(film_id: str, profile: str, root: Path, title: str | None) -> Path:
    target = root / film_id
    if (target / "film.json").exists():
        raise PackageError(f"{target} already has a film.json; refusing to overwrite")
    header = FilmHeader(film_id=film_id, title=title or film_id, profile=profile)
    save_header(target, header)
    for name in STAGE_FILES.values():
        (target / name).write_text("{}\n", encoding="utf-8", newline="\n")
    if profile == "drama":
        (target / SCRIPT_FILE).write_text("", encoding="utf-8", newline="\n")
    (target / "media").mkdir(exist_ok=True)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    new = actions.add_parser("new", help="scaffold an empty package")
    new.add_argument("film_id")
    new.add_argument("--profile", required=True, choices=["drama", "narration"])
    new.add_argument("--title")
    new.add_argument("--root", type=Path, default=ROOT / "films", help="directory holding film packages")
    for name, text in (("validate", "evaluate gates; exit 1 if any gate BLOCKs"),
                       ("status", "stages present, gates, counts")):
        sub = actions.add_parser(name, help=text)
        sub.add_argument("--film", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        if args.action == "new":
            target = scaffold(args.film_id, args.profile, args.root, args.title)
            _emit({"created": str(target), "profile": args.profile})
            return 0
        pkg = load_package(args.film)
        results = evaluate_gates(pkg)
        report = summary(results)
        if args.action == "validate":
            _emit(report)
            return 1 if report["blocked"] else 0
        _emit({
            "film_id": pkg.header.film_id,
            "profile": pkg.header.profile,
            "stages_present": sorted(pkg.stages),
            "stages_missing": pkg.missing_stages,
            "stages_empty": sorted(k for k, v in pkg.stages.items() if not v),
            "script_scenes": len(pkg.script.scenes) if pkg.script else None,
            "package_issues": pkg.issues,
            "gates": {r.gate: r.status for r in results},
        })
        return 0
    except PackageError as exc:
        _emit({"error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
