# Codex independent review (gpt-6.1-sol, read-only) — 2026-11-07

Scope: `git diff 65c4470..HEAD` at fee98a7 + working tree (P10-01..P10-04). Raw output; findings are **unverified until a P11 item confirms them**. Tests were not run by the reviewer.

Found 12 defects at `fee98a7` plus the working-tree changes, ranked by severity.

1. **BLOCK — Acceptance can approve an archive built under an outdated disclosure policy.** [gate_checks.py:194](<D:/AI FILM MAKER/AFP-stable/src/film_pipeline/production/gate_checks.py:194>)  
   **Scenario:** Deliver with `ai_label="title_card"`, then change it to `"always"` → archive verification still checks the old archive against itself; acceptance does not require rebuilding under the current policy.  
   **Fix:** Compare the current disclosure policy with the archived policy before accepting.

2. **BLOCK — The portrait’s claimed watermark is not checked.** [deliver.py:282](<D:/AI FILM MAKER/AFP-stable/src/film_pipeline/production/deliver.py:282>)  
   **Scenario:** Supply a labelled landscape master and an unlabelled portrait version → only the landscape receives the pixel check, but both receive `watermark_always_on=True`.  
   **Fix:** Verify the visible label separately on every delivered version using its actual geometry.

3. **BLOCK — Negative control contrast can manufacture positive label evidence.** [deliver.py:156](<D:/AI FILM MAKER/AFP-stable/src/film_pipeline/production/deliver.py:156>)  
   **Scenario:** The expected label region has zero glyph contrast, while the control region has −30 → subtraction produces +30 and counts the frame as labelled, despite no label at the expected location.  
   **Fix:** Require positive evidence at the target independently of the control comparison.

4. **BLOCK — A partly missing watermark satisfies “always”.** [deliver.py:157](<D:/AI FILM MAKER/AFP-stable/src/film_pipeline/production/deliver.py:157>)  
   **Scenario:** The label is absent at two of five sampled times → three positives still pass, and disclosure claims it remains on throughout the body.  
   **Fix:** Check coverage throughout the body and reject missing-label intervals.

5. **BLOCK — Gate 4 accepts assets from an obsolete prompt.** [gate_checks.py:136](<D:/AI FILM MAKER/AFP-stable/src/film_pipeline/production/gate_checks.py:136>)  
   **Scenario:** Accept a take, then change its scripted dialogue without changing `ShotDecl.version` → Gate 4 still passes because it never compares the recorded prompt hash with the current prompt.  
   **Fix:** Bind acceptance to current generation inputs and invalidate it when those inputs change.

6. **BLOCK — Missing accepted clips pass Gate 4.** [gate_checks.py:159](<D:/AI FILM MAKER/AFP-stable/src/film_pipeline/production/gate_checks.py:159>)  
   **Scenario:** Remove an accepted clip while retaining its log and review → `is_file()` is false, so verification is skipped and the gate passes. The new success test also writes clips outside `media/takes`, inadvertently exercising this bypass.  
   **Fix:** Require the clip at its resolved media location before checking its hash.

7. **BLOCK — The normal dailies workflow breaks the new review reader.** [gate_checks.py:115](<D:/AI FILM MAKER/AFP-stable/src/film_pipeline/production/gate_checks.py:115>)  
   **Scenario:** Run `dailies`, then ingest its completed sheet → `review_file` remains pointed at the wrapped dailies document; `_review()` validates that wrapper as a bare `TakeQc` and raises instead of evaluating Gate 4. The new tests ingest directly and miss this path.  
   **Fix:** Resolve the canonical ingested QC record, or correctly unwrap and validate the referenced sheet.

8. **BLOCK — Header changes do not stale the plan.** [gate_checks.py:24](<D:/AI FILM MAKER/AFP-stable/src/film_pipeline/production/gate_checks.py:24>)  
   **Scenario:** Generate an approved plan, then change `film.json` language or generation duration → Gate 3 retains the old PASS although recompilation would produce different prompts or timing.  
   **Fix:** Include the planning-relevant header fields in `planned_from`.

9. **BLOCK — Storyboard approval survives changed or deleted images.** [gate_checks.py:85](<D:/AI FILM MAKER/AFP-stable/src/film_pipeline/production/gate_checks.py:85>)  
   **Scenario:** Approve the storyboard, then replace or delete a storyboard PNG → Gate 3 reads cached issue lists without rechecking the approved image hashes and still passes.  
   **Fix:** Revalidate storyboard files and approval hashes during gate evaluation.

10. **WARN — Registered stills can enter Git accidentally.** [stills.py:134](<D:/AI FILM MAKER/AFP-stable/src/film_pipeline/production/stills.py:134>)  
    **Scenario:** Register a still in `films/<film>/media/stills/`, then run `git add -A` → the image and retained history are eligible for staging because the repository’s ignore rules do not cover that directory.  
    **Fix:** Ignore generated film media, including still history.

11. **WARN — Corrupt images can become approved start frames.** [stills.py:113](<D:/AI FILM MAKER/AFP-stable/src/film_pipeline/production/stills.py:113>)  
    **Scenario:** Supply a file containing only a PNG signature followed by garbage → registration accepts it, approval succeeds, and generation treats it as an approved image.  
    **Fix:** Decode and verify the complete image before registering it.

12. **WARN — The prompt-staleness test never changes a prompt input.** [test_production_stills.py:117](<D:/AI FILM MAKER/AFP-stable/tests/test_production_stills.py:117>)  
    **Scenario:** Prompt recomputation stops reflecting package changes → this test remains green because it changes the stored expected hash to zeros rather than changing the current prompt’s inputs.  
    **Fix:** Change a location or character description and assert that the existing approval becomes stale.

Not run: tests, renders, or provider checks; local tool access failed midway through review.  
Nothing changed. Runtime reproduction remains unverified.