"""Small operator-owned E2E project manifest for narration-led films."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path

from .core import sha256
from .editorial import EditClip, EditManifest, EditorialStore, make_edit_manifest
from .delivery import DeliveryEntry, DeliveryManifest, finalize, verify
from .live_runtime import Asset, ProviderJob, file_sha256
from .narrative.narrative import parse_srt
from .qc import (QCStore, QCEvidence, SelectedTake, evidence as make_evidence,
                 human_decision, technical_evidence)
from .rough_cut import persist_render, read_render, render_sources
from .store import SQLiteStore

PLAN_VERSION = 2
DELIVERY_VERSION = 1
GPM_PROFILE = "nethaolabycss222@gmail.com"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_once(path: Path, data: dict) -> None:
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise ValueError(f"refusing to replace immutable file: {path}")
        return
    temporary = path.with_name(path.name + ".partial")
    if temporary.exists():
        raise ValueError(f"unresolved temporary file: {temporary}")
    try:
        temporary.write_text(encoded, encoding="utf-8")
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_plan(path: Path, data: dict) -> None:
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if path.exists():
        temporary = path.with_name(path.name + ".partial")
        try:
            temporary.write_text(encoded, encoding="utf-8")
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    else:
        _write_once(path, data)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _audio_info(path: Path) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
         "stream=codec_name,sample_rate,channels", "-show_entries", "format=duration",
         "-of", "json", str(path)], capture_output=True, text=True, check=False, timeout=30)
    if result.returncode:
        raise ValueError("ffprobe could not read source audio")
    info = json.loads(result.stdout)
    if not info.get("streams") or float(info["format"].get("duration", 0)) <= 0:
        raise ValueError("source audio has no usable audio stream")
    return {"duration_s": float(info["format"]["duration"]),
            "codec": info["streams"][0]["codec_name"],
            "sample_rate": int(info["streams"][0]["sample_rate"]),
            "channels": int(info["streams"][0]["channels"])}


def _runtime(db_path: Path) -> tuple[SQLiteStore, QCStore]:
    store = SQLiteStore(db_path.resolve())
    qc = QCStore(store)
    qc.initialize()
    return store, qc


def _master_info(path: Path) -> dict:
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
        "stream=codec_type,codec_name,width,height", "-show_entries", "format=duration,format_name",
        "-of", "json", str(path)], capture_output=True, text=True, check=False, timeout=30)
    if result.returncode:
        raise ValueError("ffprobe could not read master")
    info = json.loads(result.stdout)
    video = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    audio = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    if len(video) != 1 or len(audio) != 1:
        raise ValueError("master must contain exactly one video and one audio stream")
    v, a = video[0], audio[0]
    if v.get("codec_name") != "h264" or a.get("codec_name") != "aac" or \
            int(v["height"]) < 720 or int(v["width"]) * 9 != int(v["height"]) * 16:
        raise ValueError("master must be 16:9 H.264/AAC at 720p or higher")
    return {"duration_s": float(info["format"]["duration"]), "width": int(v["width"]),
            "height": int(v["height"]), "video_codec": v["codec_name"],
            "audio_codec": a["codec_name"]}


def _clipped_srt(path: Path, start_s: float, duration_s: float) -> str:
    blocks = []
    for cue in parse_srt(path.read_text(encoding="utf-8-sig")):
        start = max(0.0, cue["start_s"] - start_s)
        end = min(duration_s, cue["end_s"] - start_s)
        if end <= start or not cue["text"].strip():
            continue
        def stamp(seconds: float) -> str:
            value = round(seconds * 1000)
            hours, value = divmod(value, 3_600_000)
            minutes, value = divmod(value, 60_000)
            whole, millis = divmod(value, 1000)
            return f"{hours:02d}:{minutes:02d}:{whole:02d},{millis:03d}"
        blocks.append(f"{len(blocks) + 1}\n{stamp(start)} --> {stamp(end)}\n{cue['text']}")
    if not blocks:
        raise ValueError("selected film interval has no timed subtitles")
    return "\n\n".join(blocks) + "\n"


def _project(root: Path) -> tuple[dict, dict]:
    root = root.resolve()
    meta_path, plan_path = root / "project.json", root / "shots.json"
    if not meta_path.is_file() or not plan_path.is_file():
        raise ValueError("not an E2E project: project.json or shots.json is missing")
    meta, plan = _json(meta_path), _json(plan_path)
    if meta.get("locked_plan_sha256") and _sha(plan_path) != meta["locked_plan_sha256"]:
        raise ValueError("locked shot plan changed; resume refused")
    if meta.get("version") not in (1, PLAN_VERSION) or plan.get("version") != meta["version"]:
        raise ValueError("unsupported E2E project version")
    shots = plan.get("shots")
    if not isinstance(shots, list) or len(shots) != meta["shot_count"]:
        raise ValueError("shot plan count differs from the locked project")
    cursor = 0.0
    seen = set()
    for shot in shots:
        shot_id = shot.get("shot_id")
        start, end = shot.get("timeline_in_s"), shot.get("timeline_out_s")
        if (not isinstance(shot_id, str) or shot_id in seen or
                type(start) not in (int, float) or type(end) not in (int, float) or
                not math.isfinite(start) or not math.isfinite(end) or
                abs(start - cursor) > 0.002 or end <= start):
            raise ValueError("shot IDs must be unique and timeline windows contiguous")
        seen.add(shot_id)
        cursor = end
    if abs(cursor - meta["film_duration_s"]) > 0.002:
        raise ValueError("shot plan does not cover the locked film duration")
    for name, expected in (("audio", meta["audio_sha256"]),
                           ("srt", meta["srt_sha256"])):
        path = root / meta[f"{name}_path"]
        if not path.is_file() or _sha(path) != expected:
            raise ValueError(f"locked {name} source is missing or changed")
    return meta, plan


def _action_meaning(shot: dict):
    """Optional operator-declared SRT meaning; None when undeclared."""
    from .drama.action_meaning import ActionMeaning
    declared = shot.get("action_meaning")
    if not declared:
        return None
    if not isinstance(declared, dict):
        raise ValueError("action_meaning must be an object")
    return ActionMeaning.model_validate(declared)


def _directed_text(shot: dict) -> str:
    blocking = shot.get("blocking") if isinstance(shot.get("blocking"), dict) else {}
    phases = (shot.get("choreography") or {}).get("phases", [])
    return " ".join([shot.get("video_prompt", ""), str(blocking.get("start", "")),
        str(blocking.get("end", "")), *map(str, blocking.get("action_beats", [])),
        *(str(p.get("description", "")) for p in phases if isinstance(p, dict))])


def _cues(root: Path, meta: dict) -> list[dict]:
    return parse_srt((root / meta['srt_path']).read_text(encoding='utf-8-sig'))


def _action_warnings(plan: dict, cues: list[dict]) -> dict[str, list[str]]:
    """Escalations the direction adds beyond the source sentence (warn only)."""
    warnings = {}
    for shot in plan["shots"] if plan["version"] >= 2 else []:
        try:
            meaning = _action_meaning(shot)
        except ValueError:
            continue  # Reported as a direction issue.
        added = meaning.escalations(cues, _directed_text(shot)) if meaning else []
        if added:
            warnings[shot["shot_id"]] = [f"direction adds {w!r}, which the source does not state"
                                         for w in added]
    return warnings


def _qc_questions(plan: dict, shot_id: str) -> list[str]:
    shot = next((s for s in plan["shots"] if s["shot_id"] == shot_id), {})
    meaning = _action_meaning(shot) if plan["version"] >= 2 else None
    return meaning.qc_questions() if meaning else []


def _direction_issues(plan: dict, cues: list[dict] | None = None,
                      audio_start_s: float = 0.0) -> list[str]:
    """Check declared choreography/state structure, never infer video quality."""
    from .e2e_flow import GENERATION_S, choreography, shot_spec
    from .sequence import validate_shot_sequence
    shots = plan["shots"]
    if plan["version"] == 1:
        return []  # Historical locked plans keep their exact ShotSpec identity.
    issues = []
    for shot in shots:
        blocking, continuity = shot.get("blocking"), shot.get("continuity")
        if not isinstance(blocking, dict) or not all(
                isinstance(blocking.get(k), str) and blocking[k].strip() for k in ("start", "end")):
            issues.append(f"{shot['shot_id']}: describe blocking start and end for all participants")
        if not isinstance(continuity, dict) or not all(
                isinstance(continuity.get(k), dict) and continuity[k] for k in ("start_state", "end_state")):
            issues.append(f"{shot['shot_id']}: declare continuity start_state and end_state")
        try:
            phases = choreography(shot)
        except ValueError as exc:
            issues.append(f"{shot['shot_id']}: invalid choreography: {exc}")
            continue
        if phases:
            issues += [i.detail for i in phases.problems(GENERATION_S) if i.severity == "BLOCK"]
        try:
            meaning = _action_meaning(shot)
        except ValueError as exc:
            issues.append(f"{shot['shot_id']}: invalid action_meaning: {exc}")
            continue
        if meaning and cues is not None:
            window = (audio_start_s + shot["timeline_in_s"], audio_start_s + shot["timeline_out_s"])
            issues += [i.detail for i in meaning.problems(shot["shot_id"], cues, window, phases)]
    if issues:
        return issues
    if any(not s.get("visual_intent") or not s.get("video_prompt") for s in shots):
        return []  # The existing missing_shot_plans report covers these fields.
    try:
        validate_shot_sequence([shot_spec(s, "direction-review", plan_version=plan['version']) for s in shots])
    except ValueError as exc:
        issues.append(str(exc))
    return issues


def _source_windows(root: Path, meta: dict, plan: dict) -> dict[str, str]:
    cues = _cues(root, meta)
    start = meta['audio_start_s']
    return {shot['shot_id']: '\n'.join(dict.fromkeys(cue['text'].strip() for cue in cues
        if cue['end_s'] > start + shot['timeline_in_s']
        and cue['start_s'] < start + shot['timeline_out_s'] and cue['text'].strip()))
        for shot in plan['shots']}


def references_for_shot(root: Path, shot_id: str) -> list[dict]:
    _, plan = _project(root)
    if shot_id not in {s["shot_id"] for s in plan["shots"]}:
        raise ValueError(f"unknown shot ID: {shot_id}")
    base = Path(root).resolve()
    receipts_dir = base / "reference_receipts"
    matches = []
    if not receipts_dir.is_dir():
        return matches
    for receipt_path in sorted(receipts_dir.glob("*.json")):
        receipt = _json(receipt_path)
        if receipt.get("profile_email") != GPM_PROFILE or receipt.get("tab_index") != 2:
            raise ValueError("reference receipt has an unexpected GPM profile or tab")
        if shot_id not in receipt.get("shot_ids", []):
            continue
        path = (base / receipt["path"]).resolve()
        if base not in path.parents or not path.is_file() or _sha(path) != receipt["sha256"]:
            raise ValueError(f"reference source missing or changed: {shot_id}")
        matches.append(receipt)
    return matches


def prepare(audio: Path, srt: Path, start_s: float, end_s: float, output: Path) -> dict:
    audio, srt, output = audio.resolve(), srt.resolve(), output.resolve()
    if not audio.is_file() or not srt.is_file():
        raise ValueError("audio and SRT files must exist")
    if not math.isfinite(start_s) or not math.isfinite(end_s) or start_s < 0 or end_s <= start_s:
        raise ValueError("audio interval must be finite, nonnegative and increasing")
    info = _audio_info(audio)
    if end_s > info["duration_s"]:
        raise ValueError("requested interval exceeds source audio duration")
    if not 30 <= end_s - start_s <= 60:
        raise ValueError("acceptance-film interval must be 30 to 60 seconds")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("project directory already contains files")
    captions = parse_srt(srt.read_text(encoding="utf-8-sig"))
    if not captions or srt.read_text(encoding="utf-8-sig").count("-->") != len(captions):
        raise ValueError("SRT contains no readable cues")
    for cue in captions:
        if not (math.isfinite(cue["start_s"]) and math.isfinite(cue["end_s"])
                and cue["end_s"] > cue["start_s"]):
            raise ValueError("SRT contains an invalid cue interval")
    selected = [c for c in captions if c["end_s"] > start_s and c["start_s"] < end_s]
    if not selected:
        raise ValueError("SRT has no captions inside the chosen audio interval")
    output.mkdir(parents=True, exist_ok=True)
    source_dir = output / "source"
    source_dir.mkdir(exist_ok=True)
    audio_target, srt_target = source_dir / ("audio" + audio.suffix.lower()), source_dir / "captions.srt"
    shutil.copy2(audio, audio_target)
    shutil.copy2(srt, srt_target)
    duration = end_s - start_s
    shot_count = max(8, min(12, round(duration / 5.7)))
    shots = []
    for index in range(shot_count):
        t0 = duration * index / shot_count
        t1 = duration * (index + 1) / shot_count
        cues = [c for c in selected if c["end_s"] > start_s + t0 and c["start_s"] < start_s + t1]
        # Captions are the authority; overlapping rolling lines stay intact here.
        text = "\n".join(dict.fromkeys(c["text"].strip() for c in cues if c["text"].strip()))
        shots.append({"shot_id": f"SHOT_{index + 1:02d}", "timeline_in_s": round(t0, 3),
                      "timeline_out_s": round(t1, 3), "source_text": text,
                      "visual_intent": "", "image_prompt": "", "video_prompt": "",
                      "blocking": {"start": "", "end": ""},
                      "continuity": {"screen_direction": None, "eyeline": None,
                          "previous_shot_id": f"SHOT_{index:02d}" if index else None,
                          "start_state": {}, "end_state": {}, "critical_invariants": []}})
    meta = {"version": PLAN_VERSION, "project_id": output.name, "status": "PLAN_REVIEW_REQUIRED",
            "audio_path": "source/" + audio_target.name, "audio_sha256": _sha(audio_target),
            "srt_path": "source/captions.srt", "srt_sha256": _sha(srt_target),
            "audio_duration_s": info["duration_s"], "audio_sample_rate": info["sample_rate"],
            "audio_channels": info["channels"], "audio_start_s": round(start_s, 3),
            "audio_end_s": round(end_s, 3), "film_duration_s": round(duration, 3),
            "shot_count": shot_count, "locked_plan_sha256": None}
    plan = {"version": PLAN_VERSION, "shots": shots}
    _write_once(output / "project.json", meta)
    _write_once(output / "shots.json", plan)
    _runtime(output / "runtime.sqlite")
    return {"project": str(output), "status": meta["status"], "shot_count": shot_count,
            "duration_s": meta["film_duration_s"], "audio_sha256": meta["audio_sha256"],
            "srt_sha256": meta["srt_sha256"], "shot_plan": str(output / "shots.json"),
            "runtime_database": str(output / "runtime.sqlite")}


def _require_planned_shot(frozen, planned, store=None, project_id=None, *, plan_version=1):
    from .e2e_flow import shot_spec, ACCOUNT_ALIAS
    if frozen.spec_version > 1:
        if store is None or project_id is None:
            raise ValueError('repair must bind to its rejected predecessor')
        from .flow_r2v_runtime import FlowR2VShotRuntime
        connection = store._connect()
        try:
            jobs = connection.execute('SELECT p.id FROM provider_jobs p JOIN generation_attempts a '
                'ON a.id=p.generation_attempt_id WHERE a.shot_spec_hash=?', (sha256(frozen),)).fetchall()
        finally:
            connection.close()
        if len(jobs) != 1:
            raise ValueError('repair job is absent or ambiguous')
        job = store.read_provider_job(jobs[0][0])
        repair_id = job.correlation_evidence.get('repair_decision_id')
        if not repair_id:
            raise ValueError('repair has no stored rejection')
        parent = FlowR2VShotRuntime(store, project_id=project_id, account_id=ACCOUNT_ALIAS).repair_parent(
            frozen, repair_id)
        _require_planned_shot(parent, planned, store, project_id, plan_version=plan_version)
        restored = frozen.model_copy(update={'spec_version': parent.spec_version,
            'references': parent.references, 'blocking': parent.blocking, 'camera': parent.camera})
        if restored != parent:
            raise ValueError('repair changed the locked story goal')
        return
    refs = frozen.references.other_asset_ids if frozen.references else []
    if len(refs) != 1 or frozen != shot_spec(planned, refs[0], plan_version=plan_version):
        raise ValueError("runtime ShotSpec differs from the locked creative plan")


def status(root: Path, db_path: Path | None = None, project_id: str | None = None) -> dict:
    root = root.resolve()
    meta, plan = _project(root)
    project_id = project_id or meta.get('flow_project_id')
    if meta.get('flow_project_id') and project_id != meta['flow_project_id']:
        raise ValueError('Flow project binding mismatch')
    if db_path is not None and not project_id:
        raise ValueError('exact Flow project ID required for an unbound runtime')
    if db_path is None and project_id:
        db_path = root / 'runtime.sqlite'
    if not isinstance(plan.get("shots"), list) or len(plan["shots"]) != meta["shot_count"]:
        raise ValueError("shot plan count changed; prepare a reviewed plan")
    missing_intent = [s["shot_id"] for s in plan["shots"] if not all(
        isinstance(s.get(k), str) and s[k].strip() for k in ("visual_intent", "image_prompt", "video_prompt"))]
    cues = _cues(root, meta)
    direction_issues = _direction_issues(plan, cues, meta['audio_start_s'])
    reference_coverage = {s["shot_id"]: len(references_for_shot(root, s["shot_id"]))
                          for s in plan["shots"]}
    reference_missing = [shot for shot, count in reference_coverage.items() if count == 0]
    windows = _source_windows(root, meta, plan)
    report = {"project_id": meta["project_id"], "status": meta["status"],
              "duration_s": meta["film_duration_s"], "shot_count": len(plan["shots"]),
              "plan_review_required": bool(missing_intent or direction_issues),
              "missing_shot_plans": missing_intent, "direction_issues": direction_issues,
              "action_warnings": _action_warnings(plan, cues),
              "legacy_direction_unassessed": plan["version"] == 1,
              "reference_coverage": reference_coverage, "missing_reference_images": reference_missing,
              "selected_shots": [], "missing_selected_shots": [s["shot_id"] for s in plan["shots"]],
              "next_action": "lock the creative shot plan; attach one ChatGPT reference receipt before each Flow dispatch"}
    report['source_window_mismatches'] = [shot['shot_id'] for shot in plan['shots']
        if shot.get('source_text') != windows[shot['shot_id']]]
    if not db_path:
        if direction_issues:
            report['next_action'] = 'complete interaction start/action/end states before locking'
        return report
    db_path = db_path.resolve()
    if not db_path.is_file():
        raise ValueError("Flow runtime database is missing")
    store = SQLiteStore(db_path)
    qc = QCStore(store)
    connection = store._connect()
    try:
        rows = connection.execute("SELECT st.id,st.payload,a.payload FROM selected_takes st "
            "JOIN assets a ON a.id=st.asset_id").fetchall()
    except Exception as exc:
        raise ValueError("runtime DB has no SelectedTake records; Flow runtime evidence is required") from exc
    finally:
        connection.close()
    approved: dict[str, list[str]] = {}
    for take_id, payload, asset_payload in rows:
        take = SelectedTake.model_validate(json.loads(payload))
        if take.selected_take_id != take_id:
            raise ValueError("SelectedTake identity mismatch")
        if take.shot_id not in {s["shot_id"] for s in plan["shots"]}:
            continue
        asset = Asset.model_validate(json.loads(asset_payload))
        shot, _, route, attempt, job, assets = store.read_runtime_lineage(
            take.generation_attempt_id, asset.provider_job_id)
        _require_planned_shot(shot, next(s for s in plan['shots'] if s['shot_id'] == shot.shot_id), store, project_id, plan_version=plan['version'])
        if (shot.shot_id != take.shot_id or take.asset_id != asset.asset_id or
                asset not in assets or job.project_binding_id != sha256(project_id) or
                job.provider_id != "flow_veo" or route.provider_id != "flow_veo"):
            raise ValueError(f"SelectedTake has the wrong Flow project or provider lineage: {take_id}")
        record, disposition = qc.read(asset, take.qc_report_id)
        if disposition != take or record.report["decision"] != "pass":
            raise ValueError(f"SelectedTake is not approved in QC: {take_id}")
        approved.setdefault(take.shot_id, []).append(take_id)
    report["selected_shots"] = [{"shot_id": shot, "selected_take_ids": ids}
                                for shot, ids in sorted(approved.items())]
    report["missing_selected_shots"] = [s["shot_id"] for s in plan["shots"] if s["shot_id"] not in approved]
    shot_ids = {s["shot_id"] for s in plan["shots"]}
    connection = store._connect()
    try:
        assets = connection.execute("SELECT a.payload,p.payload FROM assets a JOIN provider_jobs p "
            "ON p.id=a.provider_job_id WHERE p.provider_id='flow_veo'").fetchall()
        report_rows = connection.execute("SELECT asset_id,human_decision_id,payload FROM qc_reports "
                                         "ORDER BY rowid DESC").fetchall()
    finally:
        connection.close()
    review_items = []
    for payload, job_payload in assets:
        if ProviderJob.model_validate(json.loads(job_payload)).project_binding_id != sha256(project_id):
            continue
        asset = Asset.model_validate(json.loads(payload))
        shot, _, route, _, job, lineage_assets = store.read_runtime_lineage(
            asset.source_attempt_id, asset.provider_job_id)
        if (shot.shot_id not in shot_ids or route.provider_id != "flow_veo" or
                job.project_binding_id != sha256(project_id) or asset not in lineage_assets or
                job.status != "SUCCEEDED" or job.dispatch_count != 1):
            continue
        _require_planned_shot(shot, next(s for s in plan['shots'] if s['shot_id'] == shot.shot_id), store, project_id, plan_version=plan['version'])
        try:
            qc._exact_asset(asset)
        except ValueError:
            continue
        prior = next((r for r in report_rows if r[0] == asset.asset_id), None)
        if shot.shot_id in approved or (prior and (prior[1] is not None or
                json.loads(prior[2]).get("report", {}).get("decision") != "needs_human_review")):
            continue
        review_items.append({"shot_id": shot.shot_id, "project_id": project_id,
            "spec_version": shot.spec_version,
            "asset_id": asset.asset_id, "asset_sha256": asset.sha256,
            "source_attempt_id": asset.source_attempt_id, "provider_job_id": asset.provider_job_id,
            "provider_asset_id": asset.provider_asset_id, "asset_path": asset.uri_or_path,
            "prior_report_id": json.loads(prior[2])["report"]["qc_report_id"] if prior else None,
            "direction_to_review": {"start": shot.blocking.start,
                "action_beats": shot.blocking.action_beats, "end": shot.blocking.end,
                "previous_shot_id": shot.continuity.previous_shot_id,
                "start_state": shot.continuity.start_state, "end_state": shot.continuity.end_state,
                "next_shot_id": next((b["shot_id"] for a, b in zip(plan["shots"], plan["shots"][1:])
                    if a["shot_id"] == shot.shot_id), None),
                "next_start_state": next((b.get("continuity", {}).get("start_state", {})
                    for a, b in zip(plan["shots"], plan["shots"][1:])
                    if a["shot_id"] == shot.shot_id), {}),
                "qc_questions": _qc_questions(plan, shot.shot_id)},
            "reviewer_id": "", "visual_pass": None, "continuity_pass": None,
            "editorial_pass": None, "notes": [], "failure_observations": {}})
    report["review_template"] = {"project_id": project_id,
        "instructions": "Watch the whole action: initiator, receiver/prop response, release/recovery, "
            "and handoff to the next shot. Assess these under continuity_pass/editorial_pass; "
            "filled direction fields do not prove the video matches.",
        "reviews": review_items}
    if review_items:
        report['next_action'] = 'watch the acquired clips and submit their exact review_template with resume --review'
    elif not report['missing_selected_shots']:
        report['status'] = 'READY_TO_FINISH'
        report['next_action'] = 'run finish to export the approved complete timeline'
    elif meta.get('locked_plan_sha256'):
        report['next_action'] = 'attach missing reference receipts and resume the remaining explicit shot IDs'
    if direction_issues:
        report['next_action'] = 'complete interaction start/action/end states and resolve adjacent-shot conflicts before locking'
    return report


def validate_review_entry(review: dict, asset: Asset) -> None:
    expected = {"asset_id": asset.asset_id, "asset_sha256": asset.sha256,
                "source_attempt_id": asset.source_attempt_id,
                "provider_job_id": asset.provider_job_id,
                "provider_asset_id": asset.provider_asset_id,
                "asset_path": asset.uri_or_path}
    if any(review.get(key) != value for key, value in expected.items()):
        raise ValueError("Owner review asset identity or SHA-256 mismatch")
    if file_sha256(Path(asset.uri_or_path)) != asset.sha256:
        raise ValueError("Owner review media bytes changed")
    if not isinstance(review.get("reviewer_id"), str) or not review["reviewer_id"].strip():
        raise ValueError("Owner review needs reviewer_id")
    if any(type(review.get(key)) is not bool for key in
           ("visual_pass", "continuity_pass", "editorial_pass")):
        raise ValueError("Owner review needs explicit booleans for every subjective gate")
    if not isinstance(review.get("notes"), list) or not review["notes"] or any(
            not isinstance(note, str) or not note.strip() for note in review["notes"]):
        raise ValueError("Owner review needs explicit nonempty notes")
    failures = [gate for gate in ("visual", "continuity", "editorial")
                if review[f"{gate}_pass"] is False]
    observations = review.get("failure_observations", {})
    if not isinstance(observations, dict) or set(observations) != set(failures) or any(
            not isinstance(observations[g], str) or not observations[g].strip() for g in failures):
        raise ValueError("failed review gates need one exact failure_observation each")


def _apply_reviews(root: Path, db_path: Path, project_id: str, review_manifest: Path) -> list[dict]:
    meta, plan = _project(root)
    data = _json(review_manifest.resolve())
    if data.get("project_id") != project_id or not isinstance(data.get("reviews"), list):
        raise ValueError("review manifest must bind the exact Flow project and contain reviews")
    store, qc = _runtime(db_path)
    by_shot = {s["shot_id"]: s for s in plan["shots"]}
    output = []
    seen_assets = set()
    for review in data["reviews"]:
        shot_id = review.get("shot_id")
        if shot_id not in by_shot or review.get("project_id") != project_id:
            raise ValueError("Owner review shot or project binding mismatch")
        asset_id = review.get("asset_id")
        if asset_id in seen_assets:
            raise ValueError("duplicate Owner review for one Asset")
        seen_assets.add(asset_id)
        connection = store._connect()
        try:
            row = connection.execute("SELECT payload FROM assets WHERE id=?", (asset_id,)).fetchone()
        finally:
            connection.close()
        if row is None:
            raise ValueError("Owner review Asset is absent from the Flow runtime")
        asset = Asset.model_validate(json.loads(row[0]))
        validate_review_entry(review, asset)
        shot, _, route, _, job, assets = store.read_runtime_lineage(
            asset.source_attempt_id, asset.provider_job_id)
        _require_planned_shot(shot, by_shot[shot_id], store, project_id, plan_version=plan['version'])
        if (shot.shot_id != shot_id or shot_id != review["shot_id"] or asset not in assets
                or route.provider_id != "flow_veo" or job.provider_id != "flow_veo"
                or job.project_binding_id != sha256(project_id) or job.status != "SUCCEEDED"
                or job.dispatch_count != 1):
            raise ValueError("Owner review does not bind to the exact acquired Flow shot")
        qc._exact_asset(asset)
        tech, _ = technical_evidence(shot, asset)
        observations = review.get("failure_observations", {})
        notes = review["notes"]
        values = {gate: review[f"{gate}_pass"] for gate in
                  ("visual", "continuity", "editorial")}
        codes = {"visual": "VISUAL_OWNER_REJECTED", "continuity": "CONTINUITY_OWNER_REJECTED",
                 "editorial": "EDITORIAL_OWNER_REJECTED"}
        rows = list(tech)
        for gate, passed in values.items():
            rows.append(make_evidence(asset=asset, evaluator_type="human",
                evaluator_version="owner_e2e_review-v1", gate=gate, criterion="owner_review",
                observation="; ".join(notes), verdict="pass" if passed else "fail",
                failure_code=None if passed else codes[gate],
                source_artifacts=[{"path": asset.uri_or_path, "sha256": asset.sha256}]))
        failures = [gate for gate, passed in values.items() if not passed]
        decision = human_decision(asset=asset, reviewer_id=review["reviewer_id"],
            action="REJECT" if failures else "APPROVE", visual_pass=values["visual"],
            continuity_pass=values["continuity"], editorial_pass=values["editorial"],
            failure_codes=[codes[g] for g in failures],
            failure_observations={codes[g]: observations[g] for g in failures}, notes=notes,
            source="owner_explicit_review")
        connection = store._connect()
        prior = None
        try:
            prior = connection.execute("SELECT id,human_decision_id,payload FROM qc_reports WHERE asset_id=? "
                "ORDER BY rowid DESC LIMIT 1", (asset.asset_id,)).fetchone()
            if prior:
                prior_payload = json.loads(prior[2])
                if prior[1] is not None or prior_payload.get("report", {}).get("decision") != "needs_human_review":
                    raise ValueError("Asset already has a final QC decision")
                old = qc.read(asset, prior[0])[0]
                ids = old.evidence_ids
                for evidence_id in ids:
                    evidence_row = connection.execute("SELECT payload FROM qc_evidence WHERE id=?",
                                                      (evidence_id,)).fetchone()
                    if not evidence_row:
                        raise ValueError("prior QC evidence is missing")
                    rows.append(QCEvidence.model_validate(json.loads(evidence_row[0])))
            else:
                prior_id = None
        finally:
            connection.close()
        prior_id = prior[0] if prior else None
        unique_rows = {row.evidence_id: row for row in rows}
        record, disposition = qc.save(asset, list(unique_rows.values()), decision, prior_id)
        output.append({"shot_id": shot_id, "asset_id": asset.asset_id,
                       "qc_report_id": record.report["qc_report_id"],
                       "decision": record.report["decision"],
                       "repair_decision_id": disposition.get('repair_decision_id')
                           if isinstance(disposition, dict) else None,
                       "selected_take_id": disposition.selected_take_id
                           if isinstance(disposition, SelectedTake) else None})
    return output


def resume(root: Path, db_path: Path, provider_project_id: str,
           reference_manifest: Path | None = None,
           review_manifest: Path | None = None,
           flow_profile: Path | None = None,
           shot_ids: list[str] | None = None, repair_path: Path | None = None) -> dict:
    meta, plan = _project(root)
    if not provider_project_id.strip():
        raise ValueError("exact Flow project ID required")
    if not db_path.resolve().is_file():
        raise ValueError("Flow runtime database is missing")
    if not meta['locked_plan_sha256']:
        windows = _source_windows(root.resolve(), meta, plan)
        if any(shot.get('source_text') != windows[shot['shot_id']] for shot in plan['shots']):
            for shot in plan['shots']:
                shot['source_text'] = windows[shot['shot_id']]
            _write_plan(root.resolve() / 'shots.json', plan)
    report = status(root, db_path, provider_project_id)
    if report["direction_issues"]:
        raise ValueError("interaction direction incomplete or conflicting: " + "; ".join(report["direction_issues"]))
    prompts_missing = report["missing_shot_plans"]
    if reference_manifest is not None:
        refs = _json(reference_manifest.resolve())
        if refs.get("profile_email") != GPM_PROFILE or refs.get("tab_index") != 2:
            raise ValueError("reference receipts must identify the selected GPM profile and second tab")
        by_id = {s["shot_id"]: s for s in plan["shots"]}
        for item in refs.get("images", []):
            receipt_shot_ids = item.get("shot_ids", [item.get("shot_id")])
            chat_url = item.get("chat_url")
            if (not isinstance(receipt_shot_ids, list) or not receipt_shot_ids
                    or len(set(receipt_shot_ids)) != len(receipt_shot_ids)
                    or any(shot_id not in by_id for shot_id in receipt_shot_ids)
                    or not isinstance(chat_url, str) or not chat_url.startswith("https://chatgpt.com/")):
                raise ValueError("reference receipt needs known shot IDs and exact ChatGPT chat URL")
            image = Path(item.get("path", "")).resolve()
            expected = item.get("sha256")
            if (image.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}
                    or not image.is_file() or not isinstance(expected, str) or _sha(image) != expected):
                raise ValueError(f"reference file or SHA-256 mismatch for {receipt_shot_ids}")
            target_dir = root.resolve() / "references"
            target_dir.mkdir(exist_ok=True)
            target = target_dir / f"{expected}{image.suffix.lower()}"
            if not target.exists():
                shutil.copy2(image, target)
            if _sha(target) != expected:
                raise ValueError(f"copied reference SHA-256 mismatch for {shot_ids}")
            receipt = {"shot_ids": receipt_shot_ids, "path": str(target.relative_to(root.resolve())),
                "sha256": expected, "provider": "ChatGPT web", "profile_email": refs["profile_email"],
                "tab_index": refs["tab_index"], "chat_url": chat_url}
            _write_once(root.resolve() / "reference_receipts" / f"{sha256(receipt)}.json", receipt)
    plan_hash = _sha(root.resolve() / "shots.json")
    if meta["locked_plan_sha256"] and meta["locked_plan_sha256"] != plan_hash:
        raise ValueError("locked shot plan changed; resume refused")
    if not meta["locked_plan_sha256"]:
        if prompts_missing:
            raise ValueError("complete every shot's visual_intent, image_prompt and video_prompt before locking")
        meta["locked_plan_sha256"] = plan_hash
        meta["status"] = "PLAN_LOCKED_AWAITING_FLOW_MEDIA"
        meta["flow_project_id"] = provider_project_id
    elif meta.get("flow_project_id") != provider_project_id:
        raise ValueError("locked plan is bound to a different Flow project")
    meta_path = root.resolve() / "project.json"
    _write_plan(meta_path, meta)
    reviews = _apply_reviews(root, db_path, provider_project_id, review_manifest) if review_manifest else []
    selected_shots = shot_ids or []
    flow_results = []
    if flow_profile is not None and not flow_profile.resolve().is_dir():
        raise ValueError("existing Flow profile directory is missing")
    if selected_shots and flow_profile is None:
        raise ValueError("--shot requires --flow-profile; no generation is dispatched otherwise")
    if flow_profile is not None and not selected_shots:
        raise ValueError("--flow-profile requires at least one explicit --shot")
    if repair_path is not None and (flow_profile is None or len(selected_shots) != 1):
        raise ValueError('--repair requires exactly one explicit Flow shot')
    if flow_profile is not None:
        from .e2e_flow import run_shot
        for shot_id in selected_shots:
            if not references_for_shot(root, shot_id):
                raise ValueError(f"exact ChatGPT reference required before dispatch: {shot_id}")
            flow_results.append(run_shot(root.resolve(), db_path.resolve(), provider_project_id,
                                         flow_profile.resolve(), shot_id, poll_seconds=300, repair_path=repair_path))
    result = status(root, db_path, provider_project_id)
    result["human_reviews"] = reviews
    result["flow_results"] = flow_results
    return result


def _selected_sources(root: Path, db_path: Path, project_id: str,
                      source_ins: dict[str, float] | None = None) -> tuple[dict, dict, list[EditClip]]:
    meta, plan = _project(root)
    if not meta["locked_plan_sha256"] or meta["locked_plan_sha256"] != _sha(root.resolve() / "shots.json"):
        raise ValueError("review and lock shots.json by running resume first")
    if meta.get("flow_project_id") != project_id:
        raise ValueError("Flow project binding mismatch")
    source_ins = source_ins or {}
    if set(source_ins) - {shot['shot_id'] for shot in plan['shots']}:
        raise ValueError('trim references an unknown planned shot')
    store = SQLiteStore(db_path.resolve())
    connection = store._connect()
    clips = []
    try:
        for order, shot in enumerate(plan["shots"], 1):
            rows = connection.execute("SELECT st.id,st.payload,a.payload FROM selected_takes st "
                "JOIN assets a ON a.id=st.asset_id").fetchall()
            choices = []
            qc = QCStore(store)
            for take_id, payload, asset_payload in rows:
                take = SelectedTake.model_validate(json.loads(payload))
                if take.shot_id == shot["shot_id"]:
                    asset = Asset.model_validate(json.loads(asset_payload))
                    frozen_shot, _, route, _, job, assets = store.read_runtime_lineage(
                        take.generation_attempt_id, asset.provider_job_id)
                    _require_planned_shot(frozen_shot, shot, store, project_id, plan_version=plan['version'])
                    if (frozen_shot.shot_id != take.shot_id or asset not in assets or
                            job.project_binding_id != sha256(project_id) or
                            job.provider_id != "flow_veo" or route.provider_id != "flow_veo"):
                        raise ValueError(f"SelectedTake has the wrong Flow project or provider lineage: {take_id}")
                    report, disposition = qc.read(asset, take.qc_report_id)
                    if take_id != take.selected_take_id or disposition != take or report.report["decision"] != "pass":
                        raise ValueError(f"unresolved QC selection for {shot['shot_id']}")
                    choices.append((take, asset))
            if len(choices) != 1:
                raise ValueError(f"expected exactly one selected, QC-approved take for {shot['shot_id']}; found {len(choices)}")
            take, asset = choices[0]
            duration = shot["timeline_out_s"] - shot["timeline_in_s"]
            start = source_ins.get(shot['shot_id'], 0.0)
            if (not math.isfinite(start) or start < 0 or not asset.duration_s
                    or asset.duration_s < start + duration):
                raise ValueError(f"approved take is shorter than planned shot: {shot['shot_id']}")
            clips.append(EditClip(order=order, shot_id=take.shot_id,
                selected_take_id=take.selected_take_id, asset_id=asset.asset_id,
                source_in_s=start, source_out_s=start + duration, target_duration_s=duration))
    finally:
        connection.close()
    return meta, plan, clips


def finish(root: Path, db_path: Path, provider_project_id: str,
           source_ins: dict[str, float] | None = None) -> dict:
    root = root.resolve()
    meta, plan, clips = _selected_sources(root, db_path, provider_project_id, source_ins)
    manifest = make_edit_manifest(meta["project_id"], clips)
    store = SQLiteStore(db_path.resolve())
    editorial = EditorialStore(store)
    editorial.save_manifest(manifest)
    _, sources = editorial.read_manifest(manifest.edit_manifest_id)
    renders = root / "renders"
    rough_path = renders / f"rough_{manifest.edit_manifest_id}.mp4"
    connection = store._connect()
    try:
        existing = connection.execute("SELECT id FROM rough_cut_renders WHERE manifest_id=?",
                                      (manifest.edit_manifest_id,)).fetchall()
    finally:
        connection.close()
    if existing:
        if len(existing) != 1:
            raise ValueError("multiple rough-cut receipts for the locked manifest")
        render, read_manifest, read_sources = read_render(editorial, existing[0][0])
        if read_manifest != manifest or read_sources != sources:
            raise ValueError("existing rough-cut receipt does not match current selected takes")
    else:
        render = render_sources(manifest, sources, rough_path)
        persist_render(editorial, render)
        render, read_manifest, read_sources = read_render(editorial, render.render_id)
        if read_manifest != manifest or read_sources != sources:
            raise ValueError("fresh rough-cut receipt does not match current selected takes")
    audio = root / meta["audio_path"]
    srt = root / meta["srt_path"]
    if _sha(audio) != meta["audio_sha256"] or _sha(srt) != meta["srt_sha256"]:
        raise ValueError("source bytes changed before master export")
    start, duration = meta["audio_start_s"], meta["film_duration_s"]
    master = renders / "master.mp4"
    caption_path = root / "captions.srt"
    receipt = root / "delivery.json"
    if master.exists() or receipt.exists():
        if not master.is_file() or not receipt.is_file():
            raise ValueError("stale master or delivery receipt; refusing overwrite")
        old = _json(receipt)
        expected = {"manifest_id": manifest.edit_manifest_id, "render_id": render.render_id,
            "audio_sha256": meta["audio_sha256"], "srt_sha256": meta["srt_sha256"],
            "duration_s": duration, "shots": [c.shot_id for c in clips],
            "captions_path": str(caption_path.relative_to(root))}
        if any(old.get(key) != value for key, value in expected.items()):
            raise ValueError("existing master is bound to different sources")
        if _sha(master) != old.get("master_sha256") or not caption_path.is_file() or \
                _sha(caption_path) != old.get("captions_sha256"):
            raise ValueError("existing master changed")
        if abs(_master_info(master)["duration_s"] - duration) > 0.1:
            raise ValueError("existing master metadata differs from its receipt")
        verify = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(master),
                                 "-f", "null", "-"], capture_output=True, timeout=300, check=False)
        if verify.returncode:
            raise ValueError("existing master no longer decodes fully")
        return _handoff_package(root, old, manifest)
    captions = _clipped_srt(srt, start, duration)
    if caption_path.exists():
        if not caption_path.is_file() or caption_path.read_text(encoding="utf-8") != captions:
            raise ValueError("existing caption output differs from locked timeline")
    else:
        caption_path.write_text(captions, encoding="utf-8")
    staging = master.with_name("master.partial.mp4")
    if staging.exists():
        raise ValueError("unresolved master staging file")
    try:
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-i", render.output_path,
                   "-ss", str(start), "-i", str(audio), "-i", str(caption_path),
                   "-t", str(duration), "-map", "0:v:0", "-map", "1:a:0", "-map", "2:s:0",
                   "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1",
                   "-r", "24", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000",
                   "-c:s", "mov_text", "-metadata:s:s:0", "language=eng",
                   "-movflags", "+faststart", str(staging)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
        if result.returncode or not staging.is_file() or not staging.stat().st_size:
            raise ValueError("master FFmpeg export failed")
        verify = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(staging),
                                 "-f", "null", "-"], capture_output=True, timeout=300, check=False)
        if verify.returncode:
            raise ValueError("master full decode failed")
        probe = _master_info(staging)
        if abs(probe["duration_s"] - duration) > 0.1:
            raise ValueError("master duration differs from locked film timeline")
        os.link(staging, master)
    finally:
        staging.unlink(missing_ok=True)
    data = {"version": DELIVERY_VERSION, "project_id": meta["project_id"],
            "manifest_id": manifest.edit_manifest_id, "render_id": render.render_id,
            "master_path": str(master.relative_to(root)), "master_sha256": _sha(master),
            "audio_sha256": meta["audio_sha256"], "srt_sha256": meta["srt_sha256"],
            "captions_path": str(caption_path.relative_to(root)),
            "captions_sha256": _sha(caption_path),
            "duration_s": duration, "shots": [c.shot_id for c in clips],
            "video_codec": "h264", "audio_codec": "aac", "full_decode": True}
    _write_once(receipt, data)
    return _handoff_package(root, data, manifest)


def verify_package(directory: Path) -> dict:
    """Portable integrity readback; no browser, original workspace or credentials."""
    directory = directory.resolve()
    manifest = DeliveryManifest.model_validate(_json(directory / 'manifest.json'))
    if {entry.role for entry in manifest.entries} != {'master', 'caption_srt', 'provenance'}:
        raise ValueError('handoff needs master, captions and provenance')
    for entry in manifest.entries:
        if directory not in (directory / entry.path).resolve().parents:
            raise ValueError('handoff path escapes its directory')
    result = verify(manifest, directory)
    return {**result, 'delivery_id': manifest.delivery_id, 'directory': str(directory)}


def _handoff_package(root: Path, receipt: dict, edit_manifest: EditManifest) -> dict:
    directory = root / 'delivery'
    directory.mkdir(exist_ok=True)
    files = [('master', 'master.mp4', receipt['master_path'], receipt['master_sha256']),
             ('caption_srt', 'captions.srt', receipt['captions_path'], receipt['captions_sha256'])]
    for _, name, source_name, expected in files:
        source, target = (root / source_name).resolve(), directory / name
        if root not in source.parents or _sha(source) != expected:
            raise ValueError('handoff source is outside this project or changed')
        if target.exists():
            if _sha(target) != expected:
                raise ValueError('existing handoff file changed; refusing overwrite')
            continue
        temporary = target.with_name(name + '.partial')
        if temporary.exists():
            raise ValueError('unresolved handoff staging file')
        try:
            shutil.copy2(source, temporary)
            os.link(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    _write_once(directory / 'provenance.json', {'export': receipt,
        'edit_manifest': edit_manifest.model_dump(mode='json')})
    roles = [('master', 'master.mp4'), ('caption_srt', 'captions.srt'), ('provenance', 'provenance.json')]
    entries = [DeliveryEntry(role=role, path=name, sha256=_sha(directory / name),
        bytes=(directory / name).stat().st_size,
        media_type={'master': 'video/mp4', 'caption_srt': 'application/x-subrip',
                    'provenance': 'application/json'}[role], source_lineage=edit_manifest.edit_manifest_id)
        for role, name in roles]
    package = finalize(DeliveryManifest(film_id=receipt['project_id'], entries=entries), directory)
    _write_once(directory / 'manifest.json', package.model_dump(mode='json'))
    if verify_package(directory)['result'] != 'PASS':
        raise ValueError('handoff readback failed')
    return {**receipt, 'package_path': str(directory.relative_to(root)), 'delivery_id': package.delivery_id}
