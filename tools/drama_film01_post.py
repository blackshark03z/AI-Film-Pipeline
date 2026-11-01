"""Rebuild the film01 final cut from the committed clips with drama.post.

Writes to --out (default docs/drama/film01_post/rebuild/); never touches the
committed final. Run from the repo root:
    PYTHONPATH=src uv run python tools/drama_film01_post.py [--out DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from film_pipeline.drama.post import (  # noqa: E402
    PostManifest, SubtitleCue, absolute_cues, assemble, clamp_cues,
    cue_offsets, normalize_loudness, probe_video_duration, write_srt)

DOCS = REPO / "docs/drama"
TAKES = DOCS / "film01_takes/noref"
TITLE_S, END_S = 3.0, 4.0
CLIPS = [f"SC0{s}_g{g}" for s in range(1, 6) for g in (1, 2)]
# speaking-shot windows (clip-relative) from the generation plan; the other
# generations are one shot for the whole 8 s
WINDOWS = {"SC01_g2": (0.0, 3.6), "SC02_g2": (0.0, 3.8),
           "SC04_g2": (0.0, 3.4), "SC05_g2": (2.5, 5.5)}
# (clip, start_s, end_s, text): estimated from silencedetect
CUES = [
    ("SC01_g1", 4.5, 6.0, "Help you, ma'am?"),
    ("SC01_g2", 0.4, 1.9, "Good morning, Sergeant."),
    ("SC01_g2", 1.9, 3.6, "I'm here to report for duty."),
    ("SC02_g1", 3.2, 5.7, "Toy-store badge. Try again."),
    ("SC02_g2", 0.5, 2.1, "My name is Nora Hale."),
    ("SC02_g2", 2.1, 3.8, "Today is my first day."),
    ("SC03_g1", 4.5, 5.9, "Fake papers too."),
    ("SC03_g1", 5.9, 7.8, "You people will try anything."),
    ("SC04_g1", 1.1, 2.6, "Three seconds."),
    ("SC04_g1", 2.6, 4.8, "Then you're under arrest."),
    ("SC04_g2", 0.8, 2.6, "Call Lieutenant Commander Reed."),
    ("SC04_g2", 2.6, 3.4, "Right now."),
    ("SC05_g1", 2.1, 4.0, "Good morning, Chief Hale."),
    ("SC05_g2", 2.5, 4.0, "Sergeant. Your badge."),
    ("SC05_g2", 4.0, 5.5, "On the counter."),
]
TITLE = [("FIRST DAY", 96)]
END = [("FIRST DAY", 64),
       ("A short drama. All characters are fictional.", 30),
       ("Video and voices generated with AI.", 30)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path,
                    default=DOCS / "film01_post/rebuild")
    out_dir = ap.parse_args().out
    out_dir.mkdir(parents=True, exist_ok=True)

    clips = [TAKES / f"{c}.mp4" for c in CLIPS]
    notes: list[str] = []
    cues = clamp_cues(
        [SubtitleCue(generation_id=c, start_s=a, end_s=b, text=t,
                     speaker_window=WINDOWS.get(c, (0.0, 8.0)))
         for c, a, b, t in CUES], notes)
    print("\n".join(notes) or "no cue needed clamping")
    srt = write_srt(absolute_cues(cues, cue_offsets(clips, TITLE_S)),
                    out_dir / "film01_first_day.en.srt")
    final = assemble(clips, out_dir / "film01_first_day_final.mp4",
                     cues=cues, title_lines=TITLE, end_lines=END,
                     title_s=TITLE_S, end_s=END_S)
    stats = normalize_loudness(final)
    manifest = PostManifest(
        film="film01 First Day", date="2026-11-01",
        source="film01_takes/noref clips of the Owner-approved rough cut "
               "(2026-11-01)",
        clips=CLIPS, final=final.name,
        sha256=hashlib.sha256(final.read_bytes()).hexdigest(),
        duration_s=probe_video_duration(final), title_s=TITLE_S,
        end_card_s=END_S,
        grade="eq contrast 1.04, saturation 0.92, gamma 0.98; "
              "slightly cool shadows",
        audio="0.05/0.08 s edge fades per clip; loudnorm 2-pass + limiter "
              f"-> {stats['integrated_lufs']} LUFS integrated, "
              f"{stats['peak_dbfs']} dBFS peak (ebur128)",
        subtitles={"language": "en", "burned_in": True,
                   "sidecar": srt.name,
                   "timing": "estimated from silencedetect; text from the "
                             "script, not transcribed; each cue clamped to "
                             "the speaking shot of the generation plan"},
        label="AI-generated bottom-left over the body, plus end card")
    (out_dir / "film01_post.json").write_text(
        json.dumps(manifest.model_dump(), indent=2), encoding="utf-8")
    print(final, manifest.duration_s, stats)
    committed = DOCS / "film01_post/film01_first_day.en.srt"
    same = (srt.read_text(encoding="utf-8").replace("\r\n", "\n") ==
            committed.read_text(encoding="utf-8").replace("\r\n", "\n"))
    print("srt identical to committed:", same)


if __name__ == "__main__":
    main()
