#!/usr/bin/env python3
r"""
Muse Studio Unified CLI (End-to-End Headless Filmmaking Orchestrator)
Chạy từ `d:\Muse`: `python -m muse_studio.cli <command> ...`
Commands:
  accounts-import   Nhập danh sách tài khoản từ file hoặc chuỗi
  accounts-verify   Đăng nhập & xác thực headless toàn bộ Pool tài khoản
  compile           Biên dịch Story Bible + Beats -> shots_manifest.json & CSV
  preflight         Tiền kiểm toàn bộ Story Bible, Keyframes & 180-axis Prompt
  keyframes         Dry run (--simulate) of keyframe generation; real sends: pool_runner keyframes
  package           Đóng gói các shot chưa xong thành batch <= 6 shots
  qc-audit          Hậu kiểm 5-Gate tất cả clips hiện có & lưu qc_audit_report.json
  promote-take      Promote a self-reviewed passing take into the canonical clip/strip/audit
  run-pool          Điều phối Headless đa tài khoản chạy đủ toàn bộ phim + tự retry lỗi
  assemble          Hậu kỳ 1080p @ 24fps, Tag nhân vật, Hòa âm 4 tầng & EBU R128 2-Pass
"""

import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from .core.account_manager import AccountManager
    from .core.animatic_builder import AnimaticBuilder
    from .core.batch_packager import BatchPackager, ShotItem
    from .core.config import PROJECTS_DIR
    from .core.delivery_packager import DeliveryPackager
    from .core.film_qc_engine import FilmQCEngine
    from .core import send_halt
    from .core.headless_muse_client import (
        GenerationFailedException,
        HeadlessMuseClient,
        QuotaExceededException,
        SessionInvalidException,
    )
    from .core.keyframe_composer import KeyframeComposer
    from .core.lane_leases import LeaseRegistry
    from .core.master_assembler import MasterAssembler
    from .core.autoprod_orchestrator import SessionConflictError, SessionLock, _render_fingerprint, _write_json_atomic
    from .core.parallel_pool_engine import BATCH_FINGERPRINTS_FILE, ParallelPoolEngine
    from .core.screenplay_compiler import ScreenplayCompiler
    from .core.srt_normalizer import SRTNormalizer
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from core.account_manager import AccountManager
    from core.animatic_builder import AnimaticBuilder
    from core.batch_packager import BatchPackager, ShotItem
    from core.config import PROJECTS_DIR
    from core.delivery_packager import DeliveryPackager
    from core.film_qc_engine import FilmQCEngine
    from core import send_halt
    from core.headless_muse_client import (
        GenerationFailedException,
        HeadlessMuseClient,
        QuotaExceededException,
        SessionInvalidException,
    )
    from core.keyframe_composer import KeyframeComposer
    from core.lane_leases import LeaseRegistry
    from core.master_assembler import MasterAssembler
    from core.autoprod_orchestrator import SessionConflictError, SessionLock, _render_fingerprint, _write_json_atomic
    from core.parallel_pool_engine import BATCH_FINGERPRINTS_FILE, ParallelPoolEngine
    from core.screenplay_compiler import ScreenplayCompiler
    from core.srt_normalizer import SRTNormalizer


def _load_manifest_and_bible(project_dir: Path) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    manifest_p = project_dir / "shots_manifest.json"
    if not manifest_p.exists():
        raise FileNotFoundError(f"Chưa có {manifest_p}. Hãy chạy lệnh `compile` trước.")
    manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
    sb_p = project_dir / "story_bible.json"
    bible = json.loads(sb_p.read_text(encoding="utf-8")) if sb_p.exists() else None
    return manifest, bible


def _clip_integrity_bad(clip: Path, qc_rec: Optional[Dict[str, Any]] = None) -> bool:
    """True when a batch clip failed (or fails) its receipt SHA-256: listed in the batch's `integrity_failed.json`,
    quarantined, or its content differs from the receipt (older batches unpacked before quarantine existed). A
    canonical copy (`<project>/verified_clips/<sid>.mp4`) is judged through its audit record `qc_rec`: the copy's SHA
    must match the recorded one and the source batch clip must pass this same check."""
    clip = Path(clip)
    bdir = _batch_dir_of(clip)
    if bdir is None:
        if BatchPackager.clip_currently_excluded(clip, qc_rec):
            return True
        for key in ("clip_path", "source_clip_path"):  # the source batch clip, and the recorded provenance of a copy
            src = qc_rec.get(key) if isinstance(qc_rec, dict) else None
            if src and _batch_dir_of(Path(src)) is not None and _clip_integrity_bad(Path(src)):
                return True
        return False
    list_ok, excluded = BatchPackager.read_integrity_failed(bdir)
    if not list_ok:
        return True  # the exclusion list exists but cannot be read or has a bad schema: fail closed
    if clip.name in excluded:
        return True
    if not clip.exists():
        return (bdir / "integrity_failed" / clip.name).exists()
    want = BatchPackager.receipt_sha_by_file(clip.parent).get(clip.stem)
    return bool(want) and _file_sha256(clip) != want


def _discover_all_clip_candidates(
    project_dir: Path,
    manifest: Dict[str, Any],
    prefer_canonical: bool = True,
) -> Dict[str, List[Path]]:
    """Thu thập toàn bộ ứng viên MP4 không trùng lặp cho mỗi `shot_id` theo thứ tự ưu tiên."""
    shots = manifest.get("shots", [])
    cand_map: Dict[str, List[Path]] = {}
    seen_resolved: Dict[str, set] = {}

    def _add_candidate(sid: str, path: Path) -> None:
        if not path.exists() or path.stat().st_size < 100 * 1024:
            return
        res_str = str(path.resolve())
        seen = seen_resolved.setdefault(sid, set())
        if res_str in seen:
            return
        seen.add(res_str)
        cand_map.setdefault(sid, []).append(path)

    def _scan_batch_dir(bdir: Path) -> None:
        vdir = bdir / "verified_clips"
        if not vdir.exists():
            return
        batch_manifest_json = next(iter(sorted(bdir.glob("*_manifest.json"))), None)
        slot_to_shot: Dict[str, str] = {}
        if batch_manifest_json:
            bm = json.loads(batch_manifest_json.read_text(encoding="utf-8"))
            for entry in bm.get("shots", []):
                if entry.get("slot_id") and entry.get("shot_id"):
                    slot_to_shot[entry["slot_id"]] = entry["shot_id"]
        else:
            m_num = re.search(r"(\d+)$", bdir.name)
            if m_num:
                b_num = int(m_num.group(1))
                start_idx = (b_num - 1) * 6
                for slot_i in range(1, 7):
                    if start_idx + slot_i - 1 < len(shots):
                        slot_to_shot[f"shot_{slot_i:02d}"] = shots[start_idx + slot_i - 1]["shot_id"]

        for mp4 in sorted(vdir.glob("*.mp4")):
            stem = mp4.stem
            target_sid = slot_to_shot.get(stem)
            if not target_sid and any(s["shot_id"] == stem for s in shots):
                target_sid = stem
            if target_sid and not _clip_integrity_bad(mp4):
                _add_candidate(target_sid, mp4)

    def _scan_canonical() -> None:
        canonical_dir = project_dir / "verified_clips"
        if canonical_dir.exists():
            for s in shots:
                sid = s["shot_id"]
                _add_candidate(sid, canonical_dir / f"{sid}.mp4")

    def _scan_batches_v2() -> None:
        batches_v2_dir = project_dir / "BATCHES_V2"
        if batches_v2_dir.exists():
            for bdir in sorted(
                (p for p in batches_v2_dir.iterdir() if p.is_dir()),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            ):
                _scan_batch_dir(bdir)

    if prefer_canonical:
        _scan_canonical()
        _scan_batches_v2()
    else:
        _scan_batches_v2()
        _scan_canonical()

    batches_dir = project_dir / "BATCHES"
    if batches_dir.exists():
        for bdir in sorted(p for p in batches_dir.iterdir() if p.is_dir()):
            _scan_batch_dir(bdir)

    return cand_map


def _discover_existing_clip_map(project_dir: Path, manifest: Dict[str, Any]) -> Dict[str, Path]:
    """Ánh xạ `shot_id -> path.mp4` ưu tiên `BATCHES_V2` (mới nhất) -> `verified_clips/` -> `BATCHES/`."""
    cand_map = _discover_all_clip_candidates(project_dir, manifest, prefer_canonical=False)
    return {sid: paths[0] for sid, paths in cand_map.items() if paths}


def sync_project_to_web_ui(
    project_dir: Path,
    project_id: Optional[str] = None,
) -> Optional[Path]:
    """Đồng bộ tiến độ dự án `shots_manifest.json` & `qc_audit_report.json` lên Web UI Muse Studio."""
    project_dir = Path(project_dir)
    if project_id is None:
        try:
            if project_dir.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
                return None
        except Exception:
            pass
        if project_dir.name == "BLACK_PILOT_EXTENDED_FEATURE_FILM":
            project_id = "proj_black_pilot_160"
        else:
            project_id = "proj_" + hashlib.md5(str(project_dir.resolve()).encode()).hexdigest()[:8]

    manifest_p = project_dir / "shots_manifest.json"
    if not manifest_p.exists():
        raise FileNotFoundError(f"Chưa có {manifest_p}")
    manifest = json.loads(manifest_p.read_text(encoding="utf-8"))

    audit_p = project_dir / "qc_audit_report.json"
    passed_clips: Dict[str, str] = {}
    if audit_p.exists():
        _audit = json.loads(audit_p.read_text(encoding="utf-8"))
        _recs = _audit.get("per_shot_qc") or {}
        passed_clips = {
            sid: p for sid, p in (_audit.get("passed_clips") or {}).items()
            if not (p and _clip_integrity_bad(Path(p), _recs.get(sid)))
        }

    dest_dir = PROJECTS_DIR / project_id
    clips_dir = dest_dir / "clips"
    refs_dir = dest_dir / "refs"
    clips_dir.mkdir(parents=True, exist_ok=True)
    refs_dir.mkdir(parents=True, exist_ok=True)

    def _mirror_media(src: Path, dst: Path) -> Path:
        if src.resolve() == dst.resolve():
            return dst
        if dst.exists():
            try:
                if dst.stat().st_ino == src.stat().st_ino and dst.stat().st_size == src.stat().st_size:
                    return dst
            except Exception:
                pass
            dst.unlink()
        try:
            os.link(src, dst)
        except Exception:
            shutil.copyfile(src, dst)
        return dst

    now_iso = datetime.now().isoformat()
    ui_shots: List[Dict[str, Any]] = []
    completed = 0
    for idx, s in enumerate(manifest.get("shots", []), start=1):
        sid = s["shot_id"]
        cpath = passed_clips.get(sid)
        is_done = bool(cpath and Path(cpath).exists())
        ui_clip_path: Optional[str] = None
        if is_done and cpath:
            completed += 1
            mirrored_clip = _mirror_media(Path(cpath), clips_dir / f"{sid}.mp4")
            ui_clip_path = str(mirrored_clip)

        ui_refs: List[str] = []
        ff = s.get("first_frame_path")
        if ff and Path(ff).exists():
            ff_p = Path(ff)
            mirrored_ref = _mirror_media(ff_p, refs_dir / ff_p.name)
            ui_refs = [str(mirrored_ref)]

        ui_shots.append({
            "id": sid,
            "order": s.get("order", idx),
            "prompt": s.get("compiled_prompt", ""),
            "dialogue": s.get("dialogue"),
            "reference_images": ui_refs,
            "status": "COMPLETED" if is_done else "PENDING",
            "assigned_account": None,
            "progress": 100 if is_done else 0,
            "output_clip": ui_clip_path,
            "last_frame_path": None,
            "error": None,
            "updated_at": now_iso,
        })

    proj_file = dest_dir / "project.json"
    prev_created = now_iso
    if proj_file.exists():
        try:
            prev_created = json.loads(proj_file.read_text(encoding="utf-8")).get("created_at", now_iso)
        except Exception:
            pass

    proj_data = {
        "id": project_id,
        "name": manifest.get("project_title") or project_dir.name,
        "mode": "batch_parallel",
        "status": "COMPLETED" if completed == len(ui_shots) and ui_shots else ("PAUSED" if completed > 0 else "IDLE"),
        "created_at": prev_created,
        "updated_at": now_iso,
        "shots": ui_shots,
        "total_shots": len(ui_shots),
        "completed_shots": completed,
    }
    proj_file.write_text(json.dumps(proj_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return proj_file


def cmd_accounts_import(args) -> int:
    mgr = AccountManager()
    raw = Path(args.source).read_text(encoding="utf-8") if Path(args.source).exists() else args.source
    res = mgr.bulk_import_accounts(raw)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


def cmd_accounts_verify(args) -> int:
    mgr = AccountManager()
    accounts = mgr.list_accounts()
    if args.account_id:
        accounts = [a for a in accounts if a["id"] == args.account_id]
    else:
        # A bulk verify opens every profile: leave accounts held by a production lane alone.
        leased = LeaseRegistry().live_leases()
        for a in accounts:
            if a["id"] in leased:
                print(f"[*] Bỏ qua {a['id']}: đang thuộc lane {leased[a['id']].get('lane_id')}")
        accounts = [a for a in accounts if a["id"] not in leased]
    results = {}
    for acc in accounts:
        aid = acc["id"]
        print(f"[*] Xác thực headless {aid} ({acc.get('email') or acc.get('name')})...")
        results[aid] = mgr.auto_login_and_verify(aid)
        usage_summary = (results[aid].get("usage_info") or {}).get("summary")
        extra = f" | Hạn mức: {usage_summary}" if usage_summary else ""
        print(f"    -> {results[aid].get('status')}: {results[aid].get('message')}{extra}")
        if results[aid].get("status") == "BLOCKED":
            # Stop at the first block: no further account touches Muse; the halt is machine-wide (the login
            # detector already published it; publishing again is a no-op that keeps the first record).
            info = send_halt.halt_info(Exception(results[aid].get("message") or "BLOCKED at login"), aid, "LOGIN")
            send_halt.publish_halt(info)
            send_halt.finish_publication()
            print(send_halt.halted_line(info), file=sys.stderr)
            return send_halt.HALTED_EXIT_CODE
    ready_count = sum(1 for r in results.values() if r.get("status") == "READY")
    print(f"[+] Tổng kết Pool: {ready_count}/{len(results)} tài khoản READY.")
    return 0 if ready_count > 0 else 1


def cmd_accounts_redeem(args) -> int:
    mgr = AccountManager()
    accounts = mgr.list_accounts()
    if args.account_id:
        accounts = [a for a in accounts if a["id"] == args.account_id]
    results = {}
    for acc in accounts:
        aid = acc["id"]
        print(f"[*] Nhập mã mời '{args.code}' cho {aid} ({acc.get('email') or acc.get('name')})...")
        res = mgr.redeem_invite_code(aid, args.code)
        results[aid] = res
        print(f"    -> {res.get('status')}: {res.get('message')}")
    ready_count = sum(1 for r in results.values() if r.get("status") == "READY")
    print(f"[+] Sau Redeem '{args.code}': {ready_count}/{len(results)} tài khoản READY.")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0 if ready_count > 0 else 1


def cmd_compile(args) -> int:
    pdir = Path(args.project_dir)
    j_out, c_out, manifest = ScreenplayCompiler.compile_project_dir(
        project_dir=pdir,
        beats_path=Path(args.beats) if args.beats else None,
        audio_mode=args.audio_mode,
        strict_bible=not args.no_strict_bible,
        cinematic_cutaways=bool(getattr(args, "cinematic_cutaways", False)),
    )
    print(f"[+] Đã biên dịch {manifest['total_shots']} shots -> {j_out}")
    print(f"    CSV: {c_out}")
    if manifest["bible_warnings"]:
        print("[!] Bible warnings:", manifest["bible_warnings"])
    if manifest["coverage_warnings"]:
        print(f"[!] Coverage warnings ({len(manifest['coverage_warnings'])}):")
        for w in manifest["coverage_warnings"][:10]:
            print(f"    - {w}")
    return 0


def _resolve_srt_and_chapters(
    pdir: Path,
    bible: Optional[Dict[str, Any]],
    srt_arg: Optional[str] = None,
    chapters_arg: Optional[str] = None,
) -> Tuple[Optional[Path], Optional[Path]]:
    """Tìm file `.srt` và `chapters.txt` từ tham số CLI hoặc cấu hình `story_bible.json`."""
    def _pick(explicit: Optional[str], field: str) -> Optional[Path]:
        raw = explicit or ((bible or {}).get(field) if isinstance(bible, dict) else None)
        if not raw:
            return None
        p = Path(raw)
        return p if p.is_absolute() else (pdir / p)

    return _pick(srt_arg, "source_srt_path"), _pick(chapters_arg, "source_chapters_path")


def cmd_normalize_srt(args) -> int:
    data = SRTNormalizer.normalize_srt_to_beats_skeleton(
        srt_path=Path(args.srt),
        chapters_path=Path(args.chapters) if args.chapters else None,
        window_s=float(args.window),
    )
    out_txt = json.dumps(data, indent=2, ensure_ascii=False)
    if args.output:
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(out_txt, encoding="utf-8")
        print(f"[+] Normalized {data['total_beats']} beat skeletons ({data['story_end_s']}s) -> {out_p}")
    else:
        print(out_txt)
    return 0


def cmd_srt_audit(args) -> int:
    target = Path(args.target)
    if target.is_dir():
        pdir = target
        manifest, bible = _load_manifest_and_bible(pdir)
        payload = manifest
    else:
        pdir = target.parent
        sb_p = pdir / "story_bible.json"
        bible = json.loads(sb_p.read_text(encoding="utf-8")) if sb_p.exists() else None
        payload = json.loads(target.read_text(encoding="utf-8"))

    srt_p, ch_p = _resolve_srt_and_chapters(pdir, bible, args.srt, args.chapters)
    if not srt_p or not srt_p.exists():
        raise FileNotFoundError(f"Không tìm thấy file SRT nguồn để kiểm định ({srt_p}).")

    rep = SRTNormalizer.audit_srt_coverage(srt_p, payload, chapters_path=ch_p)
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    return 0 if rep["passed"] else 1


def cmd_preflight(args) -> int:
    pdir = Path(args.project_dir)
    manifest, bible = _load_manifest_and_bible(pdir)
    all_errors: List[Any] = []
    if bible:
        anchors_dir = pdir / "assets" / "anchors"
        b_errs = ScreenplayCompiler.validate_story_bible(bible, anchors_dir=anchors_dir, strict_files=True)
        for e in b_errs:
            all_errors.append({"shot_id": "STORY_BIBLE", "severity": "HARD", "error": e})

    ok_m, m_findings = FilmQCEngine.validate_manifest_preflight(manifest)
    all_errors.extend(m_findings)

    srt_coverage: Optional[Dict[str, Any]] = None
    srt_p, ch_p = _resolve_srt_and_chapters(
        pdir,
        bible,
        getattr(args, "srt", None),
        getattr(args, "chapters", None),
    )
    if getattr(args, "no_srt_gate", False):
        srt_gate = "SKIPPED_BY_FLAG"
    elif srt_p and srt_p.exists():
        srt_coverage = SRTNormalizer.audit_srt_coverage(srt_p, manifest, chapters_path=ch_p)
        for e in srt_coverage.get("errors", []):
            all_errors.append({"shot_id": "SRT_COVERAGE", "severity": "HARD", "error": e})
        srt_gate = "FAIL" if srt_coverage.get("errors") else "PASS"
    else:
        srt_gate = "NO_SRT"

    cov_warnings = list(manifest.get("coverage_warnings") or [])
    report_payload: Dict[str, Any] = {
        "passed": len(all_errors) == 0,
        "errors": all_errors,
        "warnings": cov_warnings,
        "srt_gate": srt_gate,
    }
    if srt_coverage is not None:
        report_payload["srt_coverage"] = srt_coverage

    report_p = pdir / "preflight_report.json"
    report_p.write_text(json.dumps(report_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[+] Preflight Report: {len(all_errors)} lỗi HARD | {len(cov_warnings)} cảnh báo DOP -> {report_p}")
    for item in all_errors[:15]:
        print(f"    [{item['severity']}] {item['shot_id']}: {item['error']}")
    for w in cov_warnings[:8]:
        print(f"    [DOP_WARNING] {w}")
    return 0 if len(all_errors) == 0 else 1


def _resolve_keyframes_lane(args):
    """Same lane resolution as `pool_runner`: `--lane`, else an open `<project_dir>/lane.json`."""
    try:
        from .pool_runner import _resolve_lane
    except ImportError:
        from pool_runner import _resolve_lane
    return _resolve_lane(args)


POOL_KEYFRAMES_CMD = "python -m muse_studio.pool_runner keyframes <project_dir> [--include-setups] [--include-turnarounds]"


def cmd_keyframes(args) -> int:
    pdir = Path(args.project_dir)
    if not args.simulate:
        # One production send path: the pool engine (keyframe ledger, machine-wide halt, leases, failover).
        print(json.dumps({
            "status": "REFUSED_USE_POOL_RUNNER",
            "message": "cli keyframes only runs with --simulate. Real keyframe sends go through the pool: "
                       + POOL_KEYFRAMES_CMD.replace("<project_dir>", str(pdir)),
        }, indent=2, ensure_ascii=False))
        return 2
    mgr = AccountManager()
    lane = _resolve_keyframes_lane(args)
    if lane is not None:
        # A lane uses its own leased accounts only (never another lane's, never a bulk verify of the pool).
        held = lane.renew()
        if args.simulate:
            ready_ids = sorted(a for a in held if a.startswith("sim_acc_"))
            if not ready_ids:
                ready_ids = [f"sim_acc_{i:02d}" for i in range(1, max(1, len(held)) + 1)]
        else:
            ready = {a["id"] for a in mgr.list_accounts() if a.get("status") == "READY"}
            ready_ids = sorted(a for a in held if a in ready)
        if not ready_ids:
            print(json.dumps({
                "status": "BLOCKED_NO_LANE_ACCOUNTS",
                "lane": lane.report(),
                "message": f"Lane {lane.lane_id} holds no READY account; renew or reopen the lane first.",
            }, indent=2, ensure_ascii=False))
            return 2
    else:
        leased = LeaseRegistry().live_leases()  # never touch accounts held by a production lane
        if args.simulate:
            ready_ids = ["sim_acc_01"]  # a dry run never selects a real account
        else:
            return 2  # unreachable: a real run was refused above

    client = HeadlessMuseClient(mgr)
    rep = asyncio.run(
        KeyframeComposer.generate_and_verify_keyframes(
            project_dir=pdir,
            account_ids=ready_ids,
            client=client,
            simulate=args.simulate,
            include_setups=bool(getattr(args, "include_setups", False)),
            include_turnarounds=bool(getattr(args, "include_turnarounds", False)),
        )
    )
    if lane is not None:
        lane.renew()
        rep["lane"] = lane.report()
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    return 0 if not rep.get("rejected") else 1


def cmd_animatic(args) -> int:
    pdir = Path(args.project_dir)
    out_p = Path(args.output) if args.output else None
    rep = AnimaticBuilder.build_animatic(project_dir=pdir, output_mp4=out_p, fps=int(args.fps))
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    return 0 if rep.get("success") else 1


_TAKE_SUFFIX_RE = re.compile(r"_T(\d+)(?:_FO\d+)*$")


def _batch_take(batch_name: str) -> int:
    """Take number from a pool batch id (`..._T<k>`, optionally `_FO<n>`); single-take batches are take 1."""
    m = _TAKE_SUFFIX_RE.search(batch_name)
    return int(m.group(1)) if m else 1


def _batch_dir_of(clip: Path) -> Optional[Path]:
    """`<project>/BATCHES_V2|BATCHES/<bid>/verified_clips/<x>.mp4` -> the batch dir (else None)."""
    clip = Path(clip)
    if clip.parent.name == "verified_clips" and clip.parent.parent.parent.name in ("BATCHES_V2", "BATCHES"):
        return clip.parent.parent
    return None


def _resolved(raw: Any) -> str:
    try:
        return str(Path(raw).resolve())
    except (OSError, TypeError, ValueError):
        return str(raw)


def _prev_candidate_index(prev: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Resolved clip path -> what an earlier audit / generation run knew about it (fingerprint, take, source)."""
    idx: Dict[str, Dict[str, Any]] = {}
    fps = prev.get("render_fingerprints") or {}
    passed = prev.get("passed_clips") or {}
    for sid, rec in (prev.get("per_shot_qc") or {}).items():
        rec = rec or {}
        for c in rec.get("candidates") or []:
            if c.get("clip_path"):
                idx.setdefault(_resolved(c["clip_path"]), dict(c))
        fp = fps.get(sid)
        if fp is None or sid not in passed:
            continue
        # The recorded winner: its source clip and its canonical copy carry the shot's recorded fingerprint.
        meta = {
            k: v for k, v in {
                "fingerprint": fp, "take": rec.get("take"), "clip_path": rec.get("clip_path"),
                "batch_id": rec.get("batch_id"),
            }.items() if v is not None
        }
        for raw in (rec.get("clip_path"), passed.get(sid)):
            if raw:
                idx.setdefault(_resolved(raw), {}).update(meta)
    return idx


def _candidate_info(sid: str, clip: Path, prev_idx: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Design fingerprint + take metadata of one clip candidate (None fingerprint = unknown, e.g. legacy batch)."""
    bdir = _batch_dir_of(clip)
    meta = prev_idx.get(_resolved(clip)) or {}
    fp = None
    if bdir is not None:
        side = bdir / BATCH_FINGERPRINTS_FILE
        if side.is_file():
            try:
                fp = (json.loads(side.read_text(encoding="utf-8")).get("shots") or {}).get(sid)
            except (OSError, ValueError, AttributeError):
                fp = None
    return {
        "fingerprint": fp or meta.get("fingerprint"),
        "take": _batch_take(bdir.name) if bdir is not None else meta.get("take"),
        "batch_id": bdir.name if bdir is not None else meta.get("batch_id"),
        "clip_path": str(clip) if bdir is not None else (meta.get("clip_path") or str(clip)),
        "strip_path": meta.get("strip_path"),
    }


def _file_sha256(path: Path) -> Optional[str]:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
    except OSError:
        return None
    return h.hexdigest()


def _copy_integrity_bad(cp: Path, info: Dict[str, Any], prev_rec: Dict[str, Any],
                        prev_idx: Dict[str, Dict[str, Any]]) -> bool:
    """True when a copy (e.g. the canonical clip) of a batch clip cannot be trusted.

    The copy is judged by its OWN SHA-256 against the recorded one (the source's batch receipt, else the SHA recorded
    by promote-take or an earlier audit), so an intact copy survives its source going missing or corrupt. Without any
    recorded SHA it inherits the source's integrity state."""
    src = info.get("clip_path")
    if not src or _resolved(src) == _resolved(cp):
        return False  # not a copy: batch clips are filtered by discovery
    # A copy whose content differs from the SHA the last audit / promote-take recorded for it has drifted: it is never
    # trusted just because its source batch is still clean (that would let qc-audit bless whatever sits there now).
    want_copy = prev_rec.get("copy_sha256")
    if want_copy and _file_sha256(cp) != want_copy:
        return True
    src_p = Path(src)
    if not _clip_integrity_bad(src_p):
        return False
    expected = None
    if _batch_dir_of(src_p) is not None:
        expected = BatchPackager.receipt_sha_by_file(src_p.parent).get(src_p.stem)
    if not expected and prev_rec.get("clip_path") and _resolved(prev_rec["clip_path"]) == _resolved(src):
        expected = prev_rec.get("sha256")
    if not expected:
        expected = (prev_idx.get(_resolved(src)) or {}).get("sha256")
    if expected:
        return _file_sha256(cp) != expected
    return True


def _quarantine_copy(cp: Path) -> Tuple[Optional[str], Optional[str]]:
    """Move an untrusted copy to `<dir>/integrity_failed/` (never deleted). Returns (new path, error)."""
    qdir = cp.parent / "integrity_failed"
    try:
        qdir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%y%m%d%H%M%S")
        dest = qdir / f"{cp.stem}_{stamp}{cp.suffix}"
        n = 1
        while dest.exists():
            dest = qdir / f"{cp.stem}_{stamp}_{n}{cp.suffix}"
            n += 1
        os.replace(cp, dest)
        return str(dest), None
    except OSError as e:
        return None, str(e)


def cmd_qc_audit(args) -> int:
    # Every project-state writer holds the project lock (generation, keyframes, qc-audit, promote-take).
    try:
        with SessionLock(Path(args.project_dir), session_tag="qc_audit"):
            return _qc_audit(args)
    except SessionConflictError as ce:
        print(f"[!] qc-audit refused: {ce}", file=sys.stderr)
        return 3


def _qc_audit(args) -> int:
    pdir = Path(args.project_dir)
    manifest, _ = _load_manifest_and_bible(pdir)
    cand_map = _discover_all_clip_candidates(pdir, manifest, prefer_canonical=True)

    canonical_dir = pdir / "verified_clips"
    canonical_dir.mkdir(parents=True, exist_ok=True)
    strips_dir = pdir / "qc_strips"
    strips_dir.mkdir(parents=True, exist_ok=True)

    audit_path = pdir / "qc_audit_report.json"
    prev_audit: Dict[str, Any] = {}
    if audit_path.exists():
        try:
            prev_audit = dict(json.loads(audit_path.read_text(encoding="utf-8")) or {})
        except (OSError, ValueError):
            prev_audit = {}
    prev_idx = _prev_candidate_index(prev_audit)

    shots = manifest.get("shots", [])
    # Only takes rendered for the CURRENT design may win. A shot with no fingerprint knowledge at all (legacy batches)
    # is audited as before, but its winner gets no fingerprint (the next generation run treats it as unproven).
    plans: Dict[str, List[Tuple[Path, Dict[str, Any]]]] = {}
    integrity_dropped: Dict[str, Dict[str, Any]] = {}
    shots_with_cands: List[Tuple[Dict[str, Any], List[Path], Optional[Path], float]] = []
    for shot in shots:
        sid = shot["shot_id"]
        cands = [p for p in cand_map.get(sid, []) if p.exists()]
        if not cands:
            continue
        current = {_render_fingerprint(shot, False), _render_fingerprint(shot, True)}
        infos = []
        for cp in cands:
            info = _candidate_info(sid, cp, prev_idx)
            prev_rec = (prev_audit.get("per_shot_qc") or {}).get(sid) or {}
            if _copy_integrity_bad(cp, info, prev_rec, prev_idx):
                # A copy (e.g. the canonical clip) whose own SHA-256 is not the recorded one: quarantined, not audited.
                moved, err = _quarantine_copy(cp)
                integrity_dropped[sid] = {"quarantined_to": moved} if moved else {"quarantine_error": err}
                if prev_rec.get("copy_sha256") and info["clip_path"] != str(cp):
                    integrity_dropped[sid]["cause"] = "CANONICAL_SHA_MISMATCH"
                continue
            fp = info["fingerprint"]
            info["fingerprint_status"] = "current" if fp in current else ("stale" if fp else "unknown")
            infos.append((cp, info))
        plans[sid] = infos
        known = any(i["fingerprint_status"] != "unknown" for _, i in infos)
        eligible = [cp for cp, i in infos if i["fingerprint_status"] == "current" or not known]
        if eligible:
            strip_p = (strips_dir / f"{sid}_strip.jpg") if args.strips else None
            min_dur = 2.5 if shot.get("duration_s", 10.0) <= 5.5 else 3.0
            shots_with_cands.append((shot, eligible, strip_p, min_dur))

    if len(shots_with_cands) > 1 and any(
        len((s.get("dialogue") or s.get("dialogue_text") or "").strip()) > 3
        for s, _, _, _ in shots_with_cands
    ):
        FilmQCEngine.get_whisper_model()

    eval_map: Dict[str, Tuple[Optional[Path], Dict[str, Any], List[Dict[str, Any]]]] = {}
    if len(shots_with_cands) > 1:
        max_w = min(4, max(2, os.cpu_count() or 2), len(shots_with_cands))
        with ThreadPoolExecutor(max_workers=max_w) as pool:
            futs = {
                s["shot_id"]: pool.submit(
                    FilmQCEngine.select_best_candidate,
                    cands,
                    s,
                    min_duration_s=min_dur,
                    strip_output_path=strip_p,
                )
                for s, cands, strip_p, min_dur in shots_with_cands
            }
            for sid, fut in futs.items():
                eval_map[sid] = fut.result()
    else:
        for s, cands, strip_p, min_dur in shots_with_cands:
            eval_map[s["shot_id"]] = FilmQCEngine.select_best_candidate(
                cands,
                s,
                min_duration_s=min_dur,
                strip_output_path=strip_p,
            )

    passed_clips: Dict[str, str] = {}
    failed_or_missing: List[Dict[str, Any]] = []
    per_shot: Dict[str, Any] = {}
    render_fingerprints: Dict[str, str] = {}

    for shot in shots:
        sid = shot["shot_id"]
        infos = plans.get(sid)
        if not infos:
            if sid in integrity_dropped:
                dropped = dict(integrity_dropped[sid])
                failed_or_missing.append({"shot_id": sid, "reason": "INTEGRITY_FAILED",
                                          "defects": ["Clip SHA-256 differs from the recorded SHA-256"], **dropped})
                continue
            failed_or_missing.append({"shot_id": sid, "reason": "MISSING_CLIP", "defects": ["Chưa có file MP4"]})
            continue

        passed_cpath, best_res, all_res = eval_map.get(sid, (None, None, []))
        res_by_path = {_resolved(r.get("candidate_path")): r for r in all_res or []}
        candidates = []
        sha_by_cp: Dict[str, Optional[str]] = {}
        for cp, info in infos:
            r = res_by_path.get(_resolved(cp))
            sha_by_cp[_resolved(cp)] = _file_sha256(cp)
            candidates.append({
                "candidate_path": str(cp),
                "clip_path": info["clip_path"],
                "take": info["take"],
                "batch_id": info["batch_id"],
                "verdict": (r or {}).get("verdict", "NOT_EVALUATED"),
                "quality_score": float(((r or {}).get("metrics") or {}).get("quality_score") or 0.0),
                "defects": list((r or {}).get("defects") or []),
                "metrics": dict((r or {}).get("metrics") or {}),
                "fingerprint": info["fingerprint"],
                "fingerprint_status": info["fingerprint_status"],
                "strip_path": info["strip_path"],
                # Content hash at audit time: promote-take only substitutes a copy that still matches it.
                "sha256": sha_by_cp[_resolved(cp)],
            })

        stale_canonical = canonical_dir / f"{sid}.mp4"
        if best_res is None:
            # Every take was rendered for an older design: nothing may be kept.
            defects = ["Only takes of an older design exist (render fingerprint mismatch): render the current design."]
            per_shot[sid] = {
                "verdict": "REJECT", "defect_code": "STALE_RENDER", "defects": defects, "candidates": candidates,
            }
            if stale_canonical.exists():
                stale_canonical.unlink()
            failed_or_missing.append({"shot_id": sid, "reason": "STALE_RENDER", "defects": defects})
            continue

        # A take chosen by `promote-take` stays the shot's take while it still passes for the current design.
        prev_rec = (prev_audit.get("per_shot_qc") or {}).get(sid) or {}
        kept_promotion: Dict[str, Any] = {}
        if prev_rec.get("selected_by") == "promote-take" and prev_rec.get("clip_path"):
            want = _resolved(prev_rec["clip_path"])
            want_sha = prev_rec.get("sha256")

            def _is_promoted(cp: Path, info: Dict[str, Any]) -> bool:
                if _resolved(cp) == want:
                    return True
                # A copy (the canonical clip) of the promoted source, proven by the recorded SHA-256.
                return bool(want_sha) and _resolved(info["clip_path"]) == want and sha_by_cp.get(_resolved(cp)) == want_sha

            ordered = sorted(infos, key=lambda ci: _resolved(ci[0]) != want)  # the source itself first
            for cp, info in ordered:
                r = res_by_path.get(_resolved(cp))
                if (_is_promoted(cp, info) and r and r.get("verdict") == "PASS"
                        and info["fingerprint_status"] == "current"):
                    passed_cpath, best_res = cp, r
                    kept_promotion = {k: prev_rec[k] for k in ("selected_by", "promoted_at", "previous_take",
                                                                 "previous_clip_path", "sha256", "source_clip_path",
                                                                 "copy_source_path") if k in prev_rec}
                    strip_p = (strips_dir / f"{sid}_strip.jpg") if args.strips else None
                    if strip_p is not None:
                        try:
                            if not FilmQCEngine.generate_qc_strip(cp, strip_p, label_prefix=sid) and strip_p.exists():
                                strip_p.unlink()
                        except Exception:
                            if strip_p.exists():
                                strip_p.unlink()
                    break

        chosen = passed_cpath or Path(best_res.get("candidate_path") or infos[-1][0])
        chosen_info = next((i for cp, i in infos if _resolved(cp) == _resolved(chosen)), infos[-1][1])
        per_shot[sid] = {
            **best_res,
            "take": chosen_info["take"],
            "clip_path": chosen_info["clip_path"],
            "batch_id": chosen_info["batch_id"],
            "fingerprint": chosen_info["fingerprint"],
            **kept_promotion,
            "candidates": candidates,
        }
        if passed_cpath is not None:
            dest = canonical_dir / f"{sid}.mp4"
            copied_now = passed_cpath.resolve() != dest.resolve()
            if copied_now:
                shutil.copyfile(passed_cpath, dest)
            passed_clips[sid] = str(dest)
            # A later reader re-checks the copy against this. Only a copy made NOW from a verified source gets a new
            # SHA; an existing canonical that won keeps the SHA recorded for it (its match was checked above).
            per_shot[sid]["copy_sha256"] = (
                prev_rec.get("copy_sha256") if not copied_now and prev_rec.get("copy_sha256") else _file_sha256(dest))
            if chosen_info["fingerprint_status"] == "current":
                render_fingerprints[sid] = chosen_info["fingerprint"]
        else:
            if stale_canonical.exists():
                stale_canonical.unlink()
            failed_or_missing.append({
                "shot_id": sid,
                "reason": "QC_REJECT",
                "clip_path": chosen_info["clip_path"],
                "defects": best_res.get("defects", []),
            })

    audit_data = {
        "total_shots": len(shots),
        "passed_count": len(passed_clips),
        "failed_or_missing_count": len(failed_or_missing),
        "passed_clips": passed_clips,
        "failed_or_missing": failed_or_missing,
        "per_shot_qc": per_shot,
        # Fingerprint of each kept clip, taken from the winning take itself (never inherited per shot).
        "render_fingerprints": render_fingerprints,
    }
    audit_path.write_text(json.dumps(audit_data, indent=2, ensure_ascii=False), encoding="utf-8")
    sync_project_to_web_ui(pdir)

    print(
        f"[+] 5-Gate QC Audit: PASS {audit_data['passed_count']}/{audit_data['total_shots']} "
        f"| Cần render/bù: {audit_data['failed_or_missing_count']} -> {audit_path}"
    )
    return 0


def cmd_promote_take(args) -> int:
    """Make a self-reviewed passing take the shot's canonical clip, strip and audit record (read by `assemble`)."""
    try:
        with SessionLock(Path(args.project_dir), session_tag="promote_take"):
            return _promote_take(args)
    except SessionConflictError as ce:
        print(json.dumps({"success": False, "error": "PROJECT_LOCKED", "message": str(ce)}, indent=2,
                         ensure_ascii=False))
        return 3


def _promote_take(args) -> int:
    pdir = Path(args.project_dir)
    sid = args.shot_id

    def _fail(code: str, message: str, **extra: Any) -> int:
        print(json.dumps({"success": False, "error": code, "message": message, **extra}, indent=2,
                         ensure_ascii=False))
        return 1

    manifest, _ = _load_manifest_and_bible(pdir)
    shot = next((s for s in manifest.get("shots", []) if s.get("shot_id") == sid), None)
    if shot is None:
        return _fail("UNKNOWN_SHOT", f"{sid} is not in shots_manifest.json")
    audit_path = pdir / "qc_audit_report.json"
    if not audit_path.exists():
        return _fail("NO_AUDIT", f"{audit_path} not found: run the generation step and qc-audit first")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    rec = dict((audit.get("per_shot_qc") or {}).get(sid) or {})
    cands = list(rec.get("candidates") or [])
    available = sorted({c.get("take") for c in cands if c.get("take") is not None})

    sel = str(args.take).strip()
    if sel.isdigit():
        matches = [c for c in cands if c.get("take") == int(sel)]
    else:
        target = _resolved(sel)
        matches = [c for c in cands if target in (_resolved(c.get("clip_path")), _resolved(c.get("candidate_path")))]
    uniq: Dict[str, Dict[str, Any]] = {}
    for c in matches:
        uniq.setdefault(_resolved(c.get("clip_path") or c.get("candidate_path")), c)
    if not uniq:
        return _fail("TAKE_NOT_FOUND", f"No take {sel!r} recorded for {sid}", available_takes=available)
    passing = [c for c in uniq.values() if c.get("verdict") == "PASS"]
    if not passing:
        return _fail("TAKE_NOT_PASSING", f"Take {sel!r} of {sid} did not pass FilmQC: only passing takes are promoted")
    current = {_render_fingerprint(shot, False), _render_fingerprint(shot, True)}
    valid = [c for c in passing if c.get("fingerprint") in current]
    if not valid:
        if any(not c.get("fingerprint") for c in passing):
            # A legacy batch (no render fingerprint) cannot prove it matches the current design.
            return _fail(
                "TAKE_UNPROVEN",
                f"Take {sel!r} of {sid} has no render fingerprint (legacy batch), so it cannot be proven to match "
                f"the current design. Migration path: render the shot again with `pool_runner videos` (new batches "
                f"carry fingerprints), run `cli qc-audit`, then promote one of the new takes.",
            )
        return _fail("TAKE_STALE", f"Take {sel!r} of {sid} was rendered for an older design")
    if len(valid) > 1:
        return _fail("AMBIGUOUS_TAKE", f"Several passing takes match {sel!r}: pass the clip path instead",
                     options=[c.get("clip_path") for c in valid])
    chosen = valid[0]

    # The audit record may be stale: re-check the CURRENT exclusion list / receipt before picking or copying any
    # candidate. Nothing is deleted or moved here.
    for raw in (chosen.get("clip_path"), chosen.get("candidate_path")):
        if raw and _clip_integrity_bad(Path(raw)):
            return _fail(
                "CLIP_INTEGRITY_FAILED",
                f"The clip of take {sel!r} of {sid} is excluded or fails its batch receipt SHA-256 "
                f"(integrity_failed.json): it cannot be promoted. Nothing was copied or deleted.",
                clip_path=raw,
            )

    def _source_of(c: Dict[str, Any]) -> Optional[Path]:
        # The immutable batch clip, or a copy whose content hash proves it is this take (never the mutable canonical
        # file on trust: it may hold another take by now).
        want = c.get("sha256")
        for raw in (c.get("clip_path"), c.get("candidate_path")):
            if not raw or not Path(raw).is_file():
                continue
            if want:
                if _file_sha256(Path(raw)) == want:
                    return Path(raw)
            elif _batch_dir_of(Path(raw)) is not None:
                return Path(raw)
        return None

    src = _source_of(chosen)
    if src is not None and _clip_integrity_bad(src):
        return _fail("CLIP_INTEGRITY_FAILED", f"The clip of take {sel!r} of {sid} is excluded or fails its batch "
                                              f"receipt SHA-256: it cannot be promoted.", clip_path=str(src))
    if src is None:
        return _fail("CLIP_MISSING", f"The clip of take {sel!r} is no longer on disk (or no longer matches its audit "
                                     f"hash)", clip_path=chosen.get("clip_path"))

    dest = pdir / "verified_clips" / f"{sid}.mp4"
    # Provenance = the batch clip this take came from. `src` (the file copied) may be a copy of it (the canonical clip,
    # when the batch clip is gone): then the record must still name the batch, or a later exclusion of that batch would
    # no longer reach the new record. No batch provenance = no promotion (fail closed).
    raw_prov = chosen.get("source_clip_path") or chosen.get("clip_path")
    if raw_prov and _batch_dir_of(Path(raw_prov)) is not None:
        prov: Optional[Path] = Path(raw_prov)
    elif _batch_dir_of(src) is not None:
        prov = src
    elif raw_prov and _resolved(raw_prov) == _resolved(src) and src.resolve() != dest.resolve():
        prov = src  # a legacy original outside any batch (never the mutable canonical file itself)
    else:
        prov = None
    if prov is None:
        return _fail("PROVENANCE_UNKNOWN",
                     f"Take {sel!r} of {sid} cannot be traced to a batch clip (the audit record names no batch source "
                     f"and the only copy left is the canonical file): it cannot be promoted. Nothing was copied.",
                     clip_path=chosen.get("clip_path"))
    if _clip_integrity_bad(prov):
        return _fail("CLIP_INTEGRITY_FAILED", f"The source batch clip of take {sel!r} of {sid} is excluded or fails its "
                                              f"receipt SHA-256: it cannot be promoted.", clip_path=str(prov))
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dest.resolve():
        shutil.copyfile(src, dest)
    canonical_strip = pdir / "qc_strips" / f"{sid}_strip.jpg"
    canonical_strip.parent.mkdir(parents=True, exist_ok=True)
    strip_raw = chosen.get("strip_path")
    strip_out: Optional[str] = None
    if strip_raw and Path(strip_raw).is_file() and Path(strip_raw).resolve() != canonical_strip.resolve():
        # The take's own strip; the canonical strip itself is never trusted (it may belong to another take).
        shutil.copyfile(strip_raw, canonical_strip)
        strip_out = str(canonical_strip)
    else:
        try:
            made = FilmQCEngine.generate_qc_strip(src, canonical_strip, label_prefix=sid)
            strip_out = str(made) if made else None
        except Exception:
            strip_out = None
        if strip_out is None and canonical_strip.exists():
            canonical_strip.unlink()  # never leave another take's strip under the canonical name

    new_rec = {
        "verdict": "PASS",
        "defects": list(chosen.get("defects") or []),
        "metrics": dict(chosen.get("metrics") or {"quality_score": chosen.get("quality_score", 0.0)}),
        "take": chosen.get("take"),
        "clip_path": str(prov),
        "source_clip_path": str(prov),  # provenance: exclusion checks always go through this batch clip
        "copy_source_path": str(src),  # the file that was actually copied (may be a copy of the source)
        "candidate_path": chosen.get("candidate_path") or str(src),
        "batch_id": chosen.get("batch_id"),
        "fingerprint": chosen.get("fingerprint"),
        "sha256": chosen.get("sha256"),
        "copy_sha256": _file_sha256(dest),
        "selected_by": "promote-take",
        "promoted_at": datetime.now().isoformat(timespec="seconds"),
        "previous_take": rec.get("take"),
        "previous_clip_path": rec.get("clip_path"),
        "candidates": cands,
    }
    audit.setdefault("per_shot_qc", {})[sid] = new_rec
    audit.setdefault("passed_clips", {})[sid] = str(dest)
    fps = audit.setdefault("render_fingerprints", {})
    if chosen.get("fingerprint"):
        fps[sid] = chosen["fingerprint"]
    else:
        fps.pop(sid, None)
    audit["failed_or_missing"] = [f for f in audit.get("failed_or_missing") or [] if f.get("shot_id") != sid]
    audit["passed_count"] = len(audit["passed_clips"])
    audit["failed_or_missing_count"] = len(audit["failed_or_missing"])
    _write_json_atomic(audit_path, audit)
    print(json.dumps({
        "success": True,
        "promoted": {"shot_id": sid, "take": chosen.get("take"), "clip_path": str(prov), "copy_source": str(src),
                     "canonical": str(dest),
                     "strip": strip_out, "previous_take": rec.get("take")},
    }, indent=2, ensure_ascii=False))
    return 0


def cmd_package(args) -> int:
    pdir = Path(args.project_dir)
    manifest, _ = _load_manifest_and_bible(pdir)
    audit_path = pdir / "qc_audit_report.json"
    if audit_path.exists():
        audit_data = json.loads(audit_path.read_text(encoding="utf-8"))
        done_ids = {
            sid for sid, p in audit_data.get("passed_clips", {}).items()
            if Path(p).exists() and not _clip_integrity_bad(Path(p), (audit_data.get("per_shot_qc") or {}).get(sid))
        }
    else:
        done_ids = set(_discover_existing_clip_map(pdir, manifest).keys())

    pending_items: List[ShotItem] = []
    for s in manifest.get("shots", []):
        sid = s["shot_id"]
        if not args.all and sid in done_ids:
            continue
        ff = Path(s["first_frame_path"])
        pending_items.append(
            ShotItem(
                shot_id=sid,
                prompt=s["compiled_prompt"],
                first_frame_path=ff,
                duration_s=float(s.get("duration_s", 10.0)),
                dialogue=s.get("dialogue") or "",
                speaker=s.get("speaker") or "",
                audio_mode=s.get("audio_mode") or "NATIVE_DIALOGUE",
                extra_refs=[Path(r) for r in (s.get("extra_refs") or []) if r and Path(r).exists()],
            )
        )

    out_root = pdir / "BATCHES_V2"
    batches = []
    for idx in range(0, len(pending_items), 6):
        chunk = pending_items[idx : idx + 6]
        bnum = (idx // 6) + 1
        bid = f"{args.batch_prefix}_{bnum:02d}"
        zp, _ = BatchPackager.create_batch_handoff(bid, chunk, out_root / bid)
        batches.append((bid, str(zp), len(chunk)))

    print(f"[+] Đã đóng gói {len(pending_items)} shots thành {len(batches)} batches tại {out_root}")
    return 0


def _sorted_ready_account_ids(mgr: AccountManager) -> List[str]:
    """Lấy danh sách tài khoản READY ưu tiên tổng hạn mức (weekly + bonus) còn lại cao nhất trước."""
    accs = [a for a in mgr.list_accounts() if a.get("status") == "READY"]
    accs.sort(
        key=AccountManager.get_effective_quota_pct,
        reverse=True,
    )
    return [a["id"] for a in accs]


def cmd_run_pool(args) -> int:
    """Ủy quyền điều phối sang `ParallelPoolEngine` (SessionLock + BusyAccountDetector + Dynamic Nx6 Queue + Self-Heal)."""
    pdir = Path(args.project_dir)
    mgr = AccountManager()
    engine = ParallelPoolEngine(account_manager=mgr, sync_ui=True)
    res = engine.run_videos(
        project_dir=pdir,
        max_accounts=getattr(args, "max_accounts", None),
        max_rounds=int(args.max_rounds),
        auto_repair=not bool(getattr(args, "no_auto_repair", False)),
        simulate=bool(args.simulate),
        session_tag="cli_run_pool",
    )
    if res["status"] == "HALTED":
        res["halt_publication"] = send_halt.finish_publication() or "ALREADY_HALTED"
        print(json.dumps({k: res.get(k) for k in ("status", "halted", "halt_publication", "message")},
                         indent=2, ensure_ascii=False))
        print(send_halt.halted_line(res.get("halted")), file=sys.stderr)
        return send_halt.HALTED_EXIT_CODE
    print(
        f"[+] KẾT THÚC RUN-POOL ({res['status']}): "
        f"Đạt {res['passed_count']}/{res['total_shots']} shots. "
        f"Còn thiếu: {len(res['remaining_shot_ids'])}"
    )
    if res["status"] == "COMPLETED":
        return 0
    if res["status"] == "INTEGRITY_UNPERSISTED":
        # Same exit code as pool_runner (INTEGRITY_EXIT_CODE): a clip failed its receipt SHA and could not be recorded.
        print("[!] INTEGRITY_UNPERSISTED: a clip failed its receipt SHA-256 and could be neither listed in "
              "integrity_failed.json nor quarantined; the batch is UNCONFIRMED. Fix the batch dir, then reconcile "
              "by hand.", file=sys.stderr)
        return 5
    return 2 if res["status"] == "BLOCKED_NO_ACCOUNTS" else 1


def cmd_assemble(args) -> int:
    pdir = Path(args.project_dir)
    manifest, bible = _load_manifest_and_bible(pdir)
    audit_path = pdir / "qc_audit_report.json"

    clip_map: Dict[str, Path] = {}
    qc_reports: Dict[str, Dict[str, Any]] = {}
    if audit_path.exists():
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        for sid, p in audit.get("passed_clips", {}).items():
            # The audit may predate an integrity failure: re-check the current exclusion list per clip.
            if Path(p).exists() and not _clip_integrity_bad(Path(p), (audit.get("per_shot_qc") or {}).get(sid)):
                clip_map[sid] = Path(p)
        qc_reports = audit.get("per_shot_qc", {})
        if not clip_map:
            # An audit exists and nothing passed it: never fall back to raw (unverified) BATCHES clips.
            print(json.dumps({
                "success": False,
                "error": "NO_QC_PASSED_CLIPS",
                "message": f"{audit_path} lists no passed clip on disk. Re-render or fix the rejected shots and "
                           "rerun qc-audit before assembling. Raw BATCHES clips are used only when no audit exists.",
            }, indent=2, ensure_ascii=False))
            return 1
    else:
        clip_map = _discover_existing_clip_map(pdir, manifest)

    out_mp4 = Path(args.output) if args.output else (pdir / "MASTER_OUTPUT" / "final_master_1080p.mp4")
    res = MasterAssembler.assemble_project(
        shots_manifest=manifest,
        clip_paths_by_shot=clip_map,
        output_mp4=out_mp4,
        story_bible=bible,
        qc_reports=qc_reports,
        bgm_path=Path(args.bgm) if args.bgm else None,
        room_tone_path=Path(args.room_tone) if args.room_tone else None,
        capcut_draft=args.capcut_draft,
        color_mood=getattr(args, "color_mood", "cinematic_neutral"),
        enable_film_grain=not bool(getattr(args, "no_grain", False)),
        enable_voice_timbre_lock=not bool(getattr(args, "no_timbre_lock", False)),
        enable_j_l_cuts=not bool(getattr(args, "no_jl_cuts", False)),
        with_titles=bool(getattr(args, "with_titles", False)),
        export_stems=not bool(getattr(args, "no_stems", False)),
        build_promo_kit=bool(getattr(args, "promo_kit", False)),
    )
    sync_project_to_web_ui(pdir)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


def cmd_deliver(args) -> int:
    pdir = Path(args.project_dir)
    manifest, bible = _load_manifest_and_bible(pdir)
    audit_path = pdir / "qc_audit_report.json"
    qc_reports: Dict[str, Dict[str, Any]] = {}
    if audit_path.exists():
        qc_reports = json.loads(audit_path.read_text(encoding="utf-8")).get("per_shot_qc", {})

    master_mp4 = Path(args.master) if args.master else (pdir / "MASTER_OUTPUT" / "final_master_1080p.mp4")
    if not master_mp4.exists():
        raise FileNotFoundError(f"Chưa tìm thấy Master MP4 tại {master_mp4}. Hãy chạy `assemble` trước.")

    norm_dir = master_mp4.parent / f"_build_{master_mp4.stem}" / "normalized_clips"
    usable_shots: List[Dict[str, Any]] = []
    norm_clips: List[Path] = []
    for s in manifest.get("shots", []):
        sid = s["shot_id"]
        cand_norm = norm_dir / f"norm_{sid}.mp4"
        cand_ver = pdir / "verified_clips" / f"{sid}.mp4"
        chosen = cand_norm if cand_norm.exists() else (cand_ver if cand_ver.exists() else None)
        if chosen is not None:
            usable_shots.append(s)
            norm_clips.append(chosen)

    project_title = (bible or {}).get("project_title") or manifest.get("project_title") or pdir.name
    kit = DeliveryPackager.build_delivery_kit(
        output_mp4=master_mp4,
        normalized_clips=norm_clips,
        shots=usable_shots,
        project_title=str(project_title),
        qc_reports=qc_reports,
    )
    print(json.dumps(kit, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Muse Studio Headless Filmmaking CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_imp = sub.add_parser("accounts-import")
    p_imp.add_argument("source", help="Đường dẫn file tài khoản hoặc chuỗi")
    p_imp.set_defaults(func=cmd_accounts_import)

    p_ver = sub.add_parser("accounts-verify")
    p_ver.add_argument("--account-id", default=None)
    p_ver.set_defaults(func=cmd_accounts_verify)

    p_red = sub.add_parser("accounts-redeem")
    p_red.add_argument("--code", required=True, help="Mã invite code để nạp token bonus trên Muse")
    p_red.add_argument("--account-id", default=None)
    p_red.set_defaults(func=cmd_accounts_redeem)

    p_comp = sub.add_parser("compile")
    p_comp.add_argument("project_dir")
    p_comp.add_argument("--beats", default=None)
    p_comp.add_argument("--audio-mode", default="native_drama", choices=["native_drama", "hybrid_narrated"])
    p_comp.add_argument("--no-strict-bible", action="store_true")
    p_comp.add_argument("--cinematic-cutaways", action="store_true", help="Chèn cảnh phản ứng im lặng và đặc tả đạo cụ")
    p_comp.set_defaults(func=cmd_compile)

    p_norm = sub.add_parser("normalize-srt")
    p_norm.add_argument("srt", help="Đường dẫn file phụ đề .srt nguồn")
    p_norm.add_argument("--chapters", default=None)
    p_norm.add_argument("--output", default=None)
    p_norm.add_argument("--window", type=float, default=22.0)
    p_norm.set_defaults(func=cmd_normalize_srt)

    p_saud = sub.add_parser("srt-audit")
    p_saud.add_argument("target", help="Thư mục dự án hoặc file beats JSON")
    p_saud.add_argument("--srt", default=None)
    p_saud.add_argument("--chapters", default=None)
    p_saud.set_defaults(func=cmd_srt_audit)

    p_pre = sub.add_parser("preflight")
    p_pre.add_argument("project_dir")
    p_pre.add_argument("--srt", default=None)
    p_pre.add_argument("--chapters", default=None)
    p_pre.add_argument("--no-srt-gate", action="store_true",
                       help="Skip the SRT coverage gate (preflight_report.json: srt_gate=SKIPPED_BY_FLAG)")
    p_pre.set_defaults(func=cmd_preflight)

    p_kf = sub.add_parser("keyframes")
    p_kf.add_argument("project_dir")
    p_kf.add_argument("--simulate", action="store_true")
    p_kf.add_argument("--lane", default=None, help="Lane id; default: the open <project_dir>/lane.json")
    p_kf.add_argument("--include-setups", action="store_true", help="Sinh thêm Master Location Plates vào assets/setups")
    p_kf.add_argument("--include-turnarounds", action="store_true", help="Sinh ảnh nhân vật góc 3/4 và toàn thân còn thiếu")
    p_kf.set_defaults(func=cmd_keyframes)

    p_anim = sub.add_parser("animatic")
    p_anim.add_argument("project_dir")
    p_anim.add_argument("--output", default=None, help="Đường dẫn xuất file Animatic MP4")
    p_anim.add_argument("--fps", type=int, default=12)
    p_anim.set_defaults(func=cmd_animatic)

    p_pkg = sub.add_parser("package")
    p_pkg.add_argument("project_dir")
    p_pkg.add_argument("--batch-prefix", default="FILM_BATCH")
    p_pkg.add_argument("--all", action="store_true")
    p_pkg.set_defaults(func=cmd_package)

    p_qc = sub.add_parser("qc-audit")
    p_qc.add_argument("project_dir")
    p_qc.add_argument("--strips", action="store_true")
    p_qc.set_defaults(func=cmd_qc_audit)

    p_promote = sub.add_parser(
        "promote-take", help="Promote a self-reviewed passing take into verified_clips/, qc_strips/ and the audit"
    )
    p_promote.add_argument("project_dir")
    p_promote.add_argument("shot_id")
    p_promote.add_argument("take", help="Take number (as in per_shot_qc[shot].candidates[].take) or the take's clip path")
    p_promote.set_defaults(func=cmd_promote_take)

    p_run = sub.add_parser("run-pool")
    p_run.add_argument("project_dir")
    p_run.add_argument("--max-accounts", "-n", type=int, default=None)
    p_run.add_argument("--max-rounds", type=int, default=3)
    p_run.add_argument("--no-auto-repair", action="store_true")
    p_run.add_argument("--simulate", action="store_true")
    p_run.set_defaults(func=cmd_run_pool)

    p_asm = sub.add_parser("assemble")
    p_asm.add_argument("project_dir")
    p_asm.add_argument("--output", default=None)
    p_asm.add_argument("--bgm", default=None)
    p_asm.add_argument("--room-tone", default=None)
    p_asm.add_argument("--capcut-draft", action="store_true")
    p_asm.add_argument("--color-mood", default="cinematic_neutral")
    p_asm.add_argument("--with-titles", action="store_true", help="Ghép thêm Opening Title & End Credits")
    p_asm.add_argument("--promo-kit", action="store_true", help="Xuất kèm gói Trailer + Shorts 9:16 + Poster")
    p_asm.add_argument("--no-stems", action="store_true", help="Bỏ qua xuất rời M&E Stem và Dialogue Stem")
    p_asm.add_argument("--no-grain", action="store_true", help="Tắt lớp hạt phim 35mm")
    p_asm.add_argument("--no-timbre-lock", action="store_true", help="Tắt khóa màu giọng nhân vật FIR")
    p_asm.add_argument("--no-jl-cuts", action="store_true", help="Tắt gối thoại J/L-Cut")
    p_asm.set_defaults(func=cmd_assemble)

    p_del = sub.add_parser("deliver")
    p_del.add_argument("project_dir")
    p_del.add_argument("--master", default=None, help="Đường dẫn file Master MP4 nguồn")
    p_del.set_defaults(func=cmd_deliver)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
