"""V2-010D: full conversation timeline dump (read-only) to resolve the
F2B_010D effect definitively (message order + create_time + creations)."""
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010d_adapter_delta import DolaBrowserAdapter010D
from dola_010c_browser_adapter import SEEDANCE_CONVERSATION_ID

TIMELINE_JS = """async ({conversationId}) => {
  const params = new URLSearchParams({
    version_code: "20800", language: "ja", device_platform: "web",
    doubao_device_platform: "web", aid: "495671", real_aid: "495671",
    pkg_type: "release_version", pc_version: "3.39.1", doubao_pc_version: "3.39.1",
    region: "VN", sys_region: "VN", samantha_web: "1", web_platform: "browser",
    "use-olympus-account": "1", web_tab_id: crypto.randomUUID(),
  });
  const resp = await fetch("/im/chain/single?" + params.toString(), {
    method: "POST",
    headers: {"Content-Type": "application/json; encoding=utf-8",
              "agw-js-conv": "str",
              "Accept": "application/json, text/plain, */*"},
    body: JSON.stringify({
      cmd: 3100,
      uplink_body: {pull_singe_chain_uplink_body: {
        conversation_id: conversationId,
        anchor_index: Number.MAX_SAFE_INTEGER,
        conversation_type: 3, direction: 1, limit: 30,
        ext: {}, filter: {index_list: []},
        evaluate_ab_params: "", evaluate_common_params: "",
      }},
      sequence_id: crypto.randomUUID(), channel: 2, version: "1",
    }),
    credentials: "include",
  });
  const data = await resp.json();
  const messages = ((data.downlink_body || {})
    .pull_singe_chain_downlink_body || {}).messages || [];
  const rows = [];
  for (const m of messages) {
    let blocks = m.content;
    if (typeof blocks === "string") {
      try { blocks = JSON.parse(blocks); } catch (e) { blocks = []; }
    }
    const creations = [];
    let text = "";
    for (const b of (Array.isArray(blocks) ? blocks : [])) {
      if (b.block_type === 2074) {
        for (const c of (((b.content || {}).creation_block || {}).creations || [])) {
          creations.push({id: c.id && String(c.id), type: c.type,
                          v_status: (c.video || {}).status ?? null});
        }
      } else if (b.block_type === 10000) {
        text += (((b.content || {}).text_block || {}).text || "");
      }
    }
    rows.push({index: m.index_in_conv, message_id: String(m.message_id),
               create_time: m.create_time, sender: m.sender_id &&
               String(m.sender_id).slice(-6),
               text: text.slice(0, 180), creations});
  }
  return rows;
}"""


async def main() -> int:
    adapter = DolaBrowserAdapter010D(run_id="timeline_" +
                                     datetime.now(timezone.utc)
                                     .strftime("%Y%m%dT%H%M%S"))
    await adapter.open()
    try:
        await adapter.goto_conversation(SEEDANCE_CONVERSATION_ID)
        rows = await adapter.page.evaluate(
            TIMELINE_JS, {"conversationId": SEEDANCE_CONVERSATION_ID})
    finally:
        await adapter.close(sanitize_to=None)
    for row in rows:
        ts = row.get("create_time")
        when = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()[:19] \
            if isinstance(ts, (int, float)) else "?"
        print(f"idx={row['index']:>3} {when}Z msg={row['message_id']}"
              f" sender=…{row['sender']} creations={row['creations']}")
        if row["text"]:
            print("      text:", row["text"].replace("\n", " ")[:170])
    (ROOT / "projects/quality_v2_010d_f2b_completion"
     / "V2_010D_TIMELINE_DUMP.json").write_text(
        json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
