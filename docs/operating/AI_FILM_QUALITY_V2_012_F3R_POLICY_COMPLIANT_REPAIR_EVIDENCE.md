# AI FILM QUALITY V2-012 — F3R POLICY-COMPLIANT REPAIR + FULL SEQUENCE CLOSURE

Slice: `AI-FILM-QUALITY-V2-012` · Branch `quality-v2/011b-editorial-assembly`
Start HEAD: `9ab6a26` (accepted 011D) · Provider mutations: **1/1** (F3R_012 — release, receipt captured, asset acquired)

## Final state

```
STATUS                  = COMPLETED_CANDIDATE
FULL_SEQUENCE_CONTEXT   = PROVEN
SEQ_CONTEXT_LOCK        = GRANTED
SEQ7_F1_F2_F3           = FILM_USABLE
F2_SEQUENCE_LOCKED_v1   = unchanged (sha re-verified ada66463…)
F1R                     = unchanged (sha re-verified b879f215…, ACCEPTED)
```

## Prompt audit → repair (no safety-evasion)

`V2_012_F3R_PROMPT_AUDIT.json` decomposes the frozen 011D F3R prompt (sha `4066ab6f…`) into
A–H. **PROVEN:** the provider refused that exact prompt (after billing). **UNKNOWN:** which
token/phrase/semantic relation triggered the filter — no hypothesis promoted. (Recorded
observation only: several components — `swordsman`, the weapon-negative block, storm/wind
language — are proven filter-neutral by the accepted F2A-R/F2B-R prompts.)

`V2_012_F3R_PROMPT_DIFF.json` — every change uses an allowed reason
(CLARIFY_BENIGN_ACTION / REMOVE_NONESSENTIAL_AMBIGUITY / MAKE_VISUAL_INTENT_EXPLICIT /
PRESERVE_WORLD_CONTINUITY); forbidden reason `BYPASS_PROVIDER_FILTER` was not used. The scene
was made **clearer and explicitly benign**, not disguised:

| old | new | reason |
| --- | --- | --- |
| the same swordsman | the same adult traveler | MAKE_VISUAL_INTENT_EXPLICIT |
| stands pressed close against | stands safely beside | CLARIFY_BENIGN_ACTION |
| eyes narrowed | with a steady gaze | REMOVE_NONESSENTIAL_AMBIGUITY |
| sets his jaw … the cost held | after crossing the mountain pass, his breathing settles; calm, determined, reflective | CLARIFY_BENIGN_ACTION (the beat is fully expressed; the mission authorizes dropping the literal phrase) |
| strands of hair whip across his face | the wind moves his hair | REMOVE_NONESSENTIAL_AMBIGUITY |
| storm gust keeps pulling | storm wind keeps blowing | CLARIFY_BENIGN_ACTION |

KEPT verbatim (proven filter-neutral by F2A-R/F2B-R, protects no-prop continuity): the
weapon-negative block and the world-negative block. Repaired prompt sha `99ba2bb4…`.

## Dispatch — exactly ONE mutation, clean path

ACCOUNT_D (Owner-authorized, native session). Gates: custody (F1R/F2 SHAs), repaired spec
frozen, secret audit CLEAN (note: the first audit FAIL was a false positive from the unrelated
legacy `tools/recovery_matrix_012.py` whose own marker constants match; re-scoped to V2-012
files → CLEAN), exclusive profile ownership (0 browsers), credit as PRIOR EVIDENCE per package
(3 remaining ack; no state-query message sent).

```
MUTATION_RESERVED → DISPATCH_ARMED (5s chip, fingerprint frozen, capture active)
→ NETWORK_RELEASE_OBSERVED 14:59Z → SSE_RECEIPT_CAPTURED (in window — no latch)
→ CREATION_BOUND (conversation 38417944671772433, creation 1542350901495057)
→ ASSET_DOWNLOADED → TERMINAL_SUCCESS
```

The repaired prompt was accepted and generated on the **first dispatch** — consistent with a
wording-class trigger in the old prompt, which does NOT prove which token (trigger stays
UNKNOWN in the lineage record).

## F3R_012

```
asset assets/f3r_012.mp4 · sha b558f8e89ae4664ca6d7325f84fcf18ad17174bc72caa12773354266c2427bbb
5.088005s · 1280x720 · 24fps · 121 frames · hevc · Dola AI watermark (preserved)
palette luma 78.74 / U 138.36 / V 115.68 vs F2-end target 99.10/141.53/112.97 (same cold family)
```

Creative QC — **F3R_012_ACCEPTED**: WORLD (natural dark rock, F2 family, no masonry, cold storm
light) PASS; IDENTITY PASS with a recorded observation (the MCU establishes the facial identity
for the new sequence — no resolvable face exists upstream to contradict; text-only identity
cannot bind facial geometry, the QD-003 limitation; headband reads lighter than F1R's distant
dark ribbon — flagged for the future face-reference work, not a failure); COMPOSITION PASS
(MCU, frame-left, eyeline); PERFORMANCE PASS (settling, calm determination, no panic/aggression).

## F2 → F3R_012 cut — CUT_PASS (no trim needed)

All 15 dimensions PASS (identity, wardrobe, world, rock material, lighting, palette, weather,
screen direction, eyeline, body orientation, motion→settle, action energy, character scale,
shot-size rhythm, narrative state). The 011C tan-built-wall failure is gone — both sides are the
same dark jagged natural stone. Trim window IN 0..12 evaluated: frames near-identical (still
settle beat); base IN=0 kept, selection 0..76 (77 frames = 3.208333s F3-slot parity).

## Full sequence proof

```
outputs/F1R_F2_F3R_SEQUENCE_PROOF.mp4
sha256 63eac46c7a5568ba4a3c1f0ffe54d911f7d96d35d3369bab59c70fe31c1b30ef
326 frames (115 + 134 + 77) @ 24fps · 13.583333s · h264 yuv420p + AAC 192k
junctions at frames 115 and 249 · concat FILTER · 0 timestamp discontinuities
decode PASS · no black · no frozen · frame count exact
ARRIVE → FORCE THROUGH → COST HELD — reads as one continuous storm-pass passage
```

Film QC: narrative progression / world / lighting / weather / screen direction / motion flow /
identity / wardrobe / performance / camera grammar / shot-size rhythm / edit rhythm — ALL PASS.
Carried observation: F1R's establishing WS renders the ridge monumental vs F2's human-scale
entry (recorded in 011D, unchanged). Audio: J1 step **0.8 dB** (nearly seamless — was 7.2 dB in
the 011C world), J2 step 8.0 dB → `AUDIO_CONTEXT = FINISHING_REPAIR_REQUIRED` carried to the
finishing mix; not a regeneration cause. Watermark preserved everywhere.

## Mandatory handoff

**SEQ_CONTEXT_LOCK = GRANTED → STOP.** Return to Tech Lead. Do NOT begin finishing. Next
planned slice: **V2-011W — Dola Unwatermarked Asset Authority Qualification** (read-only; zero
video-generation mutations unless separately authorized).
