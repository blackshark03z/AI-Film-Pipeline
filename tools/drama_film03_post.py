"""film03 "The Front Desk": final cut, disclosure and marked copy.

Same post chain as film02: comprehension check, context cards ("The new
captain arrives early", "Roll call, 8 a.m."), identity tags placed by
drama.tag_layout (preview sheet in post/), subtitles, loudness, AI label,
disclosure, C2PA. Declarations live in drama_film03_story.py. Run from the
repo root:
    PYTHONPATH=src uv run python tools/drama_film03_post.py
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from film_pipeline.drama.disclosure import (  # noqa: E402
    Disclosure, GeneratorRecord, VisibleLabel, check_release,
    default_dev_cert_dir, embed_metadata, read_c2pa, sha256_file,
    sign_c2pa, write_disclosure)
from film_pipeline.drama.comprehension import (  # noqa: E402
    check_comprehension, screen_text_cues, tag_overlays)
from film_pipeline.drama.tag_layout import (  # noqa: E402
    auto_place, reference_embeddings, tag_preview_sheet)
from film_pipeline.drama.post import (  # noqa: E402
    PostManifest, SubtitleCue, absolute_cues, assemble, clamp_cues,
    context_card_clip, cue_offsets, normalize_loudness,
    merge_cues, probe_video_duration, write_srt)

sys.path.insert(0, str(REPO / "tools"))
from drama_film03_story import (CARDS, FACTS, IN_FRAME, INTROS,  # noqa: E402
                                TAGS, TAKES_ORDER, VI)

DOCS = REPO / "docs/drama/film03"
TAKES = DOCS / "takes"
POST = DOCS / "post"
TITLE_S, END_S = 3.0, 4.0
CLIPS = []
for g in TAKES_ORDER:
    CLIPS += [c.card_id for c in CARDS if c.before == g] + [g]
# (clip, start_s, end_s, text): speech windows from silencedetect
# (-32 dB, 0.35 s, 200-3500 Hz); every one sits inside its ACTION phase
CUES = [
    ("SC01_g1", 2.4, 3.8, "Complaints window opens at nine."),
    ("SC01_g2", 3.4, 4.4, "I'm not here to complain."),
    ("SC02_g1", 3.3, 6.0, "Captain? Captains here don't look like you."),
    ("SC02_g2", 0.9, 2.8, "Nice try. Next."),
    ("SC03_g1", 2.5, 5.3, "Sarge, maybe we call upstairs?"),
    ("SC03_g2", 2.6, 5.0, "Maybe you go file something."),
    ("SC04_g1", 2.5, 3.5, "What's your name, officer?"),
    ("SC04_g2", 4.3, 4.9, "Ortiz, ma'am."),
    ("SC05_g1", 2.8, 5.9, "Desk. Yes, Lieutenant. The new captain?"),
    ("SC05_g2", 2.7, 4.3, "Captain Nora Bell."),
    ("SC06_g1", 2.2, 3.7, "Roll call is at eight, Sergeant."),
    ("SC06_g2", 2.6, 3.4, "Yes... Captain."),
    ("SC07_g1", 2.4, 5.4, "We check before we judge. Every time."),
    ("SC07_g2", 2.4, 4.4, "Officer Ortiz rides with me today."),
    ("SC08_g1", 2.3, 2.9, "Yes, ma'am."),
    ("SC08_g2", 3.3, 4.8, "Sergeant Kessler keeps the desk."),
]
TITLE = [("THE FRONT DESK", 96)]
END = [("THE FRONT DESK", 64),
       ("A short drama. All characters are fictional.", 30),
       ("Video, images and voices generated with AI.", 30)]


def disclosure(post: PostManifest) -> Disclosure:
    body_s = post.duration_s - TITLE_S - END_S
    return Disclosure(
        film_id="film03", title="THE FRONT DESK", created=post.date,
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
        synthetic_persons_note="NORA, KESSLER and ORTIZ are fictional; faces "
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
            "The title, context and end cards and the identity tags are "
            "plain graphics; the label runs over the whole body.",
            "C2PA signer, if present, is a self-issued development "
            "certificate: validators report it as untrusted; the manifest "
            "still binds the content hash.",
        ])


def sidecars(offsets: dict[str, float], cues: list[SubtitleCue],
             tags: list, duration_s: float) -> list[Path]:
    """Full sidecars, English and Vietnamese: title, context cards,
    identity tags, dialogue and the end card (with the AI notice), merged
    so no two cues overlap. The picture burns in only the English
    dialogue; a sidecar also serves muted / hard-of-hearing viewers."""
    out = []
    end_s = duration_s - END_S
    for lang, tr in (("en", None), ("vi", VI)):
        def t(text: str) -> str:
            return text if tr is None else tr[text]
        events = [(0.0, TITLE_S, t(TITLE[0][0])),
                  (end_s, duration_s, "\n".join(t(x) for x, _ in END[1:]))]
        events += screen_text_cues(offsets, CARDS, tags, INTROS, tr)
        events += [(a, b, t(x)) for a, b, x in absolute_cues(cues, offsets)]
        out.append(write_srt(merge_cues(events),
                             POST / f"film03_front_desk.{lang}.srt"))
    return out


def main() -> None:
    POST.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    cues = clamp_cues([SubtitleCue(generation_id=c, start_s=a, end_s=b,
                                   text=t, speaker_window=(0.0, 8.0))
                       for c, a, b, t in CUES], notes)
    refs = reference_embeddings({c.character: DOCS / "stills_out" /
                                 f"char_{c.character}.jpg" for c in INTROS})
    takes = {g: TAKES / f"{g}.mp4" for g in TAKES_ORDER}
    tags, issues = auto_place(TAGS, INTROS, takes, refs)
    issues += check_comprehension(TAKES_ORDER, IN_FRAME, INTROS, FACTS, tags,
                                  CARDS, cues)
    if any(i.severity == "BLOCK" for i in issues):
        raise SystemExit("comprehension: " + "; ".join(
            f"{i.check} {i.detail}" for i in issues))
    with tempfile.TemporaryDirectory() as tmp:
        cards = {c.card_id: context_card_clip(Path(tmp) / f"{c.card_id}.mp4",
                                              c.lines, c.duration())
                 for c in CARDS}
        clips = [cards.get(c) or TAKES / f"{c}.mp4" for c in CLIPS]
        offsets = cue_offsets(clips, TITLE_S)
        final = assemble(clips, POST / "film03_front_desk_final.mp4",
                         cues=cues, title_lines=TITLE, end_lines=END,
                         title_s=TITLE_S, end_s=END_S,
                         overlays=tag_overlays(tags, INTROS, Path(tmp)))
    tag_preview_sheet(tags, INTROS, takes, POST / "tags_preview.jpg")
    stats = normalize_loudness(final)
    srts = sidecars(offsets, cues, tags, probe_video_duration(final))
    post = PostManifest(
        film="film03 The Front Desk", date="2026-11-02",
        source="docs/drama/film03/takes (start-frame takes)",
        clips=CLIPS, final=final.name,
        sha256=hashlib.sha256(final.read_bytes()).hexdigest(),
        duration_s=probe_video_duration(final), title_s=TITLE_S,
        end_card_s=END_S,
        grade="drama.post default grade",
        audio="0.05/0.08 s edge fades per clip; loudnorm 2-pass + limiter "
              f"-> {stats['integrated_lufs']} LUFS integrated, "
              f"{stats['peak_dbfs']} dBFS peak (ebur128)",
        subtitles={"language": "en", "burned_in": "dialogue only",
                   "sidecars": [p.name for p in srts],
                   "sidecar_content": "title, context cards, identity tags, "
                                      "dialogue, end card (AI notice)",
                   "timing": "silencedetect windows; text from the script"},
        label="AI-generated bottom-left over the body, plus end card")

    disc = disclosure(post)
    bad = disc.problems()
    if bad:
        raise SystemExit("disclosure problems: " + "; ".join(bad))
    certs = default_dev_cert_dir()
    cert, key = certs / "signer_cert.pem", certs / "signer_key.pem"
    marked = POST / "film03_front_desk_final_marked.mp4"
    c2pa_info = None
    with tempfile.TemporaryDirectory() as tmp:
        staged = embed_metadata(final, Path(tmp) / "meta.mp4", disc)
        if cert.is_file() and key.is_file():
            c2pa_info = sign_c2pa(staged, marked, disc, cert, key)
        else:
            marked.write_bytes(staged.read_bytes())
    done = write_disclosure(disc, marked, POST / "disclosure.json")
    record = post.model_dump()
    record["comprehension"] = {
        "intros": [i.model_dump() for i in INTROS],
        "tags": [t.model_dump() for t in tags],
        "cards": [{**c.model_dump(), "duration_s": c.duration()}
                  for c in CARDS],
        "facts": [f.model_dump() for f in FACTS],
        "issues": [i.model_dump() for i in issues]}
    record["disclosure"] = {
        "json": "disclosure.json",
        "json_sha256": sha256_file(POST / "disclosure.json"),
        "marked": marked.name, "marked_sha256": done.content_sha256,
        "source_final_sha256": post.sha256, "metadata": True,
        "c2pa": c2pa_info is not None}
    record["delivery"] = {
        p.name: sha256_file(p) for p in
        [marked, POST / "disclosure.json", *srts]}
    (POST / "film03_post.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print("\n".join(notes) or "no cue clamped")
    print(final.name, post.duration_s, stats)
    print("check_release:", check_release(marked, POST / "disclosure.json")
          or "OK", "| c2pa:", read_c2pa(marked) is not None)


if __name__ == "__main__":
    main()
