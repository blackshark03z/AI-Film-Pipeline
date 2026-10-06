"""V2-011W Phase 1 — full creation-object reconstruction (READ-ONLY).

For each exact frozen creation: pull the conversation (limit=10 — the
Seedance 2.0 qualified path), extract the FULL provider-delivered creation
object, enumerate every URL-bearing field, and persist a REDACTED structural
representation: host + path + parameter NAMES + the lr variant marker are
kept; signed/expiry/identity parameter VALUES are redacted.

Never persists: cookies, signed query values, tokens, credentials.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qsl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010c_session import DolaSessionManager
from dola_010e_session_router import ACCOUNT_PROFILES

ROOT_PKG = ROOT / "projects/quality_v2_011w_unwatermarked_authority"
REDACT_PARAM_VALUES = {"signature", "x-signature", "x-expires", "rk3s",
                       "rrcfp", "rcl", "dy_q", "l", "a", "ch", "cr", "dr",
                       "er", "cd", "cv", "br", "bt", "cs", "ds", "ft", "qs",
                       "rc", "mime_type", "download", "lr"}
KEEP_PARAM_VALUES = {"lr"}

PULL_RAW_JS = """async ({conversationId}) => {
  const params = new URLSearchParams({
    version_code: "20800", language: "ja", device_platform: "web",
    doubao_device_platform: "web", aid: "495671", real_aid: "495671",
    pkg_type: "release_version", pc_version: "3.39.1",
    doubao_pc_version: "3.39.1", region: "VN", sys_region: "VN",
    samantha_web: "1", web_platform: "browser",
    "use-olympus-account": "1", web_tab_id: crypto.randomUUID(),
  });
  const resp = await fetch("/im/chain/single?" + params.toString(), {
    method: "POST",
    headers: {"Content-Type": "application/json; encoding=utf-8",
              "agw-js-conv": "str",
              "Accept": "application/json, text/plain, */*"},
    credentials: "include",
    body: JSON.stringify({cmd: 3100,
      uplink_body: {pull_singe_chain_uplink_body: {
        conversation_id: conversationId,
        anchor_index: Number.MAX_SAFE_INTEGER, conversation_type: 3,
        direction: 1, limit: 10, ext: {}, filter: {index_list: []},
        evaluate_ab_params: "", evaluate_common_params: ""}},
      sequence_id: crypto.randomUUID(), channel: 2, version: "1"})});
  const data = await resp.json();
  const messages = ((data.downlink_body || {})
    .pull_singe_chain_downlink_body || {}).messages || [];
  const found = [];
  for (const m of messages) {
    let blocks = m.content;
    if (typeof blocks === "string") {
      try { blocks = JSON.parse(blocks); } catch (e) { continue; }
    }
    for (const b of (Array.isArray(blocks) ? blocks : [])) {
      if (b.block_type !== 2074) continue;
      for (const c of (((b.content || {}).creation_block || {})
          .creations || [])) {
        if (c.type === 2) {
          found.push({message_id: String(m.message_id),
                      creation: c});
        }
      }
    }
  }
  return found;
}"""


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def redact_url(u: str) -> dict:
    """host + path + parameter names; lr value kept (variant marker);
    all other parameter values redacted."""
    try:
        parsed = urlparse(u)
        q = parse_qsl(parsed.query, keep_blank_values=True)
        params = []
        for k, v in q:
            entry = {"name": k}
            if k.lower() in KEEP_PARAM_VALUES:
                entry["value"] = v
            else:
                entry["value"] = "<redacted>"
            params.append(entry)
        return {"host": parsed.netloc, "path_class": parsed.path[:80],
                "scheme": parsed.scheme, "params": params,
                "n_params": len(params)}
    except Exception:
        return {"unparseable": True, "length": len(u)}


def redact_node(node):
    """Walk the creation object; redact URL query values in place (copy)."""
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if isinstance(v, str) and (v.startswith("http://") or
                                       v.startswith("https://")):
                entry = redact_url(v)
                entry["url_field"] = k
                out[k] = entry
            else:
                out[k] = redact_node(v)
        return out
    if isinstance(node, list):
        return [redact_node(x) for x in node]
    if isinstance(node, str) and len(node) > 300:
        return node[:300] + "…<truncated>"
    return node


def collect_urls(node, path="", acc=None):
    if acc is None:
        acc = []
    if isinstance(node, dict):
        for k, v in node.items():
            collect_urls(v, f"{path}.{k}", acc)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            collect_urls(v, f"{path}[{i}]", acc)
    elif isinstance(node, str) and (node.startswith("http://") or
                                    node.startswith("https://")):
        acc.append((path, node))
    return acc


CREATIONS = [
    {"label": "F1R", "account": "ACCOUNT_A",
     "conversation_id": "38417962862699025",
     "creation_id": "1546471384527889",
     "vid": "v186a3gm000cdb2dgqfog65h35lcimvg",
     "watermarked_asset_sha": "b879f21586392fa7463021f60853b1aa99fecb286890dad1b3f192c6dd805171"},
    {"label": "F2A-R", "account": "ACCOUNT_A",
     "conversation_id": "38417852262252561",
     "creation_id": "1543341075843857",
     "vid": "v186a3gm000cdb29k67og65phfv1unkg",
     "watermarked_asset_sha": "50a133c891aaa0060bc1f7d9d6c48c77a3fab1e802bc5f7a4fc43e112404d99b"},
    {"label": "F2B-R", "account": "ACCOUNT_A",
     "conversation_id": "38418085966239761",
     "creation_id": "1546449850446097",
     "vid": "v186a3gm000cdb2acjfog65s7c1c025g",
     "watermarked_asset_sha": "8679709b00860a2e3af45354b2166eae2b6d6b365731a278f21809a42babbbff"},
    {"label": "F3R_012", "account": "ACCOUNT_D",
     "conversation_id": "38417944671772433",
     "creation_id": "1542350901495057",
     "vid": None,
     "watermarked_asset_sha": "b558f8e89ae4664ca6d7325f84fcf18ad17174bc72caa12773354266c2427bbb"},
]


async def main() -> int:
    from patchright.async_api import async_playwright
    pw = await async_playwright().start()
    results = []
    for account in ("ACCOUNT_A", "ACCOUNT_D"):
        targets = [c for c in CREATIONS if c["account"] == account]
        manager = DolaSessionManager(profile_dir=ACCOUNT_PROFILES / account)
        await manager.launch_browser()
        page = manager._page
        try:
            await page.goto("https://www.dola.com/chat", timeout=60000,
                            wait_until="domcontentloaded")
            for _ in range(15):
                if await page.evaluate(
                        """() => !!(document.querySelector('textarea')
                                || document.querySelector('[contenteditable="true"]'))"""):
                    break
                await page.wait_for_timeout(1000)
            for c in targets:
                found = await page.evaluate(
                    PULL_RAW_JS, {"conversationId": c["conversation_id"]})
                match = None
                for row in found:
                    if str(row["creation"].get("id")) == c["creation_id"]:
                        match = row["creation"]
                        break
                if match is None:
                    results.append({"label": c["label"],
                                    "status": "CREATION_NOT_FOUND_IN_PULL",
                                    "found_type2_ids":
                                        [str(r["creation"].get("id"))
                                         for r in found]})
                    continue
                urls = collect_urls(match)
                variants = []
                for path, u in urls:
                    r = redact_url(u)
                    r["field_path"] = path
                    lr = [p["value"] for p in r["params"]
                          if p["name"] == "lr"]
                    r["lr"] = lr[0] if lr else None
                    variants.append(r)
                redacted = redact_node(match)
                results.append({
                    "label": c["label"], "account": c["account"],
                    "conversation_id": c["conversation_id"],
                    "creation_id": c["creation_id"],
                    "status": "RECONSTRUCTED",
                    "n_url_fields": len(urls),
                    "lr_values": sorted({v["lr"] for v in variants
                                         if v.get("lr")}),
                    "url_field_paths": [v["field_path"] for v in variants],
                    "redacted_creation_object": redacted,
                })
                print(c["label"], "reconstructed: url fields =",
                      len(urls), "lr =", sorted({v["lr"] for v in variants
                                                 if v.get("lr")}))
        finally:
            await manager.close()
    pw_stop = pw.stop()
    doc = {
        "version": "v2-011w-creation-variants-v1",
        "checkpoint": "V2011W_P1_CREATION_VARIANTS",
        "built_at": utcnow(),
        "mode": "READ_ONLY (conversation pulls; zero mutations)",
        "redaction_rule": "host+path+parameter NAMES kept; lr variant marker "
                          "kept; all signed/expiry/identity parameter VALUES "
                          "redacted; no cookies/tokens persisted",
        "creations": results,
    }
    ROOT_PKG.mkdir(parents=True, exist_ok=True)
    (ROOT_PKG / "V2_011W_CREATION_VARIANTS.json").write_text(
        json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote V2_011W_CREATION_VARIANTS.json")
    await pw_stop


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
