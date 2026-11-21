"""Resolve source-grounded staging before building shot and keyframe prompts."""

import hashlib
import json
import re
from typing import Any, Dict, List, Tuple


_OLD_PROP_ACTION = re.compile(
    r"(?:A hand moves into frame and gently rests on |"
    r"The hovering hand lowers and the fingertips gently rest on ).+, keeping it in place\."
)
_OLD_REACTION = "The listener silently takes in the words, blinks once and exhales gently, mouth closed."


def is_legacy_generated_cutaway(item: Dict[str, Any]) -> bool:
    kind = item.get("cutaway_type")
    beat_id = str(item.get("beat_id") or "")
    action = str(item.get("action_summary") or "")
    if kind == "prop_insert" and re.search(r"__prop_insert(?:_cut)*$", beat_id):
        return bool(_OLD_PROP_ACTION.fullmatch(action))
    return bool(
        kind == "reaction"
        and re.search(r"__reaction(?:_cut)*$", beat_id)
        and action == _OLD_REACTION
    )


def require_current_staging(manifest: Dict[str, Any]) -> None:
    for shot in manifest.get("shots", []):
        if is_legacy_generated_cutaway(shot):
            raise ValueError(f"Recompile the project before generating legacy cutaway {shot.get('shot_id')}")


def _text(value: Any) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def _scene(beat, default_location):
    return (
        beat.get("chapter_id") or "CH01",
        beat.get("location") or default_location,
        beat.get("scene_id"),
    )


def _prop_state(prop, beat) -> str:
    states = prop.get("state_tracking")
    return _text(states.get(beat.get("beat_id"))) if beat and isinstance(states, dict) else ""


def _names_prop(text, prop, prop_id):
    name = _text(prop.get("name")) or prop_id
    aliases = [name, *[key for key in prop.get("keywords") or [] if isinstance(key, str)]]
    return any(
        re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text, flags=re.I)
        for alias in aliases if alias
    )


def _resolve(beat, previous, direction, characters, props):
    kind = direction.get("kind")
    purpose = _text(direction.get("purpose"))
    excerpt = _text(direction.get("source_excerpt"))
    field = direction.get("source_field")
    if not purpose or field not in ("dialogue", "narration", "action_summary") or not excerpt:
        raise ValueError("staging requires a purpose, source_field and an exact source_excerpt")
    if excerpt not in _text(beat.get(field)):
        raise ValueError("source_excerpt is absent from the named source field")
    if kind not in ("omit", "reaction", "state_insert", "source_action"):
        raise ValueError("unknown staging kind")
    plan = {
        "kind": kind,
        "purpose": purpose,
        "source_field": field,
        "source_excerpt": excerpt,
        "source_beat_id": beat.get("beat_id"),
        "source_shot_id": beat["shot_id"],
    }
    if kind == "omit":
        return plan

    if kind in ("reaction", "source_action"):
        cid = _text(direction.get("character_id"))
        actor = characters.get(cid)
        if not actor or cid not in (beat.get("characters_present") or []):
            raise ValueError("staging character must be present in the source beat")
        if kind == "reaction":
            speaker = _text(beat.get("speaker")).casefold()
            labels = {cid.casefold(), _text(actor.get("name")).casefold()}
            other_speakers = {
                label for item_id, item in characters.items()
                if item_id in (beat.get("characters_present") or []) and item_id != cid
                for label in (item_id.casefold(), _text(item.get("name")).casefold())
            }
            if field != "dialogue" or not speaker or speaker in labels or speaker not in other_speakers:
                raise ValueError("reaction requires a speaking beat and a different listener")
            # Optional authored behavior keeps the source reaction instead of a generic one.
            behavior = direction.get("visible_behavior")
            if behavior is not None:
                if not _text(behavior):
                    raise ValueError("visible_behavior must describe the listener's visible reaction")
                plan["visible_behavior"] = _text(behavior)
            framing = direction.get("framing")
            if framing is not None:
                if not _text(framing):
                    raise ValueError("reaction framing must be a non-empty framing name")
                plan["framing"] = _text(framing)
        plan["character_id"] = cid

    if kind in ("state_insert", "source_action"):
        prop_id = _text(direction.get("prop_id"))
        prop = props.get(prop_id)
        if not prop:
            raise ValueError("staging prop must exist in props_ledger")
        prop_name = _text(prop.get("name")) or prop_id
        if not _names_prop(excerpt, prop, prop_id):
            raise ValueError("staging prop must be named in the source excerpt")
        plan.update(prop_id=prop_id, prop_description=_text(prop.get("description")) or prop_name)
        if kind == "state_insert":
            state = _prop_state(prop, beat)
            if not state:
                raise ValueError("state_insert requires an established state at this beat")
            plan["state"] = state
        else:
            if field != "action_summary" or beat.get("dialogue") or beat.get("narration"):
                raise ValueError("source_action must use a silent source action beat")
            if excerpt != _text(beat.get("action_summary")):
                raise ValueError("source_action must retain the complete action beat")
            actor_name = _text(characters[plan["character_id"]].get("name")) or plan["character_id"]
            if not re.search(rf"(?<!\w){re.escape(actor_name)}(?!\w)", excerpt, flags=re.I):
                raise ValueError("source_action must name its actor")
            before = _text(direction.get("before_state"))
            after = _text(direction.get("after_state"))
            if not before or not after or before == after:
                raise ValueError("source_action requires distinct opening and closing states")
            if before not in excerpt and before != _prop_state(prop, previous):
                raise ValueError("opening state needs support in this action or the previous beat of the same scene")
            if after not in excerpt and after != _prop_state(prop, beat):
                raise ValueError("closing state needs support in this action or its beat-level ledger")
            plan.update(before_state=before, after_state=after)
    return plan


def plan_staging(
    bible: Dict[str, Any],
    beats: List[Dict[str, Any]],
    include_optional: bool = False,
    max_extra_ratio: float = 0.20,
    materialize_source_action: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Review coverage proposals and preserve the sequence of authored events."""
    supplied = [
        beat for beat in beats
        if not is_legacy_generated_cutaway(beat)
        and not (beat.get("staging_plan") or {}).get("generated_insert")
    ]
    source = []
    for index, beat in enumerate(supplied, 1):
        row = {key: value for key, value in beat.items() if key != "staging_plan"}
        row["shot_id"] = beat.get("shot_id") or f"SHOT_{index:03d}_{beat.get('chapter_id') or 'CH01'}"
        source.append(row)
    saved_inserts = {
        (beat["staging_plan"].get("source_beat_id"), beat["staging_plan"].get("kind"))
        for beat in beats if (beat.get("staging_plan") or {}).get("generated_insert")
    }
    budget = int(len(source) * min(0.20, max(0.0, max_extra_ratio)))
    characters = {c["id"]: c for c in bible.get("characters", [])}
    props = {p["id"]: p for p in bible.get("props_ledger") or [] if isinstance(p, dict) and p.get("id")}
    default_location = next((loc["id"] for loc in bible.get("locations", [])), "LOC_DEFAULT")
    used_shots = {beat["shot_id"] for beat in source}
    used_beats = {beat.get("beat_id") for beat in source}
    result = []
    review = [
        {
            "source_beat_id": beat.get("prop_source_beat_id") or beat.get("beat_id"),
            "outcome": "omitted",
            "reason": "Removed an older automatically generated cutaway with no recorded directing decision.",
        }
        for beat in beats if is_legacy_generated_cutaway(beat)
    ]
    inserted = 0
    previous = None
    known_visual_states = {}
    for beat in source:
        earlier = previous if previous and _scene(previous, default_location) == _scene(beat, default_location) else None
        if not earlier:
            known_visual_states.clear()
        previous = beat
        result.append(beat)
        direction = beat.get("staging")
        if not beat.get("dialogue") and not beat.get("narration") and not (
            isinstance(direction, dict) and direction.get("kind") == "source_action"
        ):
            authored_image = _text(beat.get("action_summary"))
            for prop_id, prop in props.items():
                state = _prop_state(prop, beat)
                if state and state in authored_image and _names_prop(authored_image, prop, prop_id):
                    known_visual_states[prop_id] = state
        if direction is None:
            continue
        try:
            if not isinstance(direction, dict):
                raise ValueError("staging must be an object")
            plan = _resolve(beat, earlier, direction, characters, props)
            kind = plan["kind"]
            if kind == "omit":
                review.append({**plan, "outcome": "omitted"})
                continue
            if kind == "source_action" and not materialize_source_action:
                continue
            if kind != "source_action":
                if not include_optional and (beat.get("beat_id"), kind) not in saved_inserts:
                    continue
                if inserted >= budget:
                    review.append({**plan, "outcome": "omitted", "reason": "Optional coverage budget reached."})
                    continue
                if kind == "state_insert":
                    prop_id = plan["prop_id"]
                    if known_visual_states.get(prop_id) == plan["state"]:
                        review.append({**plan, "outcome": "omitted", "reason": "This state is already shown in the scene."})
                        continue
                    known_visual_states[prop_id] = plan["state"]
        except ValueError as error:
            review.append({"source_beat_id": beat.get("beat_id"), "outcome": "invalid", "reason": str(error)})
            continue

        fingerprint = hashlib.sha256(json.dumps(
            [plan, _scene(beat, default_location)], ensure_ascii=False, sort_keys=True
        ).encode("utf-8")).hexdigest()[:12]
        sid = f"{beat['shot_id']}__st_{fingerprint}"
        while sid in used_shots:
            sid += "_st"
        used_shots.add(sid)
        cid = plan.get("character_id")
        visual = {
            key: beat[key] for key in (
                "chapter_id", "location", "scene_id", "wardrobe_override", "lighting_mood",
                "color_mood", "is_flashback",
            ) if key in beat
        }
        visual.update(
            shot_id=sid,
            characters_present=[cid] if cid else [],
            gaze=characters[cid].get("axis_gaze") if cid else None,
            camera_motion="static",
            post_camera_motion="static",
            transition_in=beat.get("transition_in") if kind == "source_action" else "cut",
        )
        plan["fingerprint"] = fingerprint
        if kind == "source_action":
            known_visual_states[plan["prop_id"]] = plan["after_state"]
            # This directs coverage of an existing action instead of repeating it as a cutaway.
            result[-1] = {
                **beat, **visual,
                "staging_plan": plan, "cutaway_type": "prop_insert", "framing": "Macro Prop Insert",
                "shot_role": "insert", "lens_mm": 100,
            }
        else:
            bid = f"{beat.get('beat_id') or beat['shot_id']}__st_{fingerprint}"
            while bid in used_beats:
                bid += "_st"
            used_beats.add(bid)
            plan["generated_insert"] = True
            visual.update(beat_id=bid, staging_plan=plan)
            if kind == "reaction":
                listener = _text(characters[cid].get("name")) or cid
                visual.update(
                    cutaway_type="reaction", shot_role="reaction", framing="Medium Close-up", lens_mm=85,
                    target_trim_duration_s=2.5,
                    action_summary=f"{listener} silently takes in the line with a restrained reaction.",
                )
                if plan.get("visible_behavior"):
                    # Authored behavior is a sequence; keep the whole take for the edit.
                    visual.update(action_summary=plan["visible_behavior"], target_trim_duration_s=5.0)
                if plan.get("framing"):
                    visual["framing"] = plan["framing"]
                    visual.pop("lens_mm")
            else:
                visual.update(
                    cutaway_type="prop_insert", shot_role="insert", framing="Macro Prop Insert", lens_mm=100,
                    target_trim_duration_s=2.0, action_summary=plan["state"],
                )
            result.append(visual)
            inserted += 1
        review.append({**plan, "outcome": "planned", "shot_id": sid})

    return [{**beat, "order": i} for i, beat in enumerate(result, 1)], review
