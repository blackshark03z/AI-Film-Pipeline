"""AFP producer-side exporter for the AutoEdit v2 ``film_package`` v1 hand-off.

``python -m film_pipeline.film_package_export <film_dir> --out <package.json> [--picture rough_cut]``

Reads an AFP film folder strictly read-only, maps it onto film_package v1 (see docs/integration/ and the contract's
``film_package.md``), validates the result against the vendored schema and writes the JSON manifest elsewhere.
"""
from __future__ import annotations

from .build import PICTURES, build_package
from .media import ExportError
from .validate import SCHEMA_PATH, validate_package

__all__ = ["PICTURES", "SCHEMA_PATH", "ExportError", "build_package", "validate_package", "export"]


def export(film_dir, out, picture: str = "rough_cut", mix_info: dict | None = None) -> tuple[dict, list[str]]:
    """Build, validate and write the package; refuses to write inside the film folder."""
    import json
    from pathlib import Path

    root, target = Path(film_dir).resolve(), Path(out).resolve()
    if root == target or root in target.parents:
        raise ExportError(f"--out must be outside the film folder (read-only source): {target}")
    package, warnings = build_package(root, picture, mix_info)
    validate_package(package)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return package, warnings
