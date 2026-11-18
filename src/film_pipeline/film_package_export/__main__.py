from __future__ import annotations

import argparse
import sys

from . import ExportError, export


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m film_pipeline.film_package_export",
                                 description="Export an AFP film folder as a film_package v1 manifest.")
    ap.add_argument("film_dir")
    ap.add_argument("--out", required=True, help="package.json to write (outside the film folder)")
    ap.add_argument("--picture", default="rough_cut", help="media/cut/<name>.mp4 to hand over (default rough_cut)")
    args = ap.parse_args(argv)
    try:
        package, warnings = export(args.film_dir, args.out, args.picture)
    except ExportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for w in warnings:
        print(f"WARN: {w}", file=sys.stderr)
    clock = package["clock"]
    print(f"OK {args.out}: level {package['audio']['level']}, {len(package.get('timeline', []))} events, "
          f"{len(package.get('dialogue', []))} cues, {len(package['audio'].get('layers', []))} layers, "
          f"{clock['duration_frames']} frames @ {clock['fps_num']}/{clock['fps_den']}, {len(package['files'])} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
