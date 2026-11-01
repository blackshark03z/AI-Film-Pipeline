"""film02 "The Spare Key": final cut, disclosure and marked copy.

Same post chain as film01 (drama.post + drama.disclosure). The flashback
marker is a plain 2 s "That morning" card cut in before SC02 (temporal
readability, scene_bible.check_temporal). Run from the repo root:
    PYTHONPATH=src uv run python tools/drama_film02_post.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from film_pipeline.drama.disclosure import (  # noqa: E402
    Disclosure, GeneratorRecord, VisibleLabel, check_release,
    default_dev_cert_dir, embed_metadata, read_c2pa, sha256_file,
    sign_c2pa, write_disclosure)
from film_pipeline.drama.post import (  # noqa: E402
    PostManifest, SubtitleCue, absolute_cues, assemble, clamp_cues,
    cue_offsets, normalize_loudness, probe_video_duration, title_card,
    write_srt)

DOCS = REPO / "docs/drama/film02"
TAKES = DOCS / "takes"
POST = DOCS / "post"
TITLE_S, END_S, CARD_S = 3.0, 4.0, 2.0
CARD = "FLASHBACK_card"
CLIPS = ["SC01_g1", "SC01_g2", CARD, "SC02_g1", "SC02_g2", "SC03_g1",
         "SC03_g2"]
# (clip, start_s, end_s, text): speech windows from silencedetect
# (-32 dB, 0.35 s, 200-3500 Hz); every one sits inside its ACTION phase
CUES = [
    ("SC01_g1", 2.7, 4.2, "So she left the house to you."),
    ("SC01_g2", 4.8, 6.2, "Mom always liked you best."),
    ("SC02_g1", 4.3, 6.4, "The brass one opens nothing."),
    ("SC02_g2", 3.8, 4.8, "He'll take it anyway."),
    ("SC03_g1", 2.2, 3.0, "Keep it, Marcus."),
    ("SC03_g2", 1.4, 2.8, "Your mother changed the locks."),
]
TITLE = [("THE SPARE KEY", 96)]
END = [("THE SPARE KEY", 64),
       ("A short drama. All characters are fictional.", 30),
       ("Video, images and voices generated with AI.", 30)]


def flashback_card(out: Path) -> Path:
    """Plain 2 s card with silent stereo audio, same format as the takes."""
    png = title_card(out.with_suffix(".png"), [("That morning", 56)])
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", str(CARD_S),
         "-r", "24", "-i", str(png), "-f", "lavfi", "-t", str(CARD_S),
         "-i", "anullsrc=r=48000:cl=stereo", "-c:v", "libx264",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)],
        check=True)
    png.unlink()
    return out


def disclosure(post: PostManifest) -> Disclosure:
    body_s = post.duration_s - TITLE_S - END_S
    return Disclosure(
        film_id="film02", title="THE SPARE KEY", created=post.date,
        generators=[
            GeneratorRecord(provider="Google Flow", model="Omni 1.1 Flash",
                            role="video+audio",
                            settings="720p, 8 s generations from a start "
                                     "frame (Khung hình)"),
            GeneratorRecord(provider="Google Flow", model="Nano Banana 2.1",
                            role="image",
                            settings="character stills, set plates, start "
                                     "frames")],
        post_tools=["ffmpeg", "Pillow"],
        synthetic_persons=True,
        synthetic_persons_note="ELENA, MARCUS and ROSA are fictional; faces "
                               "and voices are AI-generated.",
        human_contribution=["script", "storyboard", "edit", "subtitles",
                            "by the production team with AI assistance"],
        visible_label=VisibleLabel(
            text="AI-generated", start_s=TITLE_S, duration_s=body_s,
            watermark_text="AI-generated (bottom-left, over the body); end "
                           "card: Video, images and voices generated with "
                           "AI.",
            watermark_always_on=True),
        jurisdiction_notes=[
            "EU AI Act Art. 50 (applies from 2026-08-02): deployer "
            "disclosure of AI-generated video; provider machine-readable "
            "marking.",
            "The title, 'That morning' and end cards are plain graphics; "
            "the label runs over the whole body.",
            "C2PA signer, if present, is a self-issued development "
            "certificate: validators report it as untrusted; the manifest "
            "still binds the content hash.",
        ])


def main() -> None:
    POST.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        card = flashback_card(Path(tmp) / f"{CARD}.mp4")
        clips = [card if c == CARD else TAKES / f"{c}.mp4" for c in CLIPS]
        notes: list[str] = []
        cues = clamp_cues([SubtitleCue(generation_id=c, start_s=a, end_s=b,
                                       text=t, speaker_window=(0.0, 8.0))
                           for c, a, b, t in CUES], notes)
        srt = write_srt(absolute_cues(cues, cue_offsets(clips, TITLE_S)),
                        POST / "film02_spare_key.en.srt")
        final = assemble(clips, POST / "film02_spare_key_final.mp4",
                         cues=cues, title_lines=TITLE, end_lines=END,
                         title_s=TITLE_S, end_s=END_S)
    stats = normalize_loudness(final)
    post = PostManifest(
        film="film02 The Spare Key", date="2026-11-01",
        source="docs/drama/film02/takes (first-pass takes, WP7)",
        clips=CLIPS, final=final.name,
        sha256=hashlib.sha256(final.read_bytes()).hexdigest(),
        duration_s=probe_video_duration(final), title_s=TITLE_S,
        end_card_s=END_S,
        grade="drama.post default grade",
        audio="0.05/0.08 s edge fades per clip; loudnorm 2-pass + limiter "
              f"-> {stats['integrated_lufs']} LUFS integrated, "
              f"{stats['peak_dbfs']} dBFS peak (ebur128)",
        subtitles={"language": "en", "burned_in": True,
                   "sidecar": srt.name,
                   "timing": "silencedetect windows; text from the script"},
        label="AI-generated bottom-left over the body, plus end card")

    disc = disclosure(post)
    bad = disc.problems()
    if bad:
        raise SystemExit("disclosure problems: " + "; ".join(bad))
    certs = default_dev_cert_dir()
    cert, key = certs / "signer_cert.pem", certs / "signer_key.pem"
    marked = POST / "film02_spare_key_final_marked.mp4"
    c2pa_info = None
    with tempfile.TemporaryDirectory() as tmp:
        staged = embed_metadata(final, Path(tmp) / "meta.mp4", disc)
        if cert.is_file() and key.is_file():
            c2pa_info = sign_c2pa(staged, marked, disc, cert, key)
        else:
            marked.write_bytes(staged.read_bytes())
    done = write_disclosure(disc, marked, POST / "disclosure.json")
    record = post.model_dump()
    record["disclosure"] = {
        "json": "disclosure.json",
        "json_sha256": sha256_file(POST / "disclosure.json"),
        "marked": marked.name, "marked_sha256": done.content_sha256,
        "source_final_sha256": post.sha256, "metadata": True,
        "c2pa": c2pa_info is not None}
    (POST / "film02_post.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print("\n".join(notes) or "no cue clamped")
    print(final.name, post.duration_s, stats)
    print("check_release:", check_release(marked, POST / "disclosure.json")
          or "OK", "| c2pa:", read_c2pa(marked) is not None)


if __name__ == "__main__":
    main()
