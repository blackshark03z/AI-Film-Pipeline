# AI-FILM-QUALITY-V2-005R — F2 Decomposition Reference-Compatibility Preflight — Evidence Record

**Status: F2B_REFERENCE_GEOGRAPHY_CONFLICT** — proven mechanically from
the exact bound media bytes. **V2_006_READY = false** until the Owner
authorizes the (upload-free) reference-strategy amendment.

## 1. Custody (P1)

| Item | Value |
| --- | --- |
| Exact V2-005 final HEAD | `b92e03710d5aec6a48527b4fc24c4ef35deb41c7` — verified exact (branch `quality-v2/005r-reference-preflight`); any drift would have been `BLOCKED_CUSTODY` |
| V2-005 evidence / V2-006 handoff | bound in `custody_v2_005r.json` |
| Bound reference | media `8f2f5277-aae8-44b5-a5b7-c197d1d7c115`, asset `asset_cb5bba09…`, attestation `refbind_f4277ac1…`, sha `fecf669e…8313` |
| F2A/F2B plans | frozen BS/CC ids rebound from the V2-005 plan |

## 2. Reference classification (P2) — from the ACTUAL bytes

The exact bound bytes exist locally (`attestation/fecf669e….jpg`,
256114 bytes, sha re-computed == attested). Classification is derived
from those hashed bytes — dimensions, framing/extent visual read —
never from a filename:

| Property | Value |
| --- | --- |
| REFERENCE_TYPE | **FULL_FRAME_ENVIRONMENTAL** |
| Dimensions | 1280×720 (full 16:9 frame) |
| Gate/background geometry | gate rock slab at frame-left; landscape + storm sky visible |
| Subject position | beside the rock at the gate mouth — NEAR-side geography encoded |
| Far side visible | NO (occluded by the rock) |
| Environment correlation vs canonical F2C first frame | **0.678** (> 0.5) |
| Materially constrains camera/geography | YES |

## 3. Compatibility (P3/P4)

| Shot | Verdict | Basis |
| --- | --- | --- |
| F2A (BEFORE_GATE → AT_THRESHOLD, near-side three-quarter) | **F2A_REFERENCE_COMPATIBLE = true** | the reference encodes exactly the near-side approach state F2A opens with |
| F2B (START beyond threshold, gate BEHIND subject, BEFORE_GATE forbidden) | **F2B_REFERENCE_COMPATIBLE = false** → `REFERENCE_GEOGRAPHY_CONFLICT` | full-frame near-side conditioning contradicts the required beyond-gate geography; prompt text is NOT proven to override a full-frame visual conditioning input (and V2-004-B showed staging follows the conditioning strongly) |

## 4. Decision (P5)

**B) F2B_REFERENCE_GEOGRAPHY_CONFLICT** → **V2_006_READY = false**. No
generation, no Flow submit, no upload, no provider switch, no
canonical mutation (all zero, structurally asserted).

## 5. Smallest next bounded qualification (P6) — designed, NOT executed

**Option 1 applies (preferred order):** an ALREADY-QUALIFIED
identity-only reference exists with exact provenance:

| Property | Value |
| --- | --- |
| Media | `7b725f7b-4da5-4455-a6f2-135c4ba22397` |
| Asset | `asset_2ab16c9f6aff842e3c3c15b2f1b0619217f3925a0ab2ae255b9fcd86d60a0ae2` |
| SHA256 | `ed75a8b27b9be48c30f948a93ad7f1421e60c35a6003efdfb4ddf0bc3a0ca4e8` (local bytes re-verified) |
| Classification | **IDENTITY_ONLY** — chest-up portrait, clouds/peaks only, ZERO gate geography |
| Provenance | adopted provider media (readback), durable store asset record; the qualified base reference since Packages 003+ (used for F1 and the 018 G3C candidates) |

**Proposed amendment (requires Owner authorization; 0 uploads because
the media is already bound to the project):** F2A keeps the near-side
full-frame reference `8f2f5277…` (compatible); F2B binds the
identity-only reference `7b725f7b…` (carries no geography — the
far-side plan is unconstrained). Provider switch: none.

## 6. Owner decision contract fix (P7)

V2-006 selection is now **atomic-pair**:
`SELECT_F2A_F2B_PAIR / REJECT_ALL / KEEP_CANONICAL / NEEDS_REPAIR /
DEFER`. The options that could select F2A alone (or F2B alone) are
removed — an editorially orphaned half-shot is unusable. Template:
`projects/quality_v2_006_f2_decomposed_live/owner_decision_template_v2_006.template.json`;
the handoff carries the amendment section and `V2_006_READY = false`.

## 7. Verification (P8)

- **1196 tests passed** (all predecessor suites + 11 new preflight
  tests covering every required adversarial scenario: full-frame
  near-side reference vs far-side shot, identity-only acceptance,
  UNKNOWN type → inconclusive, missing exact sha → refusal,
  reference/camera contradiction recorded, F2A-alone selection
  removed, hidden upload / provider switch / canonical mutation /
  ambiguity invariants).
- compileall clean · `git diff --check` clean · secret scan clean ·
  SoT manifest 30/30 · canonical master byte-identical.

## 8. Unresolved unknowns

1. The Owner's authorization of the split-reference amendment.
2. Whether an identity-only reference changes F2B's world continuity
   behavior on the qualified route (that is precisely what V2-006's
   single F2B submit would measure).

## 9. Final status

**F2B_REFERENCE_GEOGRAPHY_CONFLICT** · REFERENCE_TYPE =
FULL_FRAME_ENVIRONMENTAL · F2A_REFERENCE_COMPATIBLE = true ·
F2B_REFERENCE_COMPATIBLE = false (bound) / true (identity-only
amendment) · V2_006_READY = false · NEXT = Owner decision on the
amendment → V2-006 with the split reference strategy.
PACKAGE_005R_FINAL_HEAD_SHA is returned in the final worker report.
