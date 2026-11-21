# Owner policy — standing delegation

This file is the Owner's standing authorisation. Every session reads it before asking the Owner anything.
Anything this file permits needs no further question to the Owner. Only the Owner may widen it.
The Tech Lead may tighten it or record what was done under it.

**Sources.** The Owner (khoikk03) wrote in chat:
- 2026-11-09: "Thoải mái đi, đừng hỏi quyền", "Tự quyết định kỹ thuật, đừng hỏi mình, tiếp tục",
  "Mặc định: approve mọi quyền", "Bạn tự duyệt. Nếu cần cố vấn thì hỏi chatgpt. Đừng dừng để hỏi mình".
- 2026-11-20 (this revision): "Ưu tiên muse làm nhà tạo video ở thời điểm hiện tại, loại bỏ toàn bộ policy cũ cho
  mình. Khi muse hỏng/ hết qouta phải báo, mình sẽ nạp tài khoản mới vào. Với muse thì độ phân giải cứ để max ping,
  trần cao nhất cho mình, ưu tiên chất lượng và tốc độ. Lưu ý về muse việc kiểm soát tạo video sẽ khác so với flow,
  bạn phải đảm bảo để không làm hỏng những thứ mà dự án muse đã làm tốt với muse"
- 2026-11-20, on the Muse accounts: "Tài khoản được mình thêm thủ công vào muse studio (giao diện), chạy headless, có
  đủ cookie, nếu die, AI tự dùng thông tin đăng nhập/ chạy headless".

- 2026-11-21, on approvals: "Về contact sheet thì agent duyệt." On merging the rules of the two projects:
  "Hợp nhất ngay".
- 2026-11-21, in the Muse coordinator session, asked to confirm the unified rules now in `D:\Muse\CLAUDE.md`
  (this single policy, agent-approved contact sheets, local commits by explicit path, no push): "Xác nhận".
- 2026-11-21, on push and pace: "Hãy push khi phù hợp, không cần hỏi mình. và đẩy nhanh tiến độ hợp nhất/ hoàn
  thành dự án. Nếu cần nâng effort vì độ khó thì nhắn mình".

**Scope (2026-11-21).** This one file governs both projects, AFP (`D:\AI FILM MAKER\AFP-stable`) and Muse
(`D:\Muse`), as one studio (Film Studio). `D:\Muse\CLAUDE.md` defers to it. Where an older rule in either
project conflicts with this file, this file wins. An Owner instruction given in any session of either project is
valid in both: sessions record it here with the exact quote, and they do not ask the Owner to repeat it.

**What this revision removed (2026-11-20).** The old generation policy is withdrawn:
- the Flow route default (360p, Omni 1.2 Flash);
- the Vilao MiniMax H3 480P default for experiments, with its 50k VND/day cap;
- the per-film credit cap of 256.8;
- the attempt caps GREEN 1 / AMBER 2 / RED 0;
- the one-send `OWNER_GO_LIVE` switch for Muse sends.

The safety rules at the end of this file were NOT removed.

## Video provider

1. **Muse is the video and stills provider.** Sending frames, references and scripts to Muse is part of a send, not
   sharing.
   - **Quality:** use the highest resolution and the best model Muse offers. Quality and speed come first.
   - **Cap:** no request cap. Credits are not a constraint; the only limit is the accounts' own quota.
   - **Parallelism:** use as many lanes as there are usable accounts (up to 6 jobs per account batch).
2. **Flow and Vilao are paused for new sends.** Using them again needs the Owner. Finishing work already in flight
   (reconcile, download, review of earlier takes) is allowed.
   - **Flow spend always needs the Owner's approval**, for every send that can spend credits, even after Flow is
     re-enabled. Muse spend needs none. (Owner, 2026-11-20, in the Muse Tech Lead session: "Bỏ yêu cầu duyệt chi
     tiêu với Muse, flow vẫn cần".)
3. **Muse keeps what it already does well.** Its sending, guard and recovery rules (the Muse project's rounds
   r6-r12) are ported unchanged and proven by parity tests, never rewritten from scratch. Until the AFP Muse lane
   passes its pilot, production runs through the standalone Muse project.

## Delegated to the agent (Tech Lead and film brain sessions, AFP and Muse)

1. **Approvals.**
   - Approve stills and storyboards, accept or reject takes, pass gates.
   - In Muse this covers anchors and turnarounds, location plates, keyframe contact sheets, the animatic and each
     kept take (stage 2.5 to 5). Each approval is a written film-creative-review, PASS or RESTAGE per cell, in
     the project's review file.
   - Sign as `agent:tech-lead (delegated by owner-khoikk03, OWNER_POLICY.md)` or
     `agent:film-<id> (delegated by owner-khoikk03, OWNER_POLICY.md)`. Never sign as `human:owner-*`.
   - The evidence field holds concrete review notes:
     - identity and look;
     - REL_ADDRESS, REL_LISTENER, REL_GAZE, REL_BARRIER;
     - continuity against the adjacent accepted cut.
   - Review frames as a contact sheet. Reject a take that fails any required check.
2. **Takes per shot.** The agent picks how many parallel takes to send and keeps the best by QC. Default: GREEN 1,
   AMBER 2, UNKNOWN 3, dialogue shots at least 2; a RED shot is restaged, never sent. Two takes of one shot never
   share a batch.
3. **Advice.** For a judgment call, consult ChatGPT. Treat it as advice; the agent decides.
4. **Technical decisions.** The agent decides design, restaging, coverage and fixes. The Owner decides only product
   meaning: story changes, publishing.
5. **Starting a film.** A script the Owner hands over (with or without a brief card) is the authorisation to make
   that film end to end. Making a film nobody asked for still needs the Owner.

## Tell the Owner (and keep going where possible)

- **A Muse account is out of quota or cannot log in** (2 failed re-logins): mark it, keep working on the other
  accounts, and tell the Owner which account. The Owner adds new accounts.
- **No usable Muse account is left:** stop sending, tell the Owner, and wait for new accounts.
- **A CAPTCHA, verification page or unusual-activity notice on any Muse account:** stop ALL Muse sending at once,
  quarantine that account, set the production halt and tell the Owner. Never move the job to another account to
  get past it.

## Still reserved to the Owner (stop and ask)

- Publishing, uploading anywhere public, or sharing outside this machine.
- `git push` to a new remote, a force push, or making any repository public. (Plain pushes to the existing
  origin are delegated, see below.)
- Purchases, new accounts, and plan or credit top-ups. (The agent never creates accounts.)
- Changing the story's meaning (cutting a scene, changing an ending, adding characters), changing dialogue, or
  changing a locked look.
- Accepting the final master of a film. Technical PASS is not Owner acceptance.
- Sending on any provider other than Muse, and every Flow spend.

## Stop conditions for unattended runs

Stop and report when any of these happens:
- the film is assembled;
- no usable Muse account is left;
- a reserved item above is needed;
- the same defect has repeated three times after pipeline fixes.

## Unchanged safety rules

- Never print the GPM profile list.
- Never read cookies. **Exception (Owner, 2026-11-20, quoted above):**
  - **Who and what.** The Muse lane process may read the cookies and login details in the Muse Studio account store,
    only for accounts the Owner added there.
  - **How.** It uses them in memory only, to authenticate sends and re-logins. A refreshed cookie may be written back
    to that store, atomically.
  - **Never.** It never puts them in logs, traces, screenshots, receipts, events, the repo, exports, or any profile or
    file outside that store.
  - **Re-login limits.**
    - At most 1 attempt per account per 2 h, tracked across restarts; after 2 consecutive failures the account is
      marked NEEDS_LOGIN and the Owner is told.
    - Only an expired login triggers a re-login. Quota, payment and network errors never do.
    - A re-login never re-sends a job and never switches accounts to get past a warning.
  - **Stop rule.** On a CAPTCHA, a verification page or an unusual-activity notice: stop, quarantine the account and
    set the production halt. Never solve or evade it.
  - **Scope.** No other route or tool may read cookies.
- No anti-bot, stealth or fingerprint-evasion tooling.
- No curl; use Python.
- Never commit `uv.lock`.
- **Git in both repositories (Owner, 2026-11-21).** Local commits of source code and docs are allowed in AFP and
  in `D:\Muse` (this includes putting `muse_studio` under version control), staged by explicit path.
  - Never commit secrets or private data: `muse_studio/data/accounts.json*` (backups included), `muse_studio/data/profiles/`,
    `muse_studio/data/lane_leases.json`, any cookie or session file,
    `.env`, or film work folders.
  - Never clean, stash or reset another session's work.
  - `git push` (Owner, 2026-11-21): the agent pushes committed work to the existing `origin` remote when it is
    ready, without asking. Never `--force`, never a new remote or a public repository, never a branch holding
    secrets or film work folders. Muse has no remote yet; adding one stays with the Owner.
- Codex reviews run read-only.
- Never use `--approve-storyboard`.
