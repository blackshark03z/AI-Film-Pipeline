# Flow CDN reference recompression fixtures

Synthetic reference sources and their exact read-only Flow image readbacks,
captured 2026-09-30 under the Owner's V2 reconciliation authority. No new upload
or video generation was performed to obtain these fixtures. The character is
a deterministically illustrated fictional adult; the canary is a geometric
Pillow drawing. No person, authentication data or signed URL is included.

| Pair | Existing Flow image ID | Source SHA256 | CDN byte SHA256 |
| --- | --- | --- | --- |
| Canary | 347f9951-5bbc-4910-b6fd-3a17c74e29d2 | dc766e136c039ce4ae25f78dc7555c161a6178e8c835cf3d37600b4d7d0e8b0e | 93fa8edf3093a62f6053b5ae95352d7355d803329b00cb55f336c559216d8c89 |
| Character | 53b5a413-7bb5-4f97-9be4-2461794a7d80 | 31ca872d7b608dee61db0f0bdc753e4acaf659c428706ff7da88dfee98c3e531 | af0ad578968002fd6cdfa864cbf2acbafaf3e8f140d8decbb2990cca7f71012f |

`.bin` contains the original CDN encoded image bytes, decoded by Pillow in tests.
Source and CDN byte hashes differ. Tests exercise real compression ringing,
both cross-reference negatives, uniform-color dHash collisions and localized
mutations. Matching requires equal dimensions and every RGB/detail threshold.
