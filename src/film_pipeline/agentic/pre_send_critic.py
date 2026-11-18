"""Zero-credit 3-way Pre-Send Critic Loop (Director x Compiler x Still Inspector)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from film_pipeline.production import stills as S
from film_pipeline.production.plan import _Plan
from film_pipeline.production.takes import load_log

_PROP_HANDLING_RE = re.compile(
    r"\b(lays|lay|hands|hand|passes|pass|takes|take|picks up|sets|set|places|place|slides|slide)\b",
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
            if decl.coverage == "SINGLE" and len(decl.visible) == 1:
                off_frame_tokens: list[tuple[str, str]] = []
                for char_id, char_spec in pre.characters.items():
                    if char_id in decl.visible:
                        continue
                    off_frame_tokens.append((char_id, rf"\b{re.escape(char_id)}\b"))
                    if char_spec.handle.strip():
                        off_frame_tokens.append((char_spec.handle.strip(), rf"\b{re.escape(char_spec.handle.strip())}\b"))
                leaked = [tok for tok, pat in off_frame_tokens if re.search(pat, prompt, flags=re.IGNORECASE)]
                if leaked:
                    findings.append({
                        "generation_id": gid,
                        "code": "CROSS_ATTENTION_LEAK_RISK",
                        "severity": "WARN",
                        "detail": f"SINGLE prompt mentions off-frame token(s) {sorted(set(leaked))}; consider de_personify_off_frame",
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

            # 3. Start-still approval & aspect ratio check for chain heads
            if not decl.previous_generation_id:
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

        return {
            "film_id": pkg.header.film_id,
            "checked": checked,
            "clean": len(findings) == 0,
            "findings": findings,
            "ok": not any(f["severity"] == "BLOCK" for f in findings),
        }
