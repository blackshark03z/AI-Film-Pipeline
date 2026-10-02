# FLOW-PRODUCTION-TOOLS-LONGRUN-001 — Flow Tools Surface Mapping (C3)

Method: public documentation research + authenticated read-only UI observation
in the qualified clean Pro profile (`2026-10-02T07:30–07:36Z`). **Zero provider
mutation in Phase 3**: no Create/Save/Generate/Remix/Run was clicked. Local
(untracked) screenshots + sanitized DOM inventories in
`scratch/flow_tools_discovery/`. Account emails scrubbed; no cookies or tokens
captured.

## Observed surface (OBSERVED_IN_UI unless noted)

- Entry: Flow home is now a project-list view with a "Tools from creators like
  you" section and an **Explore Tools** button; Tools gallery lives at
  `/project/<project_id>/tools?tab=COMMUNITY` — the Tools surface is
  **project-scoped** (INFERRED: tool outputs are meant to live with project
  media).
- Gallery tabs: **Công cụ của tôi** (My tools) / **Cộng đồng** (Community) /
  **Mẫu** (Templates). Sidebar: All media / Images / Video / Characters /
  Scenes / Uploads / **Tools** / **Tạo công cụ (Create tool)** / Trash.
- Community gallery: featured "Master Your Soundscape" (Mondo Sónico — Ricardo
  Villavicencio, Sebastián Carvallo), "SwissFlow Studio" (Hashem Al-Ghaili,
  "Turn your scripts into clean, professional Swiss…"), sections: Featured
  creators / Images / Video / Experiments (Thử nghiệm). ~45 tool cards
  observed.
- Templates tab headline: "Tạo mọi công cụ mà bạn có thể tưởng tượng ra." +
  "Bạn chỉ cần có ý tưởng và nội dung mô tả để tạo công cụ mình cần." with a
  Tạo công cụ (Create tool) CTA and Google-authored templates: Simple Sketch,
  Scene Explorer, Mockup, Image Editor (image class).
- **My tools tab is empty** for this account ("Tác phẩm sáng tạo của tôi" with
  only a "Tạo mới" CTA) — a clean pre-canary state; a created tool would be
  this account's first.
- Re-qualification scope check (read-only): the qualified generation board is
  unchanged at the DOM-contract level — `button.settings-trigger-button`
  tokens read back exactly `Video · 720p · 8 giây crop_16_9 x1` (matches
  `NativeUiProfile.settings_tokens`), `button.generate-icon-button`,
  `div.ProseMirror[contenteditable]` and `button.add-menu-trigger` all
  present. Frontend bundle revision observed:
  `boq-labs-ai-sandbox.AiSandboxAngularFrontend.vi.pV88nTU3z_Q.2018.O`
  (differs from the qualified build string `boq_labs-ai-sandbox-frontend_20260929.10_p1`;
  the qualified selectors/settings contract still read back identical, so the
  drift is currently judged non-material for the qualified route — noted as a
  re-qualification watch item, not a violation).

## Capability matrix (12 frozen questions)

| # | Question | Classification | Evidence |
| :-- | :-- | :-- | :-- |
| 1 | Can a user create a custom Tool inside Flow? | **PUBLICLY_DOCUMENTED + OBSERVED_IN_UI** | Blog: "build custom workflows simply by describing what you need"; UI: Tạo công cụ link + empty My-tools tab |
| 2 | What code/runtime is generated or editable? | **UNKNOWN** (builder not yet entered; entering = Phase 4 create budget) | Public docs claim no-code natural-language build; no code editor documented anywhere |
| 3 | Can a Tool trigger image/video generation natively? | **PUBLICLY_DOCUMENTED** (image templates; community Video tools); live generation **UNKNOWN until canary** | Blog tools by creatives; Templates/Image + Video sections |
| 4 | Model/mode/duration/aspect/output-count controls? | **UNKNOWN** | Third-party doc (MindStudio) claims model + params selection (Veo 2/Imagen 3 era, unverified); not yet observed |
| 5 | Can a Tool consume project media/reference identities? | **UNKNOWN** | Tool-scoped URL is project-scoped; INFERRED likely, unproven |
| 6 | Batch/multiple variations? | **UNKNOWN** | MindStudio: linear workflows, no conditional logic (unverified) |
| 7 | Outputs auto-persist to current project? | **UNKNOWN** | Project-scoped tools URL suggests yes (INFERRED), unproven |
| 8 | Stable job/media/result identifiers? | **UNKNOWN** | Shared tool URLs contain opaque UUIDs (public blog); no job/media id documentation |
| 9 | Supported SDK/function surface? | **NO public SDK** (PUBLICLY_DOCUMENTED) | "No code. No API keys." (MindStudio); blog documents no API; generated code invoking internal functions would still not be an API |
| 10 | Structured ShotSpec/PromptPlan pass-in without copy/paste? | **UNKNOWN** (likely no: free-text input variables per public docs) | MindStudio documents `{scene_description}`-style free-text variables |
| 11 | Reconciliation via the Zzl0ze/as29s identity path? | **UNKNOWN** | Depends on whether a Tool-run generation echoes a Film correlation marker in durable catalog state (canary question) |
| 12 | Gaps vs native Flow UI generation? | Deferred to Phase 5 | — |

## Guardrails applied

- No tool card was opened beyond the gallery; no "Try"/Run/Remix/Create was
  clicked; no text was typed into any Flow input.
- No cookies exported; no network/token capture; evidence stays untracked.

Phase 4 pre-conditions assessment: creation affordance clearly available
(OBSERVED_IN_UI), account is clean Pro, session valid, no payment/legal/
recovery gate observed → **Phase 4 canary authorized** with budget
`MAX_CUSTOM_TOOL_CREATE_OR_SAVE = 1`, optional `MAX_FRESH_VIDEO_GENERATE = 1`.

## C4 — Minimal Tool canary result (2026-10-02T07:45–08:00Z)

Budgets (package authority, consumed exactly once, never retried):

```text
MAX_CUSTOM_TOOL_CREATE_OR_SAVE = 1  → consumed (1/1)
MAX_FRESH_VIDEO_GENERATE       = 1  → NOT USED (OWNER_AMBIGUITY_GATE active)
```

Sequence:

1. Qualified read-only baseline captured pre-mutation (9 catalog records,
   fingerprint qualified).
2. Builder opened at `/project/<id>/create-tool` (chat agent; on-page notice:
   "Hiện không tốn tín dụng khi tạo công cụ" — creating tools currently costs
   no credits). Tool description submitted once ("AI Film Shot Tool …").
3. The builder agent generated and persisted a tool object and assigned a
   provider identity: URL `/project/<id>/tool/083a64f8-6f43-4a48-bd1b-3f1cc81e6b12?mode=EDIT`.
4. ONE save ("Xong") clicked once → `create_or_save_used = 1`.
5. My-tools verification at that moment could not uniquely resolve a saved
   tool link (card carries no href) → **OWNER_AMBIGUITY_GATE recorded**;
   all further provider mutation stopped immediately (generate not released).
6. READ-ONLY post-gate verification resolved the external effect: exactly one
   tool exists, named **"Director's Shot Lab"**, ID
   `083a64f8-6f43-4a48-bd1b-3f1cc81e6b12`, in My tools of the qualified
   project; UI shows Production Mode with ASPECT 16:9 / LENGTH 08.00 SEC /
   SHOT ID #001 and a "READY FOR INPUT" canvas. No duplicates. The gate
   stands: the remaining optional Generate was not reinterpreted as retry
   authority.

### Tool code/runtime — PROVEN_BY_CODE (read-only Code view dump)

The saved tool's "Mã" (Code) tab exposes its full generated source:
a single-file **React TypeScript** mini-app (`App.tsx`) whose generation call is:

```javascript
import { Flow } from 'flow-sdk';
const result = await Flow.generate.video({
    prompt: prompt,
    modelDisplayName: 'Omni 1.1 Flash',
    aspectRatio: '16:9',
    durationSeconds: 8,
    resolution: '720p'
});
// result: { base64: <string>, mimeType: <string> }
```

Facts established by the code (all `PROVEN_BY_CODE` unless noted):

- Tools are agent-generated, **user-editable React TSX mini-apps** running
  inside Flow's tool host (Preview/Code toggle; builder agent sidebar with
  undo/restore; editor disclaimer: running the tool can consume credits).
- A first-party **`flow-sdk` module exists inside the tool runtime** exposing
  at least `Flow.generate.video` with prompt / modelDisplayName /
  aspectRatio / durationSeconds / resolution parameters.
- The SDK result used by this tool is **raw bytes (`base64`, `mimeType`) with
  NO provider job id, NO media id, NO project-persistence call and NO
  reference/ingredients parameter** — the generated tool plays the bytes as a
  blob URL. Persistence to project media, if any, is host-side and invisible
  to the tool code (UNKNOWN).
- The model is selected by display name string (`'Omni 1.1 Flash'`), not by
  the qualified wire model identifier.

### Updated capability matrix (remaining rows)

| # | Question | Classification after C4 |
| :-- | :-- | :-- |
| 2 | Code/runtime | **PROVEN_BY_CODE**: React TSX mini-app, agent-generated, editable; no external code export |
| 3 | Native image/video generation | **PROVEN_BY_CODE** (`Flow.generate.video`); live execution unproven (gated) |
| 4 | Model/mode/duration/aspect/count | **PROVEN_BY_CODE** at call level: modelDisplayName/aspectRatio/durationSeconds/resolution accepted; no reference slot in this generated call |
| 5 | Consume project media/references | **UNKNOWN** (not exposed by this generated tool; SDK surface may have more) |
| 6 | Batch variations | **INFERRED**: client-side sequential single calls only; no native batch parameter observed |
| 7 | Auto-persist to project | **UNKNOWN** (no persistence call in tool code; host behavior unverifiable without a live run) |
| 8 | Stable job/media identifiers | **NO at tool level (PROVEN_BY_CODE)**: result carries bytes only, no ids |
| 9 | SDK surface | **PROVEN_BY_CODE that an internal `flow-sdk` exists**; it is NOT publicly documented and its status as a supported API is UNKNOWN — generated code invoking an internal function is not an API contract |
| 10 | Structured ShotSpec pass-in | **NO structured channel observed**: free-text prompt only; structured data would be serialized into text |
| 11 | Zzl0ze/as29s reconciliation | **UNKNOWN** (requires a live Tool-run generation with a marker in the prompt; gated — not run) |

### Canary hygiene

- Zero cookie/token capture; wire observation recorded lengths/rpcids only;
  no request bodies persisted. All raw evidence untracked under
  `scratch/flow_tool_canary/`.
- The created tool (Director's Shot Lab, private) remains in the project as
  the canary artifact; it was NOT deleted (deletion would be a further
  mutation under an active gate) and NOT published/shared.
