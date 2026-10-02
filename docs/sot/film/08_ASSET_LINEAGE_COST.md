# Asset Lineage and Cost

## 1. Deterministic lineage

Every final asset must trace:

```text
ShotSpec version/hash
→ PromptPlan
→ RoutingDecision
→ GenerationAttempt
→ ProviderJob
→ provider output identity
→ downloaded/local Asset
→ QCReport
→ SelectedTake
→ EditManifest usage
→ Master
```

Never use:
- `latest_video()`;
- `outputs[0]`;
- newest gallery item;
- filename coincidence.

## 2. Asset record

Recommended fields:

```text
asset_id
asset_type
origin
uri_or_path
sha256
mime_type
duration_s
width
height
created_at
source_attempt_id
provider_asset_id
rights_metadata
```

Local immutable bytes should receive SHA-256.

For provider references used to condition generation, deterministic lineage must include a **reference attestation** before dispatch:

```text
canonical asset_id + canonical local SHA-256
→ provider account/project scope
→ provider media_id
→ response/resource binding for the requested media_id
→ provider readback SHA-256 + content comparison
→ immutable attestation/evidence hash
```

A provider media ID is not trusted merely because it appeared in a historical receipt, shares a filename, sits near another catalog row, or produced a visually plausible output. If exact identity/resource binding or content verification fails, generation is blocked and the existing external resource must not be silently replaced or blindly re-uploaded.

## 2.1 Provider mutation/render/acquisition lineage

For browser-backed video providers, persist the provider lifecycle as separate facts rather than one boolean success flag:

```text
attempt preclaim + unique correlation marker
→ mutation released exactly once
→ admission evidence / provider candidate identity
→ durable backend ownership binding
→ render state
→ final provider media identity
→ acquisition
→ local SHA-256 / metadata / decode validation
→ Asset
```

Current Flow evidence proves that a job may be admitted yet fail before render completion. Recommended durable fields include:

```text
correlation_marker
provider_scope_fingerprint
observed_contract_fingerprint
provider_admission_state
provider_candidate_id
provider_render_state
provider_media_id
reference_attestation_id
reconciliation_started_at / ended_at
acquisition_state
```

A fresh backend delta plus unique marker/project/reference/media binding may establish output ownership in a qualified provider scope. A signed download URL is ephemeral transport data and is never canonical identity.

Do not persist provider cookies, auth/session material, CAPTCHA/security tokens or signed CDN URLs as lineage evidence.


## 3. GenerationAttempt

Stores:
- attempt ID;
- ShotSpec version/hash;
- PromptPlan version/hash;
- RoutingDecision;
- provider/transport;
- start/end timestamps;
- result state;
- provider admission state;
- provider render state;
- correlation/contract-scope evidence;
- output asset IDs;
- error classification;
- QC report;
- cost events.

## 4. CostEvent

Browser/subscription transports may not expose a clean per-request monetary charge.

Therefore:

```text
cost_basis:
  metered
  subscription_allocated
  manual_estimate
  unknown

currency
direct_cost
allocated_cost
units
source_note
```

Unknown is valid. Do not fabricate precision.

## 5. Core economics

### Per approved shot
```text
sum(cost events for all attempts belonging to the approved shot)
```

### Per approved second
```text
total generation-related cost / total approved final seconds
```

### Per finished minute
```text
total attributable production cost / finished_duration_minutes
```

Track separately:
- attempts / approved shot;
- first-pass approval rate;
- provider failure rate;
- continuity failure rate;
- repair success rate;
- human minutes / approved shot;
- generated seconds / approved seconds.

## 6. Runtime pricing

Pricing is operational data, not SoT architecture.

Store it in versioned runtime configuration or benchmark records with:
- provider;
- model/tier;
- price source date;
- unit;
- confidence/source.

Do not hard-code old report pricing into Film IR.
