# FLOW-PRODUCTION-TOOLS-LONGRUN-001 — C0 Baseline + C1 Independent Route Audit

Package: `FLOW_PRODUCTION_TOOLS_LONGRUN_001_WORK_PACKAGE.md` (frozen)
Worktree: `D:\AI FILM MAKER\AI-Film-Pipeline`, branch `zcode/flow-production-tools-longrun-001`

## C0 — BASELINE_PROVEN

| Item | Result |
| :-- | :-- |
| Work HEAD at start | `510cc892386c1b7a8b3f66ab7a6396e9522b8c90` (package freeze commit) |
| SoT HEAD `e758f83` | verified ancestor of work HEAD |
| Evidence HEAD `29018d3` | verified ancestor of work HEAD |
| Tracked worktree | clean at start (untracked carry-overs from previous branches only: `chrome_profile/`, `scratch/`, four 2026-10-01 report MDs, four investigation tools, `uv.lock`, `.zcodeignore`) |
| Full regression (project venv, Python 3.11.9) | **497 passed** in 88.69s |
| Chrome | v154.0.8037.92 present at `C:\Program Files\Google\Chrome\Application\chrome.exe` (build 154.0.8037.93 also staged by updater) |
| Qualified clean profile | `D:\AI FILM MAKER\Flow-Claude-Clean-Profile` present (~79 MB) |
| Forensics evidence dir | `D:\AI FILM MAKER\Flow-Claude-Forensics-Evidence` present, intact (R1/R2/R3 traces, both MP4s, review packets) |

### SoT manifest verification (honest result)

`docs/sot/film/MANIFEST.sha256.json` **does not verify** against the working tree at base:

- 5 of 30 entries match raw on-disk bytes: `06_PROVIDER_CAPABILITIES.md`, `08_ASSET_LINEAGE_COST.md`, `11_IMPLEMENTATION_PLAN.md`, `12_DECISION_LOG.md`, `schemas/shot_spec.schema.json`.
- 25 entries mismatch under every tested normalization (raw, BOM-stripped, CRLF→LF, blob/LF).
- The manifest is stale relative to committed SoT files (SoT files were revised across commits after the manifest was hashed; the manifest itself is a maintenance artifact inside `docs/sot/film/`, not a frozen decision). Recorded as a hygiene finding; **no SoT truth content was rewritten**. Manifest regeneration is scheduled at delivery (Phase 6) hashed over committed git-blob bytes so verification is machine-independent.

### Secret / evidence hygiene audit (tracked files only)

- No cookie values, auth headers, session tokens or raw CAPTCHA tokens committed. `api_keys/` (holding the local runtime cookie export) is gitignored and untracked.
- Cookie *names* and local file *paths* appear in `SLICE_0003_REUSE.md`, `providers/flow_veo.py`, `tools/wait_for_flow_login.py` — names/paths only, not values.
- `providers/flow_reference_rpc.py` embeds the reCAPTCHA Enterprise **site key** (a public identifier served in page HTML, not a token). No token capture/persistence exists in production code.
- `docs/operating/FLOW_MAX_CAUSAL_FORENSICS_001_EVIDENCE.md` (historical, committed evidence) contains one signed CDN URL for Release 1; the URL's `Expires` epoch is in the past, so it is dead transport data. Per package rule, historical evidence is preserved as-is, not rewritten; recorded here so the finding is durable.

## C1 — ROUTE_REVIEWED (independent audit of FLOW-MAX-CAUSAL-FORENSICS-001 vs SoT)

Independently verified from on-disk forensics artifacts + repo code (zero live Generate spent):

### Verified PROVEN

1. **Release 1 and Release 3 are distinct successful outputs.** Independent `sha256sum` of both MP4s in the evidence dir reproduces the recorded hashes exactly (`6a5baef0…` / `d0df85b4…`); independent ffprobe reproduces 8.000 s, 1280×720 H.264 MP4 for both; file sizes 506,348 / 1,583,486 bytes; distinct provider media identities (`11ae2a2f-…` / `5b22f89d-…`); distinct markers (`job_e19067cc70dd` / `job_af0e91f211c4`); distinct prompts (decoded f.req slot-0 prompt lengths 454 vs 344). SoT P1 holds.
2. **Current wire fingerprint.** Decoded R1/R3 `f.req` payloads show exactly one request with plain prompt AST in slot 0 (`[None,None,[[[prompt]]]]`), reference binding `[[None, 7b725f7b-…]]` in slot 1, wire model `veo_3_1_r2v_lite` in slot 2, request count 1 — matching SoT P5 and `validate_native_request` in `flow_canonical_ui.py`. SoT P5 holds.
3. **Marker-based backend attribution exists and fails closed.** `match_r2v_output_v2026_10_01` owns an output only via: marker echo (exactly one candidate row; >1 → `OUTPUT_MARKER_COLLISION`), fresh identity vs frozen pre-dispatch baseline (`OUTPUT_PREEXISTING_IDENTITY`), not-the-reference, video row shape, `CAE` status, qualified model, prompt-marker slot ownership, optional lineage slots must independently agree. SoT P2 and the "never marker alone" rule hold in code.
4. **Full decode evidence exists.** `ffmpeg -xerror` full-EOF decode verdicts and review packets (contact sheets, frame sets) are present on disk for both releases; the two review packet directories contain complete frame sets.
5. **Release 2 was admitted but not render-completed.** The evidence dir contains R2 wire request/response traces and a candidate id (`04edb651-…`) but **no R2 media file** and no durable catalog record — consistent with `ADMITTED_THEN_BACKEND_DROPPED`. SoT P3 and P4 hold.
6. **Direct/private MZZa6b mutation is outside the production seam.** The productized boundary (`flow_r2v_boundary` + `flow_r2v_runtime`) releases Generate exclusively through the browser-created request (`OneGenerateGuard` observes and validates the one `MZZa6b` POST; aborts uploads and duplicates). The runtime's only uses of `FlowReferenceRpcSession` are read-only catalog capture (`QualifiedFlowCatalogCapability.capture` → `catalog()`) and media reads. SoT P6 holds at the seam.

### Classifications of the forensics record (evidence doc claims vs SoT promotion)

| Forensics claim | Evidence-level | Promoted to SoT? | Audit verdict |
| :-- | :-- | :-- | :-- |
| reCAPTCHA Enterprise token present in successful native UI requests; direct RPC without token → HTTP 200 `[null]` | OBSERVED/PROVEN within that experiment | **Correctly NOT promoted as sole/root cause** (SoT 13 "do not freeze" list; 06 "security observations are not frozen causal claims"; DR-015) | PASS |
| Prompt deduplication caused Release 2 drop | claimed `[PROVEN]` in evidence doc from n=1 one-variable intervention | **Correctly downgraded** to hypothesis (06 "Prompt/render-drop non-claim") — one intervention cannot isolate dedup vs concurrency vs transient drop; SoT is authoritative | PASS with tension noted |
| `isTrusted` telemetry | OBSERVED | Correctly NOT promoted (`do not treat isTrusted as an architectural admission requirement`) | PASS |
| Clean-account scope | PROVEN for that scope only | Correctly scope-bound (13 "Qualified scope", DR-015, 06 "Scope boundary") | PASS |

### Finding (hardening input for Phase 2)

`FlowReferenceRpcSession.submit_once()` — a **direct private MZZa6b mutation** method — exists in tracked production code (`providers/flow_reference_rpc.py`) as historical slice capability with durable-journal callbacks. The productionized runtime never calls it, but nothing structurally prevents a future caller from passing a `FlowReferenceRpcSession` into a submit-shaped transport. Phase 2/6 must keep the native-UI route the only mutation authority and add a structural regression guard/test against direct-RPC redispatch through the productized lifecycle.

No live Generate was spent for this review (0 mutations).
