"""V2-011X Phase 2 — acquire provider-issued unwatermarked siblings for the
four locked film creations (fresh authorized polls, exact-URL acquisition).
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qsl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010c_session import DolaSessionManager
from dola_010e_session_router import ACCOUNT_PROFILES

PKG = ROOT / "projects/quality_v2_011x_clean_rebind"

TARGETS = [
    {"label": "F1R", "account": "ACCOUNT_A",
     "conversation_id": "38417962862699025",
     "creation_id": "1546471384527889"},
    {"label": "F2A-R", "account": "ACCOUNT_A",
     "conversation_id": "38417852262252561",
     "creation_id": "1543341075843857"},
    {"label": "F2B-R", "account": "ACCOUNT_A",
     "conversation_id": "38418085966239761",
     "creation_id": "1546449850446097"},
    {"label": "F3R_012", "account": "ACCOUNT_D",
     "conversation_id": "38417944671772433",
     "creation_id": "1542350901495057"},
]

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
        urls[field] = {"url": url, "scheme": p.scheme, "host": p.netloc,
                       "lr": next((vv for kk, vv in q if kk.lower() == "lr"), None),
                       "param_names": sorted(kk for kk, _ in q)}
    out["urls"] = urls
    return out


def pick_unwatermarked(variants):
    """Provider-issued unwatermarked rendition; prefer highest bitrate
    (production-relevant), actual properties verified post-download."""
    candidates = []
    for v in variants:
        for field in ("main_url", "backup_url_1", "backup_url_2"):
            u = v.get("urls", {}).get(field)
            if u and u.get("lr") == "unwatermarked":
                candidates.append({"url": u["url"], "field": field,
                                   "definition": v["definition"],
                                   "bitrate": v.get("bitrate") or 0,
                                   "list_path": v["list_path"],
                                   "host": u["host"]})
    candidates.sort(key=lambda c: c["bitrate"], reverse=True)
    return candidates[0] if candidates else None


def acquire(target: dict) -> dict:
    rec = {"label": target["label"], "account": target["account"],
           "conversation_id": target["conversation_id"],
           "creation_id": target["creation_id"], "recorded_at": utcnow()}
    manager = DolaSessionManager(profile_dir=ACCOUNT_PROFILES / target["account"])

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
        data = await page.evaluate(PULL_JS,
                                   {"conversationId": target["conversation_id"]})
        lists = find_video_lists(data)
        rec["n_video_lists_in_response"] = len(lists)
        variants = []
        for path, vl in lists:
            for key in sorted(vl.keys()):
                v = vl[key]
                if isinstance(v, dict):
                    e = decode_entry(v)
                    e["list_path"] = path + "." + key
                    variants.append(e)
        rec["variants"] = variants
        pick = pick_unwatermarked(variants)
        if not pick:
            rec["status"] = "CLEAN_SIBLING_NOT_CURRENTLY_PROVIDER_EMITTED"
            print(target["label"], "-> NO unwatermarked variant emitted")
            return
        rec["selected"] = {k: v for k, v in pick.items() if k != "url"}
        rec["selected"]["url_structure"] = {
            "host": urlparse(pick["url"]).netloc,
            "lr": "unwatermarked",
            "param_names": sorted(kk for kk, _ in parse_qsl(
                urlparse(pick["url"]).query))}
        import urllib.request
        request = urllib.request.Request(
            pick["url"], headers={"User-Agent": "AI-Film-ElyumV2014/1",
                                  "Accept": "video/mp4,*/*"})
        dest = PKG / "assets" / "clean" / (
            target["label"].lower().replace("-", "_") + ".mp4")
        dest.parent.mkdir(parents=True, exist_ok=True)
        sha = hashlib.sha256()
        size = 0
        tmp = dest.with_suffix(".mp4.tmp")
        with urllib.request.urlopen(request, timeout=180) as response:
            rec["response_content_type"] = response.headers.get("Content-Type", "")
            with tmp.open("wb") as f:
                while True:
                    chunk = response.read(256 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    sha.update(chunk)
                    f.write(chunk)
        tmp.replace(dest)
        rec["acquired_asset"] = {"path": str(dest), "size": size,
                                 "sha256": sha.hexdigest()}
        rec["status"] = "ACQUIRED"
        print(target["label"], "-> ACQUIRED", size, "bytes sha",
              sha.hexdigest()[:16])

    try:
        run_result = asyncio.run(run())
    except Exception as e:
        rec["status"] = f"ACQUISITION_ERROR:{type(e).__name__}"
        rec["error"] = str(e)[:200]
    finally:
        try:
            asyncio.run(manager.close())
        except Exception:
            pass
        # the patchright close can leave the chromium child alive; the next
        # launch on the same profile would fail with "existing browser
        # session" — force-clear the profile lock between targets
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
             "Where-Object { $_.CommandLine -match 'ACCOUNT_' } | "
             "ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
             "-ErrorAction SilentlyContinue }"],
            capture_output=True)
        time.sleep(2)
    return rec


def main() -> int:
    PKG.mkdir(parents=True, exist_ok=True)
    results = []
    for t in TARGETS:
        print("acquiring", t["label"], "...")
        results.append(acquire(t))
    doc = {"version": "v2-011x-variant-acquisition-v1",
           "checkpoint": "V2011X_P2_ACQUISITION",
           "recorded_at": utcnow(),
           "mode": "fresh authorized polls; exact provider-emitted "
                   "unwatermarked URLs; zero parameter modification",
           "results": results}
    (PKG / "V2_011X_VARIANT_ACQUISITION.json").write_text(
        json.dumps(doc, indent=1, ensure_ascii=False)[:400000],
        encoding="utf-8")
    statuses = {r["label"]: r["status"] for r in results}
    print(json.dumps(statuses, indent=1))
    ok = all(s == "ACQUIRED" for s in statuses.values())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
