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
