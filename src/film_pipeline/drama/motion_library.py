"""Natural durations of single motions, so a phase can be checked against what the motion really takes.

The numbers are estimates, except the shutter one: it was measured on film04 takes (the pull took about 2 s).
They are to be tuned from measured takes (see trajectory.py).

``stop`` says where the motion ends: ``end_of_travel`` (a physical stop: shutter fully up, chair, door open),
``mid_travel`` (it must stop part way, so the shot has to name a set object where it stops) or ``free``.
"""
from __future__ import annotations

from typing import Literal

from ..core import ContractModel


class MotionSpec(ContractModel):
    min_s: float
    max_s: float
    stop: Literal["end_of_travel", "mid_travel", "free"]


MOTION_LIBRARY: dict[str, MotionSpec] = {
    "lower_roll_shutter_partial": MotionSpec(min_s=1.2, max_s=2.5, stop="mid_travel"),
    "lower_roll_shutter_full": MotionSpec(min_s=1.5, max_s=3.0, stop="end_of_travel"),
    "raise_roll_shutter": MotionSpec(min_s=1.2, max_s=2.5, stop="end_of_travel"),
    "turn_head": MotionSpec(min_s=0.5, max_s=1.2, stop="free"),
    "glance": MotionSpec(min_s=0.4, max_s=1.0, stop="free"),
    "stand_up": MotionSpec(min_s=1.2, max_s=2.2, stop="end_of_travel"),
    "sit_down": MotionSpec(min_s=1.2, max_s=2.2, stop="end_of_travel"),
    "pick_up_small_object": MotionSpec(min_s=0.8, max_s=1.8, stop="end_of_travel"),
    "put_down_small_object": MotionSpec(min_s=0.8, max_s=1.8, stop="end_of_travel"),
    "hand_over_object": MotionSpec(min_s=1.0, max_s=2.0, stop="end_of_travel"),
    "open_door": MotionSpec(min_s=1.0, max_s=2.0, stop="end_of_travel"),
    "walk_across_room": MotionSpec(min_s=1.5, max_s=3.0, stop="end_of_travel"),   # a few steps to a counter or door
}
