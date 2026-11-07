"""Offline dress rehearsal: run the real production chain on a *copy* of a package with a mock video runner.

Nothing here contacts a provider or spends credits. A rehearsal package carries ``film.json`` ``"rehearsal": true``; that flag

* lets the placeholder reviewer ``REHEARSAL-BOT`` approve stills, review takes and lock the picture (a normal package refuses
  the name everywhere, see :func:`refuse_bot`),
* lets ``generate`` use a *mock* runner without ``OWNER_GO_LIVE: YES`` (the default Flow runner still needs it),
* stamps the delivery ``REHEARSAL — synthetic``, keeps ``release_ready`` false and makes ``deliver --accept`` refuse.

The result is evidence that the *system* runs end to end, never evidence about footage quality or an Owner acceptance.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

BOT = "REHEARSAL-BOT"
STAMP = "REHEARSAL — synthetic"
ROOT = Path(__file__).resolve().parents[3]
FILM_CLI = ROOT / "tools" / "film.py"


# ------------------------------------------------------------------ the flag and the guard

def is_rehearsal(film_root: Path) -> bool:
    """True when ``film.json`` under *film_root* says ``"rehearsal": true`` (a missing or unreadable file means no)."""
    try:
        return json.loads((Path(film_root) / "film.json").read_text(encoding="utf-8")).get("rehearsal") is True
    except (OSError, ValueError, AttributeError):
        return False


def refuse_bot(film_root: Path, *names: str) -> None:
    """Raise ``ValueError`` if any name is the rehearsal placeholder and the package is not a rehearsal."""
    if any(BOT.lower() in str(n).lower() for n in names) and not is_rehearsal(film_root):
        raise ValueError(f"{BOT} is only allowed in a rehearsal package (film.json \"rehearsal\": true); "
                         f"a real review needs a named person")


# ------------------------------------------------------------------ mock runner

def mock_runner(argv: list[str], out: Path) -> dict[str, Any]:
    """Stand-in for the Flow sender: an 8 s clip (the start still + a quiet tone) and the manifest the real sender writes."""
    still = Path(argv[argv.index("--start-file") + 1])
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "24", "-i", str(still),
           "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000", "-t", "8",
           # a slow drifting crop plus grain: a frozen picture would (rightly) fail master QC
           "-vf", "scale=1408:792,crop=1280:720:x='64+60*sin(t*0.9)':y='36+30*cos(t*0.7)',noise=alls=12:allf=t+u,format=yuv420p",
           "-af", "volume=0.05", "-c:v", "libx264", "-preset", "veryfast", "-r", "24", "-c:a", "aac", "-b:a", "128k",
           "-shortest", str(out)]
    done = subprocess.run(cmd, capture_output=True, text=True, check=False)
    sha = hashlib.sha256(out.read_bytes()).hexdigest() if out.is_file() else ""
    manifest = {"result": "PASSED" if done.returncode == 0 and sha else "FAILED", "file": out.name, "sha256": sha,
                "mock": True, "note": STAMP}
    out.with_suffix(".take.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {**manifest, "returncode": done.returncode}


# ------------------------------------------------------------------ the chain

class _Log:
    def __init__(self, dest: Path) -> None:
        self.dest = dest
        self.steps: list[dict[str, Any]] = []
        self.manual: list[str] = []

    def add(self, name: str, ok: bool, secs: float, detail: str = "") -> bool:
        self.steps.append({"step": name, "ok": ok, "secs": round(secs, 1), "detail": detail[-600:]})
        print(f"[rehearse] {'ok  ' if ok else 'FAIL'} {name} ({secs:.0f}s) {detail[-160:] if not ok else ''}", flush=True)
        return ok

    def cli(self, name: str, *args: str) -> tuple[bool, str]:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(ROOT / "src")}
        t0 = time.time()
        done = subprocess.run([sys.executable, str(FILM_CLI), *args], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=env, check=False)
        text = (done.stdout or "") + (done.stderr or "")
        self.add(name, done.returncode == 0, time.time() - t0, text if done.returncode else text[-200:])
        return done.returncode == 0, text


def _write_json(path: Path, body: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _review_sheet(root: Path, film_id: str, take_id: str, gid: str) -> dict[str, Any]:
    from film_pipeline.production.qc_model import TAKE_GROUPS
    from film_pipeline.production.takes import load_log
    entry = load_log(root, film_id).get(take_id)
    checks = [{"group": g, "result": "PASS", "level": "FULL_MOTION", "reviewer": f"human:{BOT}",
               "evidence": f"{STAMP}: the clip is a still plus a tone; nothing was judged"} for g in TAKE_GROUPS]
    return {"take_id": take_id, "generation_id": gid, "checks": checks, "output_sha256": entry.output_sha256}


def rehearse(src: Path, dest: Path, *, stop_on_fail: bool = True) -> dict[str, Any]:
    """Copy *src* to *dest* (never touched afterwards: *src* stays as it is) and run the whole chain on the copy."""
    from film_pipeline.production.generate import generate
    from film_pipeline.production.package import load_package
    src, dest = Path(src).resolve(), Path(dest).resolve()
    if dest.exists() and any(dest.iterdir()):
        raise ValueError(f"{dest} is not empty; a rehearsal needs a fresh directory")
    if dest == src or src in dest.parents or dest in src.parents:
        raise ValueError("the rehearsal directory must be separate from the package")
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("media", "delivery*", "takes"))
    header_path = dest / "film.json"
    header = json.loads(header_path.read_text(encoding="utf-8"))
    header["rehearsal"] = True
    _write_json(header_path, header)
    log = _Log(dest)
    film = str(dest)
    started = time.time()

    def stop() -> bool:
        return stop_on_fail and not log.steps[-1]["ok"]

    log.cli("plan", "plan", "--film", film, "--out", str(dest / "media" / "plan"), "--approve-storyboard", BOT)
    log.manual.append("storyboard frames approved by REHEARSAL-BOT (a real run needs the Owner's storyboard approval)")
    pkg = load_package(dest)
    gids = [g.generation_id for g in pkg.typed["shots"].generations] if pkg.typed.get("shots") else []
    if not gids:
        log.add("generations", False, 0, "no generations to rehearse")
        return _finish(log, src, dest, started)
    for gid in gids:  # placeholder start stills: the storyboard frame of each generation
        frame = dest / "media" / "plan" / "storyboard" / f"{gid}.png"
        okr, _ = log.cli(f"stills register {gid}", "stills", "--film", film, "--register", gid, "--image", str(frame),
                         "--source", "REHEARSAL placeholder (storyboard frame)")
        if okr:
            log.cli(f"stills approve {gid}", "stills", "--film", film, "--approve", gid, "--by", BOT)
        if stop():
            return _finish(log, src, dest, started)
    log.manual.append("start stills are storyboard frames, not generated images (the image step needs Flow)")
    for gid in gids:
        t0 = time.time()
        pkg = load_package(dest)
        result = generate(pkg, gid, dry_run=False, start_token="tok:REHEARSAL", runner=mock_runner)
        take = (result.get("take") or {}).get("take_id")
        log.add(f"generate {gid}", bool(take), time.time() - t0,
                "" if take else json.dumps(result.get("refused") or result.get("manifest_result"))[:500])
        if not take:
            if stop_on_fail:
                return _finish(log, src, dest, started)
            continue
        sheet = dest / "media" / "review" / f"{take}.qc.json"
        _write_json(sheet, _review_sheet(dest, pkg.header.film_id, take, gid))
        log.cli(f"review {take}", "review", "--film", film, "--ingest", str(sheet))
        if stop():
            return _finish(log, src, dest, started)
    # the edit decision list: the system does not author a cut by itself yet
    events = [{"event_id": gid, "kind": "TAKE", "take_id": f"{gid}_t1"} for gid in gids]
    title = [{"text": header["title"].upper(), "size": 96}, {"text": "Generated with AI", "size": 28}]
    _write_json(dest / "05_edit.json", {"events": events, "title": title})
    log.manual.append("05_edit.json written by the rehearsal: one TAKE event per generation in plan order plus a title card "
                      "with the AI line (no editor yet; deliver blocks AI_LABEL_MISSING without that line)")
    _write_json(dest / "generators.json", [{"role": "video+audio", "name": "REHEARSAL mock", "model": "ffmpeg still+tone",
                                            "settings": STAMP}])
    log.manual.append("generators.json written by the rehearsal (the real file names the provider and model)")
    cut_dir = dest / "media" / "cut"
    gen = str(dest / "generators.json")
    chain: list[tuple[str, list[str]]] = [
        ("cut", ["cut", "--film", film, "--render", "--out", str(cut_dir / "cut.mp4")]),
        ("lock", ["lock", "--film", film, "--lock", "--by", BOT, "--reason", STAMP]),
        ("grade", ["grade", "--film", film, "--render", "--out", str(cut_dir / "graded.mp4")]),
        ("titles", ["titles", "--film", film, "--generators-file", gen, "--render", "--color", "--out", str(cut_dir / "titled_cut.mp4")]),
        ("mix", ["mix", "--film", film, "--cut", str(cut_dir / "titled_cut.mp4"), "--out", str(cut_dir / "mixed.mp4")]),
        ("mastercheck", ["mastercheck", "--film", film, "--cut-report", str(cut_dir / "titled_cut.cut.json")]),
        ("versions", ["versions", "--film", film, "--cut-report", str(cut_dir / "titled_cut.cut.json"), "--generators-file", gen]),
        ("deliver", ["deliver", "--film", film, "--cut-report", str(cut_dir / "titled_cut.cut.json"), "--generators-file", gen]),
    ]
    for name, args in chain:
        log.cli(name, *args)
        if stop():
            break
    return _finish(log, src, dest, started)


def _finish(log: _Log, src: Path, dest: Path, started: float) -> dict[str, Any]:
    delivered = (dest / "delivery" / "MANIFEST.json").is_file()
    report = {"stamp": STAMP, "source": str(src), "rehearsal": str(dest), "release_ready": False,
              "reached_delivery": delivered, "all_steps_ok": all(s["ok"] for s in log.steps),
              "wall_s": round(time.time() - started, 1), "steps": log.steps, "manual_steps": log.manual}
    _write_json(dest / "REHEARSAL_REPORT.json", report)
    return report
