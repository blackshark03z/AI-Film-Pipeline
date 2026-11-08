I agree with the direction, but require five changes before treating this as the execution plan. Reviewed `AFP-stable`, branch `feature/drama-preprod-p0`, HEAD `c910564c209b7e5df78bc5454c6bf9f5e2764b0c`. No files changed.

**Blocking objections and exact required edits**

1. **P16-01 must reconcile intent receipts as well as the take log.**  
   The 10 takes total 85 credits, correctly. However, [generate.py:159](/D:/AI%20FILM%20MAKER/AFP-stable/src/film_pipeline/production/generate.py:159) also reserves credits from sent receipts whose IDs are absent from the log. Current files make that calculation **170 spent/reserved, 86.8 remaining**. Several receipt IDs differ from their registered take IDs. This does not prove 170 credits were actually charged.

   **Edit:** Replace the reconciliation done-criterion with: “Reconcile take entries, intent receipts and attributable provider outcomes; map receipt IDs to registered takes, distinguish confirmed pre-send failures from unresolved effects, and verify the generator’s remaining-budget calculation without double counting.” Label 171.8 **cap minus logged credits, before reconciliation**, not an available spending allowance. Also update §8’s denominator: there are currently **19 sent receipts**, including 10 non-PASSED outcomes.

2. **P16-07 expands before the promised exchange proof.**  
   Principle 7 says prove `SC01_g2 → SC02_g1 → SC02_g2` first. P16-07 instead requires restaging SC01–SC06, a timed animatic and Owner approval before the first corrected send. P16-10 then starts expansion with SC02_g2, although that shot belongs to the initial proof. This risks substantial rework and repeated Owner review.

   **Edit:** Split P16-07 into **pilot exchange** and **remaining encounter rollout**. Require only the pilot’s staging, board, stills and necessary continuity decisions before P16-09. Complete and review SC02_g2 plus both adjacent cuts before expanding to SC03–SC06.

3. **The stage map compiles still prompts after approving their resulting stills.**  
   Stage 8 contains still creation/review; stage 9 creates their prompts. The repository already emits both prompt families together in [plan.py:368](/D:/AI%20FILM%20MAKER/AFP-stable/src/film_pipeline/production/plan.py:368).

   **Edit:** Move shared-source prompt compilation and contradiction checks before still generation. After Owner approval, bind the exact approved images and prompt/input hashes into the generation manifest. Any material recompilation must invalidate the affected approval.

4. **P16-06’s done-criterion does not prove the proposed spending caps.**  
   Current [generability.py:69](/D:/AI%20FILM%20MAKER/AFP-stable/src/film_pipeline/drama/generability.py:69) assigns draft counts; its gate permits a RED shot through a free-text waiver. “UNKNOWN rated; SETUP/HOLD scanned; exception records” could pass while sends still exceed allowances.

   **Edit:** Add acceptance cases proving RED cannot generate through an accepted-take-reuse record; expired or mismatched exceptions refuse; UNKNOWN stops after its authorized exploratory send; AMBER’s second send follows review; and version bumps retain attempt/defect history. Verify these through the generation entry point with an offline runner, including unchanged Owner and budget gates.

5. **P16-04 proves question display, not completed relational review.**  
   [takes.py:199](/D:/AI%20FILM%20MAKER/AFP-stable/src/film_pipeline/production/takes.py:199) emits questions separately from QC checks; ingestion consumes `qc`, not the questions. Existing dailies are also deliberately preserved. Adding questions alone cannot establish that listener identity, gaze or barrier sides were assessed.

   **Edit:** Require each applicable relation question to have explicit human evidence in the relevant required QC group before acceptance; unanswered relations remain UNASSESSED. Specify supplemental review for affected existing takes without overwriting historical sheets. The done-criterion must cover both new templates and that supplemental review.

**Non-blocking improvements, ranked**

1. **Qualify the reference diagnosis in §8.** `reference_sets=[]` and `TEXT_ONLY` are arguments to preflight, not proof that character references were unused during still creation. Write: “Video preflight does not validate character-reference attachments; actual still/video reference use requires attachment evidence.”

2. **Make the “false OFF_FRAME” fixture structurally specific.** Test a missing establishing shot, unresolved mark, contradictory foreground or absent composition evidence. Actual pixel visibility remains Owner review, consistent with the deferred projection detector.

The principal repository diagnoses hold: visibility filtering drops hidden participants, explicit camera size does not currently drive the coverage-derived prompt size, and `_handoff()` skips cross-scene positions. I endorse the proposed projection and generability principles now; I could not verify historical attribution without the original round transcripts.

No tests or media playback performed. MAR access was denied by the approval policy; this is a source-based plan review, not BUILD or go-live approval.

Required edits: blocking items 1–5 above.

VERDICT: AGREE WITH CHANGES

