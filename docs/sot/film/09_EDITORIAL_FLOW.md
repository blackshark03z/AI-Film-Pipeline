# Editorial Flow

## Principle

Editorial is part of generation.

```text
Generate
→ QC
→ Select
→ Rough Cut
→ detect missing coverage
→ PickupRequest
→ generate pickup/replacement
→ Rough/Fine Cut
→ Picture Lock
→ Resolve finishing
```

## V1 assembly

### FFmpeg
Default programmatic tool for:
- proxies;
- concatenation/rough assemblies;
- transcoding;
- metadata probes;
- thumbnails/QC extraction;
- simple audio muxing.

### OpenTimelineIO
Optional. Add when timeline interchange becomes genuinely useful.
Not a V1 dependency.

### Remotion
Not a V1 dependency.
Use only if a future format specifically benefits from programmatic HTML/React graphics enough to justify render cost.

### DaVinci Resolve
Finishing truth for:
- edit refinement;
- Fusion cleanup/VFX;
- color;
- Fairlight audio;
- delivery.

## EditManifest

The pipeline should export a simple manifest:

```text
timeline order
shot_id
selected_take_id
asset_id
source_in
source_out
target_duration
audio intent
transition intent
notes
```

The initial rough cut may be FFmpeg-generated. Resolve remains authoritative for final editorial decisions.

## PickupRequest types

- reaction;
- insert;
- cutaway;
- bridge;
- continuity repair;
- performance replacement;
- establishing;
- alternate angle.

Pickups are normal workflow, not failure of the architecture.
