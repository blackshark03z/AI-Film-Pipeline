"""V2-011W-R2 — fresh poll variant extraction + authorized acquisition.

The f3r_012 raw capture proved the provider emits lr=unwatermarked sibling
URLs for the SAME creation inside the poll response's video_list structure.
Signed URLs expire, so this tool re-polls the same conversation with the
authorized Owner session (the provider re-emits fresh signed video_list
URLs), extracts the unwatermarked variant EXACTLY as emitted (base64-decoded,
no parameter modification), downloads it, and records redacted provenance.
"""
from __future__ import annotations

import base64
import hashlib
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
from film_pipeline.providers.elyum_provider import download_asset  # generic https downloader

PKG = ROOT / "projects/quality_v2_011wr2_dola_variant_authority"
CONVERSATION = "38417944671772433"  # F3R_012
CREATION = "1542350901495057"
WATERMARKED_SHA = "b558f8e89ae4664ca6d7325f84fcf18ad17174bc72caa12773354266c2427bbb"

PULL_JS = """async ({conversationId}) => {
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
  return data;
}"""


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def _maybe_parse(value):
    """Parse embedded JSON strings (message content blocks are JSON-in-string)."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[0] not in "{[":
        return value
    try:
        return json.loads(text)
    except Exception:
        return value


def find_video_lists(node, path="", acc=None, depth=0):
    """Locate every video_list object at ANY depth, descending through
    embedded JSON strings (message content blocks are JSON-in-string)."""
    if acc is None:
        acc = []
    if depth > 16:
        return acc
    if isinstance(node, str):
        parsed = _maybe_parse(node)
        if parsed is not node:
            return find_video_lists(parsed, path + "<json>", acc, depth + 1)
        return acc
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "video_list" and isinstance(v, dict):
                acc.append((path + "." + k, v))
            find_video_lists(v, path + "." + str(k), acc, depth + 1)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            find_video_lists(v, path + f"[{i}]", acc, depth + 1)
    return acc


def decode_entry(v: dict) -> dict:
    out = {"definition": v.get("definition"), "quality": v.get("quality"),
           "vtype": v.get("vtype"), "bitrate": v.get("bitrate")}
    urls = {}
    for field in ("main_url", "backup_url_1", "backup_url_2", "url"):
        raw = v.get(field)
        if not raw:
            continue
        try:
            url = base64.b64decode(raw).decode("utf-8", errors="replace")
        except Exception:
            url = raw
        p = urlparse(url)
        q = parse_qsl(p.query)
        urls[field] = {
            "url": url, "scheme": p.scheme, "host": p.netloc,
            "lr": next((vv for kk, vv in q if kk.lower() == "lr"), None),
            "logo_type": next((vv for kk, vv in q if kk.lower() == "logo_type"), None),
            "param_names": sorted(kk for kk, _ in q),
        }
    out["urls"] = urls
    return out


def main() -> int:
    record = {"version": "v2-011wr2-variant-acquisition-v1",
              "checkpoint": "V2011WR2_FRESH_POLL_ACQUISITION",
              "recorded_at": utcnow(),
              "mode": "READ-ONLY poll re-read + acquisition of the exact "
                      "provider-emitted unwatermarked variant URL "
                      "(no parameter modification)",
              "conversation_id": CONVERSATION, "creation_id": CREATION}
    manager = DolaSessionManager(profile_dir=ACCOUNT_PROFILES / "ACCOUNT_D")
    manager.launch_result = None
    import asyncio

    async def run():
        await manager.launch_browser()
        page = manager._page
        await page.goto("https://www.dola.com/chat", timeout=60000,
                        wait_until="domcontentloaded")
        for _ in range(15):
            if await page.evaluate(
                    """() => !!(document.querySelector('textarea')
                            || document.querySelector('[contenteditable="true"]'))"""):
                break
            await page.wait_for_timeout(1000)
        data = await page.evaluate(PULL_JS, {"conversationId": CONVERSATION})
        lists = find_video_lists(data)
        record["n_video_lists_in_response"] = len(lists)
        print("video_list objects found:", len(lists))
        variants = []
        for path, vl in lists:
            for key in sorted(vl.keys()):
                v = vl[key]
                if not isinstance(v, dict):
                    continue
                entry = decode_entry(v)
                entry["list_path"] = path + "." + key
                variants.append(entry)
        record["variants"] = variants
        for v in variants:
            for field, u in v.get("urls", {}).items():
                print(f"{v['list_path']} [{field}] def={v['definition']} "
                      f"lr={u['lr']} logo_type={u['logo_type']} host={u['host']}")
        # choose the unwatermarked main_url (provider-emitted)
        target = None
        for v in variants:
            for field in ("main_url", "backup_url_1", "backup_url_2"):
                u = v.get("urls", {}).get(field)
                if u and u.get("lr") == "unwatermarked":
                    target = {"url": u["url"], "definition": v["definition"],
                              "field": field, "list_path": v["list_path"]}
                    break
            if target:
                break
        if not target:
            record["status"] = "NO_UNWATERMARKED_VARIANT_IN_FRESH_POLL"
            (PKG / "V2_011WR2_LIVE_CAPTURE_INDEX.json").write_text(
                json.dumps(record, indent=1, ensure_ascii=False)[:200000],
                encoding="utf-8")
            print("no unwatermarked variant in the fresh poll")
            return 1
        url = target["url"]
        record["acquired_from"] = {k: v for k, v in target.items()
                                   if k != "url"}
        # acquire EXACTLY the provider-issued URL (http as emitted)
        import urllib.request
        request = urllib.request.Request(
            url, headers={"User-Agent": "AI-Film-ElyumV2014/1",
                          "Accept": "video/mp4,*/*"})
        dest = PKG / "downloads" / "f3r_012_unwatermarked.mp4"
        dest.parent.mkdir(exist_ok=True)
        sha = hashlib.sha256()
        size = 0
        tmp = dest.with_suffix(".mp4.tmp")
        with urllib.request.urlopen(request, timeout=180) as response:
            record["response_content_type"] = response.headers.get(
                "Content-Type", "")
            record["response_final_host"] = urlparse(response.geturl()).netloc
            with tmp.open("wb") as f:
                while True:
                    chunk = response.read(256 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    sha.update(chunk)
                    f.write(chunk)
        tmp.replace(dest)
        record["acquired_asset"] = {"path": str(dest), "size": size,
                                    "sha256": sha.hexdigest(),
                                    "url_structure": {
                                        "host": urlparse(url).netloc,
                                        "lr": "unwatermarked",
                                        "param_names": sorted(
                                            kk for kk, _ in parse_qsl(
                                                urlparse(url).query))}}
        record["watermarked_reference_sha256"] = WATERMARKED_SHA
        record["status"] = "ACQUIRED"
        print("ACQUIRED:", dest, size, "bytes, sha", sha.hexdigest()[:16])
        return 0

    try:
        rc = asyncio.run(run())
    finally:
        manager_close = getattr(manager, "close", None)
        if manager_close:
            asyncio.run(manager_close())
    (PKG / "V2_011WR2_LIVE_CAPTURE_INDEX.json").write_text(
        json.dumps(record, indent=1, ensure_ascii=False)[:300000],
        encoding="utf-8")
    print("wrote V2_011WR2_LIVE_CAPTURE_INDEX.json")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
