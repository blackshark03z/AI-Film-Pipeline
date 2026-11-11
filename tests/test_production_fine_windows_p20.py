from film_pipeline.production import edit as E


def test_fine_windows_cover_audio_spans_that_reach_past_one_picture_neighbour():
    events = [E.EditEvent(event_id=f"e{i}", take_id="take", src_in_s=1, src_out_s=2,
                         transition=E.Transition() if i == 0 else E.Transition(type="DISSOLVE", duration_s=0.375),
                         audio=E.AudioCut() if i == 0 else E.AudioCut(j_cut_s=0.9, l_cut_s=0.9))
              for i in range(30)]
    starts = [i * 0.625 for i in range(30)]
    lengths = [1.0] * 30
    total = starts[-1] + 1
    windows = E.fine_windows(events, starts, lengths, total)
    assert windows[0][2] == 0 and windows[-1][3] == total
    for lo, hi, a, b in windows:
        assert hi - lo + 1 <= 12 and 0 < b - a <= 60
        for i, event in enumerate(events):
            speech_start = starts[i] - event.audio.j_cut_s
            speech_end = starts[i] + lengths[i] + (events[i + 1].audio.l_cut_s if i + 1 < len(events) else 0)
            if speech_start < b - 1e-6 and speech_end > a + 1e-6:
                assert lo <= i <= hi, f"window {a}-{b} lost sound from e{i}"
    assert all(left[3] == right[2] for left, right in zip(windows, windows[1:]))


def test_fine_windows_anchor_later_scenes_after_an_early_trim():
    events = [E.EditEvent(event_id=f"e{i}", take_id="take", src_out_s=7) for i in range(30)]
    scene_ids = ["A"] * 15 + ["B"] * 15
    original = E.fine_windows(events, [i * 7 for i in range(30)], [7.] * 30, 210., scene_ids=scene_ids)
    starts = [i * 7 - (1 if i > 0 else 0) for i in range(30)]
    changed = E.fine_windows(events, starts, [6.] + [7.] * 29, 209., scene_ids=scene_ids)
    assert any(b == 105 for _, _, _, b in original)
    assert any(b == 104 for _, _, _, b in changed)
    assert [(a - 105, b - 105) for _, _, a, b in original if a >= 105] == [
        (a - 104, b - 104) for _, _, a, b in changed if a >= 104]
