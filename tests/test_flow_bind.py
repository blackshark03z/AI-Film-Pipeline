"""P12-01: bind a new Flow video tile to the sent prompt from its detail page."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "drama_flow_ui"))

import flow_bind as fb  # noqa: E402

MID = "3ab4c59a-1111-4222-8333-444455556666"
OLD = "26cac4c0-1111-4222-8333-444455556666"
PROMPT = "Starts on the given frame; same room.\nMARA pulls the shutter down."


def page(url_id=MID, text=None):
    return {"url": f"https://labs.google/fx/tools/flow/project/x/edit/{url_id}",
            "text": text if text is not None else "Prompt " + PROMPT + " more UI"}


def test_one_new_tile_with_equal_prompt_binds():
    r = fb.decide(["a"], ["a", "b"], {"b": page()}, PROMPT)
    assert r["result"] == "BOUND" and r["binding"] == "DETAIL_PROMPT_MATCH"
    assert r["media_id"] == MID and r["title"] == "b"


def test_extra_whitespace_and_line_wrapping_still_bind():
    text = "Starts  on the given   frame; same room. MARA pulls\n\nthe shutter down."
    assert fb.decide([], ["b"], {"b": page(text=text)}, PROMPT)["result"] == "BOUND"


def test_truncated_prompt_on_page_does_not_bind():
    text = "Starts on the given frame; same room."
    r = fb.decide([], ["b"], {"b": page(text=text)}, PROMPT)
    assert r["result"] == "UNBOUND"


def test_two_new_tiles_are_ambiguous_even_when_both_match():
    d = {"b": page(), "c": page(url_id=OLD)}
    r = fb.decide(["a"], ["a", "b", "c"], d, PROMPT)
    assert r["result"] == "AMBIGUOUS"


def test_no_new_tile_is_unbound():
    assert fb.decide(["a"], ["a"], {}, PROMPT)["result"] == "UNBOUND"


def test_same_title_twice_counts_as_one_new_tile():
    r = fb.decide(["t"], ["t", "t"], {"t": page()}, PROMPT)
    assert r["result"] == "BOUND"


def test_known_media_id_is_never_bound():
    r = fb.decide([], ["b"], {"b": page()}, PROMPT, known_media_ids={MID.upper()})
    assert r["result"] == "AMBIGUOUS"


def test_vanished_or_replaced_tile_is_ambiguous():
    assert fb.decide(["a", "x"], ["a", "b"], {"b": page()}, PROMPT)["result"] == "AMBIGUOUS"


def test_missing_detail_or_media_id_is_unbound():
    assert fb.decide([], ["b"], {}, PROMPT)["result"] == "UNBOUND"
    bad = {"b": {"url": "https://x/projects/y", "text": PROMPT}}
    assert fb.decide([], ["b"], bad, PROMPT)["result"] == "UNBOUND"


def test_empty_prompt_never_matches():
    assert not fb.prompt_on_page("", "anything")
