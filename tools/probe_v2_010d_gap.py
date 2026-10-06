"""V2-010D: fetch messages around anchor 34 (the 31-33 gap) read-only."""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010d_adapter_delta import DolaBrowserAdapter010D
from dola_010c_browser_adapter import SEEDANCE_CONVERSATION_ID

GAP_JS = """async ({conversationId}) => {
  const fetch_ = async (anchor, direction) => {
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
      body: JSON.stringify({cmd: 3100,
        uplink_body: {pull_singe_chain_uplink_body: {
          conversation_id: conversationId, anchor_index: anchor,
          conversation_type: 3, direction, limit: 10,
          ext: {}, filter: {index_list: []},
          evaluate_ab_params: "", evaluate_common_params: "",
        }},
        sequence_id: crypto.randomUUID(), channel: 2, version: "1"}),
      credentials: "include"});
    return resp.json();
  };
  const out = {};
  for (const [label, anchor, direction] of [
      ["around_34_older", 34, 0], ["newest", 4294967295, 1]]) {
    const data = await fetch_(anchor, direction);
    const messages = ((data.downlink_body || {})
      .pull_singe_chain_downlink_body || {}).messages || [];
    out[label] = messages.map(m => {
      let blocks = m.content;
      if (typeof blocks === "string") {
        try { blocks = JSON.parse(blocks); } catch (e) { blocks = []; }
      }
      const creations = [];
      let text = "";
      for (const b of (Array.isArray(blocks) ? blocks : [])) {
        if (b.block_type === 2074) {
          for (const c of (((b.content || {}).creation_block || {})
              .creations || [])) {
            creations.push({id: c.id && String(c.id), type: c.type,
              v_status: (c.video || {}).status ?? null,
              gen_status: (c.gen_detail || {}).status ?? null});
          }
        } else if (b.block_type === 10000) {
          text += (((b.content || {}).text_block || {}).text || "");
        }
      }
      return {index: m.index_in_conv, message_id: String(m.message_id),
              content_type: m.content_type, text: text.slice(0, 160),
              creations};
    });
  }
  return out;
}"""


async def main() -> int:
    adapter = DolaBrowserAdapter010D(run_id="gap_" + "probe")
    try:
        await adapter.open()
        await adapter.goto_conversation(SEEDANCE_CONVERSATION_ID)
        data = await adapter.page.evaluate(
            GAP_JS, {"conversationId": SEEDANCE_CONVERSATION_ID})
    finally:
        try:
            await adapter.close(sanitize_to=None)
        except Exception:
            pass
    for label, rows in data.items():
        print("===", label, "===")
        for r in rows:
            print(f" idx={r['index']} msg=…{r['message_id'][-6:]} "
                  f"ctype={r['content_type']} cre={r['creations']}")
            if r["text"]:
                print("   ", r["text"].replace("\n", " ")[:140])
    (ROOT / "projects/quality_v2_010d_f2b_completion"
     / "V2_010D_GAP_PROBE.json").write_text(
        json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
