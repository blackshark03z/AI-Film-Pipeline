# FLOW-PRODUCTION-TOOLS-LONGRUN-001 — Final Evidence Record

**Status:** COMPLETED_CANDIDATE (with one live OWNER_AMBIGUITY_GATE — see Live mutation accounting)
**Worktree:** `D:\AI FILM MAKER\AI-Film-Pipeline`
**Branch:** `zcode/flow-production-tools-longrun-001`
**Base (package freeze):** `510cc892386c1b7a8b3f66ab7a6396e9522b8c90`
**Delivery:** the branch tip of `zcode/flow-production-tools-longrun-001` at
delivery time — the commit carrying this record (verify with `git log -1`).
The full checkpoint chain from base `510cc89` is in §2.
**SoT HEAD:** `e758f83` (ancestor, unchanged) · **Evidence HEAD:** `29018d3` (ancestor, unchanged)

---

## 1. Clock

| Item | Value (UTC) |
| :-- | :-- |
| Active start | ~2026-10-02T05:55Z |
| Active end | ~2026-10-02T08:10Z |
| Active wall time | ~2h15m of the 6h ceiling |
| Termination reason | All bounded acceptance criteria genuinely exhausted (see §9); remaining ceiling intentionally not spent on speculative work |

## 2. Checkpoint timeline

| Checkpoint | Commit (UTC) | Result |
| :-- | :-- | :-- |
| `C0_BASELINE_PROVEN` | b7073e5 (07:08Z) | base ancestry verified; tracked worktree clean; 497 tests pass; hygiene findings recorded |
| `C1_ROUTE_REVIEWED` | b7073e5 (07:08Z) | independent forensic audit vs SoT; all required classifications pass; 0 live Generates spent |
| `C2_FLOW_NATIVE_ROUTE_PRODUCTIZED` | ff1a3f8 (07:25Z) | render lifecycle states added to the productized seam; 507 tests |
| — (structural guard) | 96889db (07:26Z) | direct MZZa6b path excluded from the seam by test |
| `C3_FLOW_TOOLS_SURFACE_MAPPED` | 08967a8 (07:38Z) | public-doc + read-only authenticated UI mapping; qualified board re-check |
| `C4_FLOW_TOOL_CANARY` (partial) | 25e4f5b (08:02Z) | create/save 1/1 consumed and proven; optional Generate NOT run — OWNER_AMBIGUITY_GATE |
| `C5_ARCH_DECISION` | this record | FLOW_TOOL_ASSISTIVE_ONLY (§7) |
| `C6_ADVERSARIAL_REVIEW_COMPLETE` | 45c004d (08:07Z) | restart/tamper hardening, manifest regenerated 30/30, 511 tests |

Supporting records: `FLOW_PRODUCTION_TOOLS_LONGRUN_001_C0_C1_AUDIT.md`,
`FLOW_PRODUCTION_TOOLS_LONGRUN_001_FLOW_TOOLS_MAPPING.md`.

## 3. Stable native-UI route — implementation delta

The productized seam already present at base (reused, not duplicated):
`FlowR2VBoundary` (attestation gate → durable single dispatch with immutable
intent binding → native-UI request guard/qualification → backend attribution →
exact media binding), `FlowR2VShotRuntime` (freeze/resume, reserve, guarded
release observation, attribution, acquisition, QC eligibility),
`OneGenerateGuard`, hash-chained dispatch journal, atomic
`save_frozen_path_and_job`.

**This package's delta** (`ff1a3f8`, `96889db`):

1. `FlowReferenceRpcSession.media_payload()` — null-safe read-only as29s
   payload observation (no download).
2. `FlowR2VShotRuntime.observe_render_state()` — one read-only render-state
   reconciliation over an exact-type qualified session; catalog/media reads
   bind to concrete class implementations (no wrapper/shadow substitution).
3. Structural regression guard: the productized seam cannot reference
   `submit_once`/`MZZa6b`/`RPC_VIDEO`/`build_video` — the direct private
   mutation path stays outside the production route by test.

## 4. State-machine delta (admission / render / acquisition)

Dispatch journal (same immutable hash chain, DB-tamper-proof via SQLite
trigger) gains three additive fact kinds:

```text
RENDER_PENDING_OBSERVED    {output_id, basis='as29s_null_media_row_present'}
RENDER_COMPLETED_OBSERVED  {output_id, basis='as29s_media_resolved'}
ADMITTED_RENDER_DROPPED    {output_id, basis='as29s_null_media_row_absent'}
```

Post-binding recovery classifications (SoT 13 lifecycle; DR-014):

```text
bound + drop fact                  → ADMITTED_RENDER_DROPPED / REPAIR_DECISION_REQUIRED
bound + render completed           → RENDER_COMPLETED / ACQUIRE_ONLY
bound + render pending             → RENDER_PENDING / RECONCILE_ONLY
bound + no render facts yet        → OUTPUT_BOUND / ACQUIRE_ONLY   (unchanged)
```

Invariants proven by focused offline tests (`tests/test_flow_render_lifecycle.py`, 14 tests):

- an `as29s` miss while the owned row is present is **pending evidence, never
  failure and never retry authority** (`may_submit` is False in every render state);
- a null payload with the owned row absent from a **qualified** fresh catalog
  read is a terminal drop routed to an Owner RepairDecision — never to redispatch;
- any unqualified read (RPC drift, non-conforming non-null payload, catalog
  baseline drift) is `RENDER_UNOBSERVABLE` + durable `OBSERVATION_FAILURE` —
  it never invents a drop or a completion;
- re-observation is idempotent (identical facts dedupe; transitions append);
- a recorded drop stays terminal in recovery even if a later observation
  claims completion (flapping catalog is drift, not redispatch authority);
- fresh-process restarts (new runtime instance over the same store) preserve
  the classification and can never re-enter the mutation path;
- the dispatch journal rejects in-place UPDATE/DELETE at the database level.

## 5. Test results

| Suite | Result |
| :-- | :-- |
| Baseline regression (base `510cc89`) | 497 passed (88.7s) |
| After Phase 2 (render lifecycle) | 507 passed |
| Final full regression (delivery) | **511 passed** (105.7s), 0 failed |
| Focused render lifecycle | 14 passed |
| `git diff --check` | clean |
| Syntax/compile validation | all edited modules parsed clean |

## 6. Flow Tools capability matrix

Full matrix with evidence classes in
`FLOW_PRODUCTION_TOOLS_LONGRUN_001_FLOW_TOOLS_MAPPING.md`. Summary
(classifications: PUBLICLY_DOCUMENTED / OBSERVED_IN_UI / PROVEN_BY_CODE /
INFERRED / UNKNOWN):

| # | Question | Final classification |
| :-- | :-- | :-- |
| 1 | User-creatable custom Tool | PUBLICLY_DOCUMENTED + OBSERVED_IN_UI + **PROVEN (canary create)** |
| 2 | Code/runtime | **PROVEN_BY_CODE**: agent-generated, user-editable single-file React TSX mini-app inside Flow's tool host (Preview/Code toggle; builder agent sidebar) |
| 3 | Native video generation | **PROVEN_BY_CODE** (`Flow.generate.video`); live execution unproven (gated) |
| 4 | Model/mode/duration/aspect/count | **PROVEN_BY_CODE** at the call level: `modelDisplayName` (display-name string, e.g. 'Omni 1.1 Flash'), `aspectRatio`, `durationSeconds`, `resolution`; no reference slot in the generated call |
| 5 | Consume project media/references | UNKNOWN |
| 6 | Batch variations | INFERRED: sequential single calls; no native batch parameter observed |
| 7 | Auto-persist outputs to project | UNKNOWN (no persistence call in tool code; host-side behavior unverifiable without a live run) |
| 8 | Stable job/media identifiers | **NO at tool level (PROVEN_BY_CODE)**: result is `{base64, mimeType}` only |
| 9 | SDK surface | **PROVEN_BY_CODE that an internal `flow-sdk` module exists**; NOT publicly documented; supported-API status UNKNOWN |
| 10 | Structured ShotSpec/PromptPlan pass-in | No structured channel observed — free-text prompt only |
| 11 | Zzl0ze/as29s reconciliation | UNKNOWN (requires a live Tool-run generation with a marker; gated — not run) |
| 12 | Gaps vs native UI | §7 |

Public-doc vs UI-observed vs proven distinctions: the blog documents
describe-to-build + duplicate/remix and deep-linkable tool URLs (public-doc);
the Tools gallery/tabs/Create affordance and the qualified-board re-check are
UI-observed; the React TSX runtime and the `flow-sdk` call surface are
proven-by-code readback. Third-party secondary sources (MindStudio, EduTech)
provided only INFERRED-level claims (e.g. model pickers, "no conditional
logic") and were not treated as truth.

## 7. Architectural decision (C5): FLOW_TOOL_ASSISTIVE_ONLY

Flow Tools is **not** a production generation path for V1. Reasons, all
evidence-backed:

1. **No stable identity at the tool level**: the proven SDK result carries raw
   bytes with no provider job id / media id. AI-Film's ownership contract
   (marker echo + fresh baseline delta + unique media binding, SoT
   invariants 6/7/14, DR-011) cannot be satisfied from what the tool receives.
2. **No reference/ingredients slot** in the proven call: the qualified
   continuity mechanism (R2V with immutable reference attestation) is not
   reachable through the generated call shape.
3. **Live generation semantics unproven**: whether a Tool-run generation is
   catalog-reconcilable (marker echo through Zzl0ze) remains UNKNOWN — the
   one authorized Generate was not used (gate, §9).
4. **Internal SDK, not an API**: `flow-sdk` is first-party inside the tool
   runtime but undocumented and unsupported as a contract; per the frozen
   package, generated code invoking an internal function is not an API.

The proven native-UI route remains the primary generation transport,
unchanged. If a future slice proves Tool-run reconciliation, the smallest
replaceable seam would be a `flow_tool` transport behind the existing
`ProviderTransport` protocol — no Film Core change; nothing of the kind was
added now.

## 8. Custom Tool artifact (created)

- Name: **"Director's Shot Lab"** (agent-generated title)
- Provider identity: `083a64f8-6f43-4a48-bd1b-3f1cc81e6b12`
  (`/project/<qualified-project>/tool/083a64f8-…`), private, in My tools of
  the qualified project; NOT published/shared, NOT deleted (deletion would be
  a further mutation under the active gate).
- Behavior: Production-Mode UI (16:9 / 08.00 SEC / SHOT ID counter), free-text
  shot prompt, "Render Shot" → `Flow.generate.video(...)` → in-page playback
  of returned bytes.
- The artifact remains as canary evidence for the Owner.

## 9. Live mutation accounting & Owner gates

Budgets (frozen package authority; never retry authority):

```text
MAX_CUSTOM_TOOL_CREATE_OR_SAVE = 1 → consumed 1/1 (one tool created+saved once)
MAX_FRESH_VIDEO_GENERATE       = 1 → consumed 0/1 (NOT used)
```

Full provider-mutation ledger of this package:

1. Tool create/save: one description submit, one "Xong" save click. Result:
   exactly one private tool, unique ID, verified read-only post-gate.
2. No other provider mutation of any kind (no upload, no video generate, no
   publish/share, no deletes).

**OWNER_AMBIGUITY_GATE** recorded at `2026-10-02T07:54:22Z`: after the single
save click, My-tools verification could not uniquely resolve a saved-tool
link at that moment (the creation card carries no href). Per the frozen
Owner rule: all further provider mutation stopped immediately; the optional
Generate budget was NOT reinterpreted as retry authority and remains unused.

Post-gate read-only verification (no mutation) resolved the external effect:
exactly one tool with unique identity; no duplicates. The gate still stands
for the remainder of the task. One earlier runner-infrastructure failure
(missing `native_ui=True` for profile sessions) was transparently
reclassified in the canary journal — no provider access of any kind had
occurred before it, and budgets were untouched.

No OWNER_AUTH_GATE, no payment gate encountered (session stayed valid; PRO
tier active; builder explicitly stated tool creation costs no credits; the
tool editor does warn that *running* a tool can consume credits).

## 10. Security / evidence hygiene

- No cookie values, auth headers, session/CAPTCHA tokens or signed CDN URLs
  committed. `api_keys/` runtime state remains gitignored/untracked.
- Cookie names/paths and one expired signed-URL presence in HISTORICAL
  evidence were recorded as findings, not rewritten (C0 audit).
- Wire observation in the canary recorded only lengths/rpcids/structural
  booleans — no request bodies persisted; tool Code dump contains no secrets.
- Account PII (email) scrubbed from all committed docs; raw screenshots and
  journals stay untracked under `scratch/`.
- SoT manifest was stale (25/30 entries mismatched under every EOL/BOM
  normalization). Regenerated over **committed git-blob bytes** (machine
  independent) with a verifier tool (`tools/verify_sot_manifest.py`);
  30/30 verified; **no SoT truth content was modified** (diff vs base touches
  no SoT decision text).

## 11. Unresolved unknowns

1. Whether a Tool-run generation echoes a Film correlation marker in durable
   catalog state (requires one live Tool generate under a fresh authorization).
2. Whether Flow's tool host auto-persists generated media into the project
   catalog, and with what identity.
3. The full `flow-sdk` surface (reference/ingredients support, project-media
   queries, batch/count parameters).
4. Whether `flow-sdk`/tool runtime drifts independently of the main Flow
   frontend build (new re-qualification dimension).
5. Frontend bundle revision changed vs the qualified build string while the
   qualified DOM contract read back identical — treated as a watch item; the
   qualified route was not re-qualified by mutation in this package (no live
   Generate was spent on it either).

## 12. Next recommended slice

**FLOW-TOOL-RUN-RECONCILIATION-001** (one bounded live run, fresh authority):
with a fresh qualified baseline and a preclaimed marker, run the existing
canary tool once with the marker embedded in its prompt, then read-only
reconcile the catalog delta (Zzl0ze) for the marker echo and attempt as29s
resolution + exact acquisition. Outcomes: (a) marker echo + persistence →
define the `flow_tool` adapter seam; (b) no echo/persistence → Flow Tools
stays assistive-only and the finding is frozen. Secondary: re-qualify the
native-UI route after the observed bundle revision drift with one bounded
canary before the next production dispatch.
