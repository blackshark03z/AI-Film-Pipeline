"""Pure structural checks for an ordered sequence of existing ShotSpec versions."""

from __future__ import annotations

from collections.abc import Sequence

from jsonschema.exceptions import ValidationError

from .core import ShotSpec, validate_contract


def validate_shot_sequence(shots: Sequence[ShotSpec]) -> None:
    """Reject explicit structural conflicts without interpreting creative prose.

    The first shot is the start of the supplied sequence, so it cannot name an
    absent predecessor. Matching state keys are compared as structured values.
    Missing fields and free-form descriptions make no continuity claim.
    """
    if not shots:
        raise ValueError("shot sequence is empty")
    seen: set[str] = set()
    scene_id = shots[0].scene_id
    predecessor: ShotSpec | None = None
    for shot in shots:
        try:
            validate_contract("shot_spec", shot.payload())
        except ValidationError as exc:
            raise ValueError("invalid ShotSpec version or structure") from exc
        if shot.shot_id in seen:
            raise ValueError("duplicate shot_id in sequence")
        if shot.scene_id != scene_id:
            raise ValueError("cross-scene shot sequence")
        previous_id = shot.continuity.previous_shot_id
        if previous_id == shot.shot_id:
            raise ValueError("self predecessor")
        if predecessor is None:
            if previous_id is not None:
                raise ValueError("first shot has missing predecessor provenance")
        elif previous_id != predecessor.shot_id:
            raise ValueError("previous_shot_id does not match ordered predecessor")
        if predecessor is not None:
            _validate_pair(predecessor, shot)
        seen.add(shot.shot_id)
        predecessor = shot


def _validate_pair(before: ShotSpec, after: ShotSpec) -> None:
    first = before.environment
    second = after.environment
    if first is not None and second is not None:
        for key in ("location_id", "location_version", "time_of_day", "weather"):
            left, right = getattr(first, key), getattr(second, key)
            if left is not None and right is not None and left != right:
                raise ValueError(f"environment {key} conflicts")

    prior_characters = {item.character_id: item for item in before.characters}
    next_characters = {item.character_id: item for item in after.characters}
    if len(prior_characters) != len(before.characters) or len(next_characters) != len(after.characters):
        raise ValueError("duplicate character_id within a shot")
    for character_id in prior_characters.keys() & next_characters.keys():
        left, right = prior_characters[character_id], next_characters[character_id]
        if left.identity_version != right.identity_version:
            raise ValueError(f"character {character_id} identity_version conflicts")
        if left.look_state_id != right.look_state_id:
            raise ValueError(f"character {character_id} look_state_id conflicts")

    for key in before.continuity.end_state.keys() & after.continuity.start_state.keys():
        if before.continuity.end_state[key] != after.continuity.start_state[key]:
            raise ValueError(f"continuity state {key} conflicts")
