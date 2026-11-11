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


def test_a_rerun_does_not_hide_its_own_earlier_binding(tmp_path):
    """P17-04 (film05 SC01_g1_t1): a BOUND run without --download, then a re-run with --download, came back
    NOT_IN_GALLERY because the first run's media id counted as already registered."""
    import json
    from flow_reconcile import known_ids
    (tmp_path / "SC01_g1_t1.reconcile.json").write_text(
        json.dumps({"receipt_id": "SC01_g1_t1", "result": "BOUND", "media_id": "aaa"}), encoding="utf-8")
    (tmp_path / "SC02_g1_t1.reconcile.json").write_text(
        json.dumps({"receipt_id": "SC02_g1_t1", "result": "BOUND", "media_id": "bbb"}), encoding="utf-8")
    assert known_ids(None, tmp_path, frozenset({"SC01_g1_t1"})) == {"bbb"}
    assert known_ids(None, tmp_path) == {"aaa", "bbb"}


def test_settled_needs_ten_minutes_after_the_send_ended(tmp_path):
    import json
    from datetime import datetime

    import flow_reconcile as fr
    m = tmp_path / "X_t1.take.json"
    m.write_text(json.dumps({"finished": "2026-11-09T12:13:10"}), encoding="utf-8")
    assert not fr.settled(m, now=datetime(2026, 11, 9, 12, 20, 0))
    assert fr.settled(m, now=datetime(2026, 11, 9, 12, 23, 10))
    assert not fr.settled(tmp_path / "missing.take.json")
    m.write_text(json.dumps({"finished": "2026-11-09T12:00:00+00:00"}), encoding="utf-8")
    from datetime import timezone
    assert fr.settled(m, now=datetime(2026, 11, 9, 12, 10, 0, tzinfo=timezone.utc))
    assert not fr.settled(m, now=datetime(2026, 11, 9, 12, 20, 0))   # aware vs naive: no crash, not settled


def test_negative_scan_rejects_duplicates_invalid_details_and_wrong_project():
    import flow_reconcile as fr
    home = "https://labs.google/fx/tools/flow/project/p"
    details = [page(f"11111111-2222-3333-4444-{i:012d}", "other full prompt") for i in range(6)]
    assert fr.complete_negative_scan(details, home)
    assert not fr.complete_negative_scan(details[:5], home)
    assert not fr.complete_negative_scan([*details[:5], details[0]], home)
    assert not fr.complete_negative_scan([*details, {"url": home, "text": "gallery"}], home)
    assert not fr.complete_negative_scan(details, home + "2")


def test_controller_death_after_enter_can_still_settle_from_the_pre_enter_stamp(tmp_path):
    """A hard death between Enter and the SUBMITTED checkpoint leaves only the SUBMITTING checkpoint (no finished /
    submitted_at); its pre-Enter stamp must still let a verified negative scan settle, or the send stays pending forever."""
    import json
    from datetime import datetime

    import flow_reconcile as fr
    m = tmp_path / "X_t1.take.json"
    m.write_text(json.dumps({"submission_phase": "SUBMITTING", "submitting_at": "2026-11-09T12:00:00",
                             "started": "2026-11-09T11:00:00"}), encoding="utf-8")
    assert not fr.settled(m, now=datetime(2026, 11, 9, 12, 9, 0))
    assert fr.settled(m, now=datetime(2026, 11, 9, 12, 10, 0))
    # PREPARING never pressed Enter: `started` is not a send time
    m.write_text(json.dumps({"submission_phase": "PREPARING", "submitting_at": "2026-11-09T12:00:00",
                             "started": "2026-11-09T11:00:00"}), encoding="utf-8")
    assert not fr.settled(m, now=datetime(2026, 11, 9, 13, 0, 0))
