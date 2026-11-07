"""P10-04: the plan reports where the words of each emitted prompt go, and names the biggest sections when over the limit."""
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from film_pipeline.production.package import load_package
from film_pipeline.production.plan import BUDGET_SECTIONS, START_PREFIX, plan_package, top_sections, word_budget

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "films" / "film03_front_desk"
TAKES = ROOT / "docs" / "drama" / "film03" / "takes"


@pytest.fixture()
def pkg_dir(tmp_path):
    dest = tmp_path / "p"
    shutil.copytree(SRC, dest)
    return dest


def run_plan(pkg_dir, out):
    return plan_package(load_package(pkg_dir), out, takes_dir=TAKES, storyboard=False)


def meta(out):
    return json.loads((out / "plan_meta.json").read_text(encoding="utf-8"))


def test_sections_add_up_to_the_emitted_words(pkg_dir, tmp_path):
    out = tmp_path / "out"
    result = run_plan(pkg_dir, out)
    budget = meta(out)["word_budget"]
    assert set(budget) == set(result.record["generations"])
    for gid, row in budget.items():
        emitted = len((out / "prompts" / f"{gid}.txt").read_text(encoding="utf-8").split())
        assert sum(row["sections"].values()) == emitted == row["words"]
        assert set(row["sections"]) <= set(BUDGET_SECTIONS)
        assert row["sections"]["prefix"] == len(START_PREFIX.split())
        assert row["limit"] == 215


def test_gate3_json_is_untouched_by_the_budget(pkg_dir, tmp_path):
    out = tmp_path / "out"
    run_plan(pkg_dir, out)
    assert "word_budget" not in (out / "gate3.json").read_text(encoding="utf-8")
    assert "word_budget" in (out / "plan_meta.json").read_text(encoding="utf-8")


def test_overlong_message_names_the_top_three_sections(pkg_dir, tmp_path):
    path = pkg_dir / "03_preprod.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["accepted_overlong"].pop("SC02_g2")
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out"
    problems = run_plan(pkg_dir, out).problems
    line = next(p for p in problems if p.startswith("PROMPT_TOO_LONG SC02_g2: 222 words > 215"))
    sections = meta(out)["word_budget"]["SC02_g2"]["sections"]
    top = sorted(sections.items(), key=lambda kv: -kv[1])[:3]
    assert "biggest: " in line
    for name, words in top:
        assert str(words) in line.split("biggest: ")[1].split(")")[0]
    assert line.split("biggest: ")[1].count(",") == 2  # exactly three sections


def test_word_budget_helpers():
    secs = {"characters": "a b c", "setting": "d e", "continuity": "", "shots": "f", "prohibitions": "g h i j"}
    budget = word_budget(secs)
    assert budget == {"prefix": len(START_PREFIX.split()), "characters": 3, "setting": 2, "shots": 1, "prohibitions": 4}
    assert budget["prefix"] > 4  # the prefix is longer than the biggest test section, so ranking is deterministic
    assert top_sections(budget, 2) == f"start prefix {budget['prefix']}, fixed tail 4"
