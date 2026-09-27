# SLICE-0004 authorization continuation

Resume authorized by Owner from `a3cae9bfc510e2d61ba1b3536ff346091f605ee1` on the existing branch. Prior auth-stop evidence remains intact. Dispatch budget before resume: 0. No new slice or new generation authorization is created.

Order: implement runtime using fake transports; prove restart/no-retry safety; authenticated preflight; freeze request and snapshot; at most one submit; reconcile; exact correlation; valid media/hash; fresh lineage readback; regression and freeze.

Reuse source remains AutoVideoPipeline@826e01866af1b28ed29b6fbb51cabb71f31ef561, especially `_fill_and_submit`, `generate_single_video`, `_wait_and_download`, and session preflight.

Adapted: prompt fill and single generate action; read-only project navigation; bounded polling; technical media inspection and SHA-256.

Rejected: first/newest gallery card selection, filename coincidence, partial-prompt matching and automatic retry. The adapter requires explicit stable asset identifiers and exact prompt ownership. An unverified provider surface stops before dispatch.

Runtime safety: SQLite reserves the one-submit budget before calling the transport. A reserved job is never resubmitted after any crash, timeout or restart. Reservation uncertainty is preserved as INCONCLUSIVE and reconciled read-only.

The browser transport retains download URLs only in memory; no cookies, token-bearing URLs or browser storage are persisted in source or evidence. ProviderJob binds the project through a safe identity hash in execution evidence.

## Resume result

INCONCLUSIVE — OPERATOR_AUTH_GATE. Gates 2–3 are implemented and covered by fake/recovery/media tests. Full deterministic suite: 40 passed. Authenticated FlowVeoProvider.preflight was rerun only after those tests passed and returned AUTH_REQUIRED / PROJECT_READBACK_AUTH_REQUIRED. No live runtime DB, live ProviderJob or dispatch was created. Generation submit transactions remain 0.

Each actual submitted request carries a persisted execution-unique job marker in addition to the frozen PromptPlan text; the plan hash and exact submission-prompt hash remain linked. Owned cards must echo the exact marked prompt. Unrelated same-creative-prompt outputs cannot qualify. Stable asset identity attributes and marker echo are not yet qualified against authenticated Flow; absence or ambiguity blocks dispatch/correlation.

The browser transport independently rejects a nonreserved/submitted job and consumes an in-memory invocation guard before any click. The durable executor remains the sole authorized dispatch path. Recovery uses the fixed ignored projects/flow_canary/runtime.sqlite path.

Operator action remains normal login and updating the existing configured session/cookie binding. Browser authentication performed elsewhere has not established readiness for these existing files. Do not paste credentials into chat. Original one-submit authorization remains unused; no new slice is created.

## New project binding continuation (2026-09-27)

Owner authorized exactly one project creation using the currently authenticated candidate cookie. Starting candidate: 4f5d21a519c74c6dea34229122aac46930aaadd5. Existing active cookie, candidate cookie and session files were present. The Owner reported PROJECT_ACCESS_DENIED for the old binding; it was not retried. No live runtime database or ProviderJob existed; generation dispatch count was 0.

Reused local AutoVideoPipeline@99b2a33e55db84f216ebc9706682d84c74c3b871 create_flow_project, preflight_flow_session and activate_flow_candidate. A creation invocation receipt was reserved before calling the existing helper; exactly one helper invocation returned CREATED. New project ID: 51ea107f-20b9-4222-a133-b4ccbfb1963b. Project URL: https://flow.google.com/project/51ea107f-20b9-4222-a133-b4ccbfb1963b. This operational binding identity is recorded under explicit Owner request.

Candidate preflight: CONNECTED, valid=true. Existing activation helper returned ok after its own CONNECTED check; active cookie was atomically promoted and session binding updated. Exact new binding was independently read back locally without exposing session contents.

AI-Film-Pipeline FlowVeoProvider.preflight returned INCONCLUSIVE / PROJECT_READBACK_INCONCLUSIVE. Its readiness check did not establish the required usable project surface. STOP before generation as explicitly required by the continuation. No further project creation or old-project retry was attempted. No live ProviderJob, generation submit, output or Asset exists. Generation dispatch count remains 0. Gates 5–10 are not reached. Full regression: 40 passed. This is INCONCLUSIVE, not live-canary proof. New project creation and binding succeeded; provider READY remains unproven. No frozen SoT or implementation source changed.
