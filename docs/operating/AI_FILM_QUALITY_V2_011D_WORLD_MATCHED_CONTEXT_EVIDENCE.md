# AI FILM QUALITY V2-011D — WORLD-MATCHED CONTEXT REPAIR EVIDENCE

Slice: `AI-FILM-QUALITY-V2-011D` — World-Matched F1/F3 Context Repair + Full Sequence Lock
Branch: `quality-v2/011b-editorial-assembly` · Head at slice start: `40c6e5beaf3e5f76b358ba8af05c7454a1cfd411`
Provider mutations: **1/2 used** (F1R = 1, F3R = 0 unspent) · No retry · No provider switch

---

## Final state

```
ENGINEERING_STATUS    = F1R repair PROVEN and ACCEPTED; F1R->F2 CUT_PASS; F2 untouched
FILM_CONTEXT_STATUS   = FULL_SEQUENCE_CONTEXT NOT PROVEN — F3R missing
STOP REASON           = STOPPED_INSUFFICIENT_CREDIT_PRE_DISPATCH (F3R)
SEQ_CONTEXT_LOCK      = DENIED (pending F3R only)
F2_SEQUENCE           = FILM_USABLE (all three locks intact; proof sha re-verified)
```

---

## World authority

`SEQ7_WORLD_LOCK_FROM_F2` (`V2_011D_WORLD_LOCK.json`) — derived from the **actual accepted
locked-F2 imagery** (proof copied into 011D custody, sha-verified `ada66463…`), not prose:

- start region (F2 frames 0–23) = F1R world target: **luma 83.63 / U 139.85 / V 114.52**
- end region (F2 frames 110–133) = F3R world target: **luma 99.10 / U 141.53 / V 112.97**
- required / forbidden lists exactly per package (continuous natural ridge, single choke point,
  road funnel, cold storm palette; forbidden: freestanding gate, standing stones, wooden lintel,
  masonry, tan wall, bypass, warm sunlight, weapons)

## F1R — ONE mutation, proven end-to-end

Frozen spec `V2_011D_F1R_SPEC.json` (prompt sha `c3c43e1f6a973e06…`): original F1 intent verbatim
(establishing WS, locked camera, frame-left travel, arrival beat, identity) — only world + lighting
changed to the world lock. All pre-render gate phrases verified in-prompt before dispatch.

Dispatch (ACCOUNT_A, the only READY account — precheck probe credit=1):

```
MUTATION_RESERVED → DISPATCH_ARMED (5s chip, fingerprint frozen, capture active)
→ NETWORK_RELEASE_OBSERVED (account binding IMMUTABLE; release refined: duration=5, needle present)
→ receipt not captured within 120s → OWNER_AMBIGUITY_GATE LATCHED (one-way, frozen invariant)
```

**Read-only reconciliation** (latch respected; acquisition only): the F1R conversation
(`38417962862699025`) shows the provider accepted the request, generated with **Seedance 2.0**, and
billed the last credit ("本日の残りは0動画クレジットです"). Delivery-shape variance recorded: the
limit-20 conversation poll returns the completed type-2 creation **without** `download_url`; the
limit-10 poll returns the full object (signed URL) — one-shot full-creation dump
(`V2_011D_F1R_CREATION_DUMP.json`) located it; direct HTTP acquisition.

```
asset: assets/f1r.mp4
sha256 b879f21586392fa7463021f60853b1aa99fecb286890dad1b3f192c6dd805171
5.088005s · 1280x720 · 24fps · 121 frames · hevc + aac · Dola AI watermark (preserved)
creation 1546471384527889 · vid v186a3gm000cdb2dgqfog65h35lcimvg
```

### F1R hard QC — 7/7 PASS → F1R_ACCEPTED

| Item | Verdict | Evidence |
| --- | --- | --- |
| natural ridge | PASS | towering continuous dark natural rock wall, rough stone |
| single opening | PASS | one narrow gap; the road funnels into it |
| no decorative gate | PASS | no freestanding stones / wooden lintel / architecture |
| no open-field bypass | PASS | ridge extends beyond both lateral sides of the opening |
| cold storm palette | PASS | **luma 67.80 / U 139.04 / V 114.94** vs F2 start target 83.63 / 139.85 / 114.52 — chroma near-exact; zero warm light (old F1 was luma 102 warm) |
| frame-left | PASS | enters frame-right, travels/faces frame-left all 121 frames |
| identity | PASS | white robes + black sash + topknot + streaming headband; the suspected back-object resolved at full-res zoom as the wind-whipped headband ribbon — **no weapon** |

Owner review: `owner_review_011d/F1R_contact_sheet.png`, zooms under `frames/`.

## F1R → F2 cut — CUT_PASS

Junction `owner_review_011d/F1R_F2_JUNCTION.png` + full-res pair
`frames/PAIR_F1R_n114_F2_n0.png`. Base boundary F1R frame 114 → locked F2 frame 0; trim window
OUT exclusive 103..121 (±12 clipped by the 121-frame asset) evaluated — base kept.

All nine required dimensions **PASS**: geography (same continuous-ridge choke-point world — the
011C freestanding-gate/open-field failure is resolved), lighting, palette, weather, screen
direction, travel direction, motion phase, identity, causal action (arrive → commit).

Honest observations (recorded, not averaged into a failure): F1R's extreme WS renders the ridge
monumental while F2 shows the human-scale entry — establishing-shot scale rendering of the same
landmark; character-scale cut-in (tiny → mid) is standard grammar.

## F3R — UNRELEASED (0/1): the fail-closed credit gate

After F1R, the credit landscape (provider statements are the authority):

| Account | State |
| --- | --- |
| ACCOUNT_A | **0 credit** — provider statement in the F1R conversation after billing |
| ACCOUNT_B | LOGIN_REQUIRED (no sessionid in store; manual login is Owner-side) |
| ACCOUNT_C | **0 credit** — observed read-only: "残りは0動画クレジット" (router probe 11:51:07Z); the V2-010E-established text inquiry attempt hit a transient logged-out UI flap first |

`V2_011D_F3R_CREDIT_GATE.json` verdict: **INSUFFICIENT** → the F3R pre-render gate failed closed.
No dispatch attempted (a 0-credit dispatch is refused and would risk an ambiguity latch for
nothing). F3R spec stays frozen (`V2_011D_F3R_SPEC.json`, prompt sha `4066ab6f755475cd…`); its
mutation remains 0/1.

## Immutable truth verified

- `F2_SEQUENCE_EDITORIAL_PROOF.mp4` sha `ada66463…` **recomputed and unchanged** after all work.
- No F2 regeneration / retrim / cut change / asset replacement — the locked proof was used verbatim
  as the middle unit.
- Watermark: PRESERVED everywhere (Dola AI on F1R); `UNWATERMARKED_VARIANT =
  OBSERVED_NOT_AUTHORIZED`; 011W owns watermark authority separately.
- AUDIO_CONTEXT = FINISHING_REPAIR_REQUIRED carried forward (011C measured 7.2 dB / 11.8 dB
  ambience steps; mix-level repair in a finishing slice).

## Outputs

```
projects/quality_v2_011d_world_matched_context/
  V2_011D_WORLD_LOCK.json
  V2_011D_F1R_SPEC.json  V2_011D_F1R_QC.json  V2_011D_F1R_EVIDENCE.json
  V2_011D_F1R_CREATION_DUMP.json  V2_011D_F1R_RECONCILIATION(absent→superseded by dump+acquire)
  V2_011D_F3R_SPEC.json  V2_011D_F3R_CREDIT_GATE.json
  V2_011D_CONTEXT_CUT_QC.json  V2_011D_SEQUENCE_QC.json  V2_011D_EDITORIAL_RANGES.json
  V2_011D_MUTATION_LEDGER.json  V2_011D_PROVIDER_LINEAGE.json
  V2_011D_SECRET_AUDIT.json  V2_011D_SESSION_PRECHECK.json  V2_011D_PRERENDER_GATES.json
  V2_011D_CANDIDATE_SEAL.json
  assets/f1r.mp4 · inputs_F2_proof.mp4 · world_reference_frames/ · frames_f1r/ (121 frames)
  owner_review_011d/F1R_contact_sheet.png · F1R_F2_JUNCTION.png
tools/: build_v2_011d_world_lock.py · v2_011d_precheck.py · run_v2_011d_shot.py ·
        reconcile_v2_011d_f1r.py · dump_v2_011d_f1r_creation.py · v2_011d_f1r_qc.py ·
        v2_011d_f3r_credit_inquiry.py · build_v2_011d_evidence.py
```

`outputs/F1R_F2_F3R_SEQUENCE_PROOF.mp4` NOT created (F3R missing). `F3R_contact_sheet.png`,
`F2_F3R_JUNCTION.png`, `FULL_SEQUENCE_CONTACT_SHEET.png` not producible without F3R.

## Mandatory next handoff

Return to Tech Lead — do NOT start finishing:

1. **F3R successor slice** (when provider credit is available — daily reset expected ≈ JST
   midnight ≈ 16:00 UTC, or Owner top-up): ONE generate per the frozen `V2_011D_F3R_SPEC.json` on a
   READY account (rotation only before dispatch), hard QC per spec, then F2→F3R cut QC, full
   assembly `F1R → HARD CUT → LOCKED F2 → HARD CUT → F3R`, full sequence QC, and the
   `SEQ_CONTEXT_LOCK` decision. F1R custody and all specs are durable — the successor is a small slice.
2. After `SEQ_CONTEXT_LOCK = GRANTED` → **V2-011W** (Dola Unwatermarked Asset Authority
   Qualification). Provider generation in 011W should be zero unless a truly unavoidable
   qualification mutation is separately authorized.

---

# RESUME (same slice, 2026-10-06 ~12:0x–14:5xZ) — F3R half

Starting authority verified read-only (11/11 PASS: HEAD `7e97a74`, F1R sha/verdict, F1R→F2
CUT_PASS, F2 sha + 134fr@24fps, F3R spec prompt-sha `4066ab6f…`, F1R slot LATCHED+RESOLVED,
F3R 0/1, secret audit CLEAN).

## Credit gate under the governance correction

- The periodic message-inquiry plan was replaced per the Owner's governance correction: credit
  inquiries that SEND a provider message are `ACCOUNT_STATE_QUERY_MUTATIONS` (separate ledger,
  never "read-only"), minimum necessary.
- Router probe (true read-only): ACCOUNT_A=0, ACCOUNT_C=0 (statements), ACCOUNT_B LOGIN_REQUIRED.
- Chrome-profile route (Owner-authorized candidates khoikk/khoi43956/khoicaesarxxx/wanglinyy →
  mapped via `profile.info_cache`, not directory numbers): Owner signed Dola in via
  "Continue with Google" (Khởi Đặng219).
- Exactly ONE credit inquiry was sent (`ACCOUNT_STATE_QUERY_MUTATION #1`) — the bot refused
  (identical to the 010E inquiry: fresh accounts get no credit statement until the first
  generation). The UI exposes no credit surface (account menu / video panel / settings URLs all
  scanned). **Conclusion: pre-first-generation credit is NOT observable by any existing
  mechanism.**
- Owner explicitly authorized a structural dispatch on the fresh account, accepting the stated
  risk (recorded in `V2_011D_F3R_CREDIT_GATE.json` verdict SUFFICIENT with basis
  OWNER_STRUCTURAL_DISPATCH_AUTHORIZATION).

## Session remediation (documented)

- Captured-cookie route (real-Chrome session replayed inside patchright chromium) was
  invalidated by ByteDance passport fingerprint binding — the V2-010B lesson confirmed at the
  session layer (`has_sessionid: false` after replay).
- Remedied by the Owner's NATIVE Google login INSIDE the ACCOUNT_D automation profile
  (fingerprint-consistent; 32 cookies re-captured to the refreshed DPAPI blob; the runner then
  authenticated immediately).
- First dispatch attempt failed PRE-release (`USER_LOGIN_REQUIRED`) — boundary A =
  SAFE_UNSPENT; no authority consumed; F3R stayed 0/1.

## F3R release and provider refusal

```
MUTATION_RESERVED → DISPATCH_ARMED (5s chip, fingerprint frozen, capture active)
→ NETWORK_RELEASE_OBSERVED 14:31Z (account binding immutable; release refined: duration=5, needle present)
→ receipt not captured in 120s → OWNER_AMBIGUITY_GATE latched (one-way)
```

Read-only reconciliation (limit-10 poll per the Seedance 2.0 gotcha) resolved the external
effect: **the provider REFUSED the frozen F3R prompt** —

> 当社のポリシーに違反する可能性がある内容が入力されているため、動画を生成できません。修正してもう一度お試しください。

The release was accepted and **billed 1 credit** (provider ack: 本日の残りは**3**動画クレジット —
the fresh account's daily grant was 4, so the Owner's structural credit authorization was
factually sound). **No asset exists.** The failure class is the provider CONTENT-POLICY filter on
the MCU close-up wording (face/shoulders portrait with wind-whipped hair) — not credit, not
session, not world.

## Final state

```
STATUS              = STOPPED_EXPLICIT_PROVIDER_FAILURE (F3R refused after billing)
MUTATIONS           = 2/2 (F1R consumed+ACCEPTED; F3R consumed — released, billed, refused)
ACCOUNT_STATE_QUERY_MUTATIONS = 1 (bot refused; recorded separately)
F1R                 = ACCEPTED (b879f215…, world-matched, 7/7 hard QC)
F1R→F2              = CUT_PASS
F2                  = LOCKED, sha re-verified unchanged
F3R                 = RELEASED_BILLED_REFUSED_NO_ASSET (spec stays frozen)
FULL_SEQUENCE_CONTEXT = NOT_PROVEN_F3R_PROVIDER_REFUSAL
SEQ_CONTEXT_LOCK    = DENIED
outputs/F1R_F2_F3R_SEQUENCE_PROOF.mp4 = NOT CREATED (F3R missing)
```

`NO retry` post-release is absolute: the ONE F3R mutation is spent. A successor slice (proposed
**V2-012**) requires NEW Owner authorization: ONE generation with a policy-safe rephrase of the
FROZEN F3R intent (same MCU/beat/world; reword to avoid the face-close-up + hair-whip trigger
pattern), dispatched on a READY account — ACCOUNT_D now has **3 provider-visible credits** and a
native session, making it the natural dispatch target. Then the unchanged resume workflow: hard
QC → F2→F3R cut QC (IN ±12) → assembly → sequence QC → SEQ_CONTEXT_LOCK → V2-011W.
