"""WP5: measure each conditioning arm with the WP4 autoqc signals.

Per take: NORA/DOYLE identity vs the film01 anchors (SC01_g1), shot scale vs
the planned close-up, set match of SC03_g1's last frame vs the take's first
frame. Writes docs/drama/wp5/measure.json. Signals are WARN-level assists; the
visual verdict per arm is recorded by the reviewer in docs/drama/wp5/README.md.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")
from film_pipeline.drama import autoqc as q  # noqa: E402

TAKES = Path("docs/drama/film01_takes/noref")
WP5 = Path("docs/drama/wp5/takes")
SIDE_OF = {"NORA": "left", "DOYLE": "right"}
ARMS = {"A0": TAKES / "SC03_g2.mp4"}
ARMS.update({p.stem: p for p in sorted(WP5.glob("*.mp4"))})

anchors = [q.anchor_from_clip(c, TAKES / "SC01_g1.mp4", t, s)
           for c, s in SIDE_OF.items() for t in (1.0, 2.5, 4.0)]
prev = TAKES / "SC03_g1.mp4"


def own_anchors(clip):
    found = []
    for c, s in SIDE_OF.items():
        for t in (0.5, 1.0, 1.5, 2.0):
            try:
                found.append(q.anchor_from_clip(c, clip, t, s))
                break
            except ValueError:   # nobody on that side yet
                continue
    return found



out = {}
for arm, clip in ARMS.items():
    ident = q.identity_report(clip, anchors, side_of=SIDE_OF)
    scale = q.shot_scale_report(clip, "CU")
    setm = q.handoff_set_report(prev, clip)
    # drift inside the take: its own first frames as anchors (a start frame
    # defines a new identity, so the film01 anchors alone undersell it)
    selfid = q.identity_report(clip, own_anchors(clip), side_of=SIDE_OF)
    out[arm] = {
        "clip": clip.as_posix(),
        "identity": {c.character: {
            "mean": None if c.mean_similarity is None
            else round(c.mean_similarity, 3),
            "min": None if c.min_similarity is None
            else round(c.min_similarity, 3),
            "head": None if c.mean_head_similarity is None
            else round(c.mean_head_similarity, 3),
            "frames": c.frames_seen} for c in ident.characters},
        "self_identity": {c.character: None if c.mean_similarity is None
                          else round(c.mean_similarity, 3)
                          for c in selfid.characters},
        "scale": scale.majority, "scale_per_frame": scale.per_frame,
        "set_inliers": setm.similarity.inliers,
        "set_hsv": round(setm.similarity.hsv_correlation, 3),
        "warnings": [w.check for w in (ident.issues + scale.issues
                                       + setm.issues)],
    }
    o = out[arm]
    print(arm, o["identity"], o["self_identity"], o["scale"], o["set_inliers"], o["set_hsv"],
          o["warnings"])
Path("docs/drama/wp5/measure.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
