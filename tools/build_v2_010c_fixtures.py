"""AI-FILM-QUALITY-V2-010C — build sanitized golden fixtures for replay tests.

Sources: sanitized 010C captures + live evidence files. Every fixture is
passed through the sanitizer and then SECRET-SCANNED before landing in the
tracked tests/fixtures/v2_010c directory (fail-closed on any hit).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

PKG = ROOT / "projects/quality_v2_010c_dola_fullstack"
OUT = ROOT / "tests/fixtures/v2_010c"
OUT.mkdir(parents=True, exist_ok=True)

SECRET_MARKERS = re.compile(
    r"sessionid=(?!REDACTED)[A-Za-z0-9]|msToken=(?!REDACTED)[A-Za-z0-9]|"
    r"a_bogus=(?!REDACTED)[A-Za-z0-9]|"
    r"x-signature=(?!REDACTED)[A-Za-z0-9]|x-expires=(?!REDACTED)\d{9}", re.I)

URL_REDACT = re.compile(
    r"(?:\\{1,2}u0026|[?&])(msToken|a_bogus|fp|access_key|x-signature|x-expires|"
    r"signature|token)=[^&\"\\]*", re.I)


def redact_urls(node):
    if isinstance(node, dict):
        return {k: redact_urls(v) for k, v in node.items()}
    if isinstance(node, list):
        return [redact_urls(v) for v in node]
    if isinstance(node, str):
        return URL_REDACT.sub(r"\1=REDACTED", node)
    return node


def scan(text: str, name: str) -> None:
    hits = SECRET_MARKERS.findall(text)
    if hits:
        raise SystemExit(f"SECRET_SCAN_FAIL {name}: {hits[:3]}")


def main() -> int:
    from dola_010c_session import dpapi_unprotect

    # 1) SSE_ACK golden stream — from the RAW M1 capture (decrypt + redact)
    raw_dpapi = sorted((PKG / "runtime/capture").glob("raw_m1_*.jsonl.dpapi"))[-1]
    raw_lines = dpapi_unprotect(
        raw_dpapi.read_text(encoding="ascii")).decode("utf-8").splitlines()
    completion_body = None
    for line in raw_lines:
        entry = json.loads(line)
        if entry.get("kind") == "BODY" and \
                "completion" in (entry.get("url") or ""):
            completion_body = entry.get("body")
    assert completion_body and "SSE_ACK" in completion_body
    normalized = completion_body.replace("\r\n", "\n")
    frames = normalized.split("\n\n")
    keep = [f for f in frames if re.search(r"event: (\S+)", f)]
    stream_text = "\n\n".join(keep)
    stream_text = URL_REDACT.sub(r"\1=REDACTED", stream_text)
    (OUT / "sse_ack_stream_m1.json").write_text(json.dumps({
        "name": "sse_ack_stream_m1",
        "source": raw_dpapi.name + " (decrypted, URL-redacted)",
        "stream_text": stream_text}, indent=1, ensure_ascii=False),
        encoding="utf-8")

    # 2) poll downlink golden — from the RAW observation capture
    obs_dpapi = sorted((PKG / "runtime/capture").glob("raw_obs_*.jsonl.dpapi"))[-1]
    obs_lines = dpapi_unprotect(
        obs_dpapi.read_text(encoding="ascii")).decode("utf-8").splitlines()
    poll_payload = None
    for line in obs_lines:
        entry = json.loads(line)
        if entry.get("kind") == "BODY" and \
                "im/chain/single" in (entry.get("url") or ""):
            body = entry.get("body")
            try:
                candidate = json.loads(body)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(candidate, dict) and candidate.get("downlink_body"):
                poll_payload = candidate
    assert poll_payload, "no poll downlink captured"
    poll_payload = redact_urls(poll_payload)
    (OUT / "poll_downlink_observation.json").write_text(
        json.dumps({"name": "poll_downlink_observation",
                    "source": obs_dpapi.name + " (decrypted, URL-redacted)",
                    "payload": poll_payload}, indent=1, ensure_ascii=False),
        encoding="utf-8")

    # 3) M2 release request structure (already redacted query values)
    m2 = json.loads((PKG / "generation_attempt_m2.json").read_text(encoding="utf-8"))
    release = m2.get("release_requests", [{}])[0]
    (OUT / "release_request_m2.json").write_text(
        json.dumps({"name": "release_request_m2",
                    "url": release.get("url"),
                    "query_params": release.get("query_params"),
                    "body_structure": release.get("body_structure")},
                   indent=1, ensure_ascii=False), encoding="utf-8")

    # 4) receipt docs
    for name in ("m1_receipt.json", "m2_receipt.json"):
        src = json.loads((PKG / name).read_text(encoding="utf-8"))
        scan(json.dumps(src), name)
        (OUT / f"{name}").write_text(json.dumps(src, indent=1,
                                                ensure_ascii=False),
                                     encoding="utf-8")

    # final scan over everything written (after deep URL redaction)
    for path in OUT.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps(redact_urls(payload), indent=1,
                                   ensure_ascii=False), encoding="utf-8")
        scan(path.read_text(encoding="utf-8"), path.name)
    written = sorted(p.name for p in OUT.glob("*.json"))
    print(json.dumps({"checkpoint": "V2010C_FIXTURES_BUILT",
                      "fixtures": written,
                      "secret_scan": "PASS"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
