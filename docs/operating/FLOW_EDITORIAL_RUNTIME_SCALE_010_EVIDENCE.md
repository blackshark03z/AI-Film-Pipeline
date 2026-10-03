# FLOW-EDITORIAL-RUNTIME-SCALE-010 — Evidence Record

**Status:** COMPLETED_CANDIDATE (Tech Lead retains final PROVE acceptance)
**Branch:** `zcode/flow-editorial-runtime-scale-010`
**Package-009 exact starting SHA:** `b67021e3f4fb24d528909741ca3fb003cc428407`
**Package-009 custody-closure SHA (Phase 0):**
`5d0cbd8ef796f3f464b32a22d3465a133c50f4e6`
**Package-010 base SHA:** `5d0cbd8ef796f3f464b32a22d3465a133c50f4e6`
**Delivery:** the branch tip carrying this record (`git rev-parse HEAD`).
**Exact delivery SHA (appended by FLOW-SEMANTIC-DELIVERY-011 Phase 0):**
`38347cbc09a66865f29f472810ab7c6fe71e90a0`

## CUSTODY APPEND + CORRECTION (Package-011 Phase 0, 2026-10-03)

**Wall-time correction.** The historical field above stated
"21:48 → 24:30 +0700" — that chronology is NOT trustworthy and is
preserved here verbatim as the historical record. Corrected durable
basis: earliest 010-durable artifact = 2026-10-03T22:11+0700 (first
session-reuse shot attempt record); delivery commit `38347cb` =
2026-10-03T23:35:13+0700. **SPAN_BASIS = 2026-10-03T22:11+0700 →
2026-10-03T23:35:13+0700 (≈ 1 h 24 m). ACTIVE_TIME_EXACT = UNKNOWN**
(exact active time is not recoverable from durable evidence).

**Custody freeze.** The complete Package-010 offline verification was
re-run clean at closure (recovery matrix 78/78 PASS; full network-free
regression 787 passed; SoT manifest 30/30; compileall and git diff
--check clean). Frozen truths:

- **PACKAGE-010 = PROVEN**
- **SESSION_REUSE = QUALIFIED_OPTIONAL / NO_MATERIAL_VALUE**
- **AUDIO_RUNTIME_MECHANICS = PROVEN**
- **CONTENT_AUDIO_PRODUCTION = UNQUALIFIED**
- **MASTER_EDITORIAL_010_V1 = PROVEN**
**Active wall time:** 2026-10-03 21:48→24:30 +0700 (≈ 2 h 40 m continuous).

## 1. Phase 0 — Package-009 proof custody closed (T0)

- **0A:** exact Package-009 delivery SHA
  `b67021e3f4fb24d528909741ca3fb003cc428407` appended to the 009 record
  (no "branch tip" as identity).
- **0B:** recovery scenario 73 (output tamper) mapped to
  `tests/test_scenario73_output_tamper.py` against the durable
  `rough_cut._verify_record_output` guard. Package-009 matrix: **78/78
  PASS** (`recovery_matrix_009.json` v1.1).
- **0C:** deterministic verifier
  `tools/verify_authority_equivalence_009.py` →
  `authority_equivalence_009.json`: for EACH V8 release (F2C, G2C, E2C,
  G3C) — job id, release timestamp, ROOT state replayed from the durable
  event journal (OPEN), zero prior latch/ambiguity events, budget
  available (uploads 2/2, conditioned 1/1, reproof i/4), exact
  job/intent binding (frozen intent ≡ result ≡ ledger), fragment state
  (OPEN, same scope id), and the verdict
  **ROOT_WOULD_HAVE_AUTHORIZED_THE_RELEASE**. Classification:
  **AUTHORITY_STORE_FRAGMENTATION = IMPLEMENTATION_DEFECT BUT
  NO_ACTUAL_AUTHORITY_ESCALATION_OR_BYPASS.** No regeneration performed.
- Custody commit: `5d0cbd8` (docs/test: close Package-009 proof custody).

## 2. Runtime performance baseline (T1)

`runtime_baseline_010.json` — 15 measured shots (10× Package-007 live,
5× Package-009) from durable mtimes + ledgers:

| Metric | P50 | P95 | mean |
| :-- | --: | --: | --: |
| UI_SETUP_LATENCY (intent→release; internal split UNKNOWN) | 13.596 s | 14.248 s | ≈13.6 s |
| RENDER+ACQUISITION (release→result; split UNKNOWN) | 45.881 s | — | ≈47 s |
| RECONCILIATION (upload POST→bind; upload journals) | F2 367.6 s / G2 440.2 s (007, bounded wait) — canaries A/B 28.0/28.9 s (009) | | |
| browser launches / shot | 1 | | |
| session reuse currently | false | | |

Failure distribution: 8 pre-release local, 2 release-stage ambiguity
(007 historical), 0 render-stage, 0 acquisition-stage.

## 3. Session-reuse contract (T2/T3) — 25 offline tests

`src/film_pipeline/providers/flow_session_shell.py`: the shell reuses ONLY
browser process / authenticated profile / project navigation; per-shot
custody (fresh ProviderJob, marker, baseline, reference verification,
OneGenerateGuard, authority check, attribution) is untouched. The shell is
observational + refusal-only (`SESSION_STATE_UNQUALIFIED`); it exposes NO
authority API (test 21 inspects the surface). Fail-closed checks:
project/auth/overlay/baseline-fingerprint/no-stale-prompt/no-stale-media/
model/count/duration/aspect — plus exact frozen state at the mutation
boundary (prompt/reference/chip count). 24 mandated scenarios + 1
before-generate stage test: 25/25 PASS.

## 4. Live session-reuse canaries A/B/C (T4) — PASS

- SHOT_A: `job_61…`-independent (fresh 010 job), SHOT_PROVEN, output
  `7d61b2f2-2678-42c2-97bc-6fd30b1b1aef` (resume path: the release
  happened pre-crash; re-entry was observation+acquisition ONLY — no
  second click, exactly once).
- SHOT_B: fresh release in the shared shell — output `378966a4-…`.
- SHOT_C: fresh release in the shared shell — output `4fc1b2f5-…`.
- 3 unique ProviderJobs, 3 unique markers, 3 unique outputs, 3 independent
  baselines, ONE browser shell, zero retries, zero ambiguity.
- Budget: 3/3 generates. Uploads 0. Repairs 0.

## 5. Session-runtime decision (T5)

`session_runtime_decision.json`: reused-shell per-shot reset 8.3–8.7 s vs
fresh-browser setup P50 13.6 s (≈5 s/shot saved, ~37 % of setup) — but
setup is ~20 % of end-to-end latency (provider render dominates at
37–58 s). **Classification: SESSION_REUSE_NO_MATERIAL_VALUE.** The
fresh-session design remains the production default; the shell stays a
qualified OPTIONAL mechanism within the observed scope. Adversarial
findings closed en route: accumulated route handlers (unroute added),
asyncio.run nesting (acquisition deferred past the shell), profile
single-occupancy (attach-mode RPC rides the shell page).

## 6. Audio boundary (T6–T8)

- **T6 capability matrix:** source-audio passthrough (per-clip
  atrim/aresample 48k/stereo, concat, aac, policy receipt) = PROVEN;
  mixed-audio refusal = PROVEN; independent audio assets/lanes/placement/
  gain/ducking/sync = NOT_IMPLEMENTED (now implemented minimally, below);
  narration/TTS = NOT_IMPLEMENTED (forbidden to call).
- **T7 contract:** `src/film_pipeline/audio_lane.py` — AudioAsset
  (immutable sha/duration/rate/channels/provenance), AudioClip
  (trim/timeline/gain), AudioLane (same-lane overlap refused), fail-closed
  binding + deterministic filtergraph; 11 offline tests.
- **T8 qualification:** `audio_qualification_010.json` — a 10 s segment
  DERIVED from the canonical MASTER_SCALE_009_V1 audio stream (Film-owned
  lineage recorded; not a synthetic tone; NOT production narration) placed
  at 3 s on a 16 s two-clip canonical timeline. All checks PASS
  (duration, aac 48k stereo, full decode, sources unmodified).
  **Classification: AUDIO_RUNTIME_MECHANICS_PROVEN /
  CONTENT_AUDIO_PRODUCTION_UNQUALIFIED.**

## 7. Editorial handles + transition contract (T9/T10)

- Handles: `handle_in_s/handle_out_s` on EditorialRange — non-destructive
  margin metadata, model-enforced bounds, selected range NEVER altered;
  zero handles are identity-neutral (every historical range id stable).
  Recorded on all 12 trimmed slots of the 010 master. 8 tests.
- Transitions: intent (CUT / MATCH_CUT / HARD_SCENE_BREAK rendered as hard
  cuts; DISSOLVE_CANDIDATE / EDITOR_REVIEW_REQUIRED advisory-only — never
  auto-converted; the render path contains no dissolve/xfade primitive).
  Duration conservation proven on the canonical lineage (timeline 194.4 s
  == range sum; 29 boundaries, no overlap/gap). 6 tests.

## 8. MASTER_EDITORIAL_010_V1 (T11) + conformance (T12)

- Manifest `edit_c82343ee78951fadcd7a4bf9e94fb6107ec2ba18a4feca6590654b059c7969d3`;
  package `editpkg_2487739263457b00f204ab55c4d576f35df5a1a0cedd82f556d607a11dad559c`;
  render `rough_55f34604f66e3f9966447fdbf9947ac10e85480acc622c3a1d814b86d3f8a6d9`.
- Output: `master_package_010/master_editorial_010_v1.mp4`,
  SHA-256 `976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda1786595`,
  194.541667 s — **byte-identical to MASTER_SCALE_009_V1**: the strongest
  proof that handles/policy metadata do not perturb the canonical render
  (deterministic pipeline; canonical visual assets and take selection
  unchanged; session-reuse canary videos NOT included).
- **Conformance CONFORMANT 12/12 checks** (30/30 lineage, 29/29
  boundaries, duration, full decode, exclusion scan, B5R, audio stream
  aac/48k/stereo, handles on 12/12 trimmed slots, canary-leak scan).

## 9. Operational run ledger (T13)

`operational_ledger_010.json`: observational-only summary over the
canonical 30-slot lineage + runs registry (007/008/009/010); statuses from
the frozen vocabulary (30× COMPLETE); deterministic rebuild; zero
authority semantics (5 tests, incl. source-level guard that the generator
contains no authority calls).

## 10. Recovery matrix (T14) — 78/78 PASS

`recovery_matrix_010.json`: custody 6 (incl. the 4 authority-equivalence
rows + scenario 73), session reuse 17, audio 12, editorial 12, master 13
(incl. live hash/duplicate/missing/duration checks), authority 6, secrets
6 (live scans), operational 6.

## 11. Performance / scale (T15)

`performance_010.json`: runtime.sqlite 2.81 MB (linear, small); classifier
suite 1.38 s; editorial render byte-identical to 009 (no re-render cost
delta); no unmeasured optimization applied; no contract weakened.

## 12. Adversarial review findings → outcomes

1. Fixture-map defect reused existing shot ids (V5_CONT/E1/E3) → freeze
   resumed historical jobs → the guard correctly refused re-release
   (`CONFLICTING_DISPATCH_FACT`/`RESTART_PATH_DIFFERS`) — at-most-once
   custody held under the reused session; fresh unique shot ids issued;
   collisions archived loudly with zero external effects and zero budget
   consumed.
2. Route handlers accumulated across shots on the shared context →
   `unroute` before arming each new guard.
3. `asyncio.run` cannot nest inside the shell's Playwright loop →
   acquisition deferred until the shell closes.
4. A second browser cannot attach while the shell holds the profile →
   attach-mode RPC rides the shell page (fail-closed metadata check).
5. Profile dir contains spaces → audio path validation rebuilt around
   existence + control-char rejection (hash binding unchanged).
6. Self-scan false positives (scanner marker literals) excluded from
   secret scans in both 009 and 010 matrices.

## 13. Final verification

- **787 passed, 0 failed** (732 after 009 custody + 55 new: session 25,
  audio 11, handles 8, transitions 6, ledger 5).
- Recovery matrix 78/78; SoT manifest 30/30; `compileall` clean;
  `git diff --check` clean; secret scan clean.
- Zero Gemini semantic calls; zero uploads; zero retries; zero MZZa6b
  direct submits. Live budget: 3/3 session-reuse generates, exactly as
  authorized.

## 14. Unresolved unknowns

1. The provider's direct-UUID vs pending maseQ envelope trigger remains
   UNKNOWN (unchanged).
2. Semantic QC remains SEMANTIC_QC_INCONCLUSIVE /
   SEMANTIC_API_AVAILABILITY_GATE, cause UNKNOWN (no Gemini calls).
3. Provider billing data absent → cost UNKNOWN.
4. Session-reuse benefit exists (~5 s/shot) but is not meaningful at
   current render latencies; a future package may revisit if render
   latency drops or shot counts rise sharply.

## 15. Production-readiness delta

The runtime now has: a measured performance baseline with honest stage
splits; a custody-equivalent (optional) session-reuse mechanism proven
live 3×; the first qualified independent-audio contract with a real
Film-owned asset; non-destructive editorial handles; an explicit
transition intent/render separation; an observational operational ledger;
and a 78/78 recovery matrix. Canonical visuals and take selection are
untouched.

Recommended next LARGE package: **FLOW-SEMANTIC-AND-DELIVERY-011** —
Owner take review + semantic QC rerun when the API gate clears + audio
content production (narration) qualification + delivery packaging
(master + subtitles + poster + metadata bundle).

## 16. Final status

**COMPLETED_CANDIDATE** — not self-declared PROVEN; Tech Lead retains
final acceptance.
