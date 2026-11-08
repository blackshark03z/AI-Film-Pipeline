"""Offline tests for reconciling UNBOUND / AMBIGUOUS sends from recorded gallery detail pages."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "drama_flow_ui"))
import flow_bind as fb  # noqa: E402

PROMPT = "A woman walks into the empty station hall and stops under the departure board."
A, B, C = ("11111111-2222-3333-4444-5555aaaaaaaa", "11111111-2222-3333-4444-5555bbbbbbbb",
           "11111111-2222-3333-4444-5555cccccccc")


def page(mid, text):
    return {"url": f"https://labs.google/fx/tools/flow/project/p/edit/{mid}", "text": text}


def test_one_match_binds_with_its_index():
    details = [page(A, "other clip"), page(B, f"Prompt\n{PROMPT}\nModel"), page(C, "third")]
    assert fb.reconcile(PROMPT, details, set()) == {"result": "BOUND", "media_id": B, "index": 1, "already_registered": []}


def test_two_matches_are_ambiguous():
    details = [page(A, PROMPT), page(B, PROMPT)]
    got = fb.reconcile(PROMPT, details, set())
    assert got["result"] == "AMBIGUOUS" and got["media_ids"] == [A, B]


def test_a_registered_match_is_not_a_candidate_but_is_reported():
    details = [page(A, PROMPT), page(B, PROMPT)]
    got = fb.reconcile(PROMPT, details, {"aaaaaaaa"})   # tail of a take manifest
    assert got["result"] == "BOUND" and got["media_id"] == B and got["already_registered"] == [A]
    only = fb.reconcile(PROMPT, [page(A, PROMPT)], {A})
    assert only["result"] == "NOT_IN_GALLERY" and only["already_registered"] == [A]


def test_a_truncated_prompt_on_the_page_is_not_a_match():
    got = fb.reconcile(PROMPT, [page(A, PROMPT[:40] + "...")], set())
    assert got["result"] == "NOT_IN_GALLERY" and "why" in got


def test_no_match_and_an_empty_scan_are_not_in_gallery():
    assert fb.reconcile(PROMPT, [page(A, "unrelated")], set())["result"] == "NOT_IN_GALLERY"
    assert fb.reconcile(PROMPT, [], set())["result"] == "NOT_IN_GALLERY"
    assert fb.reconcile(PROMPT, [{"url": "https://x/no-id", "text": PROMPT}], set())["result"] == "NOT_IN_GALLERY"


def test_line_wrapped_prompt_still_matches():
    wrapped = "A woman walks into the empty\n  station hall and stops under\nthe departure   board."
    assert fb.reconcile(PROMPT, [page(B, wrapped)], set())["media_id"] == B


def test_media_id_tails_match_by_suffix():
    assert fb.id_matches_tail(A, "aaaaaaaa") and not fb.id_matches_tail(A, "bbbbbbbb")
    assert not fb.id_matches_tail(A, "") and not fb.id_matches_tail("", "aaaaaaaa")
    assert fb.is_known(A, {"zzzzzzzz", "AAAAAAAA"}) and fb.is_known(A, {A}) and not fb.is_known(A, set())
