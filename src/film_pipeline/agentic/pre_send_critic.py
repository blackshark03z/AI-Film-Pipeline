"""Zero-credit 3-way Pre-Send Critic Loop (Director x Compiler x Still Inspector)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from film_pipeline.production import stills as S
from film_pipeline.production.interaction import offframe_leaks, protection_on, spoken_texts as shot_spoken_texts
from film_pipeline.production.plan import _Plan
from film_pipeline.production.sections import shot_seconds
from film_pipeline.production.takes import load_log, script_dialogue

_PROP_HANDLING_RE = re.compile(
    r"\b(lays|lay|hands|hand|passes|pass|takes|take|picks up|sets|set|places|place|slides|slide)\b",
    re.IGNORECASE,
)
_STAGE_DIR_LEAK_RE = re.compile(
    r"(\([^)]{2,40}\)|\[[^\]]{2,40}\]|\bbrief pause\b|\blong pause\b|\bsighs\b|\bclears throat\b|\bvoiceover\b)",
    re.IGNORECASE,
)


def _image_size(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image
        with Image.open(path) as img:
            return img.size
    except Exception:  # noqa: BLE001
        return None


class PreSendCritic:
    """Zero-credit prompt & start-still audit before submitting a generation."""

    def inspect(
        self,
        pkg: Any,
        *,
        plan_dir: Path | None = None,
        include_accepted: bool = False,
        generation_id: str | None = None,
    ) -> dict[str, Any]:
        pre = pkg.typed.get("preprod")
        shots = pkg.typed.get("shots")
        if pre is None or shots is None:
            raise ValueError("PreSendCritic requires valid 03_preprod.json and 04_shots.json")

        root = Path(pkg.root)
        pdir = Path(plan_dir) if plan_dir is not None else root / "media" / "plan"
        log = load_log(root, pkg.header.film_id)
        by_id = {g.generation_id: g for g in shots.generations}
        accepted_ids = {
            t.generation_id
            for t in log.takes
            if t.status == "ACCEPTED" and t.shot_version == getattr(by_id.get(t.generation_id), "version", None)
        }

        plan_helper: _Plan | None = None
        still_prompt_map = S.still_prompts(pkg)
        dialogue_lines = script_dialogue(pkg)
        scene_dialogue = (
            {(s.scene_id, e.line_no): e.text for s in pkg.script.scenes for e in s.elements if e.kind == "dialogue"}
            if getattr(pkg, "script", None) is not None
            else {}
        )
        w_ratio, _, h_ratio = pkg.header.aspect.partition(":")
        expected_aspect = float(w_ratio) / float(h_ratio or 1) if w_ratio else 16.0 / 9.0

        checked = 0
        findings: list[dict[str, Any]] = []
        for decl in shots.generations:
            gid = decl.generation_id
            if generation_id is not None and gid != generation_id:
                continue
            if not include_accepted and gid in accepted_ids:
                continue
            checked += 1

            prompt_file = pdir / "prompts" / f"{gid}.txt"
            if prompt_file.is_file():
                prompt = prompt_file.read_text(encoding="utf-8").strip()
            else:
                findings.append({
                    "generation_id": gid,
                    "code": "PLAN_MISSING",
                    "severity": "BLOCK",
                    "detail": f"compiled prompt {prompt_file.name} is missing: run film.py plan first",
                })
                prompt = ""
                if pkg.typed.get("direction") is not None and getattr(pkg, "script", None) is not None:
                    from film_pipeline.drama.storyboard import StoryboardGate
                    from film_pipeline.production.plan import END_FRAME_PREFIX, START_FRAME_PREFIX, START_PREFIX

                    if plan_helper is None:
                        plan_helper = _Plan(pkg, None, None)
                    gate = StoryboardGate(pdir / "storyboard")
                    _, compiled_plan, _ = plan_helper.build(decl, gate)
                    prefix = START_FRAME_PREFIX if pre.preflight.prompt_style == "start_frame" else START_PREFIX
                    if decl.end_frame and pre.preflight.prompt_style == "start_frame":
                        prefix = END_FRAME_PREFIX
                    prompt = prefix + compiled_plan.compiled_text

            # 1. Off-frame character / handle token leakage on SINGLE shots
            protected = protection_on(pre)  # BLOCK when off-frame protection is in effect, else advice only
            if len(decl.visible) == 1 and (protected or decl.coverage == "SINGLE"):
                leaked = offframe_leaks(pre, decl, prompt, shot_spoken_texts(pkg, decl))
                if leaked:
                    findings.append({
                        "generation_id": gid,
                        "code": "CROSS_ATTENTION_LEAK_RISK",
                        "severity": "BLOCK" if protected else "WARN",
                        "detail": f"SINGLE prompt mentions off-frame token(s) {leaked}; consider de_personify_off_frame",
                    })

            # 2. Blanket 'No touching.' conflict on multi-person prop handling shots
            if len(decl.visible) >= 2 and "No touching." in prompt:
                phase_text = " ".join(
                    [*(p.description for p in decl.choreography.phases), *decl.choreography.once_actions]
                )
                if _PROP_HANDLING_RE.search(phase_text):
                    findings.append({
                        "generation_id": gid,
                        "code": "PROHIBITION_ACTION_CONFLICT",
                        "severity": "WARN",
                        "detail": "prompt contains 'No touching.' alongside prop-handling choreography; consider interperson_no_touch_ids",
                    })

            # 3. Start-still approval & aspect ratio check for chain heads & setup-anchor shots
            if not decl.previous_generation_id or getattr(decl, "independent_still", False):
                st_state, st_reason = S.state_of(pkg, gid, still_prompt_map.get(gid, ""))
                if st_state != "APPROVED":
                    findings.append({
                        "generation_id": gid,
                        "code": "START_STILL_NOT_READY",
                        "severity": "BLOCK",
                        "detail": f"start still {st_state}: {st_reason}",
                    })
                else:
                    st_path = root / pre.stills[gid].file
                    dims = _image_size(st_path)
                    if dims is not None and dims[1] > 0:
                        ratio = dims[0] / dims[1]
                        if abs(ratio - expected_aspect) > 0.08:
                            findings.append({
                                "generation_id": gid,
                                "code": "START_STILL_NOT_READY",
                                "severity": "WARN",
                                "detail": f"start still aspect {dims[0]}x{dims[1]} ({ratio:.2f}) differs from {pkg.header.aspect}",
                            })

            # 4. End-still approval & aspect ratio check when end_frame is declared
            end_k = S.end_key(gid)
            if getattr(decl, "end_frame", False) and end_k in still_prompt_map:
                e_state, e_reason = S.state_of(pkg, end_k, still_prompt_map[end_k])
                if e_state != "APPROVED":
                    findings.append({
                        "generation_id": gid,
                        "code": "END_STILL_NOT_READY",
                        "severity": "BLOCK",
                        "detail": f"end still {e_state}: {e_reason}",
                    })
                else:
                    e_path = root / pre.stills[end_k].file
                    e_dims = _image_size(e_path)
                    if e_dims is not None and e_dims[1] > 0:
                        e_ratio = e_dims[0] / e_dims[1]
                        if abs(e_ratio - expected_aspect) > 0.08:
                            findings.append({
                                "generation_id": gid,
                                "code": "END_STILL_NOT_READY",
                                "severity": "WARN",
                                "detail": f"end still aspect {e_dims[0]}x{e_dims[1]} ({e_ratio:.2f}) differs from {pkg.header.aspect}",
                            })

            # 5. Stage-direction leakage & spoken pacing overflow in assigned dialogue
            if decl.dialogue:
                spoken_texts: list[str] = []
                for ln in decl.dialogue:
                    txt = scene_dialogue.get((decl.scene_id, ln))
                    if txt is None:
                        raw_line = dialogue_lines.get(ln, "")
                        _, _, body_txt = raw_line.partition(": ")
                        txt = body_txt or raw_line
                    if txt:
                        spoken_texts.append(txt)
                    leak = _STAGE_DIR_LEAK_RE.search(txt)
                    if leak:
                        findings.append({
                            "generation_id": gid,
                            "code": "STAGE_DIRECTION_IN_DIALOGUE",
                            "severity": "WARN",
                            "detail": f"dialogue line {ln} contains stage-direction token {leak.group(0)!r} that the actor may speak aloud",
                        })
                joined_spoken = " ".join(spoken_texts).strip()
                secs = max(1.0, float(shot_seconds(decl, pkg.header)))
                words_n = len(joined_spoken.split())
                if len(joined_spoken) / secs > 22.0 or words_n / secs > 3.2:
                    findings.append({
                        "generation_id": gid,
                        "code": "DIALOGUE_PACE_OVERFLOW",
                        "severity": "WARN",
                        "detail": f"dialogue ({words_n} words, {len(joined_spoken)} chars in {secs:g}s) risks tail cutoff; consider longer duration or split",
                    })

        return {
            "film_id": pkg.header.film_id,
            "checked": checked,
            "clean": len(findings) == 0,
            "findings": findings,
            "ok": not any(f["severity"] == "BLOCK" for f in findings),
        }
