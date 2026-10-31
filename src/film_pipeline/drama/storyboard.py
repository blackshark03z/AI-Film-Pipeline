"""Drama P0 #12 — storyboard still-frame gate (Gate 2).

No video is generated for a scene until the Owner has approved a still
frame for (at least) its first shot. Approvals are hash-pinned: replacing
the image after approval re-opens the gate. The board is a JSON file so
the decision survives sessions and can be reviewed in Git.

``render_schematic_frame`` draws an offline 16:9 blocking sketch (who is
where, shot size, eyeline, time marks, line) with Pillow; it costs no
provider credit. A painted frame from any tool can replace it — the gate
only cares about the approved file hash.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field

from ..core import ContractModel
from .bible import hash_file
from .coverage import CoverageShot, SceneUnit

FrameStatus = Literal["PENDING", "APPROVED", "REJECTED"]


class StoryboardFrame(ContractModel):
    scene_id: str
    shot_id: str
    image_path: str            # relative to the board root
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: FrameStatus = "PENDING"
    reviewer: str = ""
    reviewed_at: str = ""
    note: str = ""


class StoryboardBoard(ContractModel):
    frames: list[StoryboardFrame] = Field(default_factory=list)


class StoryboardGate:
    def __init__(self, root: Path, board_file: str = "storyboard.json"
                 ) -> None:
        self.root = Path(root)
        self.path = self.root / board_file
        self.board = (StoryboardBoard.model_validate_json(
            self.path.read_text(encoding="utf-8"))
            if self.path.is_file() else StoryboardBoard())

    def save(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.board.model_dump(mode="json"),
                                        ensure_ascii=False, indent=2),
                             encoding="utf-8")
        return self.path

    def frame(self, shot_id: str) -> StoryboardFrame | None:
        return next((f for f in self.board.frames if f.shot_id == shot_id),
                    None)

    def register(self, scene_id: str, shot_id: str,
                 image_path: str) -> StoryboardFrame:
        """(Re)register a frame; a new image always resets to PENDING."""
        frame = StoryboardFrame(
            scene_id=scene_id, shot_id=shot_id, image_path=image_path,
            sha256=hash_file(self.root / image_path))
        self.board.frames = [f for f in self.board.frames
                             if f.shot_id != shot_id] + [frame]
        return frame

    def review(self, shot_id: str, *, status: FrameStatus, reviewer: str,
               note: str = "") -> StoryboardFrame:
        frame = self.frame(shot_id)
        if frame is None:
            raise KeyError(f"no storyboard frame registered for {shot_id}")
        if not reviewer.strip():
            raise ValueError("a review needs a named reviewer")
        frame.status = status
        frame.reviewer = reviewer
        frame.note = note
        frame.reviewed_at = datetime.now(timezone.utc).isoformat(
            timespec="seconds")
        return frame

    def problems(self, units: list[SceneUnit], *,
                 require_all_shots: bool = False) -> list[str]:
        """Empty list == Gate 2 open for these scenes."""
        found: list[str] = []
        for unit in units:
            shots = unit.shots if require_all_shots else unit.shots[:1]
            for shot in shots:
                frame = self.frame(shot.shot_id)
                if frame is None:
                    found.append(f"{shot.shot_id}: no storyboard frame")
                    continue
                if frame.status != "APPROVED":
                    found.append(f"{shot.shot_id}: storyboard "
                                 f"{frame.status}")
                path = self.root / frame.image_path
                if not path.is_file():
                    found.append(f"{shot.shot_id}: frame file missing")
                elif hash_file(path) != frame.sha256:
                    found.append(f"{shot.shot_id}: frame changed after "
                                 "review")
        return found


# ------------------------------------------------------------- rendering

_SIZE_SCALE = {"WIDE": 0.42, "MEDIUM": 0.62, "MEDIUM_CLOSE": 0.85,
               "CLOSE": 1.15}


def _font(size: int):
    from PIL import ImageFont
    for name in ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf",
                 "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_schematic_frame(unit: SceneUnit, shot: CoverageShot,
                           out_path: Path, *, width: int = 1280) -> Path:
    """Blocking sketch: grey silhouettes on their axis side, the subject
    highlighted, an arrow for the eyeline, time marks and the spoken line.
    Vietnamese text needs a TrueType font with diacritics (Arial/Segoe on
    Windows, DejaVu on Linux)."""
    from PIL import Image, ImageDraw

    height = width * 9 // 16
    image = Image.new("RGB", (width, height), (238, 236, 230))
    draw = ImageDraw.Draw(image)
    book = unit.axis_book
    scale = _SIZE_SCALE[shot.shot_size]
    head = int(height * 0.11 * scale)
    floor = int(height * (0.80 + 0.25 * (scale - 0.42)))
    visible = list(shot.axis.visible.items())
    for character, side in visible:
        is_subject = character == shot.subject or not shot.subject
        # OTS: the foreground shoulder sits large at the frame edge
        if shot.coverage == "OTS" and character == shot.foreground:
            cx = int(width * (0.08 if side == "LEFT" else 0.92))
            body_head = int(head * 1.6)
            fill = (120, 120, 120)
        else:
            if len(visible) == 1:
                cx = int(width * (0.42 if side == "LEFT" else 0.58))
            else:
                cx = int(width * (0.30 if side == "LEFT" else 0.70))
                if shot.coverage == "OTS":
                    cx = int(width * (0.62 if side == "RIGHT" else 0.38))
            body_head = head
            fill = (60, 90, 140) if is_subject else (150, 150, 150)
        cy = floor - body_head * 5
        draw.ellipse([cx - body_head, cy - body_head, cx + body_head,
                      cy + body_head], fill=fill)
        draw.rounded_rectangle([cx - body_head * 2, cy + body_head * 1.2,
                                cx + body_head * 2, floor + body_head * 3],
                               radius=body_head, fill=fill)
        eyeline = shot.axis.eyelines.get(character, "none")
        if eyeline in ("screen-left", "screen-right") and \
                character != shot.foreground:
            direction = 1 if eyeline == "screen-right" else -1
            x0 = cx + direction * body_head * 1.3
            x1 = x0 + direction * body_head * 2.2
            draw.line([x0, cy, x1, cy], fill=(200, 60, 40), width=4)
            draw.polygon([(x1, cy - 8), (x1, cy + 8),
                          (x1 + direction * 14, cy)], fill=(200, 60, 40))
        label_font = _font(max(16, height // 36))
        draw.text((cx, max(8, cy - body_head - 34)), character,
                  fill=(20, 20, 20), font=label_font, anchor="mm")
    small = _font(max(16, height // 34))
    header = (f"{shot.shot_id}  {shot.coverage} / {shot.shot_size}   "
              f"{shot.start_s:.1f}–{shot.end_s:.1f}s   "
              f"[{unit.scene_id}]")
    draw.rectangle([0, 0, width, height // 13], fill=(30, 30, 30))
    draw.text((16, height // 26), header, fill=(240, 240, 240),
              font=small, anchor="lm")
    caption = shot.describe(book)
    if shot.lines:
        caption = " / ".join(f"{l.character}: “{l.text}”"
                             for l in shot.lines)
    draw.rectangle([0, height - height // 9, width, height],
                   fill=(30, 30, 30))
    draw.text((16, height - height // 18), caption[:140],
              fill=(240, 240, 240), font=small, anchor="lm")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)
    return out_path
