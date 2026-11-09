# Owner policy — standing delegation

This file is the Owner's standing authorisation. Every session reads it before asking the Owner anything.
Anything this file permits needs no further question to the Owner. Only the Owner may widen it.
The Tech Lead may tighten it or record what was done under it.

**Source:** the Owner (khoikk03) wrote the following in chat on 2026-11-09:
- "Thoải mái đi, đừng hỏi quyền. Tuy nhiên cấu hình tạo video thử nghiệm cứ dùng 360p, omni flash cho tiết kiệm nhé"
- "Tự quyết định kỹ thuật, đừng hỏi mình, tiếp tục"
- "Mặc định: approve mọi quyền"
- "Bạn tự duyệt. Nếu cần cố vấn thì hỏi chatgpt. Đừng dừng để hỏi mình"
- When asked to put this into a policy file, the Owner answered: "Được"
- Later on 2026-11-09, after supplying the Vilao key: "Với các thử nghiệm, mặc định minimax h3 480p"

## Delegated to the agent (Tech Lead)

1. **Approvals.**
   - Approve stills and storyboards. Accept or reject takes.
   - Sign as `agent:tech-lead (delegated by owner-khoikk03, OWNER_POLICY.md)`. Never sign as `human:owner-*`.
   - The evidence field holds concrete review notes:
     - identity and look;
     - REL_ADDRESS, REL_LISTENER, REL_GAZE, REL_BARRIER;
     - continuity against the adjacent accepted cut.
   - Review frames as a contact sheet. Reject a take that fails any required check.
2. **Live sends.**
   - **Experiments** (probes, A/B tests, new-route tests) default to **MiniMax H3 480P via Vilao** (`omh3/h3-480p`),
     through the provider adapter once it exists. Tech Lead cap: 50k VND per day of experiments unless the Owner raises it.
   - Film takes on the Flow route stay at **360p, Omni 1.2 Flash**. A film already in production keeps its route
     to the end (film05 = P17-01 stability run stays on Flow).
   - Set `OWNER_GO_LIVE: YES` in `LOOP_BACKLOG.md` for one send at a time, with a trap that returns it to `NO` in the same shell command.
3. **Caps.**
   - Generability attempts per shot version: GREEN 1, AMBER 2, RED 0. Restage instead of retrying.
   - Total credit cap per film: 256.8.
   - A send that Flow rejects with no output (`FLOW_FAILED`) does not count toward the attempt cap. Its credits count only if the ledger shows a charge.
   - After 3 provider failures on one shot, restage or simplify the prompt and record why.
4. **Advice.** For a judgment call, consult ChatGPT in a new tab on the same GPM profile. Treat it as advice; the agent decides.
5. **Technical decisions.**
   - The agent decides design, restaging, coverage and fixes.
   - The Owner decides only product meaning: story changes, a new film, publishing.

## Still reserved to the Owner (stop and ask)

- Publishing, uploading anywhere public, or sharing outside this machine (sending frames/references to an authorised generation provider — Flow, Vilao H3 — is part of a send, not sharing).
- `git push`.
- Purchases, new accounts, and plan or credit top-ups.
- Raising a credit or VND cap, or any resolution or model other than 360p Omni Flash (Flow) and H3 480P (Vilao, experiments).
- Changing the story's meaning: cutting a scene, changing an ending, or adding characters.
- Starting a new film.

## Stop conditions for unattended runs

Stop and report when any of these happens:
- the film is assembled;
- remaining budget is below 20 credits;
- a reserved item above is needed;
- the same defect has repeated three times after pipeline fixes.

## Unchanged safety rules

- Never print the GPM profile list.
- Never read cookies.
- No curl; use Python.
- Never commit `uv.lock`.
- Codex reviews run read-only.
- Never use `--approve-storyboard`.
