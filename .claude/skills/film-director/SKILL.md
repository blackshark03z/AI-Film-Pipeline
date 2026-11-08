---
name: film-director
description: Author or review a drama film package (films/<id>/) stage by stage — story bible, direction, pre-production, shots — with the gate checks and lessons from film01–03. Use when creating a new film, adding scenes, or debugging why a gate blocks or a take failed.
---

# Film director

Follow [docs/director/DIRECTOR_PLAYBOOK.md](../../../docs/director/DIRECTOR_PLAYBOOK.md). Read only the section for the stage you are on.

## When to use

- Creating a film package (`python tools/film.py new <id> --profile drama`) or adding/changing scenes.
- A gate (`python tools/film.py validate --film films/<id>`) is BLOCK or NOT_RUN and you need to know what decision is missing.
- A shot or take went wrong and you must find which stage should have caught it.

## Order

`01_story.json` (Gate 1) → `02_direction.json` (Gate 2) → `03_preprod.json` + `04_shots.json` → `tools/film.py plan`.
Section numbers: story §2, direction §3, pre-production §4, shots §5, writing shots §6, lessons §7, red flags §11.

## Non-negotiables

- Never mark a gate PASS by hand; `NOT_RUN` is not a pass.
- A defect is fixed in the stage that should have caught it (model, validator, test), then in the film.
- Each shot is 3-15 s and as long as its action, not a fixed 8 s pair; a restaged scene may add insert shots (motion library, stop on a visible object, `film.py motion`); locked looks are never re-described in prompts; no beat may depend on an uncontrolled fall/tear/spill across a cut.
- RED beats (`film.py generability`) are restaged before stills; a RED shot blocks the plan unless it carries a `generability_waiver`.
- Generate is paused (`OWNER_GO_LIVE: NO`): plan and validate only; no credits, uploads, purchases or publishing without the Owner.
- Report technical PASS, product proof and Owner acceptance separately.
