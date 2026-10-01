# Slice 0011 — reference identity/readback resolution

Date: 2026-10-01 (Asia/Saigon). Scope: the Owner's read-only ambiguity-resolution
request; no authority to generate, upload, repair, or substitute a reference.

**Exact result: B. REFERENCE_BINDING_PROVEN_CONTENT_MISMATCH.**
**Proof state: PROVEN for the observed ID → resource → served bytes chain.**
**Owner gate remains; Shot B was not generated.**

## 1. Current identity chain

**OBSERVED:** the existing provider media ID
`347f9951-5bbc-4910-b6fd-3a17c74e29d2` resolves to the geometric transport-canary
image, not the canonical illustrated character. The complete chain is:

1. Read-only `as29s` request payload `["347f9951-5bbc-4910-b6fd-3a17c74e29d2"]`.
2. Unique decoded `wrb.fr/as29s` response echoes that exact ID at `[0]` and
   project `f6b40e79-d6f8-4354-80ae-c863260e96f5` at `[1]`.
3. Two response URL slots, `[5][10]` and `[6][1][3]`, contain the identical signed
   URL for `https://flow-content.google/image/347f9951-5bbc-4910-b6fd-3a17c74e29d2`.
   All signed-query values are redacted from durable evidence.
4. GET with `max_redirects=0`, `max_retries=0` returns HTTP 200 at that same
   origin/path. There is no redirect response or Location header.
5. HTTP Content-Type is `image/jpeg`; actual decoder reports JPEG, RGB,
   1280x720. Download size, Content-Length, and response/catalog `[5][13]` all
   equal **54,082 bytes**. Response/catalog dimensions also agree.
6. Returned bytes SHA256:
   `93fa8edf3093a62f6053b5ae95352d7355d803329b00cb55f336c559216d8c89`.

**OBSERVED:** the canonical character source SHA256 remains
`31ca872d7b608dee61db0f0bdc753e4acaf659c428706ff7da88dfee98c3e531`.
Its comparison with those bytes gives `strong_match=false`, dHash distance
123/256, maximum channel MAE 118.42483940972222 and RMS 138.69036280906872.
Both images have the same dimensions; the content is plainly different.

**OBSERVED:** the returned image shows a red rectangle, teal circle, yellow
triangle, and the label `FILM REFERENCE TRANSPORT CANARY 20260930 V1`.
It strongly matches the existing local geometric fixture with source SHA256
`dc766e136c039ce4ae25f78dc7555c161a6178e8c835cf3d37600b4d7d0e8b0e`:
`strong_match=true`, dHash distance 0/256, maximum channel MAE 1.307658420138889.

## 2. Redacted response structure and all UUIDs

**OBSERVED:** the image response is a seven-element media record, not just a URL.
The wire request envelope is:

```json
[[["as29s","[\"347f9951-5bbc-4910-b6fd-3a17c74e29d2\"]",null,"generic"]]]
```

The decoded record has these material slots:

| Slot | Observed content |
| --- | --- |
| `[0]` | requested media ID `347f9951-5bbc-4910-b6fd-3a17c74e29d2` |
| `[1]` | project ID `f6b40e79-d6f8-4354-80ae-c863260e96f5` |
| `[2]` | secondary UUID `44af8834-4c5c-44d8-822a-10609c36700a` |
| `[3]` | `CAE` |
| `[4]` | null |
| `[5][10]` | signed `/image/347f9951-5bbc-4910-b6fd-3a17c74e29d2` URL |
| `[5][13]` | 54082 |
| `[6][1][3]` | identical signed image URL |
| `[6][1][6]` | `image/jpeg` |
| `[6][2]` | `[1280,720]` |

**OBSERVED:** these are the only UUID values in this response: the requested
media ID, project ID, secondary UUID, and the requested ID repeated in both URL
paths. There is no different candidate media ID in a nested URL. Signed URL
query keys are `Expires`, `KeyName`, and `Signature`; values are not persisted.
**UNKNOWN:** the independent semantic role of slot `[2]`; it is not treated as
another media ID. It agrees exactly between catalog and media response.

## 3. Independent corroboration and differential controls

**OBSERVED:** six successful lookups/downloads were performed in one browser
session and one project: two explicit rounds of each of these three existing
IDs. No failed read was retried. Each ID yielded a distinct resource path and
the same byte hash in both rounds.

| Existing ID | Kind / size | SHA256 | Content result |
| --- | --- | --- | --- |
| `347f9951-5bbc-4910-b6fd-3a17c74e29d2` | JPEG / 54082 | `93fa8edf3093a62f6053b5ae95352d7355d803329b00cb55f336c559216d8c89` | matches geometric transport fixture; fails canonical character |
| `53b5a413-7bb5-4f97-9be4-2461794a7d80` | JPEG / 75299 | `af0ad578968002fd6cdfa864cbf2acbafaf3e8f140d8decbb2990cca7f71012f` | strongly matches canonical character; dHash 0/256, MAE 0.9335731336805555 |
| `a47636b8-f7fb-4d99-8100-4cb5d989da8d` | MP4 / 1057779 | `7cc88ca3aa0d5f2de474d2ac508755700e92f500b96477557ecc3216924bd26c` | exact approved Shot A video hash |

**OBSERVED:** catalog reads before and after the six-read batch returned the
same five IDs. For the two images, ID/project/secondary UUID/status/size and
dimensions agree independently between `Zzl0ze`, `as29s`, and downloaded bytes.

**OBSERVED:** existing historical records agree with the differential results:

- `reference_qualification_20260930/qualification.json` binds `347f…` to source
  `dc766e…` and provider bytes `93fa8edf…`. Record SHA256:
  `0692a7f043841205554d75510de4c23df43cc4641af4572a7cdffa8d1db04ba4`.
- `slice0011/frozen_reference_recovery.json` binds `53b5…` to the canonical source
  `31ca872d…` and provider bytes `af0ad578…`. Record SHA256:
  `4ee89b889d345e9fbbad23682a0071512a667c8d85fa4ac38d6ca245f9c154df`.
- `reference_qualification.py` defines `CANARY_MEDIA_ID = '347f…'`; its
  `canary_reference()` constructs that geometric drawing, explicitly distinct
  from the production character reference.

**OBSERVED:** the approved Shot A's current catalog and media response both
record `347f…` at `[5][6][1][1][0][2]`. Its visual approval remains an Owner fact.
That approval does not prove it used the canonical character reference.
The earlier claim that its provider reference `347f…` was the canonical
`asset_708349…` is **DISPROVEN** by the current and historical identity evidence.
No historical receipt or approval record was modified.

## 4. Resolver, redirects, CDN, and cache findings

**OBSERVED:** the current resolver recursively scans for URLs with the requested
kind and deduplicates full URLs. For `347f…` it finds two occurrences of exactly
one URL. Either occurrence addresses the same bound resource. For Shot A, the
response contains both `/image/<A>` (thumbnail at `[5][10]`) and `/video/<A>`
(video at `[7][0][8]`); the existing kind filter selected the video correctly.

**DISPROVEN for these captures:** selecting a wrong nested URL caused the
`93fa8edf…` result. The requested ID, echoed ID, project, resource path,
byte size, dimensions, historical receipt, and content all agree.

**OBSERVED:** the resolver currently omits explicit checks of the echoed
ID/project and exact resource path. This is a missing defensive check, but it
did not cause this content mismatch. No production resolver change was made.

**OBSERVED:** all eight investigated media GETs returned HTTP 200 directly, with
redirect following disabled. No resource was derived from gallery ordering,
URL naming guesswork, or a rewritten signed query. Catalog thumbnail URLs on
`lh3.googleusercontent.com` were not used for acquisition. Only backend-returned
`flow-content.google` URLs were downloaded.

**OBSERVED:** normal image responses reported
`Cache-Control: private,max-age=18060`, `Age` about 64,932–64,937 seconds, and
Last-Modified on 2026-09-30. Target ETag was
`"06f3ebb02c72eabac0a9fed86ee443fa"`; control ETag was
`"c558f4ce91f0541723f7cb64b2723efc"`.

**OBSERVED:** a separate bounded freshness check reopened the same existing
profile in the same project, requested each existing image once, and sent
ordinary `Cache-Control: no-cache, max-age=0` and `Pragma: no-cache` headers.
It returned the same paths, bytes, sizes, ETags and Last-Modified values. `Age`
continued to increase to 65,068/65,067. This was a planned successful-read
control, not a retry after failure. No account selection or login switch occurred.

**UNKNOWN:** whether the CDN contacted its origin despite the request headers,
why reported Age exceeds the advertised max-age, and unobserved internal CDN
indirection. An origin-freshness or permanent-resource-immutability claim is not
made. **INFERRED:** a cache alias is not the supported explanation for the
mismatch: IDs produce distinct, reproducible resources, and the same mapping
already exists in independent historical receipts.

**OBSERVED:** `[media_id]` successfully returns the matching record under the
existing `as29s` semantics. **UNKNOWN:** broader future contract stability.
No provider contract drift is needed to explain the present finding; state D
is not established.

## 5. Root cause and minimum production delta

**OBSERVED root fact:** the requested ID is a valid, content-mismatching
transport-canary resource. **INFERRED root cause of the blocked continuation:**
the qualification/continuation facts conflated the geometric canary's provider
ID with the canonical character Asset. **UNKNOWN:** the exact historical UI
selection or reporting step that introduced that conflation. A shared filename
or selector error is only a **HYPOTHESIS**, not architectural truth.

**Minimum proposed future defensive delta (not implemented here):** validate
response ID/project/status/kind against the requested and bound identity;
require the qualified media slot(s) to agree on the exact expected
`/<kind>/<media_id>` resource; retain the existing zero-redirect behavior; check
declared size/type against downloaded and decoded media; and compare references
with the immutable canonical source before authorizing mutation. Reuse the
existing production reference receipt rather than taking a filename or a
transport-canary identity as authority.

Those checks would reject the false source-to-provider binding. They cannot
make `347f…` contain the canonical character. Substituting `53b5…`, changing any
reference receipt, re-uploading, or resuming Shot B is outside this resolution.

## 6. Proof custody, validation, and stop state

**OBSERVED:** branch `codex/slice-0011-reference-i2v-continuity`, HEAD/base
`6b018fcb71f97f35458700ba671de69bfe663d52`; inherited working tree preserved.
No production source changed during this resolution. Exercised session source
SHA256: `fcb5d5cc9ffe7379a69582b13e2df5c7f3628dbd7ac19c6d3154d8c0f6abcbd8`.
The evidence records hashes for the other exercised sources and forensic tool.

Sanitized evidence under `projects/character_continuity/reference_binding_20261001/`:

- `evidence.json`: six lookups, redacted full response shapes, all UUID slots,
  headers, locally preserved exact bytes, comparisons, catalog snapshots and
  source hashes. SHA256:
  `76d81ec419cbb1c90e6c1d04c47d3eddbe3ad28b7796260391376d112815da84`.
- `cache_control_evidence.json`: two successful no-cache controls. SHA256:
  `fe83aa58bdfa1d7bd71d274cc3e12ccc544485603e55eb84ebeff03538bfd81a`.
- `offline_verification.json`: independently checks ID/resource/bytes links
  from captured evidence and local media, replays image comparisons, compares
  historical records, and rejects 13 altered-evidence controls.

**OBSERVED validation:** `tools/verify_flow_media_binding.py` passed six captured
observations plus two freshness controls and rejected wrong ID/project/request,
path/host, cardinality, redirect, hash/size/dimensions/MIME and record-kind
controls. Compilation of all three forensic tools passed. These checks qualify
this evidence; they do not qualify a complete future production adapter.

**OBSERVED local regression:**
`.venv/Scripts/python.exe -m pytest -q tests/test_reference_reconcilable_transport.py tests/test_flow_contract_20261001.py`
returned **54 passed in 11.37s**. `git diff --check` returned exit 0. A local
sanitization check found no signed-query or authentication values in the three
evidence JSON files. No full production suite was rerun because this resolution
changed no production source; the earlier 343-test result remains historical.

Exact offline replay command:
`.venv/Scripts/python.exe tools/verify_flow_media_binding.py`.
The two `investigate_*` tools are forensic live-read tools, not production
entrypoints; they refuse to rerun when their evidence files already exist.
Local image artifact filenames use a `.png` suffix inherited from the probe's
save convention; no transcoding occurred. MIME and decoded format are JPEG,
and the hashes refer to exact downloaded bytes.

**OBSERVED boundaries:** explicit RPC totals are `Zzl0ze=2`, `as29s=8`; media
GETs=8. Generate=0, upload=0, retries=0. No project/account selection, replacement
reference, canonical schema edit, runtime ledger edit, SelectedTake, or Shot B
action occurred. Existing profile authentication was reused. Absolute Google
account identity remains outside this project's verified evidence.

**Exact final state B; stop at the Owner content-mismatch gate.** The ambiguity
about attributing `93fa8edf…` to `347f…` is resolved for the observed resource.
No Shot B generation or reference repair is authorized by this proof.
