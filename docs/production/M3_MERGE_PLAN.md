# M3 code-merge plan: AFP + Muse into one repository, "Film Studio"

**Status: v3, 2026-11-21. Codex rounds 1 and 2 both REJECT; every High of both rounds is fixed here; the stop rule (2 rounds) is reached, so v3 is not re-reviewed.** Design only. Nothing in this document has been executed.
- Written by session `m3-merge-plan` for the coordinator. Basis: `STUDIO_ARCHITECTURE.md` §8, §11 (roadmap change of
  2026-11-21, non-regression rule), `MERGE_INVENTORY.md`, the lane contract v8
  (`docs/production/muse/AFP_MUSE_LANE_CONTRACT.md` §6, §12), `OWNER_POLICY.md`, AFP `pyproject.toml`, and a read-only
  look at `D:\Muse` (layout, `requirements.txt`, `core/config.py`, `tests/conftest.py`, `CLAUDE.md`).
- Review: Codex `gpt-6.1-sol`, read-only; the record is in "Review record" at the end.
- Scope: the order and method of the merge. The merged system's later features (Round A/B, S2-lite, S5, daemon, UI)
  are named only where they must fit the layout.

## 0. Decisions in one table

| # | Question | Decision |
|---|---|---|
| D1 | Target repo | **Import Muse into the existing AFP git repository** (the repo behind `AFP-stable`, remote `origin`). No new `film-studio` repo. |
| D2 | Package layout | Two import packages side by side in `src/`: `film_pipeline` (unchanged) and `muse_studio` (unchanged name, moved to `src/muse_studio/`). One new thin package `film_studio` (CLI front, path resolver, test isolation plugin, runtime pinning). No package is renamed in M3. |
| D3 | Distribution and CLI | Distribution renamed `film-studio`. Console scripts: `studio` (new), `afp-film` (alias, same entry point). Muse's `python -m muse_studio.cli` and `python -m muse_studio.pool_runner` keep working. |
| D4 | Secrets at runtime | `muse_studio/data/` leaves the code tree. The data dir is resolved from `MUSE_DATA_DIR` only, never from the code location; default `%LOCALAPPDATA%\FilmStudio\muse-data`. The AFP state dir keeps `AFP_STATE_DIR` (default `~/.afp`). |
| D5 | History import | A **filtered throwaway clone** of Muse at the tag `muse-v1.0-r15`, then a `--allow-unrelated-histories` merge into a merge branch. Fallback: plain copy plus one provenance commit. A secret scan of every reachable blob comes first. `D:\Muse` is never rewritten. |
| D6 | Dependencies | One `pyproject.toml`: AFP's three core deps stay the only mandatory ones; Muse's stack becomes the `muse` extra; headless OpenCV everywhere. Python `>=3.11,<3.13`. `uv.lock` stays untracked (standing rule); runtime pins are a committed text constraints file. |
| D7 | Runtime pinning | The lane runs `python -m muse_studio.pool_runner` from a clean detached worktree of an **in-repo annotated tag** `studio-rt-<yyyymmdd>-<n>`, with `MUSE_DATA_DIR` and a venv built from that tag. Replaces the cross-repo tag D8 (`muse-v1.0-r15` becomes the import source only). |
| D8 | Tests | Two pytest suites, one command (`studio test`, backed by `tools/run_all_tests.py`), run **sequentially**. One shared isolation plugin (`film_studio.pytest_isolation`) loaded by both suites, plus before/after canary stats of the production state files. |
| D9 | Order | 9 steps (§7), each with an owner, "done", rollback and what it blocks. The merge starts only after the inventory precondition (§7, Gate 0). |

## 1. Target repo and layout (D1-D4)

### 1.1 Why import Muse into AFP, not a new repo

- **AFP is the system of record.** It holds ~1530 commits, the `origin` remote, the S1 broker, the production
  ledgers, `films/`, `docs/production/` (OWNER_POLICY, architecture, contract) and every worktree the Tech Lead
  tooling already knows. A new repo would drop that history and the remote, or need the same import anyway.
- **Muse is small and young.** `src/muse_studio` is ~28k lines of Python, 3.3 MB without `data/`, one baseline
  commit plus a dirty tree today (contract §12). Little history is at stake; the import is cheap.
- **Roadmap.** §11 says "one repository, with the Muse code imported with its history at the pinned tag".
- **Physical folder names do not change in M3.** The repo directory keeps its names; worktree paths are brittle.
  Rename of the GitHub repo and local folders is an Owner call after P1, outside this plan.
- Work happens on a new branch `studio/m3-merge` in its own worktree cut from `feature/drama-preprod-p0`.
  The main checkout (`mission/quality-v2-022-120s`, 50 dirty files) is not touched. Merge to the feature branch
  is a fast-forward after Step 8.

### 1.2 Layout after the merge

```
<repo>/
  pyproject.toml                 # one project: distribution "film-studio"
  constraints/runtime.txt        # committed text pins for the runtime venv (not uv.lock)
  src/
    film_pipeline/               # unchanged (AFP, 53k lines)
    muse_studio/                 # imported tree, import name unchanged
      core/ cli.py lane.py pool_runner.py app.py autoprod.py static/ scripts/
      tests/                     # kept in place (see §5)
    film_studio/                 # NEW, small
      cli.py                     # `studio` front: dispatches to film_pipeline.cli (+ `studio muse ...`, `studio test`)
      paths.py                   # one resolver: MUSE_DATA_DIR, AFP_STATE_DIR, runtime tree; refuses under pytest
      runtime.py                 # tag/commit/venv fingerprint checks for §8 pinning
      pytest_isolation.py        # shared test isolation plugin (§5)
  tests/                         # AFP suite (205 files), unchanged location
  tools/run_all_tests.py         # sequential runner used by `studio test`
  docs/production/               # AFP docs (OWNER_POLICY, STUDIO_ARCHITECTURE, ...)
  docs/muse/                     # Muse docs, SOT, backlog, lessons imported here (no overwrite of AFP docs)
  .claude/skills/muse-director/  # Muse skill, merged next to AFP skills (step 7)
```

- **Why not merge or rename `muse_studio` into `film_pipeline.*`.** Muse has ~270 internal imports: 165
  `from muse_studio...`, 104 `from core...`, 13 `import muse_studio`. It also has a deliberate dual-import
  fallback (`cli.py:50-56`, `pool_runner.py:26-31`) that inserts the package dir on `sys.path` and imports `core.*`
  as a top-level name. The contract names `python -m muse_studio.pool_runner`. The non-regression rule (§11) says
  proven send, ledger and recovery code moves unchanged. A package rename or import cleanup is a behaviour risk with
  no merge benefit. It becomes a post-P1 backlog item gated by the Muse rule tests.
- **Why `src/muse_studio`.** It matches AFP's `src` layout, so one `setuptools` `packages.find where=["src"]`
  installs both packages. Muse's `cli.py` inserts `Path(__file__).parent`, so it works at any depth.
- **`film_studio` is the only new code.** It contains no send, ledger or broker logic.

### 1.3 CLI (D3)

- `pyproject.toml` `[project.scripts]`: `studio = "film_studio.cli:main"` and `afp-film = "film_studio.cli:main"`: **the
  same dispatcher**, so `afp-film test|muse|runtime` equal their `studio` forms. `film_studio.cli.main` takes `prog`
  from the invoked name (`studio` or `afp-film`), then calls `film_pipeline.cli.main` for every non-new subcommand;
  every existing `afp-film <subcommand>` works unchanged under `studio` (`studio broker ...`, `studio production ...`).
  `film_pipeline.cli:main` stays importable for old callers and tests.
- New subcommands only dispatch: `studio test` (the §5 runner), `studio muse <args>` (runs `python -m
  muse_studio.cli <args>` from the **dev tree**, for the Muse Tech Lead's own work; lanes never use it), and
  `studio runtime check|build` (§8).
- `afp-film` stays as documented alias for the whole life of this plan. Output text that says `afp-film` is not
  rewritten in M3 (STATUS, runbooks and receipts quote it). Removal of the alias is out of scope.
- The lane contract's CLI names (`afp-film broker acquire|check|...`) stay valid: same entry point.

### 1.4 Where runtime data lives (D4)

| What | Path | In repo? | Notes |
|---|---|---|---|
| Muse secrets and Muse runtime state: `accounts.json`, `accounts.lock`, `profiles/`, `lane_leases.json` (+`.lock`), `muse_halt.json` (+`.lock`), UI `projects/` and `output/` | `MUSE_DATA_DIR`, default `%LOCALAPPDATA%\FilmStudio\muse-data` | never | Read access stays with the Owner's Windows user (contract §9 secrets rule). |
| AFP machine state: broker DB `lease_pool.sqlite3`, `production_halt.json`, `halt_pending/`, `allocator_owner.json` | `AFP_STATE_DIR`, default `~/.afp` | never | Unchanged in M3. Moving it would orphan the S1 broker DB and halt history; a later migration is a separate step. |
| Film work | `C:\film-work\<film>` (Muse side), `films/<id>` (AFP package) | `films/` yes (explicit paths), `C:` no | Unchanged. |
| Lane runtime trees | `C:\film-work\_rt\studio-rt-<yyyymmdd>-<n>` | never | §8. |

- **Code changes in Muse for data location (the M3 set, step 4; each reviewed by the Muse Tech Lead).** Three places
  resolve a location from the code tree today, and **all three** move to `MUSE_DATA_DIR`:
  1. `core/config.py` derives `BASE_DIR`/`DATA_DIR` from `__file__` and calls `ensure_directories()` at import (it
     also writes `accounts.json` as `[]` when absent). It becomes `DATA_DIR = Path(os.environ["MUSE_DATA_DIR"])` or the
     default, and creates nothing inside the code tree.
  2. `core/send_halt.py` `halt_path()` defaults to `<code tree>/data/muse_halt.json` independently of `config.py`
     (`MUSE_HALT_FILE` overrides it). Its default becomes `<MUSE_DATA_DIR>/muse_halt.json`. Without this, a standalone
     or dev command run after the data move would not see the moved halt (including an `OWNER_PAUSE`) and could create
     a new empty halt file inside the code tree.
  3. `core/lane_leases.py` `default_leases_path()`/`real_leases_path()` default to `<MUSE_DATA_DIR>/lane_leases.json`
     (`MUSE_LEASES_FILE` keeps its override).
  Focused tests: with only `MUSE_DATA_DIR` set (no `MUSE_HALT_FILE`, no `MUSE_LEASES_FILE`), a halt written before is
  honoured after a fresh process start; nothing is created under the code tree; an `OWNER_PAUSE` record survives the
  move byte for byte (`muse_halt.json` holds no secret; its sha256 is compared before and after).
  This is the contract's already-named NEW `MUSE_DATA_DIR` (§12), delivered now because the pinned tree must never
  contain secrets.
- **One-time data move (step 6).** After the last standalone Muse process is stopped (no live lease, no `.lock`
  holder), the AFP Tech Lead moves `D:\Muse\muse_studio\data` to `MUSE_DATA_DIR` with a path-only script. It never
  prints or parses `accounts.json`, `profiles/` or cookie files, and logs only counts and byte sizes.
  - **Integrity.** Copy with an authorised OS tool that preserves attributes and ACLs (`robocopy /E /COPY:DATSOU`
    style), then verify by **sha256 of every file** computed in-process and compared source to destination (nothing
    printed beyond the file count and a pass/fail). Size equality is not accepted as proof.
  - **The source is not deleted** by this plan. After the verified copy the source is renamed to
    `data.MOVED_PRE_M3` so no old-tree command can use it by mistake. The Owner decides on deletion after P1.
  - **Rollback** renames the source back and removes the destination **only if** it is unchanged since the move
    (the destination hash manifest still matches); if a lane has written to it, the script refuses and escalates to
    the AFP Tech Lead. It never overwrites a non-empty destination or source.
  - The `.bak_*` files travel with the data and are never committed.
- **Windows.** Short paths for the runtime tree stay (MAX_PATH, M8). `MUSE_DATA_DIR` default is short enough for
  Chromium profile paths; `studio runtime check` verifies the longest known profile path is under the limit.

## 2. History import method (D5)

### 2.1 Preconditions (from MERGE_INVENTORY M6, M7)

- Muse today: one baseline commit plus a dirty tree; `muse_studio` is untracked. M6 (Muse Tech Lead) puts
  `muse_studio` under version control with `.gitignore` for secrets (the 31 staged scratch deletions and the modified
  `.gitignore` included), after the Owner's confirmation of the git rule in the Muse session. M7 tags
  `muse-v1.0-r15` after r15, PRE-TAG #11 and the accounts lock (M1-M3, M6).
- The import source is **exactly that tag**. A dirty or untagged tree is not imported.

### 2.2 Secret scans: three checkpoints, each before the content can enter a commit

**Checkpoint 0: before Muse's own M6 baseline commit (Muse TL; precedes Step 1).** M6 puts untracked and staged content
under git for the first time, so the first scan must run on the **index**, not on a clone. Before `git commit` in
`D:\Muse`, the Muse Tech Lead scans the exact staged blobs (`git diff --cached --name-only` for the path rules, the
staged blob content for the content rules, same scanner and patterns as below) and commits only on a clean report. This
is the only step that touches `D:\Muse` git, and it is already M6's own work under the Owner's git rule, not this plan's.

**Checkpoint 1: the source history, after M6/M7 (Step 2).**

On a **throwaway clone** of `D:\Muse` (`git clone --no-local`, made by the Muse Tech Lead, outside both repos; no git
operation is run in `D:\Muse` by this plan):

1. **Path scan over all reachable history.** List every path of every reachable commit
   (`git log --all --name-only` style) and fail on: `accounts.json*`, `*.bak*`, `profiles/`, `lane_leases.json*`,
   `muse_halt.json*`, `*.cookie*`, `*session*.json`, `.env*`, `*.sqlite*`, `Cookies`, `Login Data`, `Local State`,
   Chromium profile dirs, and any film output folder or media file larger than a set limit (default 5 MB).
2. **Content scan of every reachable blob** (text only; binary blobs are judged by path and size) for cookie headers,
   `Set-Cookie`, bearer or API key shapes, password-like assignments (`password`, `passwd`, `pwd`, `otp`), email
   addresses in credential context, and the Muse accounts schema keys. The scanner prints **file path, commit and
   pattern name only**, never the matched text. The report goes to `_archive/m3_merge_plan/scan_<tag>.md`.
3. **Pass rule.** Zero path hits and zero content hits, or each hit listed with a reason and an Owner-visible
   decision. One unexplained hit stops the merge: the secret is removed by history filtering in the clone (not by
   a later delete), then the scan repeats. A leaked live secret is also reported to the Owner for rotation
   (OWNER_POLICY: new accounts and credentials are the Owner's).
4. **Checkpoint 2: the filtered export, before anything is fetched into AFP (Step 3).** The scanner runs on every
   reachable blob of the filtered clone; AFP fetches only on a clean report.
5. **Checkpoint 3: the merge result, before its commit (Step 3).** The merge uses `--no-commit`; the scanner runs on the
   staged result (`git diff --cached`), and the AFP Tech Lead commits only on a clean report.
6. The scanner runs again on every runtime tag (§8) at build time.

### 2.3 Import (AFP TL, step 3)

Primary method: **filter in the clone, merge unrelated histories.**

1. In the throwaway clone, `git filter-repo` with an **allow-list**, not a deny-list:
   - keep `muse_studio/` (excluding `muse_studio/data/**`), `docs/`, `.claude/skills/muse-director`,
     `.claude/hooks`, `.agents/skills`, `.agents/skills.json`, `.agents/hooks.json`, `CLAUDE.md`, `AGENTS.md`,
     `PIPELINE_SOT_NATIVE_FILM.md`, `CRAFT_GAP_BACKLOG.md`, `PIPELINE_AUDIT_20261101.md`, `.gitignore`;
   - rename: `muse_studio/` → `src/muse_studio/`; `docs/` → `docs/muse/`; the root `CLAUDE.md`/`AGENTS.md` →
     `docs/muse/MUSE_CLAUDE.md` / `docs/muse/MUSE_AGENTS.md` (merged into one in step 7); the SOT and backlog files
     → `docs/muse/`; `.claude/skills/muse-director` and `.claude/hooks/stage_skills.py` keep their path under the
     name `muse-director` and `stage_skills_muse.py`; the Muse `.gitignore` becomes `docs/muse/muse.gitignore.txt`
     (its secret rules are merged into the root `.gitignore`, step 3);
   - **drop** every film folder, `_worktrees`, `_backups`, `_live_*`, `_director_review_*`, `HANDOFF_*`, zips and
     media. The B14 fixture (`_director_review_B14_20261119`, 227 MB) is **not** imported: it stays outside the repo,
     referenced by a committed manifest (path, size, sha256 of the file list) in `fixtures/muse_b14/MANIFEST.json`,
     and copied to a short path by the test setup as the contract already says (§14).
2. The AFP Tech Lead fetches the filtered clone into a local ref `refs/imports/muse/<tag>` in the merge worktree
   and records the tag, the original commit and the old-to-new commit map in the import commit message and in
   `docs/muse/IMPORT_PROVENANCE.md`.
3. `git merge --allow-unrelated-histories --no-ff --no-commit refs/imports/muse/<tag>` on `studio/m3-merge`, then the
   checkpoint-3 scan, then the commit. No file of AFP
   exists at the new Muse paths, so the merge has no content conflicts. Root `.gitignore` is resolved by hand.
4. **Fallback** (filter tool unavailable, or the scan cannot be trusted on history): export the tagged tree with
   `git archive`, apply the same allow-list and renames by script, and make **one** provenance commit ("import muse
   at tag X, commit Y"). History stays in the archived `D:\Muse` repo, which is kept read-only (never deleted).
   Because Muse's history is short, this loses little and is acceptable.
- **Why not `git subtree`.** It maps one prefix to one directory; Muse's tree needs several path moves and an
  allow-list. `git subtree` also keeps whatever history was in the source, including anything the scan would reject.
- **Plain copy is not the primary method** because it drops authorship and the per-round commit trail Codex reviews
  quoted (r6-r15).
- `D:\Muse` is renamed to a read-only archive path only after P1 passes (not part of M3). Its film folders on `D:\Muse`
  and `C:\film-work` are untouched.

## 3. Dependency and environment unification (D6)

- **Python.** Both use Python 3.11 on this machine (3.11.9). Set `requires-python = ">=3.11,<3.13"`. Python 3.13 is
  excluded until `faster-whisper`/`ctranslate2` and `opencv` wheels are proven on it. The runtime venv is created with
  one named interpreter (`uv venv --python 3.11`) and the interpreter version is part of the runtime fingerprint (§8).
- **Build tool.** AFP already uses `uv` (0.12) with a **local, untracked** `uv.lock`. Standing rule: `uv.lock` is never
  committed. This plan keeps that rule; it does not introduce a tracked lock. Reproducibility for lanes comes from a
  committed `constraints/runtime.txt` (exact versions, produced by `uv pip compile` for the `muse,qc` extras) plus the
  venv fingerprint in §8. Tracking a lock file instead would be an Owner decision, noted in §9.
- **How Muse differs from AFP.**

  | | AFP today | Muse today (`requirements.txt`, unpinned `>=`) |
  |---|---|---|
  | Packaging | `pyproject.toml`, setuptools, `src` layout | none: plain folder, `requirements.txt`, run from the repo root |
  | Core | `pydantic>=2,<3`, `jsonschema`, `Pillow` | `pydantic>=2.6`, `Pillow>=10.2`, `numpy`, `scipy` |
  | Media/QC | `opencv-python-headless`, `numpy` (extra `qc`) | `opencv-python` (full), `numpy`, `scipy`, `faster-whisper`, `jiwer`, `edge-tts` |
  | Provider | `patchright`, `playwright` (extra `flow`) | `playwright` |
  | Web | none | `fastapi`, `uvicorn[standard]`, `python-multipart` |
  | LLM | Gemini via its own adapters | `google-genai` |
  | Tests | `pytest>=8,<10` | `pytest>=8` |

- **Conflicts and how they are resolved.**
  - `opencv-python` vs `opencv-python-headless` provide the same `cv2` module and overwrite each other when both are
    installed. **Decision: headless only.** The import scan (below) found no `imshow`/`waitKey`/`namedWindow` use in
    `muse_studio`. A test asserts `cv2` imports and Muse's QC detectors run on the fixture clip.
  - `pydantic`, `Pillow`, `numpy`, `pytest` ranges overlap; AFP's upper bounds win (`pydantic<3`, `Pillow<13`).
  - `playwright` is already in AFP's `flow` extra; Muse needs it for the headless client. It moves to the `muse` extra
    and `flow` keeps its own pin; the resolved version must satisfy both.
- **Extras (new `pyproject.toml`).** Core stays `pydantic`, `jsonschema`, `Pillow` so the AFP-only workflows keep a
  lean install.
  - `muse = [fastapi, uvicorn[standard], python-multipart, playwright, numpy, scipy, opencv-python-headless,
    faster-whisper, jiwer, edge-tts, google-genai]` with upper bounds chosen at step 4 from the installed versions.
  - `qc` and `flow` as today; `dev = [pytest>=8,<10]`; `provenance` as today.
  - `edge-tts` and `python-multipart` are declared by Muse but not imported by any module found by an AST scan of
    `muse_studio` (outside `data/`); step 4 checks whether they are loaded lazily or by subprocess before keeping or
    dropping them. Dropping a dependency without proof is not allowed.
- **Package data.** `muse_studio/static/**` is nested (`static/css`, `static/js`, ...), so it is included
  **recursively** (`"muse_studio" = ["static/**/*"]` or an explicit list per subdirectory; the exact syntax is verified
  against the setuptools version in use). The step-4 gate builds the wheel, lists its contents and checks that every
  file under `static/` is present, then starts the UI (`app.py`) from the **wheel install** and requests one CSS and one
  JS asset, rather than validating only the editable dev install.
- **Install modes.** Dev: `uv pip install -e ".[dev,qc,muse,flow]"`. Lane runtime: **dependencies only**
  into its own venv, never an install of the project (§8): `uv pip install -r constraints/runtime.txt`; the code runs from
  the runtime tree on `PYTHONPATH`. A non-editable wheel install is a packaging check only (gate below), not a runtime.
- **Gate.** `uv pip install` of both modes on a clean venv succeeds; `import film_pipeline, muse_studio, film_studio`
  passes; `studio --help` and `python -m muse_studio.cli --help` (with `PYTHONIOENCODING=utf-8`) run.

## 4. Import boundary and the `core` name

- `src/muse_studio` is added to `sys.path` only by Muse's own fallback inside Muse processes (`cli.py`, `pool_runner.py`,
  `lane.py`), which then import `core.*` as a top-level name. AFP code must never `import core`.
- Two AST tests in the AFP suite (step 4): (1) no `film_pipeline` or `film_studio` module imports `muse_studio` or `core`,
  and no `muse_studio` module imports `film_pipeline`; (2) `film_pipeline` and `film_studio` import cleanly with no
  `core` on `sys.path`.
- This keeps the lane contract's process boundary a property of the code, not only of the launch command (§6).

## 5. Test unification (D8)

### 5.1 Two suites, one command

- **Suites.** AFP: `tests/` (205 files, ~2.9k tests, root `tests/conftest.py`). Muse: `src/muse_studio/tests/`
  (31 files, its own `conftest.py`). Test files stay where they are: the Muse rule tests must run unchanged
  (contract §14), and several Muse tests resolve paths from `__file__`.
- **Why not one pytest invocation.** Two `conftest.py` files with the same basename and no `__init__` collide in
  pytest's default import mode; `--import-mode=importlib` would change how AFP's 205 test files import helpers. A
  single process would also mix the two `sys.modules` worlds (Muse's `core.x` vs `muse_studio.core.x`).
- **The command.** `studio test [--fast] [-k ...]` = `python tools/run_all_tests.py`:
  1. snapshot the canary list (§5.3);
  2. `python -m pytest tests -p film_studio.pytest_isolation` (AFP);
  3. `python -m pytest src/muse_studio/tests -p film_studio.pytest_isolation` (Muse);
  4. compare canaries; **fail the run** if any changed, even when both suites are green;
  5. one summary line per suite and one overall exit code; full output to files, never printed whole.
- **Sequential, never parallel.** The AFP film lock lives in `%LOCALAPPDATA%` and a parallel pytest produces a false
  `FILM_BUSY` failure (S1 hand-over). The runner refuses to start a second instance (its own lock file in the temp dir).
- Targeted runs (`pytest tests/test_x.py`, `pytest src/muse_studio/tests/test_x.py`) keep working, and the plugin is
  loaded from `addopts` in each suite's config so a targeted run is also isolated.

### 5.2 Isolation (lesson L37)

On 2026-11-21 a Muse test wrote the real `muse_halt.json` and stopped the P0 run. Today each suite isolates only its own
side: AFP's `conftest` sets `AFP_STATE_DIR`, `AFP_HALT_FILE` and **deletes** `MUSE_HALT_FILE`; Muse's `conftest`
sets `MUSE_HALT_FILE`, `AFP_STATE_DIR` and `MUSE_LEASES_FILE`. After the merge both suites run in one tree, so the rule
is one shared plugin:

- `film_studio.pytest_isolation`, loaded with `-p` (and via `addopts`), runs **at import time**, before any test module
  is collected, and creates one **test root** (a session temp dir). It exports `FILM_STUDIO_TEST_ROOT=<root>` and sets,
  all inside that root: `AFP_STATE_DIR`, `AFP_HALT_FILE`, `MUSE_DATA_DIR`, `MUSE_HALT_FILE`, `MUSE_LEASES_FILE`. The
  Muse accounts file and profiles dir resolved from `MUSE_DATA_DIR` are scratch paths.
- **Validate destinations, not defaults.** A guard that only rejects the production default lets a non-default production
  path (a typo, an old path in a test, an override) through. The rule is the opposite: **when `FILM_STUDIO_TEST_ROOT` is
  set, every resolved path must lie inside it, or the resolver raises.** `film_studio.paths.require_test_owned(path)`
  is called at each resolver and constructor, including explicit overrides:
  - AFP: `production/halt.py` `state_dir()` **and** `halt_path()` (today `AFP_HALT_FILE` is accepted without going
    through `state_dir()`), the broker/lease-pool DB path (`--db` included), `halt_pending/`, `allocator_owner.json`;
  - Muse: `config.py` (`DATA_DIR`, `ACCOUNTS_FILE`, `PROFILES_DIR`), `send_halt.halt_path()` (replaces the
    pytest-only check), `lane_leases` paths, and the `AccountManager` constructor, so a test that passes explicit
    `accounts_file` / `profiles_dir` arguments outside the root also raises.
  The pytest-only checks already in Muse stay as a second line.
- **Child processes cannot lose the guard.** The plugin wraps `subprocess.Popen.__init__` for the whole session (and
  `os.spawn*`, `os.system` and `os.exec*` are forbidden in tests by a lint check in `run_all_tests.py`): whatever `env` a
  test passes (a scrubbed dict, `{}`, or `None`), the child's environment gets `FILM_STUDIO_TEST_ROOT` and the five paths
  set to test-root values, **overriding** any value that points outside the root. A child therefore never starts without
  the guard, and no test code has to remember to pass it. The subprocess guard test proves this with a child started with
  `env={}` and with a child whose env names a production path: both are rewritten, and neither touches a production
  path. The canary check remains the last line, not the only one.
- An autouse function-scoped fixture repoints the five paths per test inside the root (as today) and resets
  `send_halt._reset_memory()` for both module identities (`core.send_halt` and `muse_studio.core.send_halt`). AFP's
  existing autouse fixture, which **deletes** `MUSE_HALT_FILE`, is removed in step 5; the plugin owns all five paths, so
  the two suites' overlapping fixtures are consolidated in one place.
- **Bootstrap.** Today, importing Muse's `config.py` creates directories and `accounts.json` in the code tree. The
  baseline rule tests are therefore first run in the throwaway clone (step 2), and in the merge worktree only **after** the
  step-4 data-location edits (§1.4) with the plugin loaded, so no test import can touch a real data dir.
- **Guard tests** (both suites): `tests/test_isolation_guard.py` and `src/muse_studio/tests/test_isolation_guard.py`
  assert each of the paths above resolves inside the root; that an override pointing outside the root raises, including
  `AFP_HALT_FILE`, `MUSE_HALT_FILE`, `MUSE_LEASES_FILE`, `AFP_STATE_DIR`, `MUSE_DATA_DIR`, explicit `AccountManager`
  arguments and the broker `--db` path; and that a subprocess started by a test inherits the guard.

### 5.3 Canary check

`tools/run_all_tests.py` records `os.stat` (mtime, size) of these production files before and after the run, and fails
if any changed: `<AFP_STATE_DIR>/production_halt.json`, `halt_pending/` (entry list), `lease_pool.sqlite3`,
`allocator_owner.json`, `<MUSE_DATA_DIR>/muse_halt.json`, `lane_leases.json`. It **stats only and never opens**
`accounts.json`, `profiles/` or cookie files. If a production file does not exist, "still absent" is the pass state.

### 5.4 CI

There is no CI service today (no workflow files); "CI" means one command that any session or hook can run. M3 adds the
command and a hermetic mode (`FILM_STRICT_LOCAL_EVIDENCE` as AFP uses it). A hosted CI definition is out of scope.
The Muse suite takes about 3 minutes; AFP's is larger. `--fast` runs the targeted set that guards custody:
S1 broker files, `production_halt`, lane leases, and Muse `test_review6/7/9/11`, `test_blocked_halt`, `test_stop_all_r14`,
`test_stop_all_r15`.

## 6. Non-regression and what must not change

- **Lane contract v8 process boundary.** The AFP lane runs Muse as **one OS process per account** through `python -m
  muse_studio.pool_runner`; AFP imports no Muse module and Muse imports no AFP module. Merging repositories does not
  change this. A CI check asserts: no `film_pipeline` module imports `muse_studio` or `core`, and no `muse_studio`
  module imports `film_pipeline` (static AST test, in the AFP suite).
- **Muse proven code is moved, not edited.** Files moved verbatim by the import: `core/headless_muse_client.py`,
  `core/batch_packager.py`, `core/parallel_pool_engine.py`, `core/autoprod_orchestrator.py`, `core/send_halt.py`,
  `core/lane_leases.py`, `core/account_manager.py`, `pool_runner.py`, `lane.py`, the QC and compiler modules.
  Step 3 gate: a content diff between the tag tree and the imported tree shows **only** the planned path moves; the
  Muse rule tests (`test_review6/7/9/11_fixes`, `test_blocked_halt`, `test_stop_all_r14`, `test_stop_all_r15`) run
  green **before any edit** (step 3) and after each later step.
- **Allowed Muse edits in M3, exhaustive** (each reviewed by the Muse Tech Lead; any edit touching sending, the ledger,
  recovery or integrity needs that review by the §11 rule, and none of those is expected):
  1. data-location resolution: `core/config.py`, `core/send_halt.py` (`halt_path()` default only), `core/lane_leases.py`
     (default registry path only), and direct readers of `DATA_DIR`/`ACCOUNTS_FILE`/`PROFILES_DIR` (§1.4);
  2. the `require_test_owned` guard calls at the Muse resolvers and the `AccountManager` constructor (§5.2);
  3. a **new**, stdlib-only, side-effect-free module `muse_studio/_runtime_bootstrap.py`, imported as the **first statement**
     of `pool_runner.py` and of the lane entry points of `lane.py`, **before** the existing `from core... import ...`
     lines (which load `config.py` and `AccountManager`). This is an authorised import-order edit; no other line of those
     files changes. `muse_studio/__init__.py` must be (and is verified to be) free of side effects, because `python -m
     muse_studio.pool_runner` executes it first. The bootstrap decides the **mode**:
     - **lane mode** = `STUDIO_LANE=1` in the environment (set by the AFP supervisor) or a `--batch-request` argument
       (Round A). In lane mode a trusted manifest is **required**: `STUDIO_RUNTIME_MANIFEST` unset, unreadable or not
       matching its recorded hash means exit non-zero before any other import: no account read, no browser, no send;
     - **standalone mode** = neither marker. The bootstrap does nothing. This is the pre-P1 standalone path that the P1
       scope freeze already keeps (single mode, no mixing with lanes). It is the explicit, documented development
       exemption, and it ends for real sends when P1 passes (§8);
     - in lane mode `config.py` also never creates `accounts.json`: a missing store is an error, not an empty list.
     It adds no send code. The bootstrap is the §8 child check.
  4. `tests/conftest.py` (reduced to the shared plugin plus Muse-only fixtures) and the new guard tests.
  **Not in M3:** writing `lane_result.json` and the `batch_request.json` request handling. They do not exist in the
  current `pool_runner` and are contract Round A work (M4), built after the merge. M3 supplies the verified identity
  (`_runtime_bootstrap` result) that Round A later copies into `lane_result.json`.
- **Contract field names stay.** `muse_tag` and `muse_commit` keep their names in `batch_request.json` and
  `lane_result.json` (contract v8, §5, §8). Their **values** become the in-repo runtime tag and the repo commit; a new field `runtime_manifest_sha256` carries the §8
  manifest hash. This is
  recorded as a contract v8.1 editorial amendment (step 7), so both Tech Leads agree on one reading.
- **Sends stay paused.** No step sends anything. Film runs resume only after the merged system's P1.
- **Flow films (film03-film08) and their provider code** keep their current runtime; nothing is migrated.

## 7. Ordered steps (≤ 10)

### Gate 0: precondition (coordinator; not a step)

The merge starts only when all of these are true and recorded in `MERGE_INVENTORY.md`:
**A1** (S1 addendum, Codex round 8 ACCEPT), **M1** with fixes a, b and c (r15 stop-all, Codex ACCEPT), **M2** (PRE-TAG #11,
no `src.unlink()`), **M3** (accounts lock), **M6** (git baseline, with its checkpoint-0 scan, §2.2) and **M7**
(import tag `muse-v1.0-r15`, scan clean); both repos clean (no WIP, no open lease, no unresolved child, no live lane);
the pre-M3 housekeeping rows (A5 push by the Owner, A8-A10, M10-M13) decided; M8/M9 (P0/BIKER) stopped or finished and
the data dir quiet.

**Inventory amendment required (coordinator, Step 1).** `MERGE_INVENTORY.md` row M7 says the tag comes "after M1-M6",
and M4/M5 (Round A/B) are in that range, but this plan builds Round A/B **after** the merge. As written the order is
circular. M7 is re-scoped: its prerequisites are **M1, M2, M3 and M6 only** (the pre-merge safety fixes and the
baseline); M4 and M5 land in the merged repo and ship under a runtime tag (§8). The amended row is committed by the
coordinator before Step 1 is signed.

### Steps

**Step 1: Freeze and import-source check.** Owner: coordinator with both Tech Leads (AFP TL records).
- Do: Gate 0 verified by reading, not by reports; `git status` clean in both repos; tag `muse-v1.0-r15` points at the
  commit the P0 hash list refers to; no process with a lane lease.
- Done: a signed checklist in `docs/production/M3_MERGE_CHECKLIST.md` (commit hashes of both repos, tag SHA).
- Rollback: none needed (read-only). Cancel the merge.
- Blocks: Step 2.

**Step 2: Source-history scan and baseline test run.** Owner: Muse TL runs; AFP TL verifies.
- Do: throwaway clone of the tag; the §2.2 checkpoint-1 scan over all reachable history, report to
  `_archive/m3_merge_plan/`; in the clone, with its own isolation env set, the Muse rule tests
  (`test_review6/7/9/11_fixes`, `test_blocked_halt`, `test_stop_all_r14`, `test_stop_all_r15`) as the **baseline result**
  (pass/fail list and counts saved), and the **B14 baseline**: one `pool_runner --simulate` run on the B14 fixture (copied
  to a short path), with its custody records, receipts and quarantine decisions saved under `_archive/m3_merge_plan/`.
- Done: zero unexplained scan hits; baseline recorded; the scanner script handed to the AFP Tech Lead.
- Rollback: delete the throwaway clone. Fix by filtering in the clone, never in `D:\Muse`.
- Blocks: Step 3.

**Step 3: Import Muse (code and docs).** Owner: AFP TL.
- Do: branch `studio/m3-merge` in a new worktree; §2.3 filter, checkpoint-2 scan of the export, `merge --no-commit`,
  checkpoint-3 scan of the staged result, commit; fix `.gitignore`. No test is run in this step: the baseline already
  exists (step 2), and importing Muse's `config.py` before its data-location edit would create a data dir in the tree.
- Done: merge commit with `IMPORT_PROVENANCE.md`; both scans clean; the content diff of the imported tree against the
  tag shows only the planned path moves and drops; AFP suite unchanged.
- Rollback: abandon the branch (nothing else changed; `git worktree remove`, branch delete after a look).
- Blocks: Steps 4-9.

**Step 4: One package, one environment, data location.** Owner: AFP TL; Muse TL reviews every Muse-side edit.
- Do: first the §1.4 data-location edits (`config.py`, `send_halt.py`, `lane_leases.py`), then new `pyproject.toml` (§3),
  `film_studio` skeleton, import audit, AST boundary tests (§4), `constraints/runtime.txt`, the `studio` and `afp-film`
  scripts, `muse_studio/_runtime_bootstrap.py` (§6, §8), a wheel build with the static-asset check, and the Playwright browser
  decision (§8).
- Done: clean-venv install in both modes; `studio --help`, `afp-film --help` and `python -m muse_studio.cli --help` pass;
  the Muse rule tests, run with `MUSE_DATA_DIR` set to a scratch dir and the plugin of step 5 stubbed by env, reproduce the
  step-2 baseline result exactly; the §1.4 focused tests pass; no data dir is created inside the tree.
- Rollback: revert the step's commits; the step-3 state stays valid.
- Blocks: Step 5.

**Step 5: Test unification and isolation.** Owner: AFP TL; Muse TL reviews the Muse side.
- Do: `film_studio.pytest_isolation` with test-root validation (§5.2), guard tests in both suites, consolidation of the two
  suites' autouse fixtures, `tools/run_all_tests.py`, `studio test`, canary check; a deliberate negative drill in a scratch
  clone (a temp test that resolves each production path, via default, non-default override and explicit constructor
  argument, and one that spawns a subprocess) to prove every guard fires.
- Done: `studio test` is green end to end; the canary list is unchanged; the negative drill fails as designed.
- Rollback: revert; each suite still runs alone with its own conftest (step-4 state).
- Blocks: Step 6 (the data move needs the guard first).

**Step 6: Runtime tag and data move.** Owner: AFP TL; Muse TL verifies lane behaviour on the tag.
- Do: (a) stop all Muse processes and confirm no live lease; (b) the §1.4 one-time move with sha256 verification, source
  renamed and kept; (c) `studio runtime build` creates the tag `studio-rt-<yyyymmdd>-1`, the detached worktree at
  `C:\film-work\_rt\...`, its venv, the browser and the `runtime_manifest.json` (§8); (d) `pool_runner --simulate` on the
  B14 offline fixture from the runtime tree with `MUSE_DATA_DIR`; (e) the wrong-tree drills of §8.
- Done:
  - **Parity is judged on normalized custody records, not counts.** From the Muse baseline run (made on the tagged source
    in step 2 with the same fixture and `--simulate`) and the runtime-tree run, compare per child: the AFP-mapped state
    (RESULT / AMBIGUOUS / NOT_SENT ...), `batch_id` + `slot_id` + `request_id`, the receipt sha256, the quarantine
    decision per file, the ledger record sequence, and the number of send attempts (0 in `--simulate`); timestamps, temp paths
    and the random per-run `batch_id` values are normalized out (each `batch_id` becomes its ordinal in creation order,
    also inside the receipt JSON before its sha256 is compared). Any difference after normalization is a failure.
  - the §8 drills reject a modified file, a moved tag, a wrong interpreter and a wrong import origin;
  - `studio runtime check` passes; the runtime tree contains no secret (scanner clean).
- Rollback: §1.4 rollback (source renamed back only if the destination is unchanged); retire the runtime tag (listed, never deleted or reused; no push) and remove its worktree.
- Blocks: Step 7 (docs would describe unproven paths) and A3.

**Step 7: Governance and docs merge.** Owner: AFP TL; coordinator approves; Muse TL reviews contract text.
- Do: one `AGENTS.md`/`CLAUDE.md` for the merged repo (Muse's operating rules move into `docs/muse/`); merge the
  `muse-director` skill and `stage_skills` hook into the AFP agent setup; contract **v8.1 amendment** (field values,
  `studio` as the primary CLI name, runtime tag in place of D8, §12 rewritten); update `STUDIO_ARCHITECTURE.md` §8 and
  the roadmap; `MERGE_INVENTORY.md` rows updated; handoff in `STATUS.md`.
- Done: Codex review of the contract amendment ACCEPT (no High); grep shows no stale `D:\Muse` run instruction left
  as the current path.
- Rollback: revert the docs commit.
- Blocks: Step 8.

**Step 8: Whole-tree acceptance and fast-forward.** Owner: AFP TL; independent check by the coordinator.
- Do: integrate any later AFP commits into the merge branch (R8) **one batch at a time with `--no-commit`**: first scan
  every reachable blob of the incoming commits (those not in the tip recorded at Step 1), then scan the staged result,
  then commit. A secret introduced and later deleted inside the incoming range is still a hit, because history is
  scanned, not only the final tree. Then `studio test` on the exact final candidate (both suites +
  canaries); Codex read-only review of `<merge base>..HEAD` over the product-code diff (config, `film_studio`,
  `_runtime_bootstrap`, pyproject, isolation); scan on the final tree. **If any runtime-relevant file changed since the
  step-6 tag** (anything under `src/`, `pyproject.toml`, `constraints/`), cut a new runtime tag and repeat the step-6
  runtime checks (§8 drills and B14 parity) on that exact candidate; the old tag is not reused.
- Done: all green; Codex ACCEPT (no High); `feature/drama-preprod-p0` fast-forwarded to the merge branch (local only,
  **no push**). The Owner pushes when the Owner decides (A5).
- Rollback: do not fast-forward; the feature branch is unchanged. After a fast-forward: `git reset` is **not** used;
  a revert commit or a new branch from the old tip is created instead.
- Blocks: Step 9 and every later round.

**Step 9: Hand-over to the in-repo work.** Owner: coordinator.
- Do: open the merged-repo backlog in this order: Muse **Round A**, then **Round B** (needs A1), **S2-lite**, then the
  **S5 adapter**, then **P1** as acceptance of the merged system. Each runs on a branch from the merged tip and ends in
  a new runtime tag; the old `D:\Muse` is archived read-only after P1, not before.
- Done: `MERGE_INVENTORY.md` shows M3 done and A2-A4, M4, M5 reassigned to the merged repo.
- Rollback: n/a (planning).
- Blocks: nothing.

Owners: steps 1, 9 coordinator; 2 Muse TL; 3-8 AFP TL (the lane contract names the AFP Tech Lead as owner of M3);
Muse TL reviews every change that touches sending, the ledger, recovery or integrity, and `config.py`.

## 8. Runtime pinning after the merge (supersedes D8; STUDIO_ARCHITECTURE §8)

- **Tag.** An annotated tag `studio-rt-<yyyymmdd>-<n>` on the merged repo, made by the AFP Tech Lead after the full
  `studio test`, scanner and (for sending code) a B14 offline parity run (§7 step 6). The import tag `muse-v1.0-r15` is kept as
  provenance only. A runtime tag is local; pushing it is the Owner's call.
- **Tree.** `studio runtime build <tag>`: `git worktree add --detach C:\film-work\_rt\<tag> <tag>`, made read-only for
  the lane user by ACL where possible; **never** the dev worktree or a dirty tree. No `data/`, `.env`, cookies or
  accounts file exists in it (scanner check at build time).
- **Interpreter and venv: dependencies only, code from the tree.** A venv beside the tree
  (`C:\film-work\_rt\<tag>.venv`, a **sibling** of the tree, not inside it), created with the pinned Python and populated **only** with third-party packages:
  `uv pip install -r constraints/runtime.txt` (the fully pinned list for the `qc,muse` extras). **The project itself is
  not installed** into that venv, so there is no second copy of `film_pipeline`, `film_studio` or `muse_studio` in
  `site-packages`; the code runs from `PYTHONPATH=<tree>\src`. The check asserts that no `film-studio` distribution
  exists in the venv and that no package of ours resolves outside the tree. (A wheel install of the project remains a dev
  and packaging check, §3; it is never a runtime.)
- **Browser.** Muse drives Chromium through Playwright; `pip freeze` does not cover that executable. Step 4 records which
  executable `headless_muse_client` launches (bundled Playwright Chromium or an installed Chrome channel). The runtime
  build installs it into a path owned by the runtime (`PLAYWRIGHT_BROWSERS_PATH=<tree>\browsers`) when it is the bundled
  one, records its revision and the sha256 of the executable in the manifest, and runs an **offline launch check**
  (headless start on `about:blank`, no profile, no network) before the tag is accepted. Profile data stays in
  `MUSE_DATA_DIR`.
- **Manifest (`runtime_manifest.json`, written at build, hashed).** It records: the tag name, the **tag object id**
  (`git rev-parse <tag>`), the commit id, the root tree id, a `source_sha256` (sha256 over sorted `(path, file sha256)` of the
  **tracked** files of the commit, read from `git ls-tree -r <commit>` for `src/`, `pyproject.toml` and `constraints/`;
  generated caches such as `__pycache__` are excluded, the launch sets `PYTHONDONTWRITEBYTECODE=1`, and **any importable
  file (`.py`, `.pyd`, `.dll`) inside the source tree that is not in the tracked list is itself a mismatch**; the venv is
  outside the tree and is covered by the venv fingerprint, not by this rule), the Python version and executable sha256, the venv
  fingerprint (sha256 of the sorted `pip freeze`), the browser revision and executable sha256. The manifest's sha256 is
  `runtime_manifest_sha256`; each film and each job request records it together with the tag and commit (a field added
  to contract v8.1, §6).
- **Tags are immutable.** A runtime tag is never moved, re-made or deleted. A tag whose object id differs from the recorded
  one is an error; a changed or failed runtime is always a **new tag name**. A failed or abandoned tag is **retired**: it
  is kept and listed in `docs/production/RETIRED_RUNTIME_TAGS.md` with the reason, so its name is never reused.
- **Launch.** The AFP lane starts `python -m muse_studio.pool_runner ...` with that venv's interpreter, `cwd` = the
  runtime tree, `PYTHONPATH=<tree>\src`, `STUDIO_RUNTIME_MANIFEST=<manifest path>` and `MUSE_DATA_DIR`, `MUSE_HALT_FILE`,
  `MUSE_LEASES_FILE`, `AFP_STATE_DIR` from the supervisor. The lease token goes only on stdin (contract §5, §14 Round B);
  it never enters the tree or job dir.
- **Verification runs twice, before spawn and inside the child (replaces the contract D8 check).**
  1. *Before spawn* (`studio runtime check`, AFP side): the manifest hash equals the one recorded for the film/request; the
     tag object id and commit still equal the recorded ones; the tree is clean (`git status --porcelain` empty for the
     worktree) and the recomputed `source_sha256` equals the manifest; the interpreter, venv fingerprint and browser
     hash equal the manifest. Any mismatch: no spawn, a JSON error, no send.
  2. *Inside the child* (`muse_studio/_runtime_bootstrap.py`, the first statement of `pool_runner.py`, before `config.py` or `AccountManager` is imported): it recomputes
     `source_sha256` over the tree it was loaded from, checks the interpreter path and version, and checks **import
     origins**: for every module already in `sys.modules` whose name starts with `muse_studio`, `core`, `film_pipeline`
     or `film_studio` (both Muse aliases are covered whichever is loaded), `__file__` lies inside the runtime tree, never in
     a dev tree or an installed copy elsewhere; it repeats the check once after the lane's imports finish and before the
     first account is read. A mismatch exits non-zero before any account,
     browser or send code runs. Modified source leaves the commit id unchanged but changes `source_sha256`, which is why
     the hash, not the tag name, is the identity.
  3. Round A (post-merge) copies the verified identity into `lane_result.json` (`muse_tag`, `muse_commit`,
     `runtime_manifest_sha256`); in M3 the bootstrap's result is checked by the drills below.
- **Wrong-tree drills (step 6).** Each must fail closed with no send: a tree with one modified file; a moved/re-made tag;
  a different interpreter; a `PYTHONPATH` pointing at the dev tree; a changed browser executable; an extra importable file in the tree; a
  `film-studio` copy in `site-packages`; **lane mode with the manifest unset or wrong** (refused before any account read;
  the drill uses a scratch data dir with an access-tracked decoy store and asserts it was never opened).
- **One tag for both halves.** AFP code (broker, job rows, intake) and Muse code (the subprocess) now come from one
  commit, so a runtime tag pins both. The AFP orchestrator process may run from the dev tree during development; for
  a real film the whole `studio` process also runs from the runtime tag.
- **A change** to any code in the runtime tree means a new tag, a new tree and a new manifest, plus the B14 re-run.
  The old tree stays until the last film on it finishes (§11 of the architecture: a film finishes on the runtime it
  started on). Trees are removed only by the Owner's or the coordinator's decision after a look.
- **Standalone use of the dev tree** for real sends ends when P1 passes (D5 of the architecture). Until then the
  single-mode scope freeze of the lane contract holds.

## 9. Risks and open items

| # | Risk | Control |
|---|---|---|
| R1 | A secret reaches git history (profiles, cookies, accounts, `.bak`). | Allow-list filter; §2.2 scanner at four points (Muse index before M6, source history, filtered export, staged merge result) plus every runtime tag; path-only, hash-verified data move that keeps the source; an unexplained hit stops the merge. |
| R2 | Silent behaviour change in Muse's send/ledger/recovery code. | Verbatim import; content-diff gate; step-2 baseline vs later reruns; Muse TL reviews every touching change; B14 parity compared on normalized custody records, not counts. |
| R3 | Two import worlds in Muse (`core.x` and `muse_studio.core.x`) now sit beside AFP in one repo and one venv. | `core` is only on `sys.path` inside Muse processes; AST test forbids AFP importing `core`; cleanup is post-P1. |
| R4 | A test or tool writes the production halt, leases or accounts again (L37). | Shared isolation plugin at import time; every resolver validates its destination against the test root (defaults, overrides, constructors, subprocesses); guard tests in both suites; canary stats around `studio test`. |
| R5 | `opencv` and dependency drift; `uv.lock` untracked means different machines resolve differently. | Headless only; `constraints/runtime.txt` committed; venv fingerprint recorded and checked; open item O1. |
| R6 | The data move interrupts something or loses profiles. | Quiet-time move, path-only, sha256-verified, source kept (renamed) until the Owner decides after P1, rollback refuses to overwrite a changed destination. |
| R7 | History import brings 227 MB fixture or film media. | Allow-list excludes them; B14 stays external with a manifest. |
| R8 | The merge branch drifts while sessions keep committing on `feature/drama-preprod-p0`. | Gate 0 freezes both repos; later AFP commits are merged into `studio/m3-merge` before Step 8, and a runtime-relevant change there forces a new runtime tag and re-run of the step-6 checks; no step starts on a dirty tree. |
| R9 | Contract v8 is read as changed because the tag is now in-repo. | Field names unchanged; v8.1 amendment in Step 7; Codex review of the amendment. |
| R10 | `filter-repo` is not available on this machine. | Fallback import (§2.3) with one provenance commit; history stays in the read-only archive. |

**Open items for the coordinator / Owner** (decisions that are not technical):
- **O1.** Track a lock file for reproducible installs? Standing rule says no `uv.lock`; this plan uses a text
  constraints file. Owner may overrule.
- **O2.** Rename of the GitHub repo and local folder to "Film Studio": after P1, Owner's call.
- **O3.** Push of the merged branch and of runtime tags: Owner only (reserved).

## 10. What this plan does not do

No code, no git operation in `D:\Muse`, nothing under `films/`, no send, no browser, no network. It defines no new
feature; Round A/B, S2-lite and S5 follow inside the merged repo (Step 9).

## M3 backlog: harvested from A8 and 88a99bee

Source: `D:\AI FILM MAKER\_archive\merge_triage\AFP_TRIAGE_20261121.md`. Branches are tagged `archive/<branch>`. These are backlog
items, not P1 scope (lane contract v8 scope freeze). Nothing here is ported yet.

Dirty diffs of the two old Muse worktrees are saved as `_archive\merge_triage\a8_muse-video-gateway.patch` and
`a8_muse-flight-pilot.patch` (git diff plus untracked-file sha256; film media not copied).

| # | Idea | Source | One line |
|---|---|---|---|
| B1 | Thread-bound claims | `muse_gateway.py` `dispatch(thread=, max_in_flight=)` | A claim binds to one exact `muse.ai/thread/<id>`; a second claim needs another thread and a free in-flight slot; a result from another thread is rejected. This is the piece behind contract section 15 decision 1 (thread URL capture deferred). |
| B2 | Operator-observed refusal close | `reconcile_failure`, `FailureResponse` | A visible terminal provider refusal with hashed evidence inside the request dir closes a claim as `FAILED_NO_OUTPUT`; never clears an UNKNOWN send, never retries. Compare with section 11 / M.3. |
| B3 | `interaction.py` empty-subject guard | `placement_sentences`, `OFF_FRAME` and gaze branches | Skip the "looks toward / eyes go past the lens" sentence when the shot has no subject (today it emits "'s eyes go..."). Small AFP bug fix with a 17-line test in the patch; independent of Muse. |
| B4 | Research docs as input to S5 and film-craft | `GEMINI_MUSE_AI_CONTINUITY_AND_PRODUCTION_RESEARCH.md`, `MUSE_CONTINUITY_AND_PROMPT_MASTERY.md` (untracked in `wt-muse-flight-pilot`) | Master keyframe + snapshot chaining against face drift, character-DNA prompting, camera control. Unreviewed agent claims: verify before use. Not in the patch file (untracked); read them in the worktree before it is archived. |

Not harvested: `tools/muse_browser_batch.mjs` (browser relay, superseded by the lane) and `ingest-zip` (the lane contract already
covers ZIP receipts).

### `88a99bee` `tests/test_production_integrity.py` (336 lines, 16 tests)

Verdict: **port needed, but only if the legacy runtime stays.** HEAD has no test with these names or topics (searched `tests/`:
release accounted once, assessed continuity contract, codec fallback, complete-graph export and trim, changed-source blocks next
stage, render failure keeps prior output, crash-after-acquisition resume, exhausted quota). Partial overlap only: audio-lane
decode checks in `tests/test_audio_lane_010.py`, editorial trim wording in `tests/test_narrative_compiler_021.py`, changed-source
in `tests/test_e2e.py`; none assert the same cases. The tests target the legacy v2-021/022 runner (`tools/run_v2_022_production.py`,
`audio_lane.py`, `rough_cut.py`, `narrative/continuity.py`) and import helpers from `test_v2_021_hardening` and `mutation_authority`.
Not checked: whether HEAD's copies of those `src` files already contain the `88a99bee` fixes (the file differs in 11 of 14 paths).
Decision for later: if the legacy runner is retired at M3, record "retired, not ported"; otherwise port the test after
checking the `src` fixes.

## Review record

- Round 1 (`_archive/m3_merge_plan/codex_out1.md`): REJECT, 7 High (scan order vs M6 commit; `send_halt` default path;
  guards on defaults only; Gate 0/M7 circularity; allowed-edit list could not deliver the gates; tag/freeze identity
  too weak; cross-volume move deleting the source on size checks) and 5 Medium. All fixed in v2.
- Round 2 (`codex_out2.md`): REJECT, 5 High (env-scrubbed child; guard did nothing without a manifest; non-editable install
  hid a second code copy; guard called after module-level imports; Step 8 scanned only the final tree) and 4 Medium. All fixed
  in v3 (§5.2 Popen wrapper, §6/§8 lane-mode bootstrap before imports, §8 dependencies-only venv and tracked-file manifest,
  Step 8 incoming-history scans, retired tags, B14 baseline and normalization).
- Stop rule reached after 2 rounds. v3 changes are **not independently re-reviewed**; the coordinator or the Step 7 review
  of the contract amendment should treat §8 as the part most worth a second look.
- Round 3 (`codex_out3.md`, verification only): R2 H1, H2, H4, H5 FIXED; H3 NOT FIXED (§3 still said to install the
  project into the lane venv) and one NEW High (the venv sat inside the runtime tree, so its installed files tripped the
  "untracked importable file" rule). Both fixed in v3.1 (§3 install mode is dependencies-only; the venv is a sibling
  `C:\film-work\_rt\<tag>.venv`). No round 4 by the coordinator's stop rule; v3.1 edits are not re-reviewed.
