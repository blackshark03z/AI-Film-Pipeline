"""Real approved-take to EditManifest and local rough-cut entrypoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .editorial import EditClip, EditorialStore, make_edit_manifest
from .live_runtime import Asset
from .qc import SelectedTake
from .rough_cut import persist_render, read_render, render_sources
from .store import SQLiteStore


def real_rough_cut(db_path: Path, *, project_id: str, selected_take_id: str | None = None,
                   selected_take_ids: list[str] | None = None,
                   output_dir: Path) -> dict:
    ids = selected_take_ids if selected_take_ids is not None else [selected_take_id]
    if not ids or any(not item for item in ids) or len(set(ids)) != len(ids):
        raise ValueError("ordered distinct SelectedTake IDs required")
    runtime = SQLiteStore(db_path)
    connection = runtime._connect()
    clips = []
    asset_ids = []
    try:
        for order, selected_id in enumerate(ids, 1):
            row = connection.execute("SELECT asset_id,payload FROM selected_takes WHERE id=?",
                                     (selected_id,)).fetchone()
            if row is None:
                raise ValueError("approved SelectedTake not found")
            take = SelectedTake.model_validate(json.loads(row[1]))
            asset_row = connection.execute("SELECT payload FROM assets WHERE id=?", (row[0],)).fetchone()
            if asset_row is None:
                raise ValueError("SelectedTake Asset not found")
            asset = Asset.model_validate(json.loads(asset_row[0]))
            if take.asset_id != asset.asset_id or not asset.duration_s:
                raise ValueError("SelectedTake Asset mismatch")
            clips.append(EditClip(order=order, shot_id=take.shot_id,
                selected_take_id=take.selected_take_id, asset_id=asset.asset_id,
                source_in_s=0.0, source_out_s=None, target_duration_s=asset.duration_s))
            asset_ids.append(asset.asset_id)
    finally:
        connection.close()
    manifest = make_edit_manifest(project_id, clips)
    editorial = EditorialStore(runtime)
    editorial.save_manifest(manifest)
    fresh_manifest, sources = EditorialStore(SQLiteStore(db_path)).read_manifest(manifest.edit_manifest_id)
    if fresh_manifest != manifest or len(sources) != len(ids):
        raise ValueError("EditManifest fresh readback mismatch")
    output = output_dir / f"rough_cut_{manifest.edit_manifest_id}.mp4"
    connection = runtime._connect()
    try:
        existing = connection.execute("SELECT id FROM rough_cut_renders WHERE manifest_id=?",
                                      (manifest.edit_manifest_id,)).fetchall()
    finally:
        connection.close()
    if existing:
        if len(existing) != 1:
            raise ValueError("multiple rough-cut receipts for manifest")
        record, read_manifest, read_sources = read_render(EditorialStore(SQLiteStore(db_path)),
                                                         existing[0][0])
    else:
        record = render_sources(manifest, sources, output)
        persist_render(editorial, record)
        record, read_manifest, read_sources = read_render(EditorialStore(SQLiteStore(db_path)),
                                                         record.render_id)
    if read_manifest != manifest or read_sources != sources or \
            record.source_asset_ids != asset_ids or \
            record.selected_take_ids != ids:
        raise ValueError("rough-cut fresh lineage mismatch")
    return {"project_id": project_id, "manifest_id": manifest.edit_manifest_id,
            "clip_count": len(manifest.clips), "selected_take_ids": record.selected_take_ids,
            "render_id": record.render_id, "output_path": record.output_path,
            "output_sha256": record.output_sha256, "duration_s": record.duration_s,
            "width": record.width, "height": record.height,
            "video_codec": record.video_codec, "audio_codec": record.audio_codec,
            "audio_policy": record.audio_policy, "render_method": record.render_method,
            "full_decode": record.full_decode, "ffmpeg_version": record.ffmpeg_version,
            "fresh_readback": True}


def main() -> None:
    parser = argparse.ArgumentParser(description="Approved SelectedTake to local rough cut")
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--selected-take-id", required=True, action="append",
                        help="Repeat in the desired clip order")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(real_rough_cut(args.db, project_id=args.project_id,
                                    selected_take_ids=args.selected_take_id,
                                    output_dir=args.output_dir),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
