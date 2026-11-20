# Edge-intrusion detector calibration (upgrade plan step 5), 2026-11-20

Detector: `src/film_pipeline/production/edge_intrusion.py`, `DETECTOR_VERSION = "1.0.0"`.
Machine-readable numbers: `edge_intrusion_calibration_20261120.json` (same folder).
Scratch artifacts (manifest, feature cache, scripts): `D:/AI FILM MAKER/_archive/step5_edge/`
(`build_manifest.py`, `extract_all.py`, `calibrate.py`, `old_check.py`, `final_report.py`, `manifest.jsonl`).

**Decision: targets NOT met on held-out. The detector ships as an advisory `INFO` signal in dailies
triage, not `WARN`. It never auto-rejects. The legacy 12-frame `EDGE_INTRUSION_RISK` check stays.**

## 1. Labelled set

Sources: `films/<film>/takes/index.json` (status, cause), `takes/reviews/<take>.qc.json`
(`cause_note`, non-PASS check `note`/`evidence` for rejects, all checks for accepts),
`takes/dailies/<take>.review.json` (`shot.visible`, `shot.coverage` at generation time; fallback
`04_shots.json`), clip `media/takes/<output_file>` (sha256 recomputed).

Keyword rules (case-insensitive, applied per clause of the failing notes):
- R1 edge-person: a person term (`listener|head|hair|face|shoulder|arm|forehead|ear|nose|profile|person|sliver|older man|woman|bun`)
  and an edge term (`left/right/bottom/top edge`, `edge of frame`, `frame-left/right edge`, `left/right of the frame`, `listener-at-edge`, `listener-edge`, `right of the pillar`).
- R2 extra person: `second … woman/man/person`, `two RUTHs/SAMs`, `another/extra/other person`.
- R3 drift phrasing: `slides/drifted the listener`, `listener enters/appears at/visible/leaks`.
- A clause that only states a clean edge (`edges fine/clean/bare`, `nothing at the edges`, `wholly out`) is skipped.
- Clean negative: ACCEPTED (final status in index) of a single-visible shot, unless any clause mentions a
  tolerated sliver/leak (`sliver`, `listener hair/head/blur`, `hair grows in`, `leak confined to outer N%`,
  `reframe note`, `punch-in`; but not `no leak`, `none needed`, `strip clean`) -> excluded as ambiguous.
  Also a reject whose note explicitly says the edges were fine (1 take: film08 SC02_g08_t2).
- Everything else rejected for another reason, and multi-visible takes, is excluded.

| label | film07 | film08 |
|---|---|---|
| positive (single-visible) | 50 | 28 |
| negative: accepted single-visible | 263 | 242 |
| negative: reject, edges explicitly fine | 0 | 1 |
| excluded: accepted with tolerated sliver/leak | 15 | 43 |
| excluded: reject for another reason | 6 | 24 |
| excluded: multi-visible (pos / accepted) | 1 / 22 | 0 / 15 |
| **evaluation set (pos / neg)** | **50 / 263** | **28 / 243** |

Spot-check (10 random positives, one contact sheet at the last 0.8 s): 6 show the intruder clearly
(SC08_g06_t1, SC09_g05_t1, f08 SC04_g09_t1, SC05_g19_t2, SC05_g04_t1, SC09_g15_t1); 4 not visible at that
instant/scale, consistent with brief or tiny intrusions in their notes (SC02_g09_t1 "clearly at 5.7 s",
f08 SC03_g02_t1 "for ~3 s", SC08_g05_t4, SC03_g22_t2 bottom-right fragment). One note names the wrong side
(SC09_g15_t1 says right, the hair is at the left). Labels are binary, so side errors do not affect scores.
Label noise exists on the negative side: some top false alarms look like unlabelled slivers (film07
SC12_g14_t1, SC10_g06_t1, SC10_g09_t1); labels were not changed after seeing detector output.

## 2. Detector

Decodes every 2nd frame (12 fps at 24 fps source) at 320x180 gray. Camera motion: frame-to-frame LK
corners (inner 88% of width) + RANSAC similarity, composed to the first frame; phase correlation fallback;
implausible increments rejected. Diff vs the motion-compensated first frame, only where the reference
covers the pixel (a pan does not count). Stored per frame: changed-fraction profiles, a 12x64 cell grid,
edge-attached blobs, YuNet faces (optional). Features tried: (a) YuNet faces vs visible count / edge
margin; (b) side-band changed fraction (`band`), band minus inner band (`band_contrast`), one-sided
(`band_onesided`), edge-attached blob (`blob`), optional bottom band and head-height rows (`band_rows`);
(c) faces OR edge. Persistence = the highest level kept for `min_persist_s`. Output: score, verdict,
sides, time ranges, detector + version, clip sha256, face status.

Faces (YuNet 2023mar, OpenCV Zoo, **Apache-2.0** — not MIT; 232 KB, copied to
`production/models/` with licence and provenance): alone recall 0.08 (f07) / 0.04 (f08) at FPR 0.
Partial heads/hair at the edge are not detected as faces. Default config does not load it; a missing
model gives `face_status = "missing_model"` and the edge feature still runs.

## 3. Calibration

Pre-registered (before any held-out number): held-out recall >= 0.80 and FPR <= 0.15; tune on film07 only,
pick max recall with tuning FPR <= 0.10 (ties: lower FPR, fewer features, longer persistence).

| run | config | tune (recall / FPR) | held-out (recall / FPR) | met |
|---|---|---|---|---|
| pre-registered f07 -> f08 | band_contrast 4%, diff 35, level 0.10, 0.5 s, faces 0.6 | 0.88 / 0.091 | **0.75 / 0.214** | no |
| reverse f08 -> f07 | band_contrast 4%, top 50% rows, diff 20, level 0.325, 0.5 s | 0.75 / 0.074 | **0.78 / 0.076** | no |
| legacy 12-frame check | — | f07 0.56 / 0.053 | f08 0.21 / 0.070 | no |

Confusion matrices:
- Pre-registered on film08 held-out: TP 21, FN 7, FP 52, TN 191.
- **Shipped operating point** (= reverse config, `DEFAULT_PARAMS`): film07 (held-out) TP 39, FN 11,
  FP 20, TN 243 (0.78 / 0.076); film08 (its tuning film) TP 21, FN 7, FP 18, TN 225 (0.75 / 0.074).
  Chosen over the pre-registered one because it holds up across both films; the film07-tuned config
  overfitted (FPR 0.09 -> 0.21).

Held-out looks (honest log): look 1 (first motion model) f07->f08 0.75 / 0.173; look 2 (sequential motion,
more features) 0.75 / 0.214, reverse 0.74 / 0.042; after look 2 film08 misses/false alarms were viewed
for this report, so film08 is no longer a clean held-out; look 3 added head-height rows (`band_rows`),
f07->f08 unchanged, reverse 0.78 / 0.076. Numbers after look 2 are optimistic.

5 worst on film08 held-out (pre-registered config):
- Misses: SC03_g02_t1 (0.40) head in for ~3 s only, small; SC05_g07_t2 (0.54) thin late sliver at right;
  SC09_g03_t2 (0.62) back of head already in frame 0, so no change vs the reference; SC01_g04_t1 (0.64)
  glasses arm + head part in 2 frames only; SC05_g03_t1 (0.73) face enters late, small area.
- False alarms: SC11_g18_t1 (7.7), SC02_g19_t1 (7.2), SC02_g13_t1 (5.2), SC02_g17_t1 (4.8) camera push-in /
  dolly with parallax on the subject's shoulders at both edges; SC03_g24_t1 (7.3) subject turns and
  her shoulder moves at the right edge.

5 worst on film07 held-out (shipped config): misses SC03_g22_t2 (shoulder already in the start still),
SC09_g15_t1, SC02_g09_t1, SC05_g14_t1, SC12_g24_t1 (small slivers under the level); false alarms
SC11_g05_t1, SC10_g11_t2 (push-in/reframe), SC10_g17_t2 (subject turns at edge), SC10_g08_t2 and
SC02_g01_t2 (the subject himself walks out of frame).

Runtime: ~0.5 s per 6 s 360p clip (default, no faces), ~0.7 s with faces, single process.

## 4. Integration and decision

`dailies_triage.triage_take` runs the detector on single-visible takes and, when SUSPECT, adds the exact
signal `{"code": "EDGE_INTRUSION_SUSPECT", "detector": "edge_intrusion", "detector_version", "take_id",
"clip_sha256", "sides", "time_ranges", "score", "severity": "INFO"}` to `result["signals"]`; details and the
measured numbers are in `metrics.edge_intrusion.message`. `INFO` signals are not added to `warnings`, so
they do not flip the review UI to FLAGGED. To promote to `WARN` (added to `warnings`, explicit reviewer
decision) set `EDGE_INTRUSION_SEVERITY = "WARN"` only after a clean held-out film (e.g. the first film09
batch) meets 0.80 / 0.15. Triage cache version 2 -> 3.

The legacy 12-frame `EDGE_INTRUSION_RISK` check is kept: the new detector does not strictly supersede it
(it is not run on multi-visible takes, and the legacy check compares against the start still, which the
new one does not). The legacy check is weaker on both films (recall 0.56 / 0.21).

Known gaps: intrusions present in the first frame / start still; subject's own exits and turns at the
edge; camera push-ins with parallax. Next ideas: start-still vs reference-character appearance at the
edge, a person segmenter for the edge strips, using the declared choreography (exit/walk) to gate.
