"""V2-016 Phase 1 — inspect Dola video_model blobs for model identity."""
import json
import re
from pathlib import Path

CAP = Path("projects/quality_v2_010c_dola_fullstack/runtime/capture/"
           "raw_f3r_012_20261006T145913.jsonl")

line = max((l for l in CAP.read_text(encoding="utf-8", errors="replace")
            .splitlines() if "video_model" in l),
           key=lambda l: l.count("video_model"))
data = json.loads(line)
body = data.get("body") or ""
if not isinstance(body, str):
    body = json.dumps(body)

# video_model may appear escaped at various depths: find the marker and
# progressively unescape the surrounding quoted string
n = 0
for m in list(re.finditer(r"video_model", body))[:6]:
    start = body.rfind('"', 0, m.start() - 1)
    # take a generous window and strip escape layers iteratively
    window = body[m.start():m.start() + 3000]
    layers = 0
    text = window
    while text.startswith("\\") or layers < 3:
        try:
            candidate = text.encode().decode("unicode_escape")
        except Exception:
            break
        if candidate == text:
            break
        text = candidate
        layers += 1
        if text.lstrip().startswith("{"):
            break
    try:
        v = json.loads(text[text.find("{"):text.rfind("}") + 1])
        n += 1
        print(f"=== video_model blob {n} (escape layers {layers}) ===")
        print("keys:", sorted(v.keys()))
        for k in ("model", "model_name", "version", "quality", "resolution",
                  "duration", "status", "message", "video_id", "videoDuration"):
            if k in v:
                print(f"  {k} = {str(v[k])[:90]}")
        head = json.dumps(v)[:500]
        print("  head:", head)
        print()
        if n >= 2:
            break
    except Exception:
        continue
if n == 0:
    print("no parseable video_model blob found in the simple walk")
