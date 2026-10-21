# S3 — XIANXIA60 DOLA 3-SHOT COMBAT SCENE REPORT: PREFLIGHT AUDIT & STOP

**Author:** Gemini Flash 3.8 (Tech Lead Execution Mode)  
**Date:** 2026-10-21  
**Governing WP:** [`docs/operating/TASK_S3_XIANXIA60_DOLA_3SHOT_COMBAT_SCENE.md`](file:///D:/AI%20FILM%20MAKER/AI-Film-Pipeline/docs/operating/TASK_S3_XIANXIA60_DOLA_3SHOT_COMBAT_SCENE.md) (SHA-256: `31b5f60b44d3e79e3ddcde6190619688a07c884822cae241289f8ac99d035e9c`)  
**POLICY_REF:** `45f71d6226c5ffc58b4e70f3bcea1bb0151b7003`  
**Primary Repo / HEAD:** `mission/quality-v2-022-120s@1f408f94a0cee24e3160316e8ca60cb1f244a948`  
**Worker Worktree / HEAD:** `feature/film120-gemini-realshot-001@f218012e60cd0f18f0e38664487ef1a0f6d97b8a`  
**OneClick Worktree / HEAD:** `feature/dola-session-oneclick-001@958337ec799e2616a1d7fea767b41c5aedeaf3b7`  

---

## 1. Goal & Product Delta

- **Goal:** Execute one bounded, Owner-authorized 3-shot consecutive combat scene (X04-DOLA-A Attack $\rightarrow$ X04-DOLA-B Contact $\rightarrow$ X04-DOLA-C Reaction) using the existing approved browser-native Dola OneClick runtime, verifying each output via provider creation ID, exact MP4 bytes, SHA-256, and full decode.
- **Product Delta:** **STOPPED AT PREFLIGHT GATE (Zero mutations / Zero credit burn)**. Physical asset ledger and existing 12+3 footage remain 100% intact. No unauthorized cookie-HTTP replay, no blind retry, no simulated generation.

---

## 2. OneClick Dola Runtime Audit & Account Truth

Per WP Section "Dola provider runtime and finite authorization", generation is authorized **ONLY** upon an authenticated, eligible, non-deferred account with **verified live balance/quota** (`SESSION_VALID ≠ PROVIDER GENERATE READY`).

A read-only audit of all 11 registered OneClick accounts was performed using `python tools/dola_oneclick_sessions.py status` and targeted live CDP sync:

| Alias | Source | Session State | Bound Identity | Credit Evidence | Observed / Source Timestamp | Action / Eligibility Status |
|---|---|---|---|---|---|---|
| `ACCOUNT_A` | managed | `SESSION_VALID` | `bound:443fc2ee` | **UNKNOWN (`null`)** | Obs: `2026-10-21T12:33:03Z`<br>Src: `2026-10-20T07:59:00Z` | **NOT READY** — Stale source statement (2 credits recorded yesterday); no fresh same-day provider statement for today (2026-10-21 JST). |
| `ACCOUNT_B` | managed | `EXPIRED` | unbound | **UNKNOWN** | — | **INELIGIBLE** — No sessionid cookie. |
| `ACCOUNT_C` | managed | `EXPIRED` | unbound | **UNKNOWN** | — | **INELIGIBLE** — No sessionid cookie. |
| `ACCOUNT_D` | managed | `SESSION_VALID` | `observed:fc25eed` | **UNKNOWN** | Obs: `2026-10-18T04:43:13Z` | **INELIGIBLE** — Identity not bound (`enroll` required). |
| `ACCOUNT_E` | managed | `SESSION_VALID` | `bound:8b2b5523` | **UNKNOWN (`null`)** | Obs: `2026-10-21T12:37:02Z`<br>Src: `2026-10-16T08:26:04Z` | **NOT READY** — Stale source statement (from 5 days ago). |
| `ACCOUNT_F` | managed | `SESSION_VALID` | `bound:4fa268e5` | **UNKNOWN (`null`)** | Obs: `2026-10-21T12:37:16Z`<br>Src: `2026-10-16T08:27:26Z` | **NOT READY** — Stale source statement (from 5 days ago). |
| `GPM_..._63C2627E0C3` | gpm | `SESSION_VALID` | `bound:6e777a51` | **UNKNOWN (`null`)** | Obs: `2026-10-21T12:37:44Z`<br>Src: `null` | **NOT READY** — No credit statements found in conversation history. |
| `GPM_..._80079A4C479` | gpm | `SESSION_VALID` | `bound:a9ab53aa` | **UNKNOWN (`null`)** | Obs: `2026-10-18T10:30:30Z` | **NOT READY** — No credit statements found in conversation history. |
| `GPM_..._8480AB14EF7` | gpm | `SESSION_VALID` | `bound:cf45a31b` | **UNKNOWN (`null`)** | Obs: `2026-10-18T10:31:07Z` | **NOT READY** — No credit statements found in conversation history. |
| `GPM_..._AF3515CC626` | gpm | `OWNER_DEFERRED` | unbound | **UNKNOWN** | — | **STOP / PROTECTED** — Owner deferred profile (proxy); browser untouched per policy. |
| `GPM_..._E0148C6093B` | gpm | `SESSION_VALID` | `bound:1b9a98ec` | **UNKNOWN (`null`)** | Obs: `2026-10-18T10:31:21Z` | **NOT READY** — No credit statements found in conversation history. |

### Production Bridge Preflight Readback
Running `python tools/dola_production_bridge_cli.py accounts`:
- Every non-deferred account is categorized as `operator: NEEDS_OWNER`.
- `may_mutate_provider = False` enforced across all 11 accounts.
- Zero accounts are currently in `READY` status.

---

## 3. Main Blocker & Governance Invariant

1. **Credit Correctness Hardening (A3 Rule):**  
   Under frozen OneClick delivery [`DOLA_ONECLICK_MULTIACCOUNT_CLEAN_DELIVERY.md`](file:///D:/AI%20FILM%20MAKER/AI-Film-Pipeline-OneClick/docs/operating/DOLA_ONECLICK_MULTIACCOUNT_CLEAN_DELIVERY.md), provider credit evidence is strictly fail-closed:
   $$\text{credit\_is\_fresh}(t_{\text{source}}, t_{\text{observed}}) = \text{True} \iff \text{date}_{\text{JST}}(t_{\text{source}}) == \text{date}_{\text{JST}}(t_{\text{observed}})$$
   A prior-day message or unproven daily reset is **never** accepted as today's live entitlement.
2. **Quota Sufficiency:**  
   The trial requires 3 video generations. Even if yesterday's statement on `ACCOUNT_A` (`残りは2動画クレジット`) were hypothetically active, 2 credits $< 3$ required outputs.
3. **Mandatory STOP Boundary:**  
   The governing WP explicitly mandates:
   > *"Nếu runtime OneClick chưa có phiên/quota hợp lệ, báo đúng blocker thay vì dùng phiên không được phép."*  
   > *"If no qualified existing session exists, return ONE precise `OWNER_ACTION_REQUIRED: DOLA_SESSION_CAPTURE_OR_ENTITLEMENT` and STOP; do not ask Owner to research via screenshot."*

---

## 4. Decision & Owner Action Required

**VERDICT:**  
`OWNER_ACTION_REQUIRED: DOLA_SESSION_CAPTURE_OR_ENTITLEMENT`

### Concrete Smallest Owner Action Sequence (Choose ONE):

#### Option A: One-Click Extension Capture (Ordinary Chrome)
1. Open your regular Chrome profile already logged into `dola.com`.
2. Ensure the unpacked extension `chrome_extension/` is enabled, or run `Install Dola Native Host.cmd`.
3. Open a tab on `https://www.dola.com/chat`.
4. Click the Dola extension icon and click **"Capture this session"**.
5. Run `Sync Dola Sessions.cmd` to register fresh same-day entitlement.

#### Option B: Refresh Entitlement on Existing Managed Profile (`ACCOUNT_A`)
1. Open the existing persistent profile for `ACCOUNT_A` in Dola:
   ```cmd
   cd /d "D:\AI FILM MAKER\AI-Film-Pipeline-OneClick"
   python tools\dola_oneclick_sessions.py login --alias ACCOUNT_A
   ```
2. In the opened browser window on `dola.com/chat`, confirm whether today's daily free allowance (or subscription credits) is active.
3. Once active, close the browser window. The session will immediately reflect fresh same-day credit on `sync`, unblocking dispatch of Shots A, B, and C.
