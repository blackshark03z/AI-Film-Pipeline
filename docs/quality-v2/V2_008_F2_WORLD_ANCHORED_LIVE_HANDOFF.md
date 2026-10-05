# V2-008 F2 WORLD-ANCHORED LIVE HANDOFF

**From:** AI-FILM-QUALITY-V2-007 (world-anchor + pacing preflight)
**To:** V2-008 (world-anchored live experiment, when the Owner
authorizes the one reference-qualification upload)
**Status:** HANDOFF — READY contingent on the Owner authorizing:
(1) the reference-qualification upload (ONE still, from already-
acquired project media), (2) the F2A pacing delta proposal.

---

## 1. Proven facts carried in

- **F2A is NOT salvageable**: all 27 contiguous 2.8 s windows fail
  (interval proof in `f2a_salvage_scan_v2_007.json` — sword from 1.4 s,
  metal gate from 5.0 s, arrival ≈6.2 s).
- **The far-side world reference EXISTS inside project media**: the
  V2-004-B render @ **6.6 s** — granite doorway BEHIND the subject,
  storm-gate world, identity correct, exact provenance
  (asset `b573cf13…`, output `279e5139…`). The REJECTED take is NOT
  promoted; it supplies ONE reference frame through explicit
  reference-qualification provenance only.
- **F2A's failure classes**: TOO_MUCH_TRAVEL_DISTANCE ·
  PROVIDER_ACTION_DELAY · UNSCHEDULED_SWORD_ACTION ·
  WORLD_STRUCTURE_INVENTION.

## 2. V2-008 scope (frozen)

1. **Reference qualification (once, Owner-authorized upload):**
   extract the V2-004-B @ 6.6 s still
   (`qc_evidence/wref_V2004B_t6.6.png`,
   sha `fc527bac6fa9a85f…` — recompute at extraction), qualify it
   through the standard reference-binding/attestation path
   (`refbind_*`), bind it as F2B's WORLD reference. Exactly **1
   upload**; no other upload; no provider switch.
2. **F2A — ONE revised minimal-pacing render** (the pacing delta
   PROPOSED in V2-007 §6, now Owner-authorized into the plan as a new
   plan revision — previous revision preserved, all gates rerun):
   - `F2A_START = CLOSE_BEFORE_THRESHOLD` (no long approach);
   - gust already active → immediate body commitment → one/two steps
     → threshold;
   - NO sword draw, weapon passive, no rock interaction;
   - reference: near-side F1 last-frame (compatible with a close
     start);
   - window 2.8 s, arrival anchor ≤ 2.4 s.
3. **F2B — ONE far-side render** with the qualified WORLD reference
   (gate-behind read anchored by real storm-gate far-side geography).
4. Budget: **≤ 2 new Generates** (1 F2A + 1 F2B). No alternate takes
   initially. Retries 0. Ambiguity ⇒ OWNER_AMBIGUITY_GATE.
5. Canonical promotion 0.

## 3. QC contracts carried unchanged

- F2A A1–A10 hard set (arrival inside the window is the point of the
  pacing delta); F2B B1–B10 hard set (far-side readable ≤ 2.4 s);
  pair P1–P10 only when both pass; atomic pair decision
  (SELECT_F2A_F2B_PAIR / REJECT_ALL / KEEP_CANONICAL / NEEDS_REPAIR /
  DEFER).
- Identity must not regress; world continuity must be materially
  compatible (the WORLD_REFERENCE still carries the storm-gate world;
  the fortress/metal/warm-cloud failure classes are named recovery
  cases).

## 4. Stop conditions

1. Reference-qualification upload fails or attestation mismatch ⇒
   BLOCKED_INVARIANT (no improvised upload route).
2. Any ambiguity ⇒ OWNER_AMBIGUITY_GATE (no second submit).
3. Either hard set fails ⇒ pair refused (honest record; no retry).
4. Budget exhausted ⇒ stop.
