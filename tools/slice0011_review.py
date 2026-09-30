"""Local-only reference/A/B review packet. Never approves or selects a take."""
from __future__ import annotations

import html
import io
import json
import os
import hashlib
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageDraw

from film_pipeline.core import canonical_json
from film_pipeline.live_runtime import file_sha256
from film_pipeline.qc import QCStore, evidence, technical_evidence
from film_pipeline.qc_media import make_review_media
from film_pipeline.qc_runner import exact_lineage
from film_pipeline.reference_qualification import require_production_reference, FROZEN_MEDIA_ID, SLICE_ROOT
from film_pipeline.slice0011 import REFERENCE_ASSET_ID, _existing_job_for_shot
from film_pipeline.store import SQLiteStore

CRITERIA = {
    'visual': (
        ('face_geometry_age_skin', 'Reference face geometry, adult age and skin appearance preserved?'),
        ('hair_silhouette_body', 'Teal bob, silhouette and body proportions preserved?'),
        ('wardrobe_accessories', 'Mustard jacket, blue shirt, crimson glasses, triangle earrings and beauty mark preserved?'),
        ('unexplained_mutations', 'One person; no identity, wardrobe or accessory mutation throughout?')),
    'continuity': (
        ('reference_character_identity', 'Same reference character in both shots throughout?'),
        ('screen_direction_eyeline', 'Frame-right direction and A-to-B gaze shift remain plausible?'),
        ('look_state', 'ID_V1 and LOOK_V1 remain stable across reference, A and B?')),
    'editorial': (
        ('editorial_plausibility', 'MCU-to-CU change and calm action provide a usable two-shot sequence?'),),
}


def build_packet():
    recovered = require_production_reference()
    database, output = SLICE_ROOT / 'runtime.sqlite', SLICE_ROOT / 'character_review'
    output.mkdir(parents=True, exist_ok=True)
    store = SQLiteStore(database)
    reference = store.read_reference_asset(REFERENCE_ASSET_ID)
    if file_sha256(Path(reference.uri_or_path)) != reference.sha256:
        raise ValueError('frozen review reference changed')
    entries = []
    for shot_id in ('CHAR_CONTINUITY_A', 'CHAR_CONTINUITY_B'):
        job = _existing_job_for_shot(store, shot_id)
        if job is None or job.correlation_evidence['reference_binding']['media_id'] != FROZEN_MEDIA_ID:
            raise ValueError('both exact reference-grounded jobs required')
        _, _, _, _, _, assets = store.read_runtime_lineage(job.generation_attempt_id, job.provider_job_id)
        if len(assets) != 1:
            raise ValueError('exactly one acquired Asset per shot required')
        _, shot, asset = exact_lineage(database, job.generation_attempt_id, job.provider_job_id, assets[0].asset_id)
        technical, metadata = technical_evidence(shot, asset)
        if not metadata or any(e.verdict != 'pass' for e in technical):
            (output / f'{shot_id}_technical_failure.json').write_text(canonical_json(technical), encoding='utf-8')
            raise ValueError('technical QC failed; Owner review packet withheld')
        entries.append({'shot': shot, 'asset': asset, 'job': job, 'technical': technical})
    # Both clips pass deterministic technical checks before subjective media/QC.
    for entry in entries:
        rows, media = make_review_media(entry['asset'], output / entry['shot'].shot_id, criteria=CRITERIA)
        entry.update(rows=rows, media=media)
        # Preserve a full-resolution middle frame for face/accessory inspection.
        handle, name = tempfile.mkstemp(suffix='.png', dir=output)
        os.close(handle)
        staging = Path(name)
        try:
            completed = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss',
                str(entry['asset'].duration_s / 2), '-i', entry['asset'].uri_or_path,
                '-frames:v', '1', str(staging)], capture_output=True, timeout=60)
            if completed.returncode or not staging.stat().st_size:
                raise ValueError('full-resolution review frame unavailable')
            final = output / f"{entry['shot'].shot_id}_middle_{file_sha256(staging)}.png"
            try:
                os.link(staging, final)
            except FileExistsError:
                if file_sha256(final) != file_sha256(staging):
                    raise ValueError('review frame collision')
            entry['middle_frame'] = {'path': str(final), 'sha256': file_sha256(final)}
        finally:
            staging.unlink(missing_ok=True)
    sheet = Image.new('RGB', (1920, 860), '#151a24')
    draw = ImageDraw.Draw(sheet)
    for index, (label, path) in enumerate([
            ('REFERENCE', reference.uri_or_path),
            ('SHOT A - 4.0s', entries[0]['middle_frame']['path']),
            ('SHOT B - 4.0s', entries[1]['middle_frame']['path'])]):
        draw.text((index * 640 + 12, 12), label, fill='white')
        with Image.open(path) as image:
            sheet.paste(image.convert('RGB').resize((640, 360), Image.Resampling.LANCZOS), (index * 640, 40))
    for index, entry in enumerate(entries):
        y = 415 + index * 222
        draw.text((12, y), entry['shot'].shot_id + ' / 0.2s, 2s, 4s, 6s, 7.8s', fill='white')
        with Image.open(entry['media']['contact_sheet']['path']) as image:
            sheet.paste(image.convert('RGB').resize((1600, 180)), (160, y + 25))
    data = io.BytesIO()
    sheet.save(data, 'PNG')
    digest = hashlib.sha256(data.getvalue()).hexdigest()
    sheet_path = output / f'reference_A_B_{digest}.png'
    if sheet_path.exists() and sheet_path.read_bytes() != data.getvalue():
        raise ValueError('review sheet collision')
    sheet_path.write_bytes(data.getvalue())
    artifacts = [{'path': reference.uri_or_path, 'sha256': reference.sha256},
                 {'path': str(sheet_path), 'sha256': digest},
                 *[{'path': e['asset'].uri_or_path, 'sha256': e['asset'].sha256} for e in entries],
                 *[e['middle_frame'] for e in entries]]
    summaries = []
    for entry in entries:
        asset = entry['asset']
        pair = evidence(asset=asset, evaluator_type='ffmpeg', evaluator_version='character-review-v1',
            gate='continuity', criterion='reference_A_B_comparison', verdict='uncertain',
            observation='Owner must compare exact reference/A/B; sampled frames cannot prove all-frame character identity.',
            source_artifacts=artifacts)
        record, disposition = QCStore(store).save(asset, entry['technical'] + entry['rows'] + [pair])
        fresh, fresh_disposition = QCStore(SQLiteStore(database)).read(asset, record.report['qc_report_id'])
        if (fresh != record or disposition is not None or fresh_disposition is not None
                or record.report['decision'] != 'needs_human_review' or record.human_decision_id is not None):
            raise ValueError('review must remain pending without take selection')
        summaries.append({'shot_id': entry['shot'].shot_id, 'asset_id': asset.asset_id, 'sha256': asset.sha256,
            'video_path': asset.uri_or_path, 'attempt_id': asset.source_attempt_id, 'job_id': asset.provider_job_id,
            'report_id': record.report['qc_report_id'], 'technical_pass': True, 'decision': record.report['decision'],
            'middle_frame': entry['middle_frame']})

    def link(path):
        return html.escape(quote(os.path.relpath(path, output).replace('\\', '/'), safe='/:._-'))

    cards = f'<section><h2>Ảnh tham chiếu</h2><img src="{link(reference.uri_or_path)}"></section>'
    for item in summaries:
        cards += (f'<section><h2>{item["shot_id"]}</h2><video controls preload="metadata" src="{link(item["video_path"])}"></video>'
                  f'<p><a style="color:#93c5fd" href="{link(item["middle_frame"]["path"])}">Mở ảnh giữa clip ở độ phân giải gốc</a></p>'
                  f'<p>Technical QC: PASS · 8 giây · SHA256 <code>{item["sha256"]}</code></p></section>')
    checks = ''.join(f'<li>{html.escape(question)}</li>' for group in CRITERIA.values() for _, question in group)
    page = ('<!doctype html><meta charset="utf-8"><title>SLICE-0011 — Character review</title>'
        '<style>body{background:#111827;color:#e5e7eb;font:17px system-ui;max-width:1500px;margin:36px auto;padding:20px}'
        'h1,h2{color:white}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}section{background:#1f2937;padding:16px;border-radius:12px}'
        'img,video{width:100%;height:auto}code{overflow-wrap:anywhere;font-size:12px}li{margin:10px 0}.gate{padding:20px;background:#374151;border-radius:12px}</style>'
        '<h1>SLICE-0011 — Duyệt nhân vật xuyên hai shot</h1><p>So sánh ảnh gốc ↔ A, ảnh gốc ↔ B, A ↔ B. Xem cả hai clip đầy đủ.</p>'
        f'<div class="cards">{cards}</div><h2>Ảnh so sánh và các mốc thời gian</h2><img src="{link(sheet_path)}">'
        f'<h2>Các tiêu chí cần duyệt</h2><ul>{checks}</ul><div class="gate"><strong>Chờ Owner: APPROVE hoặc REJECT cho cả cặp.</strong>'
        '<p>Nếu REJECT, nêu shot và vấn đề nhìn thấy. Chưa chọn take hoặc dựng phim. Không có generation thay thế được phép.</p></div>')
    packet = output / 'REVIEW_PACKET.html'
    packet.write_text(page, encoding='utf-8')
    result = {'stage': 'OWNER_CHARACTER_CONTINUITY_REVIEW_GATE', 'reference_asset_id': reference.asset_id,
        'reference_sha256': reference.sha256, 'reference_media_id': recovered['media_id'], 'shots': summaries,
        'comparison': {'path': str(sheet_path), 'sha256': digest},
        'packet': str(packet), 'packet_sha256': file_sha256(packet), 'owner_decision': None, 'selected_takes': 0,
        'vlm': {'used': False, 'reason': 'human review of exact pair required; no advisory API call needed'}}
    (output / 'review_gate.json').write_text(canonical_json(result), encoding='utf-8')
    return result


if __name__ == '__main__':
    try:
        print(json.dumps(build_packet()), flush=True)
    except Exception as exc:
        print(json.dumps({'stage': 'review_stopped', 'type': type(exc).__name__, 'reason': str(exc)[:180]}), flush=True)
        raise SystemExit(1)
