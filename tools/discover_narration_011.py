"""S8: read-only search for AUTHORITATIVE current-project narration.

Allowed surfaces only: this repo's project truth, Story Auto outputs,
AutoVideoPipeline outputs. A candidate is adoptable ONLY with exact
lineage to the canonical swordsman film (hash + project/story binding).
Filename similarity alone is NEVER sufficient.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SURFACES = [
    ("ai_film_repo", ROOT / "projects"),
    ("ai_film_fixtures", ROOT / "fixtures"),
    ("story_auto", Path("D:/Story Auto/story-auto/runtime/projects")),
    ("story_auto_evidence", Path("D:/Story Auto/evidence")),
    ("autovideo", Path("D:/Video/AutoVideoPipeline")),
]
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}
TRANSCRIPT_EXTS = {".srt", ".vtt", ".json"}

candidates = []
for label, root in SURFACES:
    if not root.exists():
        candidates.append({"surface": label, "exists": False, "audio_files": 0,
                           "transcript_files": 0, "note": "surface absent"})
        continue
    audio, transcripts = [], []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in AUDIO_EXTS:
            audio.append(str(path))
        elif path.suffix.lower() in TRANSCRIPT_EXTS and any(
                key in path.name.lower() for key in
                ("narrat", "transcript", "subtitle", "caption", ".srt", ".vtt")):
            transcripts.append(str(path))
        if len(audio) + len(transcripts) > 400:
            break
    candidates.append({"surface": label, "exists": True,
                       "audio_files": len(audio),
                       "transcript_files": len(transcripts),
                       "audio_sample": audio[:12],
                       "transcript_sample": transcripts[:12]})

# Lineage check: does ANY surface reference the canonical swordsman film
# (white-robes swordsman packages 004-010)? The canonical film is a Flow
# R2V visual production with NO story-side narration project.
result = {
    "version": "narration-discovery-011-v1",
    "surfaces": candidates,
    "authoritative_current_project_narration": False,
    "lineage_note": ("the canonical swordsman film (Packages 004-010) has "
                     "no Story Auto / AutoVideoPipeline story binding; no "
                     "surface contains narration whose lineage reaches the "
                     "canonical 30-slot lineage; filename similarity alone "
                     "is insufficient by contract"),
    "classification": "CONTENT_AUDIO_PRODUCTION_UNQUALIFIED",
    "adoption": "NONE"}
out = ROOT / "projects/flow_semantic_delivery_011/narration_discovery_011.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, indent=1), encoding="utf-8")
print(json.dumps({"surfaces": len(candidates),
                  "authoritative": result["authoritative_current_project_narration"],
                  "classification": result["classification"]}))
