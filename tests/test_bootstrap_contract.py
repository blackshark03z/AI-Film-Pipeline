import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_canonical_sot_files_exist():
    expected = [
        ROOT / "docs/sot/development/AI_NATIVE_DEV_MODEL_SOT_v1_FROZEN.md",
        ROOT / "docs/sot/film/00_SOT_INDEX.md",
        ROOT / "docs/operating/PROJECT_OPERATING_PROFILE.md",
        ROOT / "docs/operating/CURRENT_SLICE.md",
        ROOT / "docs/operating/IMPLEMENTATION_STATUS.md",
        ROOT / "schemas/shot_spec.schema.json",
    ]
    missing = [str(p.relative_to(ROOT)) for p in expected if not p.exists()]
    assert not missing, f"Missing canonical files: {missing}"

def test_json_files_parse():
    for p in list((ROOT / "schemas").glob("*.json")) + list((ROOT / "fixtures").glob("*.json")):
        json.loads(p.read_text(encoding="utf-8"))
