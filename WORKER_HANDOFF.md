# Worker Handoff — AI Film Pipeline Bootstrap

You are the BUILD worker for `SLICE-0001`.

## Read first

In this exact order:

1. `AI-Film-Pipeline/docs/sot/development/AI_NATIVE_DEV_MODEL_SOT_v1_FROZEN.md`
2. `AI-Film-Pipeline/docs/sot/film/00_SOT_INDEX.md`
3. `AI-Film-Pipeline/docs/operating/PROJECT_OPERATING_PROFILE.md`
4. `AI-Film-Pipeline/docs/operating/CURRENT_SLICE.md`
5. `AI-Film-Pipeline/docs/operating/IMPLEMENTATION_STATUS.md`

Then inspect the rest of the Film SoT and schemas as needed.

## Mission

Initialize the project repository and persist the complete SoT baseline to GitHub.

Do not start Film Core feature implementation.

## Execution semantics

- Own HOW inside the slice.
- Search/reuse before building.
- Progress through internal gates automatically.
- Do not ask the Owner for routine engineering decisions.
- Stop only when a listed stop condition or authority boundary is reached.
- Never alter acceptance to make the candidate pass.
- Preserve uncertainty as INCONCLUSIVE when remote state cannot be established.
- Accept only the exact revision you verified.

## GitHub default

If no repository already exists and your authorized GitHub account permits creation:
- create **private** repository `AI-Film-Pipeline`;
- use the normal default branch chosen by GitHub/tooling, preferably `main`;
- push only after local package/secret/schema checks pass.

If repo ownership or permissions are ambiguous, stop before external creation.

## Final report format

Return:

```text
RESULT: PROVEN | DISPROVEN | INCONCLUSIVE

REPOSITORY:
DEFAULT_BRANCH:
ACCEPTED_SHA:

GATES:
1 Package integrity: PASS/FAIL
2 Secret hygiene: PASS/FAIL
3 Schema proof: PASS/FAIL
4 Git baseline: PASS/FAIL
5 GitHub persistence/readback: PASS/FAIL
6 Status handoff: PASS/FAIL

CHANGES:
- ...

EVIDENCE:
- ...

OPEN ISSUES:
- ...

NEXT:
- SLICE-0002 may begin / must not begin
```
