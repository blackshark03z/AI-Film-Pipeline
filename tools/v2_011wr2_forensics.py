"""V2-011W-R2 Phase 1 — historical forensics across ALL Dola raw captures.

Scans every retained raw capture (DPAPI-decrypting the encrypted ones through
the authorized Owner-session tooling) for `unwatermarked` occurrences, and
records for each hit the exact provenance: capture, event kind, utc, URL,
JSON path of the marker within the body, vid/filehash, creation id, and the
lr value. Output is REDACTED structural evidence (no signed query values).
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qsl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from dola_010c_session import dpapi_unprotect  # noqa: E402

C10C = ROOT / "projects/quality_v2_010c_dola_fullstack/runtime/capture"
PKG = ROOT / "projects/quality_v2_011wr2_dola_variant_authority"
CAPTURES = sorted(C10C.glob("raw_*.jsonl*"))


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def redact_url(u: str) -> dict:
    try:
        p = urlparse(u)
        q = parse_qsl(p.query, keep_blank_values=True)
        params = [{"name": k,
                   "value": v if k.lower() == "lr" else "<redacted>"}
                  for k, v in q]
        lr = next((v for k, v in q if k.lower() == "lr"), None)
        return {"host": p.netloc, "path_head": p.path[:90],
                "n_params": len(params), "params": params, "lr": lr,
                "signed": any(k.lower() in {"signature", "x-signature",
                                            "x-expires", "rk3s", "rc"}
                              for k, _ in q) or "/video/tos/" in p.path}
    except Exception:
        return {"unparseable": True}


def json_paths_for_marker(text: str, marker: str, limit: int = 8) -> list[dict]:
    """Locate the marker inside a JSON-ish blob and record the exact JSON path
    of the containing key, plus nearby key names (siblings)."""
    out = []
    for m in list(re.finditer(marker, text))[:limit]:
        start = text.rfind("{", 0, m.start())
        # walk backwards to find the enclosing key: "key": "…unwatermarked…"
        key_match = None
        for km in re.finditer(r'"([A-Za-z0-9_.\-]*)"(\s*:\s*)"', text[:m.start()]):
            key_match = km
        key = key_match.group(1) if key_match else "?"
        # nearby keys (siblings) within the enclosing object window
        window_start = text.rfind("{", 0, key_match.start() if key_match else 0)
        window_end = text.find("}", m.end())
        window = text[window_start:window_end if window_end > 0 else
                      m.end() + 300]
        siblings = sorted(set(re.findall(r'"([A-Za-z0-9_.\-]{2,30})"\s*:',
                                         window)))[:18]
        # the string value containing the marker (URL?)
        val_match = re.search(r'"((?:[^"\\]|\\.)*)"',
                              text[m.start() - 1:m.end() + 400])
        value_head = val_match.group(1)[:220] if val_match else ""
        out.append({"marker": marker,
                    "json_key": key,
                    "value_head": value_head[:220],
                    "siblings": siblings,
                    "url_struct": redact_url(value_head)
                    if value_head.startswith("http") else None})
    return out


def scan_capture(path: Path) -> dict:
    name = path.name
    if path.suffix == ".dpapi":
        try:
            lines = dpapi_unprotect(path.read_text(encoding="ascii")).decode(
                "utf-8", "replace").splitlines()
        except Exception as e:
            return {"capture": name, "error": f"DECRYPT_FAILED:{type(e).__name__}"}
    else:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    hits = []
    total = 0
    entries_scanned = 0
    for line in lines:
        if "unwatermarked" not in line:
            continue
        total += line.count("unwatermarked")
        try:
            entry = json.loads(line)
        except Exception:
            continue
        entries_scanned += 1
        kind = entry.get("kind")
        utc = entry.get("utc")
        url = entry.get("url") or entry.get("endpoint") or ""
        body = entry.get("body") or entry.get("response_body") or ""
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        body = body if isinstance(body, str) else str(body)
        paths = json_paths_for_marker(body, "unwatermarked")
        # video identity fields near the hits
        vid = None
        filehash = None
        creation_ids = sorted(set(re.findall(r'"id"\s*:\s*"(\d{15,})"', body)))[:6]
        vm = re.search(r'"vid"\s*:\s*"([^"]+)"', body)
        if vm:
            vid = vm.group(1)
        fh = re.search(r'"(?:download_)?filehash"\s*:\s*"([^"]+)"', body)
        if fh:
            filehash = fh.group(1)
        if paths:
            hits.append({"kind": kind, "utc": utc, "entry_url_head":
                         url[:110], "n_unwatermarked_in_entry":
                         line.count("unwatermarked"),
                         "creation_ids": creation_ids, "vid": vid,
                         "filehash": filehash,
                         "paths": paths})
    return {"capture": name, "lines": len(lines),
            "unwatermarked_mentions": total, "entries_with_hits": hits[:12],
            "n_entries_with_hits": len(hits)}


def main() -> int:
    PKG.mkdir(parents=True, exist_ok=True)
    scans = []
    for cap in CAPTURES:
        result = scan_capture(cap)
        print(result.get("capture"), "->",
              result.get("unwatermarked_mentions", result.get("error")),
              "mentions,", result.get("n_entries_with_hits", 0), "entries")
        scans.append(result)
    doc = {
        "version": "v2-011wr2-historical-provenance-v1",
        "checkpoint": "V2011WR2_P1_HISTORICAL_FORENSICS",
        "recorded_at": utcnow(),
        "mode": "read-only forensic scan of retained raw captures "
                "(DPAPI-decrypted through authorized Owner-session tooling "
                "where encrypted); signed query values redacted",
        "captures_scanned": len(scans),
        "scans": scans,
    }
    (PKG / "V2_011WR2_HISTORICAL_PROVENANCE.json").write_text(
        json.dumps(doc, indent=1, ensure_ascii=False)[:400000],
        encoding="utf-8")
    print("wrote V2_011WR2_HISTORICAL_PROVENANCE.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
