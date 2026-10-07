"""V2-021 — strict slot verification (read-only).

Distinguishes a REAL logged-in session from an anonymous one:
  - authenticated UI shows the account nickname in the sidebar;
  - /alice/profile/self returns a real entity for logged-in sessions;
  - an anonymous session shows a login entry point in the DOM.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010c_session import DolaSessionManager

PKG = ROOT / "projects/quality_v2_021_narrative_compiler"

CHECK_JS = """async () => {
  const body = (document.body && document.body.innerText) || '';
  const params = new URLSearchParams({
    version_code: "20800", language: "ja", device_platform: "web",
    doubao_device_platform: "web", aid: "495671", real_aid: "495671",
    pkg_type: "release_version", pc_version: "3.39.1",
    region: "VN", sys_region: "VN", samantha_web: "1",
    "use-olympus-account": "1", web_tab_id: crypto.randomUUID(),
  });
  let self = null;
  try {
    const resp = await fetch("/alice/profile/self?" + params.toString(),
        {method: "GET", credentials: "include",
         headers: {"Accept": "application/json, text/plain, */*"}});
    if (resp.ok) {
      const data = await resp.json();
      const brief = ((data.data || {}).profile_brief) || {};
      self = {nickname: brief.nickname || null,
              entity_id: brief.entity_id || null,
              level: ((brief.membership_info || {}).level) || null};
    }
  } catch (e) {}
  const loginMarkers = ["ログイン", "Log in", "Sign in", "đăng nhập",
                        "登录"];
  const hasLoginMarker = loginMarkers.some(m => body.includes(m));
  return {nickname: self ? self.nickname : null,
          entity_id: self ? self.entity_id : null,
          level: self ? self.level : null,
          has_login_marker: hasLoginMarker,
          body_head: body.slice(0, 300)};
}"""


async def verify(alias: str, profile_root: Path) -> dict:
    manager = DolaSessionManager(profile_dir=profile_root / alias)
    result = {"alias": alias}
    try:
        page = await manager.launch_browser()
        await page.goto("https://www.dola.com/chat", timeout=60000,
                        wait_until="domcontentloaded")
        for _ in range(20):
            await page.wait_for_timeout(2000)
            try:
                state = await page.evaluate(CHECK_JS)
                if state.get("nickname"):
                    break
                if state.get("has_login_marker"):
                    break
            except Exception:
                continue
        result.update({k: v for k, v in state.items()})
        result["verdict"] = ("LOGGED_IN" if result.get("nickname")
                             else "ANONYMOUS_OR_LOGIN_REQUIRED")
        return result
    except Exception as error:
        result["verdict"] = "ERROR"
        result["error"] = f"{type(error).__name__}: {error}"[:200]
        return result
    finally:
        try:
            await manager.close()
        except Exception:
            pass


async def main() -> int:
    profile_root = PKG / "pool_profiles"
    out = {}
    for alias in sys.argv[1:] or ["ACCOUNT_E", "ACCOUNT_F"]:
        out[alias] = await verify(alias, profile_root)
        print(json.dumps(out[alias], ensure_ascii=False)[:400],
              flush=True)
    (PKG / "V2_021_SLOT_VERIFICATION.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
