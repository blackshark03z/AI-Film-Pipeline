# Current Slice — Bootstrap Repository and Freeze Baseline

**Slice ID:** SLICE-0001  
**Status:** READY  
**Intent:** establish the exact repository baseline from which implementation begins.

## Outcome

Create the AI Film Pipeline repository, persist the complete frozen SoT package in Git, establish the minimal repository skeleton, and prove that the exact baseline is safely reproducible before feature implementation starts.

## In scope

1. Create or use a dedicated GitHub repository for this project.
2. Default repository name: `AI-Film-Pipeline`.
3. Default visibility: **private**, unless Owner explicitly authorizes public.
4. Commit:
   - Development SoT;
   - Film Pipeline SoT;
   - promoted schemas/fixtures/config examples;
   - Project Operating Profile;
   - Current Slice;
   - Implementation Status;
   - repository README / `.gitignore`;
   - minimal empty Python package/test/project directories.
5. Establish initial protected/frozen baseline revision.
6. Validate:
   - all expected SoT files exist;
   - no obvious secrets/cookies/API key values are committed;
   - JSON files parse;
   - ShotSpec fixtures validate against schema;
   - repository working tree is clean after commit.
7. Update `IMPLEMENTATION_STATUS.md` with the exact accepted Git commit SHA and GitHub repository identity.

## Out of scope

- implementing Film Core;
- real Gemini calls;
- live Flow/Veo generation;
- Dola/Elyum automation;
- provider cookies/sessions;
- web UI;
- database migrations beyond future scaffolding;
- Resolve integration;
- production deployment.

## Acceptance claims

A. A dedicated Git repository exists and contains the complete authoritative SoT set.

B. The Development SoT and Film SoT are clearly separated:
- development SoT governs HOW;
- film SoT governs WHAT/System Truth.

C. The repository has no committed credentials, cookies or live session files.

D. The promoted JSON schemas and fixtures are machine-readable.

E. All three canonical ShotSpec fixtures validate against `schemas/shot_spec.schema.json`.

F. The final accepted baseline is identified by an exact Git commit SHA.

G. `IMPLEMENTATION_STATUS.md` records:
- GitHub repo;
- default branch;
- accepted baseline SHA;
- proof summary;
- next authorized slice.

## Required evidence

- repository URL/identity;
- `git status --short` clean;
- `git rev-parse HEAD`;
- file inventory or deterministic manifest;
- schema-validation command output;
- secret-scan evidence sufficient for this bootstrap;
- GitHub remote readback showing the expected revision exists.

## Worker authority

Worker MAY:
- create local repository;
- arrange files into the frozen structure;
- create minimal package metadata if required;
- choose replaceable Python tooling for validation;
- create a private GitHub repository under the already-authorized account if no target repo exists;
- push the bootstrap baseline;
- perform non-destructive readback;
- fix packaging/path/formatting errors that do not alter frozen semantics;
- self-progress through all internal gates below.

Worker MUST NOT:
- make repository public without Owner authorization;
- alter frozen SoT semantics to simplify implementation;
- commit credentials or cookies;
- perform live paid generation;
- start feature implementation beyond bootstrap;
- rewrite acceptance to obtain PASS.

## Internal gates

### Gate 1 — Package integrity
All expected files exist and hashes/inventory are sensible.

### Gate 2 — Secret hygiene
No live key/cookie/session material is staged.

### Gate 3 — Schema proof
JSON parses; 3 ShotSpec fixtures validate.

### Gate 4 — Git baseline
Initial commit created; working tree clean.

### Gate 5 — GitHub persistence
Exact commit is visible on remote default branch.

### Gate 6 — Status handoff
`IMPLEMENTATION_STATUS.md` updated with exact baseline identity and next action.

## Stop conditions

Stop and report INCONCLUSIVE if:
- GitHub owner/repository target cannot be established safely;
- repository creation/push permission is unavailable;
- remote push result is ambiguous;
- exact remote revision cannot be read back;
- a secret is discovered in any frozen source;
- any change to frozen SoT semantics seems necessary.

## Completion

This slice is PROVEN only when the exact remote revision has been read back and matches the accepted local baseline.
