"""Browser-assisted Muse handoff. No cookies, hidden API, automatic sends or creative planning.

Keep these receipts outside Flow's intent/recovery journal. Muse's visible response is
operator evidence, never a server-verified job ID or proof of picture/dialogue quality.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field

from film_pipeline.core import ContractModel, canonical_json
from film_pipeline.editorial import probe_media
from film_pipeline.production import takes as T
from film_pipeline.production.gate_checks import plan_inputs_sha
from film_pipeline.production.generate import build_payload, owner_go_live
from film_pipeline.production.runtime import atomic_json, atomic_text, film_writer
from film_pipeline.providers.request import GenerationRequest


class Packet(ContractModel):
    schema_version: Literal[1, 2] = 1
    request_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    shot_version: int = Field(ge=1)
    source_inputs: dict[str, str]
    request: GenerationRequest
    source_prompt_sha256: str = Field(default="", pattern=r"^([0-9a-f]{64})?$")


class Response(ContractModel):
    request_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_source: str = Field(min_length=1)
    observed_output: str = Field(min_length=1)
    media_handle: str = ""
    snapshot_id: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base(pkg) -> Path:
    return Path(pkg.root) / "media/muse"


def _frames(request):
    return [f for f in (request.first_frame, request.last_frame, *request.references) if f is not None]


def condition_camera_prompt(prompt: str, camera) -> str:
    """Render the system's camera plan as Muse text; never promise hard frame conditioning."""
    from film_pipeline.production.plan import START_FRAME_PREFIX, END_FRAME_PREFIX, START_PREFIX
    for prefix in (START_FRAME_PREFIX, END_FRAME_PREFIX, START_PREFIX):
        if prompt.startswith(prefix):
            prompt = "Use the attached image(s) as visual references for the planned shot. " + prompt[len(prefix):]
            break
    if camera is None:
        raise ValueError("Muse camera conditioning needs a declared camera plan")
    hint = camera.prompt_hint() + ". "
    if camera.movement == "STATIC":
        hint += ("Camera locked off on a tripod for the entire shot. Hold the exact initial framing and subject sizes; "
                 "no zoom, push-in, pull-back, pan, tilt, reframing or cuts. ")
    return hint + prompt


def _planned(pkg, gid, *, condition_camera=False):
    # Reuse the existing compiler, storyboard/still approval and continuity checks.
    # Flow pricing/argv are source-route checks only; never export them as a Muse quote/send.
    payload = build_payload(pkg, gid)
    blocked = [b for b in payload["blockers"] if not b.get("live_only") or b["code"] == "SEND_PENDING"]
    if blocked:
        raise ValueError("Muse source plan blocked: " + "; ".join(b["code"] for b in blocked))
    request = GenerationRequest.model_validate(payload["request"])
    if not re.fullmatch(r"[A-Za-z0-9_-]+", request.generation_id):
        raise ValueError("generation id is not safe for a take filename")
    if request.prompt_sha256 != T.sha256_text(request.prompt):
        raise ValueError("compiled prompt hash mismatch")
    source_prompt_sha = request.prompt_sha256
    if condition_camera:
        decl = next(g for g in pkg.typed["shots"].generations if g.generation_id == gid)
        request.prompt = condition_camera_prompt(request.prompt, decl.camera)
        request.prompt_sha256 = T.sha256_text(request.prompt)
    originals = _frames(request)
    for frame in originals:
        if not frame.sha256 or T.sha256_file(Path(frame.path)) != frame.sha256:
            raise ValueError("source reference changed or has no hash")
    original_paths = [Path(f.path) for f in originals]
    for i, frame in enumerate(originals):
        frame.path = f"assets/{i:02d}{original_paths[i].suffix.lower()}"
    request.take_id = f"muse_{gid}_v{payload['shot_version']}"  # not a reserved canonical take number
    request.output = "output.mp4"
    body = {"schema_version": 1, "shot_version": payload["shot_version"],
            "source_inputs": plan_inputs_sha(Path(pkg.root)), "request": request.model_dump(mode="json")}
    if condition_camera:
        body.update(schema_version=2, source_prompt_sha256=source_prompt_sha)
    packet = Packet(request_id=T.sha256_text(canonical_json(body)), **body)
    return packet, original_paths


def _read(pkg, folder: Path) -> Packet:
    folder = Path(folder).resolve()
    packet = Packet.model_validate_json((folder / "request.json").read_text(encoding="utf-8"))
    if folder != (_base(pkg) / packet.request_id).resolve():
        raise ValueError("request folder does not belong to this film")
    if packet.request.film_id != pkg.header.film_id:
        raise ValueError("request identifies another film")
    current, _ = _planned(pkg, packet.request.generation_id, condition_camera=packet.schema_version == 2)
    if current != packet:
        raise ValueError("stale or altered Muse request; re-plan the shot")
    for frame in _frames(packet.request):
        path = (folder / frame.path).resolve()
        if not path.is_relative_to(folder) or T.sha256_file(path) != frame.sha256:
            raise ValueError("exported reference hash mismatch")
    expected = {"request.json", "prompt.txt", "relay.txt", *(f.path for f in _frames(packet.request))}
    try:
        with zipfile.ZipFile(folder / "handoff.zip") as archive:
            if set(archive.namelist()) != expected or len(archive.namelist()) != len(expected):
                raise ValueError("handoff archive has unexpected or missing files")
            if any(archive.read(name) != (folder / name).read_bytes() for name in expected):
                raise ValueError("handoff archive differs from the verified request")
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise ValueError("invalid handoff archive") from exc
    if (folder / "prompt.txt").read_text(encoding="utf-8") != packet.request.prompt:
        raise ValueError("handoff prompt differs from the compiled request")
    if (folder / "relay.txt").read_text(encoding="utf-8") != _relay(packet):
        raise ValueError("handoff instructions changed")
    return packet


def _states(pkg):
    for path in sorted(_base(pkg).glob("*/state.json")):
        # An unreadable journal is not permission to send again.
        yield path, json.loads(path.read_text(encoding="utf-8"))


@film_writer()
def prepare(pkg, generation_id: str, *, condition_camera: bool = False) -> Path:
    packet, originals = _planned(pkg, generation_id, condition_camera=condition_camera)
    for _, state in _states(pkg):
        if state["generation_id"] == generation_id and state["shot_version"] == packet.shot_version:
            if state["request_id"] != packet.request_id:
                raise ValueError("one Muse dispatch per shot version; restage before another attempt")
    folder = _base(pkg) / packet.request_id
    if (folder / "request.json").exists():
        _read(pkg, folder)
        return folder
    folder.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=packet.request_id + ".", dir=folder.parent.resolve()) as temp:
        stage = Path(temp) / "bundle"
        if not stage.resolve().is_relative_to(folder.parent.resolve()):
            raise ValueError("staging directory escaped the Muse workspace")
        stage.mkdir()
        for frame, original in zip(_frames(packet.request), originals):
            target = stage / frame.path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
            if T.sha256_file(target) != frame.sha256:
                raise ValueError("reference changed while copying; no handoff is ready")
        atomic_json(stage / "request.json", packet.model_dump(mode="json"))
        atomic_text(stage / "prompt.txt", packet.request.prompt)
        atomic_text(stage / "relay.txt", _relay(packet))
        with zipfile.ZipFile(stage / "handoff.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(stage.rglob("*")):
                if path.is_file() and path.name != "handoff.zip":
                    archive.write(path, path.relative_to(stage).as_posix())
        # Only a complete bundle receives its deterministic name. Interrupted staging is disposable.
        stage.rename(folder)
    return folder


def _relay(packet: Packet) -> str:
    return (f"AFP MUSE SHOT REQUEST {packet.request_id}\n"
             "Render exactly ONE video with media.generate_video using the attached request.json and assets. "
             "The external system owns the shot: pass prompt verbatim as the text input, then the ordered images. "
             "Do not plan, rewrite dialogue, generate extra images/videos, retry, schedule, upload or publish. "
             "Use existing account entitlement only; stop at payment, upgrade, quota or account warnings. "
             "Pricing is UNKNOWN. Duration/aspect/first-frame are requested, not guaranteed controls. "
             "If any input is missing, stop. After generation return the actual downloadable video, its SHA-256, "
             "the request_id, actual tool input, raw output identifiers, and observed metadata. "
             "Do not claim QC PASS or invent a job ID.\n")


@film_writer()
def dispatch(pkg, folder: Path, *, backlog: Path | None = None) -> dict:
    packet = _read(pkg, folder)
    if pkg.header.rehearsal:
        raise ValueError("a rehearsal cannot be dispatched to Muse")
    if not owner_go_live(backlog):
        raise ValueError("OWNER_GO_LIVE must say YES for this handoff")
    if (Path(folder) / "state.json").exists():
        raise ValueError("this request was already claimed; reconcile the existing browser response")
    for _, state in _states(pkg):
        if state["generation_id"] == packet.request.generation_id and state["shot_version"] == packet.shot_version:
            raise ValueError("this shot version already has a Muse dispatch; restage before another attempt")
        if state["status"] != "IMPORTED":
            raise ValueError("another Muse handoff is pending; reconcile it before dispatch")
    state = {"request_id": packet.request_id, "generation_id": packet.request.generation_id,
             "shot_version": packet.shot_version, "status": "DISPATCH_CLAIMED", "claimed_at": _now(),
             "submitted_attempts": 1, "monetary_cost": None, "pricing_status": "UNKNOWN"}
    atomic_json(Path(folder) / "state.json", state)
    return {**state, "sent": "UNKNOWN", "relay": str(Path(folder) / "relay.txt"),
            "note": "claim recorded BEFORE browser action; it does not prove provider submission"}


def _next_take(pkg, gid: str) -> str:
    log = T.load_log(pkg.root, pkg.header.film_id)
    names = [name for t in log.takes for name in (t.take_id, Path(t.output_file).stem)]
    names += [p.name.removesuffix(".intent.json") for p in (Path(pkg.root) / "takes/intents").glob("*.intent.json")]
    names += [p.stem for p in (Path(pkg.root) / "media/takes").glob("*")]
    pattern = re.compile(rf"^{re.escape(gid)}_t(\d+)$")
    number = max([0] + [int(m[1]) for name in names if (m := pattern.fullmatch(name))]) + 1
    return f"{gid}_t{number}"


@film_writer()
def ingest(pkg, folder: Path, clip: Path, response: dict) -> dict:
    packet = _read(pkg, folder)
    response = Response.model_validate(response)
    url = urlsplit(response.response_source)
    if response.request_id != packet.request_id or url.scheme != "https" or url.hostname != "muse.ai":
        raise ValueError("response does not identify this request and its visible Muse source")
    folder, clip = Path(folder), Path(clip)
    state_file = folder / "state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    if state.get("request_id") != packet.request_id or state.get("status") not in {"DISPATCH_CLAIMED", "BINDING", "IMPORTED"}:
        raise ValueError("no valid dispatch claim for this result")
    if state.get("take_id") is not None and not re.fullmatch(
            rf"{re.escape(packet.request.generation_id)}_t[1-9]\d*", str(state["take_id"])):
        raise ValueError("invalid take id in the binding journal")
    digest = T.sha256_file(clip)
    if digest != response.output_sha256 or state.get("output_sha256", digest) != digest:
        raise ValueError("download hash conflicts with the response or an existing binding")
    existing = [t for t in T.load_log(pkg.root, pkg.header.film_id).takes if t.output_sha256 == digest]
    if existing and (existing[0].take_id != state.get("take_id") or existing[0].provider != "muse"
                     or existing[0].generation_id != packet.request.generation_id
                     or existing[0].shot_version != packet.shot_version):
        raise ValueError("these bytes are already bound to another request, version or provider")
    output = Path(pkg.root) / "media/takes" / (state.get("take_id", "") + ".mp4")
    if state["status"] == "IMPORTED":
        if not existing or T.sha256_file(output) != digest:
            raise ValueError("imported take is missing or changed")
        return {"created": False, "take": existing[0].model_dump(mode="json"), "receipt": str(state_file)}
    media = probe_media(clip)
    # shortcut: relay clips are bounded to 60 seconds; qualify longer intake when Muse exposes it.
    if media.duration_s > 60:
        raise ValueError("Muse relay clip exceeds the 60-second intake bound")
    decoded = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(clip),
                              "-map", "0:v:0", "-map", "0:a?", "-f", "null", "-"],
                             capture_output=True, timeout=60, check=False)
    if decoded.returncode:
        raise ValueError("download failed full video/audio decode")
    if T.sha256_file(clip) != digest:
        raise ValueError("download changed during verification")
    warnings = []
    if abs(media.duration_s - packet.request.duration_s) > 1 / media.fps:
        warnings.append("DURATION_DIFFERS")
    if packet.request.audio_mode == "NATIVE_DIALOGUE" and media.audio_codec is None:
        warnings.append("DIALOGUE_AUDIO_MISSING")
    a, b = map(int, packet.request.aspect.split(":"))
    if abs(media.width / media.height - a / b) > 0.02:
        warnings.append("ASPECT_DIFFERS")
    take_id = state.get("take_id") or _next_take(pkg, packet.request.generation_id)
    output = Path(pkg.root) / "media/takes" / f"{take_id}.mp4"
    state.update(status="BINDING", take_id=take_id, output_sha256=digest, response=response.model_dump(),
                 media=asdict(media), warnings=warnings, binding="operator_observed_download")
    atomic_json(state_file, state)  # recover the same binding after an interrupted copy/register
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        if T.sha256_file(output) != digest:
            raise ValueError("existing output conflicts; evidence is never overwritten")
    else:
        with output.open("xb") as dest, clip.open("rb") as source:
            shutil.copyfileobj(source, dest)
    if T.sha256_file(output) != digest:
        raise ValueError("copied output hash mismatch")
    frame = packet.request.first_frame
    entry, created = T.register_take(pkg.root, pkg.header.film_id, packet.request.generation_id, output,
        prompt_text=packet.request.prompt, route="muse:browser-relay", model="Muse (backend unreported)", credits=0,
        start_frame=folder / frame.path if frame else None, shot_version=packet.shot_version,
        provider="muse", provider_job_id="", cost_unit="muse_requests", cost_amount=1)
    state.update(status="IMPORTED", imported_at=_now())
    atomic_json(state_file, state)
    return {"created": created, "take": entry.model_dump(mode="json"), "receipt": str(state_file),
            "warnings": warnings, "qc": "UNASSESSED", "monetary_cost": None}
