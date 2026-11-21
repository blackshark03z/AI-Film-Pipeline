# Codex review r15b — fix report

All tests are in `muse_studio/tests/test_r15b_fixes.py` (tmp stores only; never the real halt, `~/.afp` or `accounts.json`).
Full suite result is at the bottom.

| # | Sev | Fix (`file:line`) | Test | Result |
|---|-----|-------------------|------|--------|
| 1 | HIGH | `core/config.py:16-21` — `ensure_directories()` only creates directories; `accounts.json` is created only by `AccountManager._ensure_storage()` (lock + create-exclusive) | `test_ensure_directories_does_not_create_accounts_file` | PASS |
| 2 | HIGH | `core/account_manager.py:402` new atomic `increment_account`; `:523-538` bulk import passes only supplied fields; `core/headless_muse_client.py:614` uses the atomic increment | `test_bulk_import_does_not_overwrite_fields_it_did_not_supply`, `test_increment_account_is_atomic_under_threads` | PASS |
| 3 | HIGH | `core/parallel_pool_engine.py:415-418` — `_send_allowed()` is False once `_integrity_stop` is set | `test_send_allowed_false_after_integrity_stop` | PASS |
| 4 | HIGH | `cli.py:975-999` promote-take re-checks the CURRENT exclusion list (`CLIP_INTEGRITY_FAILED`, never deletes); stale-audit readers filtered: `cli.py:220` (sync), `:1069` (package), `:1162` (assemble); `core/autoprod_orchestrator.py:93,120` checkpoint reader | `test_promote_take_refuses_an_excluded_clip_and_deletes_nothing`, `test_assemble_drops_clips_excluded_after_the_audit`, `test_render_checkpoint_does_not_revive_an_excluded_clip` | PASS |
| 5 | HIGH | `core/batch_packager.py:505` (`parse_keyframe_receipt`), `:717` (`unpack_keyframe_result`: receipt SHA + exclusion + fail-closed list); `core/parallel_pool_engine.py:110` (`kf_result_image`: same checks) | `test_unpack_keyframe_result_receipt_sha_mismatch_is_not_verified_and_kept`, `test_unpack_keyframe_result_matching_receipt_verifies`, `test_kf_result_image_rejects_receipt_mismatch_and_excluded_names` | PASS |
| 6 | HIGH | `core/queue_dispatcher.py:243` `_quarantine_rejected_clip` (move to `qc_rejected/`, unique name, file kept on failure); the REJECT branch no longer calls `unlink()` | `test_qc_reject_moves_clip_to_quarantine`, `test_qc_reject_failed_move_leaves_the_file`, `test_dispatcher_source_never_unlinks_a_rejected_clip` | PASS |
| 7 | HIGH | `core/parallel_pool_engine.py:1471` ledger entry flagged `integrity_failure`; `:1162-1163` the release loop never auto-releases a flagged entry (only `MANUAL`) | `test_integrity_unpersisted_entry_is_not_auto_released_next_run` | PASS |
| 8 | MED | `core/batch_packager.py:458` single fail-closed `read_integrity_failed -> (ok, names)`; callers: `cli.py:89`, `batch_packager.py:717`, `parallel_pool_engine.py:110` | `test_read_integrity_failed_validates_schema_and_fails_closed` (8 cases incl. `null`), `test_record_integrity_failure_refuses_to_overwrite_an_unreadable_list` | PASS |
| 9 | HIGH | `core/send_halt.py:69` `_guard_not_production` (real halt, its `.lock`, anything in `~/.afp`) shared by `halt_path()`, new `afp_halt_file()` (`:92`, used for `AFP_HALT_FILE`), `send_stop`, `clear_halt` | `test_send_halt_guard_refuses_real_halt_and_afp_paths_under_pytest` | PASS |
| 10 | LOW | `cli.py:1142-1147` `run-pool` returns 5 on `INTEGRITY_UNPERSISTED`; `docs/AFP_MUSE_LANE_CONTRACT.md` §9 exit-5 row | `test_run_pool_returns_5_on_integrity_unpersisted`, `test_lane_contract_documents_exit_5` | PASS |

`muse_studio/tests/test_m2_never_delete.py`: two assertions switched to `read_integrity_failed` (the old helpers are gone).

## Phase 2 — secret scanner hang + `total_rendered` race

| # | Fix (`file:line`) | Test | Result |
|---|-------------------|------|--------|
| A1 | `tools/secret_scan.py:143-157` — the hang was quadratic regexes, not blob size: every open-ended `{n,}` (cookie, bearer, basic, vendor keys, api-key value, email) and the unanchored lazy `_NAME` prefix rescanned a long word run from each start. All quantifiers are now bounded or exact, `_NAME` has a start-boundary lookbehind and a possessive suffix, `RE_EMAIL` a lookbehind; 2 MB of `x` scans in 0.7 s | `test_scan_text_is_linear_on_long_runs[x_run, at_sign_run]` (both under 2 s) | PASS |
| A2 | `tools/secret_scan.py` `RE_CRED_BARE` — `?` before `$`: a CRLF config line (`password=...`) was missed (old bug, hidden by the hang) | `test_crlf_config_line_is_still_a_credential`, `test_long_names_and_emails_still_detected` | PASS |
| A3 | `tools/secret_scan.py:187` `_literal_value_ok` — a numeric value on a `*tokens` name is a count, not a credential (`max_tokens = "4096"` fired; old bug, hidden by the hang) | `test_common_non_secrets_do_not_fire[max_tokens = "4096"]` | PASS |
| A4 | `tools/secret_scan.py:424` `scan_history` counts every tree entry in `files` (before the same-blob dedupe), so `blobs_scanned < files` holds (old bug, hidden by the hang) | `test_history_reports_one_blob_once_however_many_commits_hold_it` | PASS |
| A5 | `tools/test_secret_scan.py:27,40` fixtures built with `j(...)` so the scanner's own self-scan stays clean | `test_the_scanner_and_its_tests_are_clean` | PASS |
| B | `core/browser_worker.py:272` new `_record_render()` (used at `:245`, `:293`): `increment_account(id, "total_rendered", 1)` + `update_account(last_used=...)` | `test_browser_worker_render_count_loses_no_concurrent_increment` (stale snapshots + 4 threads) | PASS |

`python -m pytest tools/test_secret_scan.py -q` (no timeout wrapper): **125 passed** in 90 s. `python tools/secret_scan.py --staged D:\Muse`: exit 0, 0 hits.

Deviation from the brief: oversize text blobs are still content-scanned (capped at `CONTENT_SCAN_CAP`); the existing test
`test_history_scans_text_larger_than_the_limit_for_content_too` requires it, and with the regexes fixed it costs under 1 s per 2 MB.

## Phase 3 — Codex r15c (10 findings, all confirmed in the code)

Muse tests: `muse_studio/tests/test_r15c_fixes.py`. Scanner tests: `tools/test_secret_scan.py` (end of file, "r15c").

| # | Sev | Fix (`file:line`) | Test | Result |
|---|-----|-------------------|------|--------|
| 1 | HIGH | `core/batch_packager.py:476,484` new `batch_dir_of_clip` + `clip_currently_excluded(clip, qc_rec)`: the canonical `verified_clips/<sid>.mp4` is judged through its source batch (`per_shot_qc.clip_path`), the current exclusion list (unreadable = excluded) and the recorded `copy_sha256`; callers `cli.py:89` (`_clip_integrity_bad`, qc-audit and promote-take record `copy_sha256`) and `core/autoprod_orchestrator.py:93,116` | `test_canonical_copy_is_trusted_while_its_source_is_clean`, `test_canonical_copy_rejected_when_its_source_batch_clip_is_excluded` (incl. `assemble` -> `NO_QC_PASSED_CLIPS` and the render checkpoint), `..._when_the_source_exclusion_list_is_unreadable`, `..._when_the_copy_no_longer_matches_its_recorded_sha` | PASS |
| 2 | HIGH | `core/queue_dispatcher.py:27,320,377` — a failed quarantine raises the non-retry `ClipPreservationError`; the shot ends FAILED (`CLIP_PRESERVATION_FAILED`) and is never requeued, so nothing overwrites the kept clip | `test_failed_quarantine_stops_the_shot_and_the_next_attempt_never_overwrites` (through the dispatcher, several ticks), `test_successful_quarantine_gives_every_take_its_own_file` | PASS |
| 3 | HIGH | `core/send_halt.py:82` new `_project_halt_path`; `publish_halt` (checked before any write), `load_halt` and `clear_halt` all go through `_guard_not_production` | `test_project_dir_halt_paths_refuse_the_real_data_dir_and_afp` (real data dir and `~/.afp`; real halt file unchanged; a scratch project dir still works) | PASS |
| 4 | HIGH | `core/batch_packager.py:620` `unpack_batch_result` reads the current exclusion list: listed names are not verified (file kept), an unreadable/malformed list fails the whole batch (`integrity_list_unreadable`) | `test_unpack_batch_result_excludes_listed_names_and_fails_closed_on_a_bad_list` | PASS |
| 5 | HIGH | `tools/secret_scan.py:492,500` `os.walk(..., onerror=walk_error)` raises `ScanError("E_TREE_LIST ...")` -> exit 2; stat/read errors are `E_TREE_STAT` / `E_TREE_READ` | `test_tree_mode_fails_closed_when_a_folder_cannot_be_listed` | PASS |
| 6 | HIGH | `tools/secret_scan.py:376` content cache keyed `(sha, is-code-file)` | `test_one_blob_is_scanned_per_file_type_not_once_per_sha` (same blob as `a.py` and `b.ini`, staged and history) | PASS |
| 7 | MED | `tools/secret_scan.py:99` `RE_COOKIE_EXPORT_NAME` + `path_rules` (`cookies.json`, `cookies.txt`, `session.txt`, `session_state.json.tmp`, hidden `.accounts.json.tmp.<pid>.<thread>`); `:260` new rule `content-cookie-export` (a `{name, value, domain}` object with a non-placeholder value) | `PATH_CASES` (+6 rows), `CONTENT_CASES` (`cookiejson`), `test_cookie_export_json_is_found_by_content_and_a_plain_object_is_not`; the innocent-name list still passes | PASS |
| 8 | MED | `tools/secret_scan.py:528,551+` `_reason_is_unsafe`: an allow reason that hits a content rule, looks like `name=value`, or holds a 24+ char opaque word with a digit is refused (`E_ALLOW_REASON`) before it can reach the Markdown report | `test_allow_reason_that_looks_like_a_credential_is_refused[4 cases]`, `test_allow_reason_in_plain_words_is_still_accepted` | PASS |
| 9 | MED | `tools/secret_scan.py:291,293,305` git failures print only `E_GIT: git <op> failed (exit N)`; allow-file errors print only `E_ALLOW_READ/FORMAT/RULE/REASON` + the line number (no raw rule, no stderr, no repo path) | `test_errors_never_echo_a_raw_allow_rule_or_git_stderr`; `test_errors_do_not_echo_content` adjusted (its line-1 reason is now prose) | PASS |
| 10 | MED | `tools/secret_scan.py:422` `_unwalked_blobs`: `git rev-list --objects --all` + `cat-file --batch-check` (via the new `stdin=` of `_git`); blobs no commit tree holds are scanned as commit `ref-only` | `test_history_scans_a_blob_that_only_a_ref_points_at` | PASS |

All 10 reproduced by reading the code (no `onerror`, SHA-only cache key, `rev-list --all` lists commits only, raw rule/stderr interpolated into `ScanError`, no guard on the project paths, unpacker never called the exclusion helper). Finding 8 note: Codex said "Markdown, not JSON": the reason is refused instead of redacted, so nothing unchecked is ever written.

`python -m pytest tools/test_secret_scan.py -q` (no timeout wrapper): **142 passed** in 132 s. `python tools/secret_scan.py --staged D:\Muse`: exit 0, 0 hits (the self-scan stays clean).

## Phase 4 — Codex r15d (3 items, final round)

Muse tests: `muse_studio/tests/test_r15d_fixes.py` (4 tests). Scanner test: `tools/test_secret_scan.py` (end of file, "r15d"). Each test failed before its fix and passes after.

| Item | Sev | Fix (`file:line`) | Test |
|------|-----|-------------------|------|
| A. qc-audit blessed a drifted canonical clip | HIGH | `cli.py:666` `_copy_integrity_bad`: a canonical whose SHA differs from the `copy_sha256` of the prior record is excluded from selection even when its source batch is clean (quarantined, kept; failed entry keeps `reason: INTEGRITY_FAILED` and adds `cause: CANONICAL_SHA_MISMATCH`). `cli.py:892` the winner write re-copies only from a verified source and an existing canonical that wins keeps its recorded `copy_sha256`: the SHA is never overwritten to bless a copy | `test_qc_audit_does_not_bless_a_drifted_canonical_copy`, `test_qc_audit_drops_a_drifted_canonical_when_no_verified_source_is_left` |
| B. promote-take fallback lost the source batch | HIGH | `cli.py:1032` `_promote_take` derives the provenance batch clip and refuses with `PROVENANCE_UNKNOWN` when none exists (nothing copied, audit untouched); the record carries `clip_path` and `source_clip_path` = the batch clip, and `copy_source_path` = the file actually copied. `cli.py:99` `_clip_integrity_bad` and `core/batch_packager.py:484` `clip_currently_excluded` check both `clip_path` and `source_clip_path`. `cli.py:867` the kept promotion keeps both fields over later audits | `test_promote_take_fallback_keeps_the_source_batch_provenance`, `test_promote_take_refuses_when_no_batch_provenance_can_be_established` |
| C. long cookie-array JSON missed | MED | `tools/secret_scan.py:212,288` `_json_has_cookie_object`: JSON-looking text is parsed and any dict (any depth, iterative walk, linear time) with a non-empty `name`, a non-empty `domain` and a non-placeholder `value` of 8+ chars is flagged `content-cookie-export`; the regex path stays as the fallback; values are never printed | `test_long_cookie_array_json_is_found_at_a_neutral_name` (2,160-char value at `exports/c.json` and nested `{cookies:[...]}` flagged; no-domain and placeholder objects not; value not in the findings) |

Results: `muse_studio/tests` **351 passed** (6 min); `tools/test_secret_scan.py` **143 passed**; `python tools/secret_scan.py --staged D:\Muse --allow tools/secret_scan_allow.txt`: 0 hits (17 explained fixtures allowed).

## Not done (out of scope)
- Keyframe `kf_receipt.json` is trusted only as far as its own SHA; there is no cross-check against the remote side.

## Full suite
Phase 3 (r15c) full suite: `PYTHONIOENCODING=utf-8 python -m pytest muse_studio/tests -q --tb=short -rs`: **347 passed, 0 failed, 0 skipped** (488 s). The load-sensitive v50 wall-clock test passed this run.

`PYTHONIOENCODING=utf-8 python -m pytest muse_studio/tests -q --tb=short -rs`: **338 passed, 1 failed** (339 tests, 409 s), after the phase-2 test was added.
The failure is `test_v50_speed_and_quality_upgrades.py::test_v50_qc_engine_speed_and_in_memory_parity`, a wall-clock assert (`elapsed < 1.2` s, got 1.40 s); alone it passes one run and fails the next, so it is load-sensitive. It does not touch any file changed here.
Phase 1 result before that test was added: 338 passed, 0 skipped (368 s).
