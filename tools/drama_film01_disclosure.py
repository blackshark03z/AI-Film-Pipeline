"""Write the film01 disclosure.json and a marked copy of the approved final.

The approved film01_first_day_final.mp4 is never modified: the marked copy
gets metadata (stream copy) and, when the ``provenance`` extra and a dev cert
exist, a C2PA manifest as the last step (it binds the final bytes). Also adds
a ``disclosure`` block to film01_post.json. Run from the repo root:
    PYTHONPATH=src uv run python tools/drama_film01_disclosure.py
"""
from __future__ import annotations

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

POST = REPO / "docs/drama/film01_post"
MANIFEST = POST / "film01_post.json"
FINAL = POST / "film01_first_day_final.mp4"
MARKED = POST / "film01_first_day_final_marked.mp4"
DISCLOSURE = POST / "disclosure.json"


def build(post: dict) -> Disclosure:
    title_s, end_s = post["title_s"], post["end_card_s"]
    body_s = post["duration_s"] - title_s - end_s
    return Disclosure(
        film_id="film01", title="FIRST DAY", created=post["date"],
        generators=[GeneratorRecord(
            provider="Google Flow", model="Omni 1.1 Flash",
            role="video+audio",
            settings="720p, 8 s generations, text-only route")],
        post_tools=["ffmpeg", "Pillow"],
        synthetic_persons=True,
        synthetic_persons_note="Characters NORA and DOYLE are fictional; "
                               "faces and voices are AI-generated.",
        human_contribution=[
            "script", "storyboard", "edit", "subtitles",
            "by the production team with AI assistance"],
        # label as burned in by drama_film01_post.py: "AI-generated" bottom
        # left over the body (after the plain 3 s title card), plus an end
        # card line "Video and voices generated with AI."
        visible_label=VisibleLabel(
            text="AI-generated", start_s=title_s, duration_s=body_s,
            watermark_text="AI-generated (bottom-left, over all generated "
                           "footage); end card: Video and voices generated "
                           "with AI.",
            watermark_always_on=True),
        jurisdiction_notes=[
            "EU AI Act Art. 50 (applies from 2026-08-02): deployer "
            "disclosure of AI-generated video; provider machine-readable "
            "marking.",
            "Fictional/artistic work: discreet label kept, not dropped.",
            "The 0-3 s title card is a plain graphic; the label is on for "
            "the whole generated body.",
            "C2PA signer, if present, is a self-issued development "
            "certificate: validators report it as untrusted; the manifest "
            "still binds the content hash.",
        ])


def main() -> None:
    post = json.loads(MANIFEST.read_text(encoding="utf-8"))
    disc = build(post)
    bad = disc.problems()
    if bad:
        raise SystemExit("disclosure problems: " + "; ".join(bad))
    certs = default_dev_cert_dir()
    cert, key = certs / "signer_cert.pem", certs / "signer_key.pem"
    c2pa_info = None
    with tempfile.TemporaryDirectory() as tmp:
        staged = embed_metadata(FINAL, Path(tmp) / "meta.mp4", disc)
        try:
            import c2pa  # noqa: F401
            can_sign = cert.is_file() and key.is_file()
        except ImportError:
            can_sign = False
        if can_sign:
            c2pa_info = sign_c2pa(staged, MARKED, disc, cert, key)
        else:
            MARKED.write_bytes(staged.read_bytes())
    done = write_disclosure(disc, MARKED, DISCLOSURE)
    post["disclosure"] = {
        "json": DISCLOSURE.name, "json_sha256": sha256_file(DISCLOSURE),
        "marked": MARKED.name, "marked_sha256": done.content_sha256,
        "source_final_sha256": sha256_file(FINAL),
        "metadata": True, "c2pa": c2pa_info is not None,
        "c2pa_signer": "self-issued dev certificate (untrusted by validators)"
                       if c2pa_info else None}
    MANIFEST.write_text(json.dumps(post, indent=2) + "\n", encoding="utf-8")
    print("check_release:", check_release(MARKED, DISCLOSURE) or "OK")
    print("c2pa:", json.dumps(c2pa_info, indent=1) if c2pa_info
          else "not applied")
    print("marked sha256:", done.content_sha256, "read_c2pa:",
          read_c2pa(MARKED) is not None)


if __name__ == "__main__":
    main()
