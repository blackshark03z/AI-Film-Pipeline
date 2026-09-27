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

## 3. GenerationAttempt

Stores:
- attempt ID;
- ShotSpec version/hash;
- PromptPlan version/hash;
- RoutingDecision;
- provider/transport;
- start/end timestamps;
- result state;
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
