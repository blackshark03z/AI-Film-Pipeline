"""Place identity tags automatically: find the character, put the tag
beside the face, never over a face or the subtitle band.

film02 anchors were measured by eye per shot. Here faces come from the
autoqc detector (YuNet), each face is named by its SFace match against the
character stills (screen side cannot split ROSA and ELENA, who share the
left), and the tag goes to the first free slot: the side facing the frame
centre, the other side, then above the head. Faces are sampled across the
whole tag window, so a character who moves (MARCUS crossing to the table)
is avoided at every moment. White text over a lamp or a lit window washes
out even with its stroke (film02 SC02_g1/SC03_g1 trial), so a slot whose
background is mostly glare is used only when nothing else is free.
``place_tag`` is pure; the rest needs the
``qc`` extra and the autoqc models.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..core import ContractModel
from .comprehension import CharacterIntro, IdentityTag
from .post import H, TAG_MARGIN, W, identity_tag_size
from .scene_bible import RuleIssue

GAP = 18                 # px between face and tag
FACE_PAD = 10            # px kept clear around every face
SUBTITLE_BAND = 110      # px at the bottom reserved for subtitles
MATCH_MIN = 0.25         # autoqc IDENTITY_MEAN_MIN: below it, no name
GLARE_LUMA = 200         # 0-255: brighter pixels wash white text out
GLARE_MAX = 0.10         # max share of glare pixels behind a tag


class Box(ContractModel):
    x: float
    y: float
    w: float
    h: float

    def grown(self, pad: float) -> "Box":
        return Box(x=self.x - pad, y=self.y - pad, w=self.w + 2 * pad,
                   h=self.h + 2 * pad)

    def hits(self, other: "Box") -> bool:
        return (self.x < other.x + other.w and other.x < self.x + self.w
                and self.y < other.y + other.h and other.y < self.y + self.h)


def place_tag(target: Box, faces: list[Box], size: tuple[float, float],
              glare: Callable[[Box], float] | None = None
              ) -> tuple[float, float] | None:
    """(anchor_x, anchor_y) for a tag of ``size`` px beside ``target``, or
    None when no slot is free. ``faces``: every face to keep clear,
    target included (all samples of the window). ``glare(slot)``: share of
    glare pixels behind a slot; the first free slot under ``GLARE_MAX``
    wins, else the free slot with the least glare."""
    w, h = size
    toward_right = target.x + target.w / 2 < W / 2
    rows = [target.y, target.y + target.h - h, target.y + target.h + GAP]
    right = [Box(x=target.x + target.w + GAP, y=y, w=w, h=h) for y in rows]
    left = [Box(x=target.x - GAP - w, y=y, w=w, h=h) for y in rows]
    above = Box(x=target.x + target.w / 2 - w / 2,
                y=target.y - GAP - h, w=w, h=h)
    order = right + left if toward_right else left + right
    clear = [f.grown(FACE_PAD) for f in faces]
    free = [s for s in [*order, above]
            if s.x >= TAG_MARGIN and s.x + w <= W - TAG_MARGIN
            and s.y >= TAG_MARGIN and s.y + h <= H - SUBTITLE_BAND
            and not any(s.hits(f) for f in clear)]
    calm = [s for s in free if glare is None or glare(s) <= GLARE_MAX]
    if not calm and free:
        calm = [min(free, key=glare)]
    slot = (calm or [None])[0]
    return None if slot is None else ((slot.x + w / 2) / W, slot.y / H)


def assign_by_identity(embeddings: list[list[float]],
                       refs: dict[str, list[float]]) -> dict[str, int]:
    """Character -> face index, best cosine first, each face once, and only
    above ``MATCH_MIN``."""
    from .autoqc import cosine
    pairs = sorted(((cosine(e, r), who, i) for i, e in enumerate(embeddings)
                    for who, r in refs.items()), reverse=True)
    out: dict[str, int] = {}
    for score, who, i in pairs:
        if score >= MATCH_MIN and who not in out and i not in out.values():
            out[who] = i
    return out


# ------------------------------------------------------------------ io

def reference_embeddings(stills: dict[str, Path]) -> dict[str, list[float]]:
    """SFace embedding of the largest face in each character still."""
    import cv2
    from .autoqc import detect_faces, face_embedding
    out = {}
    for who, path in stills.items():
        img = cv2.imread(str(path))
        faces = detect_faces(img) if img is not None else []
        if faces:
            out[who] = face_embedding(img, max(faces, key=lambda b: b.h))
    return out


def glare_of(frame) -> Callable[[Box], float]:
    """Share of pixels brighter than ``GLARE_LUMA`` inside a W x H box."""
    import cv2
    luma = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (W, H))

    def share(b: Box) -> float:
        x0, y0 = max(int(b.x), 0), max(int(b.y), 0)
        patch = luma[y0:int(b.y + b.h), x0:int(b.x + b.w)]
        return float((patch > GLARE_LUMA).mean()) if patch.size else 1.0
    return share


def _named_faces(frame, refs: dict[str, list[float]]
                 ) -> tuple[dict[str, Box], list[Box]]:
    from .autoqc import detect_faces, face_embedding, people_faces
    fh, fw = frame.shape[:2]
    sx, sy = W / fw, H / fh
    found = people_faces(detect_faces(frame))
    boxes = [Box(x=b.x * sx, y=b.y * sy, w=b.w * sx, h=b.h * sy)
             for b in found]
    names = assign_by_identity([face_embedding(frame, b) for b in found],
                               refs)
    return {who: boxes[i] for who, i in names.items()}, boxes


def auto_place(tags: list[IdentityTag], intros: list[CharacterIntro],
               clips: dict[str, Path], refs: dict[str, list[float]],
               samples: int = 5) -> tuple[list[IdentityTag], list[RuleIssue]]:
    """Fill ``anchor_x``/``anchor_y`` of every tag that has none. A tag
    whose character is not found, or has no free slot, keeps no anchor and
    gets a BLOCK issue (place it by hand or pick another window)."""
    from .autoqc import frame_at
    by_char = {i.character: i for i in intros}
    out, issues = [], []
    for t in tags:
        if t.anchor_x is not None:
            out.append(t)
            continue
        span = t.end_s - t.start_s
        times = [t.start_s + span * k / (samples - 1)
                 for k in range(samples)]
        seen, faces = [], []
        for at in times:
            named, boxes = _named_faces(frame_at(clips[t.generation_id], at),
                                        refs)
            faces += boxes
            if t.character in named:
                seen.append(named[t.character])
        if not seen:
            issues.append(RuleIssue(
                check="TAG_FACE_NOT_FOUND", severity="BLOCK",
                detail=f"{t.character} not recognised on {t.generation_id} "
                       f"{t.start_s:g}-{t.end_s:g} s"))
            out.append(t)
            continue
        target = seen[len(seen) // 2]
        intro = by_char[t.character]
        mid = frame_at(clips[t.generation_id], (t.start_s + t.end_s) / 2)
        slot = place_tag(target, faces,
                         identity_tag_size(intro.label, intro.relation),
                         glare_of(mid))
        if slot is None:
            issues.append(RuleIssue(
                check="TAG_NO_FREE_SLOT", severity="BLOCK",
                detail=f"{t.character} on {t.generation_id}: every slot "
                       "beside the face hits a face or the subtitle band"))
            out.append(t)
            continue
        out.append(t.model_copy(update={"anchor_x": round(slot[0], 3),
                                        "anchor_y": round(slot[1], 3)}))
    return out, issues


def tag_preview_sheet(tags: list[IdentityTag], intros: list[CharacterIntro],
                      clips: dict[str, Path], out: Path) -> Path:
    """Contact sheet (2 columns) of every tag over the middle frame of its
    window, for the human check before the final render."""
    import cv2
    from PIL import Image

    from .autoqc import frame_at
    from .post import identity_tag_png
    by_char = {i.character: i for i in intros}
    tiles = []
    for k, t in enumerate(tags):
        frame = frame_at(clips[t.generation_id], (t.start_s + t.end_s) / 2)
        bg = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                             ).convert("RGBA").resize((W, H))
        intro = by_char[t.character]
        png = identity_tag_png(out.parent / f".tag_preview_{k}.png",
                               intro.label, intro.relation, t.anchor_x,
                               t.anchor_y)
        tiles.append(Image.alpha_composite(bg, Image.open(png))
                     .convert("RGB").resize((W // 2, H // 2)))
        png.unlink()
    rows = (len(tiles) + 1) // 2
    sheet = Image.new("RGB", (W, rows * H // 2))
    for k, tile in enumerate(tiles):
        sheet.paste(tile, ((k % 2) * W // 2, (k // 2) * H // 2))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=85)
    return out
