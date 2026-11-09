"""P17-02: a chained cut compares the previous end state with its start state the way the prompt sees both.

film05 SC01_g2 (a single on IRIS, HAL off frame): the prop state "one white mug before HAL" was dropped from the start
(a prop placed on someone out of frame would summon a stranger) but kept in the previous end, so the plan raised a
false STATE BLOCK on every chained cut that leaves a person out of frame."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "films" / "film05_one_cup"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json",
         "05_edit.json", "06_post.json", "07_delivery.json", "ledger.json")


def test_prop_naming_an_off_frame_person_does_not_break_the_handoff(tmp_path):
    root = tmp_path / "film05"
    root.mkdir()
    for name in FILES:
        if (PKG / name).exists():
            (root / name).write_bytes((PKG / name).read_bytes())
    pre = json.loads((root / "03_preprod.json").read_text(encoding="utf-8"))
    for state in pre["states"].values():
        state["props"]["the mugs:"] = "one white mug before HAL, a second white mug steaming beside the key"
    (root / "03_preprod.json").write_text(json.dumps(pre), encoding="utf-8")
    out = tmp_path / "plan"
    subprocess.run([sys.executable, str(ROOT / "tools" / "film.py"), "plan", "--film", str(root), "--out", str(out)],
                   capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
                   env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"})
    gate3 = json.loads((out / "gate3.json").read_text(encoding="utf-8"))
    issues = gate3["generations"]["SC01_g2"]["issues"]  # chained to SC01_g1, HAL off frame
    assert not [i for i in issues if i["check"] == "STATE"], issues
