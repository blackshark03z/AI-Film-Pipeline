"""Post-render QC between generations (render gating).

Generations of a scene are rendered one at a time: after generation N is
rendered, ``handoff_sheet`` puts its last frame next to the planned start of
N+1 and ``HandoffQC`` turns the declared end state into a checklist (every
position, prop and look). Generation N+1 may assume that end state only when
a reviewer has passed every item; ``HandoffQC.to_handoff`` then sets
``end_state_verified``. ``character_sheet`` lays out sampled frames of every
generation in rows so a character's look can be compared across the film.

Frames come from ffmpeg; nothing here judges images automatically.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import Field

from ..core import ContractModel
from .bible import CharacterLook
from .continuity import ContinuityState, GenerationHandoff

CheckStatus = Literal["PENDING", "PASS", "FAIL"]


def _probe_duration(clip: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(clip)],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def extract_frame(clip: Path, out: Path, *, at_s: float | None = None
                  ) -> Path:
    """Frame at ``at_s`` seconds; ``None`` means the last frame."""
    if at_s is None:
        at_s = max(_probe_duration(clip) - 0.1, 0.0)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at_s:.3f}",
                    "-i", str(clip), "-frames:v", "1", str(out)], check=True)
    return out


def _labelled_row(images: list[Path], label: str, height: int):
    from PIL import Image, ImageDraw
    tiles = []
    for path in images:
        img = Image.open(path).convert("RGB")
        tiles.append(img.resize((int(img.width * height / img.height),
                                 height)))
    row = Image.new("RGB", (sum(t.width for t in tiles), height), "black")
    x = 0
    for tile in tiles:
        row.paste(tile, (x, 0))
        x += tile.width
    draw = ImageDraw.Draw(row)
    draw.rectangle((0, 0, 8 + 7 * len(label), 16), fill="black")
    draw.text((4, 3), label, fill="yellow")
    return row


def _stack(rows, out: Path) -> Path:
    from PIL import Image
    width = max(r.width for r in rows)
    sheet = Image.new("RGB", (width, sum(r.height for r in rows)), "black")
    y = 0
    for row in rows:
        sheet.paste(row, (0, y))
        y += row.height
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def handoff_sheet(previous_clip: Path, next_clip: Path | None, out: Path,
                  *, height: int = 360) -> Path:
    """Last frame of the previous generation | first frame of the next one
    (or the last frame alone, before the next generation is rendered)."""
    with tempfile.TemporaryDirectory() as tmp:
        frames = [extract_frame(previous_clip, Path(tmp) / "end.png")]
        if next_clip is not None:
            frames.append(extract_frame(next_clip, Path(tmp) / "start.png",
                                        at_s=0.0))
        label = "end | start" if next_clip is not None else "end"
        return _stack([_labelled_row(frames, label, height)], out)


def character_sheet(clips: dict[str, Path], out: Path, *,
                    frames_per_clip: int = 4, height: int = 180) -> Path:
    """One labelled row of evenly sampled frames per generation."""
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for label, clip in clips.items():
            duration = _probe_duration(clip)
            step = duration / frames_per_clip
            frames = [extract_frame(clip, Path(tmp) / f"{label}_{i}.png",
                                    at_s=step * (i + 0.5))
                      for i in range(frames_per_clip)]
            rows.append(_labelled_row(frames, label, height))
        return _stack(rows, out)


class HandoffCheck(ContractModel):
    item: str
    expected: str
    status: CheckStatus = "PENDING"
    note: str = ""


class HandoffQC(ContractModel):
    previous_generation_id: str
    next_generation_id: str
    sheet: str = ""
    checks: list[HandoffCheck] = Field(default_factory=list)
    reviewer: str = ""

    @classmethod
    def from_end_state(cls, previous_id: str, next_id: str,
                       end_state: ContinuityState, *,
                       looks: list[CharacterLook] | None = None,
                       sheet: str = "") -> "HandoffQC":
        by_id = {lk.look_id: lk for lk in looks or []}
        checks = [HandoffCheck(item=f"position:{who}", expected=where)
                  for who, where in end_state.positions.items()]
        checks += [HandoffCheck(item=f"prop:{prop}", expected=where)
                   for prop, where in end_state.props.items()]
        for who, look_id in end_state.looks.items():
            look = by_id.get(look_id)
            expected = "; ".join(look.invariants) if look else look_id
            checks.append(HandoffCheck(item=f"look:{who}", expected=expected))
        return cls(previous_generation_id=previous_id,
                   next_generation_id=next_id, sheet=sheet, checks=checks)

    def review(self, item: str, status: CheckStatus, note: str = ""
               ) -> None:
        check = next(c for c in self.checks if c.item == item)
        check.status = status
        check.note = note

    @property
    def verified(self) -> bool:
        return bool(self.reviewer) and bool(self.checks) and \
            all(c.status == "PASS" for c in self.checks)

    def to_handoff(self, *, previous_action: str,
                   previous_start: ContinuityState,
                   previous_end: ContinuityState) -> GenerationHandoff:
        return GenerationHandoff(
            previous_generation_id=self.previous_generation_id,
            previous_action=previous_action, previous_start=previous_start,
            previous_end=previous_end, end_state_verified=self.verified)
