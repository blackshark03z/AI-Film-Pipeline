"""Audio stems and the mix (categories 107-130: dialogue, ambience, effects, music, ducking, loudness).

Input is a rendered cut (``edit.render_cut`` output and its ``.cut.json`` report, which holds the planned clock) and an
optional ``<film>/audio/mix_plan.json`` (`MixPlan`). Four stems are written next to each other in ``<film>/audio/stems``
(or ``--stems``), all as long as the cut, 48 kHz stereo:

* ``dialogue.wav``: the sound of the cut itself (takes with their J/L cuts); this is the key for ducking.
* ``ambience.wav``: one noise bed per scene span (consecutive TAKE events of one scene), coloured by the location's
  ``room_tone`` text, set to ``ambience_lufs`` and cross-faded at the span edges. It is generated offline, deterministic.
* ``sfx.wav``: an effect is placed at the start of the event whose shot declares it (``sfx`` in 04_shots) **only if**
  ``audio/sfx/<slug>.wav`` exists; otherwise it is reported ``SFX_UNSOURCED`` (the take's own sound stays) - nothing is
  invented.
* ``music.wav``: the cues of the plan (an asset under ``audio/``, start/end, gain, fades); a missing asset blocks.

The ambience and the music (the "bed") are ducked by a side-chain on the dialogue; ``bed.wav`` and ``bed_ducked.wav`` are
kept so the depth can be measured (median over frames where the dialogue is active). The final mix is muxed into the
cut's picture (copied) and normalised to ``target_lufs`` / ``true_peak_db`` with ``drama.post.normalize_loudness``.
Assets used (sfx, music) are recorded with their sha256 so P5-02 can check them against the rights ledger.
"""
from __future__ import annotations

import array
import hashlib
import json
import math
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pydantic import Field

from film_pipeline.core import ContractModel

SR = 48000
TONES = (  # keywords of room_tone -> (noise colour, low-pass Hz, hum Hz or 0)
    (("hum", "fridge", "refrigerator", "air condition", "ventilation", "fluoresc", "buzz", "server"), ("brown", 900, 100)),
    (("rain", "wind", "storm", "street", "traffic", "outside", "city"), ("pink", 6000, 0)),
    (("silence", "quiet", "still"), ("brown", 400, 0)),
)
DEFAULT_TONE = ("pink", 3500, 0)
EDGE_FADE_S = 0.4


class MusicCue(ContractModel):
    cue_id: str
    asset: str                       # path under <film>/audio/
    start_s: float = Field(ge=0)     # final clock, title card included
    end_s: float | None = None       # None: until the end of the cut
    gain_db: float = -18.0
    fade_in_s: float = Field(default=1.0, ge=0)
    fade_out_s: float = Field(default=2.0, ge=0)
    why: str = ""


class MixPlan(ContractModel):
    ambience_lufs: float = -40.0
    sfx_gain_db: float = -6.0
    duck_threshold_db: float = -50.0   # ffmpeg reads the key quietly: -50 gives ~10 dB under dialogue peaking near -20 dBFS
    duck_ratio: float = Field(default=8.0, ge=1.0, le=20.0)
    duck_attack_ms: float = Field(default=20.0, ge=0.01)
    duck_release_ms: float = Field(default=400.0, ge=0.01)
    min_duck_depth_db: float = 6.0
    target_lufs: float = -14.0
    true_peak_db: float = -1.0
    lufs_tolerance: float = 1.0
    music: list[MusicCue] = Field(default_factory=list)


def audio_dir(root: Path) -> Path:
    return Path(root) / "audio"


def load_plan(root: Path) -> MixPlan:
    path = audio_dir(root) / "mix_plan.json"
    return MixPlan.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else MixPlan()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-nostats", "-y", *args], check=True, capture_output=True)


def tone_for(text: str) -> tuple[str, int, int]:
    low = text.lower()
    for words, tone in TONES:
        if any(w in low for w in words):
            return tone
    return DEFAULT_TONE


def scene_spans(pkg: Any, section: Any, planned: dict[str, Any]) -> list[dict[str, Any]]:
    """Consecutive TAKE events of one scene as {scene_id, location, room_tone, start_s, end_s} on the final clock."""
    shots, pre = pkg.typed.get("shots"), pkg.typed.get("preprod")
    if shots is None or pre is None:
        return []
    scene_of = {g.generation_id: g.scene_id for g in shots.generations}
    event = {e.event_id: e for e in section.events}
    spans: list[dict[str, Any]] = []
    for placed in planned["events"]:
        src = event[placed["event_id"]]
        scene_id = scene_of.get(src.generation_id) if src.kind == "TAKE" else None
        if scene_id is None or scene_id not in pre.scenes:
            continue
        if spans and spans[-1]["scene_id"] == scene_id and abs(spans[-1]["end_s"] - placed["start_s"]) < 0.5:
            spans[-1]["end_s"] = max(spans[-1]["end_s"], placed["end_s"])
            continue
        location = pre.scenes[scene_id].location
        spans.append({"scene_id": scene_id, "location": location, "room_tone": pre.locations[location].room_tone,
                      "start_s": placed["start_s"], "end_s": placed["end_s"]})
    return spans


def calibrated_bed(tone: tuple[str, int, int], seconds: float, seed: int, lufs: float, out: Path) -> Path:
    """A noise bed of ``seconds`` at ``lufs`` (measured on the file, then gained), written to ``out``."""
    from film_pipeline.drama.post import measure_ebur128
    colour, lowpass, hum = tone
    source = f"anoisesrc=color={colour}:amplitude=0.5:sample_rate={SR}:seed={seed}:duration={seconds:.3f}"
    hum_in = ["-f", "lavfi", "-t", f"{seconds:.3f}", "-i", f"sine=frequency={hum}:sample_rate={SR}"] if hum else []
    graph = (f"[0:a]lowpass=f={lowpass}[n];[1:a]volume=-26dB[h];[n][h]amix=inputs=2:normalize=0:duration=first,"
             f"aformat=channel_layouts=stereo[o]") if hum else f"[0:a]lowpass=f={lowpass},aformat=channel_layouts=stereo[o]"
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.wav"
        _ff("-f", "lavfi", "-i", source, *hum_in, "-filter_complex", graph, "-map", "[o]", "-c:a", "pcm_f32le", str(raw))
        measured = measure_ebur128(raw)["integrated_lufs"]
        _ff("-i", str(raw), "-af", f"volume={lufs - measured:.3f}dB", "-c:a", "pcm_f32le", str(out))
    return out


def _timed(label_in: str, label_out: str, start_s: float, fade_in: float, fade_out: float, length: float,
           gain_db: float = 0.0) -> str:
    """Fade the (already trimmed) stream, gain it and delay it to ``start_s`` on the final clock."""
    ms = max(0, round(start_s * 1000))
    parts = [f"aresample={SR}", "aformat=channel_layouts=stereo"]
    if gain_db:
        parts.append(f"volume={gain_db:.2f}dB")
    if fade_in > 0:
        parts.append(f"afade=t=in:d={fade_in:.3f}")
    if fade_out > 0:
        parts.append(f"afade=t=out:st={max(0.0, length - fade_out):.3f}:d={fade_out:.3f}")
    parts.append(f"adelay={ms}|{ms}")
    return f"[{label_in}]{','.join(parts)}[{label_out}]"


def _stem(layers: list[tuple[Path, str]], total_s: float, out: Path) -> Path:
    """Sum timed layers onto a silent bed of ``total_s``. ``layers`` = (input file, filter chain applied before timing)."""
    cmd = ["-f", "lavfi", "-t", f"{total_s:.3f}", "-i", f"anullsrc=r={SR}:cl=stereo"]
    graph, labels = [], []
    for i, (path, chain) in enumerate(layers, 1):
        cmd += ["-i", str(path)]
        graph.append(chain.replace("{in}", f"{i}:a").replace("{out}", f"L{i}"))
        labels.append(f"[L{i}]")
    mix = f"[0:a]{''.join(labels)}amix=inputs={len(layers) + 1}:normalize=0:duration=first,atrim=0:{total_s:.3f}[o]"
    _ff(*cmd, "-filter_complex", ";".join([*graph, mix]), "-map", "[o]", "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le",
        str(out))
    return out


def _silent(total_s: float, out: Path) -> Path:
    _ff("-f", "lavfi", "-t", f"{total_s:.3f}", "-i", f"anullsrc=r={SR}:cl=stereo", "-c:a", "pcm_s16le", str(out))
    return out


def _frames_db(path: Path, hop_s: float = 0.1, start_s: float = 0.0, end_s: float | None = None) -> list[float]:
    """RMS in dBFS per hop (mono mix), via 8 kHz s16 (no numpy needed); optionally only [start_s, end_s]."""
    window_args = ["-ss", f"{start_s:.3f}"] + (["-t", f"{end_s - start_s:.3f}"] if end_s is not None else [])
    raw = subprocess.run(["ffmpeg", "-v", "error", *window_args, "-i", str(path), "-vn", "-ac", "1", "-ar", "8000",
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    samples = array.array("h")
    samples.frombytes(raw[: len(raw) // 2 * 2])
    hop = int(8000 * hop_s)
    out = []
    for i in range(0, len(samples) - hop + 1, hop):
        window = samples[i:i + hop]
        mean_sq = sum(v * v for v in window) / hop
        out.append(-120.0 if mean_sq <= 0 else max(-120.0, 10 * math.log10(mean_sq / 32768.0 ** 2)))
    return out


def _frames_db_range(path: Path, t0: float, t1: float) -> list[float]:
    return _frames_db(path, 0.1, t0, t1)


def duck_depth(dialogue: Path, bed: Path, ducked: Path, active_db: float = -45.0) -> dict[str, Any]:
    """Median reduction (dB) of the bed over frames where the dialogue is active (> ``active_db``), skipping the first
    three frames of every dialogue region (the compressor's attack)."""
    d, b, k = _frames_db(dialogue), _frames_db(bed), _frames_db(ducked)
    n = min(len(d), len(b), len(k))
    drops, run = [], 0
    for i in range(n):
        run = run + 1 if d[i] > active_db else 0
        if run > 3 and b[i] > -90:
            drops.append(b[i] - k[i])
    drops.sort()
    return {"frames": len(drops), "depth_db": round(drops[len(drops) // 2], 2) if drops else None}


def build_stems(pkg: Any, section: Any, cut: Path, stems_dir: Path, plan: MixPlan | None = None) -> dict[str, Any]:
    """Write the four stems for ``cut`` and return {stems, problems, ambience, sfx, music, total_s}."""
    cut, stems_dir = Path(cut), Path(stems_dir)
    report_path = cut.with_suffix(".cut.json")
    if not report_path.is_file():
        raise ValueError(f"{report_path.name} not found: render the cut first (film.py cut --render)")
    planned = json.loads(report_path.read_text(encoding="utf-8"))["planned"]
    root = Path(pkg.root)
    plan = plan or load_plan(root)
    total = float(planned["total_s"])
    stems_dir.mkdir(parents=True, exist_ok=True)
    problems: list[dict[str, str]] = []

    dialogue = stems_dir / "dialogue.wav"
    _ff("-i", str(cut), "-vn", "-ac", "2", "-ar", str(SR), "-t", f"{total:.3f}", "-c:a", "pcm_s16le", str(dialogue))

    spans = scene_spans(pkg, section, planned)
    layers, used_ambience = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for index, span in enumerate(spans, 1):
            length = span["end_s"] - span["start_s"]
            tone = tone_for(span["room_tone"])
            bed = calibrated_bed(tone, length, seed=index, lufs=plan.ambience_lufs, out=Path(tmp) / f"amb{index}.wav")
            fade = min(EDGE_FADE_S, length / 2)
            layers.append((bed, _timed("{in}", "{out}", span["start_s"], fade, fade, length)))
            used_ambience.append({**span, "tone": list(tone)})
        ambience = _stem(layers, total, stems_dir / "ambience.wav") if layers else _silent(total, stems_dir / "ambience.wav")

    # effects: placed only when an asset exists
    shots = pkg.typed.get("shots")
    declared = {g.generation_id: list(g.sfx) for g in shots.generations} if shots is not None else {}
    event = {e.event_id: e for e in section.events}
    sfx_layers, sfx_report = [], []
    for placed in planned["events"]:
        src = event[placed["event_id"]]
        for text in declared.get(src.generation_id, []) if src.kind == "TAKE" else []:
            asset = next((p for ext in (".wav", ".flac", ".mp3") if (p := audio_dir(root) / "sfx" / f"{slug(text)}{ext}").is_file()),
                         None)
            row = {"event_id": placed["event_id"], "text": text, "slug": slug(text), "at_s": placed["start_s"],
                   "asset": str(asset.relative_to(root)).replace("\\", "/") if asset else "",
                   "sha256": sha256_file(asset) if asset else ""}
            sfx_report.append(row)
            if asset is None:
                problems.append({"code": "SFX_UNSOURCED", "severity": "WARN",
                                 "detail": f"{placed['event_id']}: '{text}' has no asset audio/sfx/{slug(text)}.wav; "
                                           f"the take's own sound stays"})
            else:
                sfx_layers.append((asset, _timed("{in}", "{out}", placed["start_s"], 0.01, 0.0, 0.0, plan.sfx_gain_db)))
    sfx = _stem(sfx_layers, total, stems_dir / "sfx.wav") if sfx_layers else _silent(total, stems_dir / "sfx.wav")

    music_layers, music_report = [], []
    for cue in plan.music:
        asset = audio_dir(root) / cue.asset
        if not asset.is_file():
            problems.append({"code": "MUSIC_ASSET_MISSING", "severity": "BLOCK", "detail": f"{cue.cue_id}: {asset} not found"})
            continue
        end = min(cue.end_s if cue.end_s is not None else total, total)
        if end <= cue.start_s:
            problems.append({"code": "MUSIC_RANGE", "severity": "BLOCK", "detail": f"{cue.cue_id}: end <= start"})
            continue
        length = end - cue.start_s
        music_layers.append((asset, f"[{{in}}]atrim=0:{length:.3f},asetpts=PTS-STARTPTS[t_{{out}}];" +
                             _timed(f"t_{{out}}", "{out}", cue.start_s, cue.fade_in_s, cue.fade_out_s, length, cue.gain_db)))
        music_report.append({**cue.model_dump(mode="json"), "end_s": round(end, 3), "sha256": sha256_file(asset)})
    music = _stem(music_layers, total, stems_dir / "music.wav") if music_layers else _silent(total, stems_dir / "music.wav")
    return {"total_s": total, "stems": {"dialogue": str(dialogue), "ambience": str(ambience), "sfx": str(sfx),
                                        "music": str(music)},
            "ambience": used_ambience, "sfx": sfx_report, "music": music_report, "problems": problems}


def mix_stems(stems: dict[str, str], stems_dir: Path, plan: MixPlan, total_s: float) -> dict[str, Any]:
    """Duck the bed (ambience + music) under the dialogue, sum everything and return {mix, bed, bed_ducked, duck}."""
    stems_dir = Path(stems_dir)
    mix, bed, ducked = stems_dir / "mix.wav", stems_dir / "bed.wav", stems_dir / "bed_ducked.wav"
    threshold = 10 ** (plan.duck_threshold_db / 20)
    graph = (
        "[0:a]asplit=2[dk][dm];"
        "[1:a][3:a]amix=inputs=2:normalize=0[bedraw];[bedraw]asplit=2[bed][bedc];"
        f"[bedc][dk]sidechaincompress=threshold={threshold:.6f}:ratio={plan.duck_ratio}:"
        f"attack={plan.duck_attack_ms}:release={plan.duck_release_ms}:makeup=1[duck];[duck]asplit=2[ducked][duckm];"
        "[dm][duckm][2:a]amix=inputs=3:normalize=0:duration=first[m]")
    cmd = []
    for key in ("dialogue", "ambience", "sfx", "music"):
        cmd += ["-i", stems[key]]
    _ff(*cmd, "-filter_complex", graph, "-map", "[m]", "-c:a", "pcm_s16le", str(mix),
        "-map", "[bed]", "-c:a", "pcm_s16le", str(bed), "-map", "[ducked]", "-c:a", "pcm_s16le", str(ducked))
    return {"mix": str(mix), "bed": str(bed), "bed_ducked": str(ducked),
            "duck": duck_depth(Path(stems["dialogue"]), bed, ducked)}


def mix_cut(pkg: Any, section: Any, cut: Path, out: Path, *, stems_dir: Path | None = None,
            plan: MixPlan | None = None) -> dict[str, Any]:
    """Stems, ducked mix, mux into the cut's picture and loudness normalisation. Returns the report (also written to
    ``<film>/audio/mix.json``). Raises ValueError when a BLOCK problem stops the mix."""
    from film_pipeline.drama.post import measure_ebur128, normalize_loudness
    root, out = Path(pkg.root), Path(out)
    plan = plan or load_plan(root)
    stems_dir = Path(stems_dir) if stems_dir else audio_dir(root) / "stems"
    built = build_stems(pkg, section, Path(cut), stems_dir, plan)
    blocks = [p for p in built["problems"] if p["severity"] == "BLOCK"]
    if blocks:
        raise ValueError("; ".join(f"{p['code']}: {p['detail']}" for p in blocks))
    mixed = mix_stems(built["stems"], stems_dir, plan, built["total_s"])
    problems = list(built["problems"])
    has_bed = bool(built["ambience"] or built["music"])
    depth = mixed["duck"]["depth_db"]
    if has_bed and depth is None:
        problems.append({"code": "NO_DIALOGUE", "severity": "WARN", "detail": "no active dialogue frames: nothing ducked"})
    elif has_bed and depth < plan.min_duck_depth_db:
        problems.append({"code": "DUCK_TOO_SHALLOW", "severity": "WARN",
                         "detail": f"bed ducked by {depth} dB under dialogue, wanted >= {plan.min_duck_depth_db}"})
    out.parent.mkdir(parents=True, exist_ok=True)
    before = measure_ebur128(Path(mixed["mix"]))
    _ff("-i", str(cut), "-i", mixed["mix"], "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
        "-shortest", "-movflags", "+faststart", str(out))
    after = normalize_loudness(out, target_i=plan.target_lufs, true_peak=min(plan.true_peak_db, -1.5))
    ok_loud = abs(after["integrated_lufs"] - plan.target_lufs) <= plan.lufs_tolerance and \
        after["peak_dbfs"] <= plan.true_peak_db
    if not ok_loud:
        problems.append({"code": "LOUDNESS_OFF", "severity": "BLOCK",
                         "detail": f"{after['integrated_lufs']} LUFS / {after['peak_dbfs']} dBTP, wanted "
                                   f"{plan.target_lufs} +-{plan.lufs_tolerance} / <= {plan.true_peak_db}"})
    report = {"film_id": pkg.header.film_id, "cut": str(cut), "cut_sha256": sha256_file(Path(cut)), "output": str(out),
              "output_sha256": sha256_file(out), "total_s": built["total_s"], "plan": plan.model_dump(mode="json"),
              "stems": built["stems"], "ambience": built["ambience"], "sfx": built["sfx"], "music": built["music"],
              "duck": {**mixed["duck"], "wanted_db": plan.min_duck_depth_db},
              "loudness": {"before": before, "after": after, "target_lufs": plan.target_lufs,
                           "true_peak_db": plan.true_peak_db, "ok": ok_loud},
              "problems": problems, "ok": not any(p["severity"] == "BLOCK" for p in problems)}
    path = audio_dir(root) / "mix.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["report"] = str(path)
    return report


def stamp_post_item(pkg: Any, name: str, item: dict[str, Any]) -> str:
    """Record ``item`` as the post item ``name`` in 06_post.json, stamped with the fresh picture lock it was built on
    (empty stamp when the picture is not locked: the item is then reported UNSTAMPED by ``film.py lock``)."""
    from film_pipeline.production.lock import lock_status
    root = Path(pkg.root)
    status = lock_status(pkg)
    stamp = status["lock_edl_sha256"] if status.get("locked") and status.get("fresh") else ""
    path = root / "06_post.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    data[name] = {**item, "locked_against": stamp}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return stamp
