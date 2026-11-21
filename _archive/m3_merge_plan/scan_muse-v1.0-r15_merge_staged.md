# Secret scan: staged

- target: `D:\AI FILM MAKER\wt-m3-merge`
- time: 2026-11-21T16:38:16
- size limit: 5 MB
- files checked: 119; blobs read: 119
- result: **CLEAN** (0 hit(s), 17 allowed)

Matched text is never printed here: only the path, the commit, the rule and the line number.

## Hits

none

## Allowed (explained)

| path | commit | rule | line | reason |
|---|---|---|---|---|
| `src/muse_studio/static/index.html` | `index` | content-email-near-credential | 360 | UI placeholder text for the bulk-import textarea; fake tempmail sample rows, no real account |
| `src/muse_studio/static/index.html` | `index` | content-email-near-credential | 361 | UI placeholder text for the bulk-import textarea; fake tempmail sample rows, no real account |
| `src/muse_studio/tests/test_bulk_import_and_tempmail.py` | `index` | content-cookie-export | 32 | test fixture cookie array with dummy values |
| `src/muse_studio/tests/test_bulk_import_and_tempmail.py` | `index` | content-email-near-credential | 44 | test fixture import rows with dummy addresses and passwords |
| `src/muse_studio/tests/test_bulk_import_and_tempmail.py` | `index` | content-email-near-credential | 45 | test fixture import rows with dummy addresses and passwords |
| `src/muse_studio/tests/test_bulk_import_and_tempmail.py` | `index` | content-email-near-credential | 47 | test fixture import rows with dummy addresses and passwords |
| `src/muse_studio/tests/test_bulk_import_and_tempmail.py` | `index` | content-email-near-credential | 56 | test fixture import rows with dummy addresses and passwords |
| `src/muse_studio/tests/test_bulk_import_and_tempmail.py` | `index` | content-email-near-credential | 64 | test fixture import rows with dummy addresses and passwords |
| `src/muse_studio/tests/test_end_to_end_pipeline.py` | `index` | content-email-near-credential | 310 | dummy tempmail address passed to a mocked OTP client |
| `src/muse_studio/tests/test_end_to_end_pipeline.py` | `index` | content-email-near-credential | 311 | dummy tempmail address passed to a mocked OTP client |
| `src/muse_studio/tests/test_lane_leases.py` | `index` | content-credential-assignment | 217 | sentinel values proving lease records never copy credentials |
| `src/muse_studio/tests/test_lane_leases.py` | `index` | content-credential-assignment | 218 | sentinel values proving lease records never copy credentials |
| `src/muse_studio/tests/test_lane_leases.py` | `index` | content-credential-assignment | 219 | sentinel values proving lease records never copy credentials |
| `src/muse_studio/tests/test_lane_leases.py` | `index` | content-email-near-credential | 221 | dummy address for the lease redaction test |
| `src/muse_studio/tests/test_r15b_fixes.py` | `index` | content-email-near-credential | 61 | dummy import rows for the bulk-import field-merge test |
| `src/muse_studio/tests/test_r15b_fixes.py` | `index` | content-email-near-credential | 62 | dummy import rows for the bulk-import field-merge test |
| `src/muse_studio/tests/test_r15b_fixes.py` | `index` | content-email-near-credential | 65 | dummy import rows for the bulk-import field-merge test |
