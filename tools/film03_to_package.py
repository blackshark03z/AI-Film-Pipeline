"""P7-02: bring film03's shipped takes into its production package (no generation, no spend).

Registers the 16 existing takes (hash-bound, copied under the gitignored films/<id>/media/takes), writes the one
check a machine may honestly make (technical, ffprobe) as each take's review - the content groups stay UNASSESSED, so
every take is INCOMPLETE until a human reviews it - and writes the EDL (05_edit.json) and the dialogue timing
(titles/cues.json) that reproduce the shipped cut, from the same declarations the shipped post used.

    PYTHONPATH=src python tools/film03_to_package.py [--film films/film03_front_desk]
"""
from __future__ import annotations

import argparse
import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from film_pipeline.production import takes as T                                  # noqa: E402
from film_pipeline.production.edit import EditEvent, EditSection, TagEvent, TextLine   # noqa: E402
from film_pipeline.production.package import load_package                      # noqa: E402
from film_pipeline.production.qc_model import GroupCheck, TakeQc, blank_take   # noqa: E402
from film_pipeline.production.titles import _shot_lines                        # noqa: E402

LEGACY = REPO / "docs" / "drama" / "film03"
ROUTE, MODEL = "start_frame+Khung hinh", "Google Flow Omni 1.1 Flash"


def probe(clip: Path) -> str:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-show_entries", "format=duration", "-of", "json", str(clip)],
                         capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    s = data["streams"][0]
    return f"{s['width']}x{s['height']}, {float(data['format']['duration']):.2f} s"


def register_all(root: Path, pkg, order: list[str]) -> list[str]:
    notes = []
    for gid in order:
        src = LEGACY / "takes" / f"{gid}.mp4"
        meta = json.loads((LEGACY / "takes" / f"{gid}.take.json").read_text(encoding="utf-8"))
        prompt = (REPO / meta["prompt_file"]).read_text(encoding="utf-8")
        dst = root / "media" / "takes" / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.is_file():
            shutil.copyfile(src, dst)
        start = LEGACY / "stills_out" / f"start_{gid}.jpg"
        entry, created = T.register_take(root, pkg.header.film_id, gid, dst, prompt_text=prompt, route=ROUTE, model=MODEL,
                                         credits=0.0, start_frame=start if start.is_file() else None)
        if entry.output_sha256 != meta["sha256"]:
            raise SystemExit(f"{gid}: the take bytes differ from the legacy take record")
        qc = blank_take(entry.take_id, gid)
        evidence = f"ffprobe {dst.name}: {probe(dst)}; legacy bind {meta.get('binding', '?')}"
        qc.checks = [GroupCheck(group="technical", result="PASS", level="FULL_MOTION", evidence=evidence,
                                reviewer="auto:ffprobe")
                     if c.group == "technical" else c for c in qc.checks]
        body = qc.model_dump(mode="json")
        body["output_sha256"] = entry.output_sha256
        done = T.ingest_review(root, pkg.header.film_id, body)
        notes.append(f"{entry.take_id} {'new' if created else 'kept'} -> {done['status']}")
    return notes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--film", default=str(REPO / "films" / "film03_front_desk"))
    args = ap.parse_args()
    root = Path(args.film)
    story = importlib.import_module("drama_film03_story")
    post = importlib.import_module("drama_film03_post")
    pkg = load_package(root)
    notes = register_all(root, pkg, story.TAKES_ORDER)

    legacy_post = json.loads((LEGACY / "post" / "film03_post.json").read_text(encoding="utf-8"))
    anchors = {t["character"]: t for t in legacy_post["comprehension"]["tags"]}
    intros = {i.character: i for i in story.INTROS}
    cards = {c.before: c for c in story.CARDS}
    events, tags = [], []
    for gid in story.TAKES_ORDER:
        if gid in cards:
            c = cards[gid]
            events.append(EditEvent(event_id=c.card_id, kind="CARD", card_lines=list(c.lines),
                                    card_duration_s=c.duration()))
        events.append(EditEvent(event_id=gid, take_id=f"{gid}_t1"))
    for tag in story.TAGS:
        a, i = anchors[tag.character], intros[tag.character]
        tags.append(TagEvent(event_id=tag.generation_id, character=tag.character, label=i.label, relation=i.relation,
                             start_s=tag.start_s, end_s=tag.end_s, anchor_x=a["anchor_x"], anchor_y=a["anchor_y"]))
    # the shipped title burned the AI label bottom-left over the body; the package states it on the title card instead
    section = EditSection(events=events, tags=tags, title_s=post.TITLE_S, end_s=post.END_S,
                          title=[TextLine(text=post.TITLE[0][0], size=post.TITLE[0][1]),
                                 TextLine(text="Generated with AI", size=28)])
    (root / "05_edit.json").write_text(section.model_dump_json(indent=2) + "\n", encoding="utf-8")

    cues, unmatched = [], []
    for gid, a, b, text in post.CUES:
        match = [l for l in _shot_lines(pkg, gid) if l.text.strip().lower() == text.strip().lower()]
        if len(match) != 1:
            unmatched.append((gid, text))
            continue
        cues.append({"event_id": gid, "line_no": match[0].line_no, "start_s": a, "end_s": b})
    if unmatched:
        raise SystemExit(f"cues without exactly one script line: {unmatched}")
    titles = root / "titles"
    titles.mkdir(exist_ok=True)
    (titles / "cues.json").write_text(json.dumps({"cues": cues}, indent=2) + "\n", encoding="utf-8")
    print("\n".join(notes))
    print(f"05_edit.json: {len(events)} events, {len(tags)} tags; titles/cues.json: {len(cues)} cues")


if __name__ == "__main__":
    main()
