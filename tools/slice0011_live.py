"""Bounded SLICE-0011 live Flow operations. Each command is one deliberate step.

The cookie export is read from an explicit local path and is never printed.
Never rerun a failed upload or shot command as a retry: the durable stores gate it.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from film_pipeline.providers.flow_reference_rpc import FlowReferenceRpcSession
from film_pipeline.slice0011 import (
    ACCOUNT_ID, PROJECT_ID, compile_character_paths, freeze_reference, freeze_shot_job,
    submit_and_acquire_shot, reconcile_and_acquire_shot,
    upload_reference_once, _existing_job_for_shot,
)
from film_pipeline.providers.flow_reference_upload import ReferenceUploadStore
from film_pipeline.store import SQLiteStore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("preflight", "upload", "shot-a", "shot-b",
                                          "recover-a", "recover-b"))
    parser.add_argument("--cookie", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("projects/character_continuity/slice0011"))
    args = parser.parse_args()
    root = args.root.resolve()
    db_path = root / "runtime.sqlite"
    reference = freeze_reference(db_path, root / "reference")
    _, profile, paths = compile_character_paths(db_path)
    with FlowReferenceRpcSession(cookie_path=args.cookie, project_id=PROJECT_ID) as session:
        records = session.catalog()
        print(json.dumps({"stage": "preflight", "catalog_records": len(records),
            "fingerprint": session.catalog_fingerprint, "profile": profile.profile_version}), flush=True)
        if args.stage == "preflight":
            return 0
        if args.stage == "upload":
            receipt = upload_reference_once(db_path, session, reference)
            print(json.dumps({"stage": "upload", "reference_sha256": reference.sha256,
                "provider_media_id": receipt["media_id"],
                "upload_attempts": receipt["upload_attempts"]}), flush=True)
            return 0
        receipt = ReferenceUploadStore(db_path).read_verified(
            "flow_veo", PROJECT_ID, ACCOUNT_ID, reference)
        if receipt is None:
            raise ValueError("verified reference upload required before shot")
        index = 0 if args.stage.endswith("-a") else 1
        job = (_existing_job_for_shot(SQLiteStore(db_path), paths[index][0].shot_id)
               if args.stage.startswith("recover-") else
               freeze_shot_job(db_path, session, paths[index], receipt))
        if job is None:
            raise ValueError("no existing shot to reconcile")
        print(json.dumps({"stage": "job_frozen", "shot": paths[index][0].shot_id,
            "attempt": job.generation_attempt_id, "job": job.provider_job_id,
            "dispatch_count": job.dispatch_count}), flush=True)
        last_update = 0.0

        def progress(**values):
            nonlocal last_update
            if time.monotonic() - last_update >= 30:
                print(json.dumps({"stage": "waiting_exact_output", **values}), flush=True)
                last_update = time.monotonic()

        asset = (reconcile_and_acquire_shot(db_path, session, job, root / "videos")
                 if args.stage.startswith("recover-") else
                 submit_and_acquire_shot(db_path, session, job,
                     root / "videos", progress=progress))
        print(json.dumps({"stage": "asset_acquired", "shot": paths[index][0].shot_id,
            "asset_id": asset.asset_id, "sha256": asset.sha256,
            "path": asset.uri_or_path, "duration_s": asset.duration_s,
            "width": asset.width, "height": asset.height}), flush=True)
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # Never print exception chains from the authenticated browser runtime.
        print(json.dumps({"stage": "stopped", "type": type(exc).__name__,
                          "reason": str(exc)[:180]}), flush=True)
        sys.exit(1)
