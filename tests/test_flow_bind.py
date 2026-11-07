"""P12-01: bind a new Flow video to the sent prompt by front-insertion proof."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "drama_flow_ui"))

import flow_bind as fb  # noqa: E402

NEW = "3ab4c59a-1111-4222-8333-444455556666"
OLD = "26cac4c0-1111-4222-8333-444455556666"
PROMPT = "Starts on the given frame; same room.\nMARA pulls the shutter down."


def page(mid, text=None):
    return {"url": f"https://labs.google/fx/tools/flow/project/x/edit/{mid}",
            "text": text if text is not None else "Prompt " + PROMPT + " more UI"}


def decide(n_before=2, n_after=3, front_before=OLD, front=None, second=None, prompt=PROMPT):
    return fb.decide_front(n_before, n_after, front_before,
                           front if front is not None else page(NEW),
                           second if second is not None else page(OLD), prompt)


def test_one_more_video_old_front_now_second_binds():
    r = decide()
    assert r["result"] == "BOUND" and r["binding"] == "DETAIL_PROMPT_MATCH"
    assert r["media_id"] == NEW


def test_first_video_ever_binds_without_a_second():
    r = fb.decide_front(0, 1, None, page(NEW), None, PROMPT)
    assert r["result"] == "BOUND"


def test_equal_prompts_and_titles_still_bind_by_media_id():
    # attempt 5: three clips with the same prompt and two titles
    assert decide()["result"] == "BOUND"


def test_extra_whitespace_and_line_wrapping_still_bind():
    text = "Starts  on the given   frame; same room. MARA pulls\n\nthe shutter down."
    assert decide(front=page(NEW, text))["result"] == "BOUND"


def test_truncated_prompt_on_page_does_not_bind():
    r = decide(front=page(NEW, "Starts on the given frame; same room."))
    assert r["result"] == "UNBOUND"


def test_no_new_video_is_unbound():
    assert decide(n_after=2)["result"] == "UNBOUND"


def test_two_or_more_new_videos_are_ambiguous():
    assert decide(n_after=4)["result"] == "AMBIGUOUS"


def test_front_video_unchanged_is_ambiguous():
    assert decide(front=page(OLD))["result"] == "AMBIGUOUS"


def test_old_front_not_second_is_ambiguous():
    other = "99999999-1111-4222-8333-444455556666"
    assert decide(second=page(other))["result"] == "AMBIGUOUS"


def test_old_front_unknown_is_ambiguous():
    assert decide(front_before=None)["result"] == "AMBIGUOUS"


def test_missing_media_id_is_unbound():
    bad = {"url": "https://x/projects/y", "text": PROMPT}
    assert decide(front=bad)["result"] == "UNBOUND"


def test_empty_prompt_never_matches():
    assert not fb.prompt_on_page("", "anything")
    assert decide(prompt="")["result"] == "UNBOUND"
