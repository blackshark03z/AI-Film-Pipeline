"""Pre-freeze prompt-budget check for every Sequence C fixture (007).

Dry-runs the exact deterministic compact reduction (flow_r2v_runtime
.compact_r2v_prompt over the canonical PromptPlan) for each frozen fixture
and reports body chars/words against the frozen gates (500 chars / 75
words). Read-only; no provider contact; no mutation.
"""
import json
import sys
from pathlib import Path

sys_path = str(Path(__file__).resolve().parents[1] / "src")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)
tools_path = str(Path(__file__).resolve().parent)
if tools_path not in sys.path:
    sys.path.insert(0, tools_path)

from film_pipeline.core import ProviderCapabilities, References, load_shot
from film_pipeline.flow_r2v_runtime import compile_plan, compact_r2v_prompt
from film_pipeline.live_runtime import Asset

MAX_PROMPT_CHARS = 500
MAX_PROMPT_WORDS = 75

caps = ProviderCapabilities.model_validate({
    "profile_version": "t", "provider_id": "flow_veo",
    "transport_type": "other", "supports_text_to_video": True,
    "supports_image_input": True, "supports_duration_control": True})
ref = Asset(asset_id="asset_x", origin="reference", asset_type="image",
            uri_or_path="x", sha256="a" * 64, mime_type="image/png",
            width=1, height=1, file_size=1)


def main() -> None:
    rows = []
    worst = 0
    for i in range(1, 5):
        for s in "EFG":
            sid = f"SEQ7_{s}{i}"
            spec = load_shot(Path(__file__).resolve().parents[1] /
                             f"fixtures/sequence007/{sid}.json")
            spec = spec.model_copy(update={
                "references": References(other_asset_ids=["asset_x"])})
            plan = compile_plan(spec, caps, ref)
            prompt = compact_r2v_prompt(plan, "job_" + "a" * 64, model="m")
            body = prompt.text[:prompt.text.rfind(prompt.marker)].strip()
            chars, words = len(body), len(body.split())
            worst = max(worst, chars)
            rows.append({"shot_id": sid, "chars": chars, "words": words,
                         "fits": chars <= MAX_PROMPT_CHARS and
                                 words <= MAX_PROMPT_WORDS})
    ok = all(r["fits"] for r in rows)
    print(json.dumps({"all_fit": ok, "max_chars": worst, "rows": rows}))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
