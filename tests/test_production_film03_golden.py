"""P0 exit criterion: `plan` from films/film03_front_desk reproduces what tools/drama_film03.py wrote.

Scope = files that tool itself writes: prompts/<gid>.txt (16), stills/char_* (3), stills/plate_* (2),
stills/start_<gid>.txt (16) and the gate3 record (as gate3.json). Out of scope: docs/drama/film03/prompts/*.soft.txt
(4 files, hand-softened variants written during the live run after moderation blocks; no tool generates them).
Only line endings are normalised. No expected diffs.
"""
import json
from pathlib import Path

import pytest

from film_pipeline.production.package import load_package
from film_pipeline.production.plan import plan_package

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "docs" / "drama" / "film03"
GIDS = [f"SC0{s}_g{g}" for s in range(1, 9) for g in (1, 2)]


def norm(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


PKG = ROOT / "films" / "film03_front_desk"


@pytest.fixture(scope="module")
def planned(tmp_path_factory):
    """Text artefacts only: no rendering, so these comparisons never depend on Pillow."""
    out = tmp_path_factory.mktemp("film03_plan")
    plan_package(load_package(PKG), out, takes_dir=LEGACY / "takes", storyboard=False)
    return out, None


def test_prompt_files_byte_identical(planned):
    out, _ = planned
    for gid in GIDS:
        assert norm(out / "prompts" / f"{gid}.txt") == norm(LEGACY / "prompts" / f"{gid}.txt"), gid


def test_still_files_byte_identical(planned):
    out, _ = planned
    expected = ([f"char_{n}.txt" for n in ("NORA", "KESSLER", "ORTIZ")]
                + [f"plate_{k}.txt" for k in ("lobby_morning", "briefing_morning")]
                + [f"start_{g}.txt" for g in GIDS])
    assert sorted(p.name for p in (out / "stills").iterdir()) == sorted(expected)
    for name in expected:
        assert norm(out / "stills" / name) == norm(LEGACY / "stills" / name), name


def test_every_legacy_tool_output_is_covered():
    legacy = {p.name for p in (LEGACY / "prompts").glob("*.txt")}
    assert legacy - {f"{g}.txt" for g in GIDS} == {n for n in legacy if n.endswith(".soft.txt")}


def test_gate3_record_identical(tmp_path):
    """Needs the storyboard renderer (Pillow); the legacy record was produced with APPROVED frames."""
    pytest.importorskip("PIL")
    result = plan_package(load_package(PKG), tmp_path, takes_dir=LEGACY / "takes",
                          approve_storyboard="Tech Lead (Owner-delegated)")
    assert result.ok, result.problems
    assert json.loads(norm(tmp_path / "gate3.json")) == json.loads(norm(LEGACY / "gate3_film03.json"))

