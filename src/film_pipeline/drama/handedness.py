"""Handedness lint: a hand named in choreography or prop state is stated in both frames.

film07 pilot: SC01_g17-g24 said Sam's "left hand" while the picture showed the anatomical right (the arm farther from the
camera, on screen-left). Anatomy and screen side flip depending on which way the person faces, so a bare "left hand" /
"right hand" cannot be checked by eye. State both: "his right hand (the arm farther from camera, on screen-left)".

Geometry for the counter and booth setups (camera on the customer side, RUTH frame-left facing screen-right, SAM frame-right
facing screen-left): SAM's right hand = farther from camera, on screen-left; SAM's left = nearer, on screen-right;
RUTH's right = nearer the camera, on screen-left; RUTH's left = farther, on screen-right.
"""
from __future__ import annotations

import re

_HAND = re.compile(r"\b(left|right)[- ](hand|arm|palm|fingers?)\b", re.IGNORECASE)
_BOTH_FRAMES = re.compile(r"^\s*\(([^)]*)\)")


def _states_both_frames(tail: str) -> bool:
    m = _BOTH_FRAMES.match(tail)
    if not m:
        return False
    inside = m.group(1).lower()
    return bool(re.search(r"\bscreen-(left|right)\b", inside)) and "camera" in inside


def bare_hand_mentions(text: str) -> list[str]:
    """"left hand"-style mentions in `text` that are not followed by a parenthetical giving the camera side and the screen side."""
    out = []
    for m in _HAND.finditer(text or ""):
        if not _states_both_frames(text[m.end():]):
            out.append(f"{m.group(1).lower()} {m.group(2).lower()}")
    return out
