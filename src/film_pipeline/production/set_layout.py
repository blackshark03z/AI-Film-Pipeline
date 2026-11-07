"""Spatial set layout per location and per-shot readout (what the viewer must understand).

Declared in the package:

* `03_preprod.locations.<id>.layout` -> `SetLayout`  (zones, objects fixed in those zones, named camera positions)
* `04_shots.generations[].camera_position` -> id of one of the location's camera positions
* `04_shots.generations[].readout`         -> `Readout` list (the fact the viewer must read + the visible evidence)

Rules (`layout_issues`, all BLOCK):

* ``LAYOUT_CAMERA``     a shot names a camera position its location does not have, or its location has a layout and the
                        shot names no camera position
* ``READOUT_MISSING``   once any shot declares a readout every shot must; a film with none is not forced
* ``READOUT_EVIDENCE``  evidence must be a character in frame or an object the shot's camera position sees
* ``READOUT_SIZE``      the shot is wider than the size at which the readout's evidence still reads

Everything is optional: a film without layouts or readouts behaves and renders exactly as before.
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, StringConstraints, model_validator

from film_pipeline.core import ContractModel
from film_pipeline.drama.scene_bible import RuleIssue
from film_pipeline.production.camera import _SIZE_ORDER, Size

Ident = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")]


class SetZone(ContractModel):
    id: Ident
    label: str  # "clerk booth (staff side)"
    box: tuple[float, float, float, float] | None = None  # top-down floor plan, 0..1: x0, y0, x1, y1


class SetObject(ContractModel):
    id: Ident
    label: str  # "roll-down shutter"
    zone: Ident
    placement: str  # fixes it relative to other things: "mounted above the ticket window, rolls down over its glass"
    operation: str = ""  # how a person works it on screen: "pulled down by the handle on its bottom edge"
    at: tuple[float, float] | None = None


class CameraPosition(ContractModel):
    id: Ident
    zone: Ident
    view: str  # "from the public hall, facing the ticket window; the clerk booth is seen through the window"
    sees: list[Ident]  # object ids in view
    at: tuple[float, float] | None = None
    look_at: Ident | None = None  # object id the camera faces


def _in_unit(values: tuple[float, ...]) -> bool:
    return all(0.0 <= v <= 1.0 for v in values)


class SetLayout(ContractModel):
    zones: list[SetZone]
    objects: list[SetObject]
    cameras: list[CameraPosition]

    @model_validator(mode="after")
    def _consistent(self) -> "SetLayout":
        if not self.zones:
            raise ValueError("a set layout needs at least one zone")
        if not self.cameras:
            raise ValueError("a set layout needs at least one camera position")
        ids = [x.id for x in (*self.zones, *self.objects, *self.cameras)]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        if dup:
            raise ValueError(f"set layout: duplicate ids {dup} (zones, objects and cameras share one id space)")
        zone_ids = {z.id for z in self.zones}
        object_ids = {o.id for o in self.objects}
        for o in self.objects:
            if o.zone not in zone_ids:
                raise ValueError(f"set layout: object {o.id} is in unknown zone {o.zone!r}")
        for c in self.cameras:
            if c.zone not in zone_ids:
                raise ValueError(f"set layout: camera {c.id} is in unknown zone {c.zone!r}")
            unknown = [s for s in c.sees if s not in object_ids]
            if unknown:
                raise ValueError(f"set layout: camera {c.id} sees unknown objects {unknown}")
            if c.look_at is not None and c.look_at not in object_ids:
                raise ValueError(f"set layout: camera {c.id} looks at unknown object {c.look_at!r}")
        for z in self.zones:
            if z.box is not None:
                x0, y0, x1, y1 = z.box
                if not _in_unit(z.box) or not (x0 < x1 and y0 < y1):
                    raise ValueError(f"set layout: zone {z.id} box {z.box} must lie within 0..1 with x0<x1, y0<y1")
        for x in (*self.objects, *self.cameras):
            if x.at is not None and not _in_unit(x.at):
                raise ValueError(f"set layout: {x.id} position {x.at} must lie within 0..1")
        return self

    def camera(self, cid: str) -> CameraPosition | None:
        return next((c for c in self.cameras if c.id == cid), None)

    def object(self, oid: str) -> SetObject | None:
        return next((o for o in self.objects if o.id == oid), None)

    def view_text(self, cid: str) -> str:
        cam = self.camera(cid)
        if cam is None:
            return ""
        parts = [f"{cam.view}."]
        for oid in cam.sees:
            o = self.object(oid)
            if o is None:
                continue
            parts.append(f"The {o.label} is {o.placement}.")
            if o.operation:
                parts.append(f"The {o.label} is {o.operation}.")
        return " ".join(parts)

    def unseen_text(self, cid: str) -> str:
        """Objects this camera does not see. The location text names every object, so without this the
        model draws the missing ones somewhere in frame (film04 plate B grew a second clock in the hall)."""
        cam = self.camera(cid)
        if cam is None:
            return ""
        labels = [o.label for o in self.objects if o.id not in cam.sees]
        return f"Out of frame, not shown: {', '.join('the ' + l for l in labels)}." if labels else ""

    def drawable(self) -> bool:
        return (all(z.box is not None for z in self.zones) and all(o.at is not None for o in self.objects)
                and all(c.at is not None for c in self.cameras))


class Readout(ContractModel):
    fact: str = Field(min_length=1)  # what the viewer must understand, plain words
    evidence: list[str] = Field(min_length=1)  # set object ids (from the shot's camera view) or character names in frame
    min_size: Size = "WIDE"  # the widest camera size at which the evidence still reads


def _issue(out: list[RuleIssue], check: str, detail: str) -> None:
    out.append(RuleIssue(check=check, severity="BLOCK", detail=detail))  # type: ignore[arg-type]


def layout_issues(pre: Any, shots: Any) -> list[RuleIssue]:
    """Every layout / readout finding for the typed `preprod` + `shots` sections."""
    out: list[RuleIssue] = []
    any_readout = any(g.readout for g in shots.generations)
    for g in shots.generations:
        gid = g.generation_id
        scene = pre.scenes.get(g.scene_id)
        loc_id = scene.location if scene is not None else ""
        loc = pre.locations.get(loc_id)
        layout: SetLayout | None = getattr(loc, "layout", None) if loc is not None else None
        cam = None
        if g.camera_position:
            if layout is None:
                _issue(out, "LAYOUT_CAMERA", f"{gid}: camera_position {g.camera_position!r} but location {loc_id} "
                                              "has no set layout")
            else:
                cam = layout.camera(g.camera_position)
                if cam is None:
                    have = ", ".join(c.id for c in layout.cameras)
                    _issue(out, "LAYOUT_CAMERA", f"{gid}: location {loc_id} has no camera position "
                                                  f"{g.camera_position!r} (has {have})")
        elif layout is not None:
            have = ", ".join(c.id for c in layout.cameras)
            _issue(out, "LAYOUT_CAMERA", f"{gid}: location {loc_id} has a set layout; pick a camera position ({have})")
        if any_readout and not g.readout:
            _issue(out, "READOUT_MISSING", f"{gid}: the shot tells the viewer nothing - declare what they must read")
        for r in g.readout:
            for item in r.evidence:
                if item in g.visible:
                    continue
                if cam is not None and item in cam.sees:
                    continue
                if cam is not None and layout is not None and layout.object(item) is not None:
                    why = f"is an object outside camera position {cam.id}'s view"
                else:
                    why = "is neither a character in frame nor an object the camera position sees"
                _issue(out, "READOUT_EVIDENCE", f"{gid}: evidence {item!r} for '{r.fact}' {why}")
            if g.camera is not None and _SIZE_ORDER.index(g.camera.size) < _SIZE_ORDER.index(r.min_size):
                _issue(out, "READOUT_SIZE", f"{gid}: '{r.fact}' needs {r.min_size} or closer, the shot is {g.camera.size}")
    return out


def _font(size: int):
    from PIL import ImageFont
    for name in ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_floor_plan(layout: SetLayout, title: str, path: Path, size: int = 640) -> None:
    """Top-down sketch of the set for the Owner: zones as boxes, objects as labelled dots, each camera position as a
    view cone toward what it faces, and a legend with every camera's view. Deterministic."""
    if not layout.drawable():
        return
    import math
    import textwrap

    from PIL import Image, ImageDraw

    top = 32
    font, small = _font(16), _font(13)
    legend = [line for c in layout.cameras for line in textwrap.wrap(f"{c.id}: {c.view}", 86)]
    image = Image.new("RGB", (size, size + top + 18 * len(legend) + 12), (238, 236, 230))
    draw = ImageDraw.Draw(image)
    draw.text((8, 6), title, fill=(30, 30, 30), font=font)

    def px(x: float, y: float) -> tuple[float, float]:
        return x * size, top + y * size

    def label(x: float, y: float, text: str, fill: tuple[int, int, int], f) -> None:
        width = draw.textlength(text, font=f)
        lx = x + 10 if x + 10 + width < size - 4 else x - 10 - width  # keep labels inside the image
        draw.text((lx, y - 8), text, fill=fill, font=f)

    for z in layout.zones:
        x0, y0, x1, y1 = z.box  # type: ignore[misc]
        a, b = px(x0, y0), px(x1, y1)
        draw.rectangle([a, b], outline=(90, 90, 90), fill=(226, 223, 214), width=2)
        draw.text((a[0] + 4, a[1] + 3), z.label, fill=(70, 70, 70), font=small)
    for c in layout.cameras:  # cones first, so dots and labels stay readable on top
        cx, cy = px(*c.at)  # type: ignore[misc]
        target = layout.object(c.look_at) if c.look_at else None
        tx, ty = px(*target.at) if target is not None else (cx, cy - size * 0.3)  # type: ignore[misc]
        angle, reach = math.atan2(ty - cy, tx - cx), min(size * 0.18, max(40.0, math.hypot(tx - cx, ty - cy)))
        cone = [(cx, cy)] + [(cx + reach * math.cos(angle + d), cy + reach * math.sin(angle + d)) for d in (0.35, -0.35)]
        draw.polygon(cone, outline=(200, 60, 40), width=2)
    for o in layout.objects:
        cx, cy = px(*o.at)  # type: ignore[misc]
        draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(60, 90, 140))
        label(cx, cy, o.label, (20, 40, 90), small)
    for c in layout.cameras:
        cx, cy = px(*c.at)  # type: ignore[misc]
        draw.ellipse([cx - 11, cy - 11, cx + 11, cy + 11], fill=(200, 60, 40))
        draw.text((cx - 5, cy - 9), c.id, fill=(255, 255, 255), font=font)
    y = top + size + 6
    for line in legend:
        draw.text((8, y), line, fill=(120, 35, 25), font=small)
        y += 18
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
