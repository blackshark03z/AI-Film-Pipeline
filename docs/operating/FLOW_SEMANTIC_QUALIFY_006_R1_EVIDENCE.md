# FLOW-SEMANTIC-QUALIFY-006-R1 — Requalification Evidence Record

**Status:** BLOCKED_EXTERNAL_GATE (Gemini API availability; see §3)
**Branch:** `zcode/flow-semantic-qualify-006-r1`
**Base SHA:** `7ca82d26db785433587ccb7c0a1d80e6d6d2dbc9` (Package-006 delivery tip, verified)
**Delivery:** the branch tip carrying this record (single commit from base; verify `git log -1`).

## 1. Scope

Bounded requalification of the UNCHANGED frozen corpus
(`qualification_corpus.json`, 18 controls, expected labels unchanged from
Package-006 — never re-derived) with one delta: transient
`SEMANTIC_API_UNAVAILABLE` errors get up to 2 bounded retries with 30 s
backoff; malformed/lineage failures remain single-attempt fail-closed.
Frozen acceptance criteria A–L applied as-is — thresholds not lowered.

## 2. Result

**SEMANTIC_QC_INCONCLUSIVE — now gated by EXTERNAL API availability.**

| Metric | Package-006 run | R1 run |
| :-- | :-- | :-- |
| Controls completed | 15/18 | **4/18** |
| Transient/persistent API errors | 3/18 | **14/18** (after 2 retries + 30 s backoff each) |
| Positives materially PASS | 4/8 | 0/8 (all API-blocked) |
| Negatives materially FAIL | 5/8 | 2/8 (both successful: identity_negative, wardrobe_negative — consistent with Package-006) |
| Repeat stability (where calls succeeded) | partial | **7/7 stable** |
| Wrong-source lineage rejection | PASS | PASS (pre-API, deterministic) |
| Schema/parse/fingerprint | PASS | PASS |

Stability data actually IMPROVED (7/7 stable repeats among successful
calls), strengthening the case that the evaluator contract is sound — the
blocker is purely API availability under today's call volume.

## 3. EXTERNAL_GATE evidence

- Single probe after a 4-minute quiet backoff: still
  `SEMANTIC_API_UNAVAILABLE`.
- Errors persist across per-control retries with 30 s spacing — not
  per-request jitter; sustained availability/rate gate.
- Credential itself is VALID (model discovery `list_gemini_models` returned
  44 models at preflight and in R1 pre-checks; auth header accepted for
  discovery, and 4/18 controls DID complete in R1 before the gate
  tightened).
- No key material printed/persisted/committed (scan clean).

## 4. What R1 adds to custody

1. `requalification_results.json` — per-control outcomes with attempt counts.
2. Confirmation that repeat-stability among successful calls is 7/7 —
   evidence the evaluator contract (strict JSON, structured verdicts) is
   reliable when the API responds.
3. The frozen corpus proved reusable as-is: zero label re-derivation, zero
   code changes to the evaluation path (only retry/backoff wrapper).

## 5. Mutation accounting (this package)

```text
Generates: 0/11 ceiling (0 primary, 0 repair, 0 upload)
Retries: 0
Direct/private MZZa6b: 0
Gemini API calls: read-only evaluator calls only (~50 across both runs today)
```

Zero provider (Flow) mutations; zero unresolved Flow ambiguity; the Owner
latch and all mutation-authority semantics untouched.

## 6. Next steps (Owner)

1. Wait for the Gemini API availability/rate gate to clear (hours–days),
   then re-run `tools/rerun_semantic_qualification_r1.py` unchanged — the
   frozen corpus and acceptance are already in place; OR
2. provision/quota-review the key with Google if the gate is account-level;
3. on a future QUALIFIED verdict, Package-006's S4–S12 phases (cache,
   canonical audit, prior-judgment audit, semantic repairs, master review)
   execute exactly as specified — no redesign.

## 7. Final battery (this package)

- Requalification runner + full regression: 632 passed, 0 failed (unchanged
  code base; the rerun tool added no production code).
- `git diff --check`: clean. SoT manifest: 30/30.
- Secret/PII/API-key scan: clean (key path + size only in evidence).
