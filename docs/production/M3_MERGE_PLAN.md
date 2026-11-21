# M3 code-merge plan: AFP + Muse into one repository, "Film Studio"

**Status: DRAFT v1, 2026-11-21.** Design only. Nothing in this document has been executed.
- Written by session `m3-merge-plan` for the coordinator. Basis: `STUDIO_ARCHITECTURE.md` §8, §11 (roadmap change of
  2026-11-21, non-regression rule), `MERGE_INVENTORY.md`, the lane contract v8
  (`docs/production/muse/AFP_MUSE_LANE_CONTRACT.md` §6, §12), `OWNER_POLICY.md`, AFP `pyproject.toml`, and a read-only
  look at `D:\Muse` (layout, `requirements.txt`, `core/config.py`, `tests/conftest.py`, `CLAUDE.md`).
- Review: Codex `gpt-6.1-sol`, read-only; the verdict is recorded at the end.
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

- `pyproject.toml` `[project.scripts]`: `studio = "film_studio.cli:main"` and `afp-film = "film_pipeline.cli:main"`.
  Both reach the same parser. `film_studio.cli.main` sets `prog="studio"`, then calls `film_pipeline.cli.main`; every
  existing `afp-film <subcommand>` works unchanged under `studio` (`studio broker ...`, `studio production ...`).
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

- **Code change in Muse (the only one M3 needs, step 4).** `core/config.py` today derives
  `BASE_DIR`/`DATA_DIR` from `__file__` and calls `ensure_directories()` at import (it also writes `accounts.json`
  as `[]` when absent). It becomes: `DATA_DIR = Path(os.environ.get("MUSE_DATA_DIR") or default)`, with:
  - no data directory is ever created inside the code tree;
  - under pytest, a `MUSE_DATA_DIR` that is unset or resolves to the production default raises (same pattern as
    `send_halt.halt_path()` raising `ProductionHaltPathInTest`);
  - `MUSE_HALT_FILE` and `MUSE_LEASES_FILE` keep their override semantics and default **inside** `MUSE_DATA_DIR`.
  This is the contract's already-named NEW `MUSE_DATA_DIR` (§12); it is delivered in this merge because the pinned
  tree must never contain secrets.
- **One-time data move (step 6).** After the last standalone Muse process is stopped, the AFP Tech Lead **moves**
  (not copies) the data dir from `D:\Muse\muse_studio\data` to `MUSE_DATA_DIR`, by a script that works on paths only:
  it moves directories and files without opening or printing `accounts.json`, `profiles/` or cookie files, and logs
  only counts and byte sizes. Same volume, so a rename keeps it atomic; otherwise copy-verify-by-size, then delete
  after the Owner's look. The `.bak_*` files travel with the data and are never committed.
- **Windows.** Short paths for the runtime tree stay (MAX_PATH, M8). `MUSE_DATA_DIR` default is short enough for
  Chromium profile paths; `studio runtime check` verifies the longest known profile path is under the limit.

## 2. History import method (D5)

### 2.1 Preconditions (from MERGE_INVENTORY M6, M7)

- Muse today: one baseline commit plus a dirty tree; `muse_studio` is untracked. M6 (Muse Tech Lead) puts
  `muse_studio` under version control with `.gitignore` for secrets (the 31 staged scratch deletions and the modified
  `.gitignore` included), after the Owner's confirmation of the git rule in the Muse session. M7 tags
  `muse-v1.0-r15` after r15, PRE-TAG #11 and the accounts lock (M1-M3, M6).
- The import source is **exactly that tag**. A dirty or untagged tree is not imported.

### 2.2 Secret scan before the first commit (Muse TL runs, AFP TL verifies the report)

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
4. The same scanner runs again **on the merge result** (step 3 gate) and on every runtime tag (§8).

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
3. `git merge --allow-unrelated-histories --no-ff refs/imports/muse/<tag>` on `studio/m3-merge`. No file of AFP
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
- **Package data.** `package-data` for `muse_studio` (`static/*`, `scripts` stay as files) is added to
  `[tool.setuptools.package-data]`; `muse_studio` has no `__init__` data beyond that.
- **Install modes.** Dev: `uv pip install -e ".[dev,qc,muse,flow]"`. Lane runtime: a non-editable install from the
  runtime tag into its own venv (§8): `uv pip install --constraint constraints/runtime.txt ".[qc,muse]"`.
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
  is collected, and sets for the whole session:
  - `AFP_STATE_DIR`, `AFP_HALT_FILE` → a session temp dir (`afp/`);
  - `MUSE_DATA_DIR`, `MUSE_HALT_FILE`, `MUSE_LEASES_FILE` → a session temp dir (`muse-data/`); the Muse accounts file
    resolved from it is a scratch file, never the production one;
  - unset `AFP_HALT_FILE` overrides that point outside the temp dir.
- An autouse function-scoped fixture repoints these per test (as today), and resets `send_halt._reset_memory()` for
  both module identities (`core.send_halt` and `muse_studio.core.send_halt`).
- **Hard guards in product code, not only in tests** (extends what exists):
  - `send_halt.halt_path()` already raises under pytest when `MUSE_HALT_FILE` is unset. Add the same guard for
    `MUSE_DATA_DIR` (config, §1.4), `AFP` `state_dir()` (`production/halt.py:56`) and the lane leases path.
  - A guard fires when the resolved path equals or is inside the production default path, even if the variable is set.
- **A test can no longer reach the production path by accident**, and the guard test proves it:
  `tests/test_isolation_guard.py` (AFP suite) and `src/muse_studio/tests/test_isolation_guard.py` (Muse suite) each
  assert all five paths resolve under the session temp dir, and each assert that unsetting the variable raises
  instead of falling back.
- Subprocess-based tests inherit the isolated environment; a test that scrubs the environment (`env={...}`) must pass
  the isolated paths explicitly. Step 5 greps both suites for `env=` calls that drop them.

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
- **Allowed Muse edits in M3, exhaustive:** `core/config.py` and its direct readers of `DATA_DIR`/`ACCOUNTS_FILE`/
  `PROFILES_DIR` (data dir resolution, §1.4); `tests/conftest.py` (reduced to the shared plugin plus Muse-only fixtures);
  `pool_runner` `lane_result.json` field values (§8). Each is reviewed by the Muse Tech Lead (rule: §11 of
  STUDIO_ARCHITECTURE; any change touching sending, the ledger, recovery or integrity needs its review).
- **Contract field names stay.** `muse_tag` and `muse_commit` keep their names in `batch_request.json` and
  `lane_result.json` (contract v8, §5, §8). Their **values** become the in-repo runtime tag and the repo commit. This is
  recorded as a contract v8.1 editorial amendment (step 7), so both Tech Leads agree on one reading.
- **Sends stay paused.** No step sends anything. Film runs resume only after the merged system's P1.
- **Flow films (film03-film08) and their provider code** keep their current runtime; nothing is migrated.

## 7. Ordered steps (≤ 10)

### Gate 0: precondition (coordinator; not a step)

The merge starts only when all of these are true and recorded in `MERGE_INVENTORY.md`: **A1** (S1 addendum, Codex
round 8 ACCEPT), **M1** with fixes a, b and c (r15 stop-all, Codex ACCEPT), **M2** (PRE-TAG #11, no `src.unlink()`),
**M3** (accounts lock), **M6** (git baseline) and **M7** (tag `muse-v1.0-r15`, secret scan clean); both repos clean
(no WIP, no open lease, no unresolved child, no live lane); the pre-M3 housekeeping rows (A5 push by the Owner,
A8-A10, M10-M13) decided. M8/M9 (P0/BIKER) are stopped or finished and the data dir is quiet.

### Steps

**Step 1: Freeze and import-source check.** Owner: coordinator with both Tech Leads (AFP TL records).
- Do: Gate 0 verified by reading, not by reports; `git status` clean in both repos; tag `muse-v1.0-r15` points at the
  commit the P0 hash list refers to; no process with a lane lease.
- Done: a signed checklist in `docs/production/M3_MERGE_CHECKLIST.md` (commit hashes of both repos, tag SHA).
- Rollback: none needed (read-only). Cancel the merge.
- Blocks: Step 2.

**Step 2: Muse history secret scan.** Owner: Muse TL runs; AFP TL verifies.
- Do: throwaway clone of the tag, the §2.2 scan over all reachable history, report to `_archive/m3_merge_plan/`.
- Done: zero unexplained hits; the scanner script is committed in the merge branch under `tools/` (step 3).
- Rollback: delete the throwaway clone. Fix by filtering in the clone, never in `D:\Muse`.
- Blocks: Step 3.

**Step 3: Import Muse (code and docs).** Owner: AFP TL.
- Do: branch `studio/m3-merge` in a new worktree; §2.3 filter + merge; fix `.gitignore`; run the scanner on the merge
  result; run the Muse rule tests from `src/muse_studio` with the old `conftest` (green **before any edit**).
- Done: merge commit with `IMPORT_PROVENANCE.md`; scan clean on the merge result; content diff against the tag shows
  only planned moves; rule tests green; AFP suite unchanged.
- Rollback: abandon the branch (nothing else changed; `git worktree remove`, branch delete after a look).
- Blocks: Steps 4-9.

**Step 4: One package, one environment.** Owner: AFP TL, Muse TL reviews `config.py`.
- Do: new `pyproject.toml` (§3), `film_studio` skeleton, `config.py` with `MUSE_DATA_DIR`, import-audit of third-party
  modules, `constraints/runtime.txt`, `studio` and `afp-film` scripts.
- Done: fresh-venv install in both modes; `studio --help`, `afp-film --help`, `python -m muse_studio.cli --help`
  and the AST import-boundary test pass; Muse rule tests green with `MUSE_DATA_DIR` set; no data dir created inside
  the tree.
- Rollback: revert the step's commit; Step 3 state stays valid.
- Blocks: Step 5.

**Step 5: Test unification and isolation.** Owner: AFP TL; Muse TL reviews the Muse side.
- Do: `film_studio.pytest_isolation`, guard tests, `tools/run_all_tests.py`, `studio test`, canary check, reduced Muse
  `conftest.py`; one deliberate negative drill (a temp test that tries to resolve each production path) in a scratch
  clone to prove the guards fire.
- Done: `studio test` is green end to end; the canary list is unchanged; the negative drill fails as designed; the guard
  tests pass in both suites.
- Rollback: revert; each suite still runs alone with its own conftest.
- Blocks: Step 6 (the data move needs the guard first).

**Step 6: Runtime tag and data move.** Owner: AFP TL; Muse TL verifies lane behaviour on the tag.
- Do: (a) stop all Muse processes and confirm no live lease; (b) the §1.4 one-time **move** of `muse_studio/data` to
  `MUSE_DATA_DIR`, path-only, no content read; (c) `studio runtime build` creates the tag
  `studio-rt-<yyyymmdd>-1`, the detached worktree at `C:\film-work\_rt\...` and its venv; (d) `pool_runner --simulate`
  on the B14 offline fixture from the runtime tree with `MUSE_DATA_DIR`; (e) `lane_result.json` carries tag, commit and
  fingerprint (§8).
- Done: B14 offline parity equals the Muse baseline (shot, receipt and ledger counts equal, no send); `studio runtime
  check` passes; the runtime tree contains no secret (scanner clean, `accounts.json` absent from the tree).
- Rollback: move the data dir back to `D:\Muse\muse_studio\data` (same script, reversed); the old Muse tree is still
  intact, so standalone Muse runs again; remove the runtime worktree and tag (a tag is local; no push).
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
- Do: `studio test` on the merge branch (both suites + canaries); Codex read-only review of `<merge base>..HEAD` over
  the product-code diff (config, `film_studio`, pyproject, isolation); scan on the final tree.
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
  `studio test`, scanner and (for sending code) a B14 offline parity run. The import tag `muse-v1.0-r15` is kept as
  provenance only. A runtime tag is local; pushing it is the Owner's call.
- **Tree.** `studio runtime build <tag>`: `git worktree add --detach C:\film-work\_rt\<tag> <tag>`, made read-only for
  the lane user by ACL where possible; **never** the dev worktree or a dirty tree. No `data/`, `.env`, cookies or
  accounts file exists in it (scanner check at build time).
- **Interpreter and venv.** A venv beside the tree (`C:\film-work\_rt\<tag>\.venv`), created with the pinned Python and
  `uv pip install --constraint constraints/runtime.txt ".[qc,muse]"` (non-editable). Its **fingerprint**
  (`sha256` of the sorted `pip freeze` + Python version) is written to `runtime_manifest.json` in the tree dir at build time.
- **Launch.** The AFP lane starts `python -m muse_studio.pool_runner ...` with that venv's interpreter, `cwd` = the
  runtime tree, `PYTHONPATH=<tree>\src`, and `MUSE_DATA_DIR`, `MUSE_HALT_FILE`, `MUSE_LEASES_FILE`, `AFP_STATE_DIR`
  from the supervisor. The lease token goes only on stdin (contract §5, §14 Round B); it never enters the tree or job dir.
- **Check (replaces the contract D8 check).** `pool_runner` records `muse_tag` (= the runtime tag), `muse_commit`
  (= tree commit) and `runtime_fingerprint` in `lane_result.json`, and refuses to run (exit non-zero, no send) when
  the tag, commit or fingerprint differs from the request's `muse_tag`/runtime manifest. The AFP side also verifies
  before spawn (`studio runtime check`). A film records the runtime tag it started with; the daemon or CLI refuses to
  run it on a different tag unless the Tech Lead migrates it (STUDIO_ARCHITECTURE §8, unchanged).
- **One tag for both halves.** AFP code (broker, job rows, intake) and Muse code (the subprocess) now come from one
  commit, so a runtime tag pins both. The AFP orchestrator process may run from the dev tree during development; for
  a real film the whole `studio` process also runs from the runtime tag.
- **A change** to any code in the runtime tree means a new tag, a new tree and a new fingerprint, plus the B14 re-run.
  The old tree stays until the last film on it finishes (§11 of the architecture: a film finishes on the runtime it
  started on). Trees are removed only by the Owner's or the coordinator's decision after a look.
- **Standalone use of the dev tree** for real sends ends when P1 passes (D5 of the architecture). Until then the
  single-mode scope freeze of the lane contract holds.

## 9. Risks and open items

| # | Risk | Control |
|---|---|---|
| R1 | A secret reaches git history (profiles, cookies, accounts, `.bak`). | Allow-list filter, §2.2 scanner on source history, merge result and every runtime tag; path-only data move; step 2 stops the merge on an unexplained hit. |
| R2 | Silent behaviour change in Muse's send/ledger/recovery code. | Verbatim import; content-diff gate; rule tests before and after each step; Muse TL reviews every touching change; B14 parity on the runtime tree. |
| R3 | Two import worlds in Muse (`core.x` and `muse_studio.core.x`) now sit beside AFP in one repo and one venv. | `core` is only on `sys.path` inside Muse processes; AST test forbids AFP importing `core`; cleanup is post-P1. |
| R4 | A test or tool writes the production halt, leases or accounts again (L37). | Shared isolation plugin at import time, guards in product code, guard tests in both suites, canary stats around `studio test`. |
| R5 | `opencv` and dependency drift; `uv.lock` untracked means different machines resolve differently. | Headless only; `constraints/runtime.txt` committed; venv fingerprint recorded and checked; open item O1. |
| R6 | The data move interrupts something or loses profiles. | Quiet-time move, path-only, reversible, old tree left until P1 (step 6 rollback). |
| R7 | History import brings 227 MB fixture or film media. | Allow-list excludes them; B14 stays external with a manifest. |
| R8 | The merge branch drifts while sessions keep committing on `feature/drama-preprod-p0`. | Gate 0 freezes both repos; later AFP commits are merged into `studio/m3-merge` before Step 8; no step starts on a dirty tree. |
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
