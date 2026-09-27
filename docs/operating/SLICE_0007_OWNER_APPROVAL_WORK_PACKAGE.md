# SLICE-0007 — Human Approval → SelectedTake → Close Slice

## Worker model

```text
Model: GPT-5.6 Sol
Thinking effort: Medium
```

This is a bounded continuation of SLICE-0007.

Do not reopen QC architecture research.

Do not rerun generation.

Do not start SLICE-0008.

---

# 1. Owner decision

Owner explicitly reviewed the real take and returned:

```text
APPROVE
```

Treat this as the human-authoritative disposition for the real SLICE-0007 canary.

The previously persisted QC report is:

```text
qc_report_id:
qcr_fa1ef8247c17b733d2a010a7f090dc847404d3f9954b9163bbc521d4b8e9c86d
```

Current state before Owner approval:

```text
decision: needs_human_review
SelectedTake: NONE
RepairDecision: NONE
```

---

# 2. Accepted candidate

Continue from:

```text
ad7624a2da578c57a64d43316feabaf95cb0a71d
```

Do not rewrite prior QC evidence.

Do not erase the fact that the machine/VLM stage originally required human review.

---

# 3. Exact Asset

Use the already proven Asset:

```text
asset_sha256:
c5014f1438dd8b4e1fbcd85df85fc5216bf91985b2164d0afbe5c3a0695abacf
```

Source video:

```text
projects/flow_canary/outputs/95d299c70b8a5a37ec1e1fed.mp4
```

Use the exact GenerationAttempt / Asset IDs from persisted lineage.

Do not reconstruct IDs manually if they already exist in SQLite.

---

# 4. Human evidence

Persist a minimal human QC evidence record representing:

```text
authority: human
decision: approve
source: owner_explicit_review
```

Do not fabricate confidence scores.

Do not claim the human watched specific timestamps unless such evidence already exists.

Do not overwrite VLM evidence.

The human evidence should coexist with:

```text
deterministic evidence
temporal advisory evidence
Gemini advisory evidence
```

---

# 5. Final QCReport

Derive the finalized QC state using the existing QC policy.

Because:

```text
technical gate = pass
Owner explicitly APPROVED the subjective gates
no failure codes exist
```

final disposition should become:

```text
decision: pass
```

Preserve provenance showing that the prior report required human review before human authority resolved it.

Preferred approach:

```text
append/finalize through existing domain semantics
```

rather than silently mutating historical evidence.

If the implementation already defines immutable QCReport semantics, create the appropriate finalized successor/report version instead of mutating an immutable record.

Do not redesign the schema unless genuinely required.

---

# 6. SelectedTake

Create exactly one SelectedTake for this shot.

Required lineage:

```text
ShotSpec
→ GenerationAttempt
→ Asset
→ QCReport(pass)
→ SelectedTake
```

SelectedTake must point to the exact Asset.

Selection authority:

```text
human_with_vlm_assist
```

or the exact equivalent already implemented by SLICE-0007.

Do NOT record:

```text
ai
vlm
automatic
```

as final authority.

---

# 7. No RepairDecision

Because Owner approved:

```text
RepairDecision: NONE
```

Do not generate a repair.

Do not call Flow.

Do not call Seedance.

Do not generate new media.

---

# 8. Fresh readback proof

After persistence, close/reopen storage or use the existing fresh-readback mechanism.

Prove:

```text
QCReport final decision = pass
SelectedTake exists exactly once
SelectedTake points to correct shot
SelectedTake points to correct GenerationAttempt
SelectedTake points to exact Asset
SelectedTake points to finalized QCReport
selection authority is human-backed
Asset SHA-256 still matches
```

Also verify:

```text
no duplicate SelectedTake
no RepairDecision created
prior QC evidence still exists
```

---

# 9. Idempotency

Re-running the approval-finalization command/process must not create duplicate selections.

Prove deterministic/idempotent behavior.

Expected:

```text
same approval
+ same QCReport lineage
+ same Asset
→ same logical SelectedTake
```

not another take row.

---

# 10. Regression

Run full suite.

Existing baseline:

```text
123 tests PASS
```

Add focused tests for:

```text
human APPROVE resolves needs_human_review → pass
human authority persists
SelectedTake created exactly once
SelectedTake exact Asset linkage
fresh readback
idempotent re-application
APPROVE does not create RepairDecision
historical machine/VLM evidence is retained
```

No regression is acceptable.

---

# 11. Independent check

A lightweight independent review is sufficient.

Check:

```text
Owner APPROVE was not converted into AI authority
QC history was not erased
SelectedTake points to exact Asset
no duplicate selection
no repair created
no generation occurred
```

---

# 12. Slice closure

If all acceptance checks pass:

```text
SLICE-0007 = PROVEN AND CLOSED
```

Update operating status accordingly.

Do not modify frozen Film SoT.

Do not start the next slice.

---

# 13. Final report

Return:

```text
RESULT: PROVEN | INCONCLUSIVE | DISPROVEN
SLICE: SLICE-0007

OWNER_DECISION:
  decision: APPROVE
  authority: human

QC_REPORT:
  prior_id:
  final_id:
  final_decision:
  historical_evidence_preserved:
  fresh_readback:

SELECTED_TAKE:
  id:
  shot_id:
  generation_attempt_id:
  asset_id:
  asset_sha256:
  qc_report_id:
  selection_authority:
  fresh_readback:

REPAIR_DECISION:
  created: false

IDEMPOTENCY:
  duplicate_selected_take: false
  rerun_safe:

REGRESSION:
  tests:

INDEPENDENT_REVIEW:

GENERATION:
  flow_generate: 0
  seedance_generate: 0

CANDIDATE_SHA:
REMOTE_SHA:
WORKING_TREE:
SECRETS_COMMITTED:
SOT_FILES_CHANGED:

NEXT:
  SLICE-0007 CLOSED
  READY_FOR_SLICE-0008
```