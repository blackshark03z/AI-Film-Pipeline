"""V2-019 — scrub signed-URL query values from Phase A/B/C evidence JSONs.

Template strings nest JSON-in-JSON, so value-level regex redaction is used
(parameter NAMES survive, signed VALUES are replaced) — the same policy as
dola_010c_capture.SIGNED_URL_QUERY_RE but applied to whole files.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / \
    "projects/quality_v2_019_dola_productionization"
SIGNED_VALUE_RE = re.compile(
    r"(x-signature|X-Amz-Signature|signature|x-expires|Expires|X-Goog-"
    r"Signature|rcl|rk3s|rrcfp|key_seed|access_key)="
    r"[^&\"\\<>]{4,}")


def scrub_text(text: str) -> str:
    return SIGNED_VALUE_RE.sub(lambda m: m.group(1) + "=REDACTED", text)


def main() -> int:
    scrubbed = 0
    for path in sorted(PKG.glob("*.json")):
        text = path.read_text(encoding="utf-8")
        new = scrub_text(text)
        if new != text:
            # keep valid JSON structure
            try:
                json.loads(new)
            except Exception:
                print("SKIP non-json after scrub:", path.name)
                continue
            path.write_text(new, encoding="utf-8")
            scrubbed += 1
            print("scrubbed", path.name)
    print("files scrubbed:", scrubbed)
    residual = []
    for path in sorted(PKG.glob("*.json")):
        text = path.read_text(encoding="utf-8")
        for bad in ("X-Amz-Signature=", "a_bogus=", "msToken=",
                    "key_seed=TVDY", "x-signature=%2B", "x-signature=Jt",
                    "x-signature=7C", "x-signature=x9", "x-signature=tV"):
            if bad in text:
                residual.append((path.name, bad))
        for match in re.finditer(r"x-signature=([A-Za-z0-9%]{6})", text):
            if match.group(1) != "REDACT":
                residual.append((path.name, match.group(0)))
    if residual:
        print("RESIDUAL:", residual)
        return 1
    print("verify: CLEAN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
