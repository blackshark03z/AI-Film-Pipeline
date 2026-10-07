"""V2-019 Phase A — static forensics over historical Dola captures (read-only).

Extracts the provider wire truth that previous slices recorded but never
normalized:
  1. the chat/completion request body structure (video option selections),
  2. the FULL composer model-option template (all options + extra fields),
  3. the creation video_model<json> echo (generation parameters),
  4. WS/SSE transport taxonomy.

No network. No mutation. Output: projects/quality_v2_019_dola_productionization/
"""
from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_019_dola_productionization"
CAP = ROOT / "projects/quality_v2_010c_dola_fullstack/runtime/capture"
PKG.mkdir(parents=True, exist_ok=True)

PLAIN_CAPTURES = [
    "raw_f3r_012_20261006T145913.jsonl",   # V2-012 F3R (most recent dispatch)
    "raw_f1r_20261006T111232.jsonl",       # V2-011D F1R
    "raw_f2b010e_20261006T052909.jsonl",   # V2-010E F2B
    "raw_f2b-r_20261006T073747.jsonl",     # V2-011R F2B-R
    "raw_f2a-r_20261006T064440.jsonl",     # V2-011R F2A-R
]


def load_events(name: str) -> list[dict]:
    path = CAP / name
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            events.append(json.loads(line))
        except Exception:
            continue
    return events


def deep_unescape(text: str, rounds: int = 8) -> str:
    u = text
    for _ in range(rounds):
        try:
            u2 = u.encode("utf-8", "ignore").decode("unicode_escape")
        except Exception:
            break
        if u2 == u:
            break
        u = u2
    return u


def find_req(events: list[dict], needle: str) -> dict | None:
    for e in events:
        if e.get("kind") == "REQ" and needle in (e.get("url") or ""):
            return e
    return None


def find_bodies(events: list[dict], needle: str) -> list[dict]:
    out = []
    for e in events:
        if e.get("kind") == "REQ" and needle in (e.get("url") or ""):
            out.append(e)
    return out


def main() -> int:
    report: dict = {"version": "v2-019-phaseA-capture-forensics-v1",
                    "captures": {}}

    for name in PLAIN_CAPTURES:
        events = load_events(name)
        if not events:
            continue
        entry: dict = {"events": len(events)}

        # -- taxonomy -------------------------------------------------------
        req_urls = {}
        for e in events:
            if e.get("kind") == "REQ":
                u = (e.get("url") or "").split("?")[0]
                req_urls[u] = req_urls.get(u, 0) + 1
        entry["request_urls_top"] = sorted(req_urls.items(),
                                           key=lambda kv: -kv[1])[:12]
        entry["ws_frames"] = sum(1 for e in events
                                 if e.get("kind") == "WS_FRAME")
        entry["ws_created"] = sum(1 for e in events
                                  if e.get("kind") == "WS_CREATED")

        # -- the send-completion request body -------------------------------
        for e in find_bodies(events, "/chat/completion"):
            body = e.get("body") or e.get("post_data") or ""
            if not body:
                # body may live in a paired BODY event
                rid = e.get("request_id") or e.get("id")
                for b in events:
                    if b.get("kind") == "REQ_EXTRA" and \
                            (b.get("request_id") or b.get("id")) == rid:
                        body = b.get("body") or b.get("post_data") or ""
                        if body:
                            break
            if body:
                try:
                    parsed = json.loads(body)
                except Exception:
                    parsed = None
                entry["completion_request"] = {
                    "url_head": (e.get("url") or "").split("?")[0],
                    "method": e.get("method"),
                    "body_len": len(body),
                    "parsed": parsed is not None,
                }
                # find video-related keys anywhere in the parsed body
                flat: list[str] = []

                def walk(node, path):
                    if isinstance(node, dict):
                        for k, v in node.items():
                            walk(v, f"{path}.{k}")
                    elif isinstance(node, list):
                        for i, v in enumerate(node):
                            walk(v, f"{path}[{i}]")
                    else:
                        s = str(node)
                        if any(tok in path.lower() for tok in
                               ("video", "model", "option", "ratio",
                                "duration", "resolution", "setup", "config")):
                            flat.append(f"{path} = {s[:160]}")

                if parsed is not None:
                    walk(parsed, "")
                    entry["completion_request"]["video_related_fields"] = \
                        flat[:60]
                else:
                    m = re.search(r"(video|option_key|ratio|duration|"
                                  r"resolution|model)", body[:6000])
                    entry["completion_request"]["raw_probe_hit"] = \
                        m.group(0) if m else None
                break

        # -- composer template (full option list) ---------------------------
        whole = "\n".join(
            json.dumps(e, ensure_ascii=False)[:200000]
            for e in events if e.get("kind") in ("REQ", "RESP", "BODY"))
        unesc = deep_unescape(whole)
        opts = []
        for m in list(re.finditer(
                r"option_key\\?\":\\?\"([a-z0-9_.]+)\\?\"", unesc))[:40]:
            key = m.group(1)
            window = unesc[max(0, m.start() - 800):m.start() + 500]
            disp = re.search(
                r"display_text\\?\":\\?\"([^\"]{2,60})\\?\"", window)
            model = re.search(r"model\\?\":\\?\"([a-z0-9_.\-]+)\\?\"", window)
            sub = re.search(r"sub_display\\?\":\\?\"([^\"]{2,120})\\?\"",
                            window)
            subs = re.search(r"subs_only_tag\\?\":\\?\"([a-z_]+)\\?\"", window)
            opts.append({
                "option_key": key,
                "display": disp.group(1) if disp else None,
                "model": model.group(1) if model else None,
                "sub_display": sub.group(1) if sub else None,
                "subs_only_tag": subs.group(1) if subs else None,
            })
        # dedupe by option_key preserving order
        seen = set()
        uniq = []
        for o in opts:
            if o["option_key"] in seen:
                continue
            seen.add(o["option_key"])
            uniq.append(o)
        entry["composer_option_keys"] = uniq

        # -- duration / ratio templates -------------------------------------
        durs = sorted(set(re.findall(
            r"(?:duration|seconds)\\?\":\\?\"?([0-9]{1,2})", unesc)))[:20]
        ratios = sorted(set(re.findall(
            r"(16:9|9:16|1:1|4:3|3:4|21:9)", unesc)))
        entry["duration_tokens"] = durs
        entry["ratio_tokens"] = ratios
        # resolution tokens near video config
        res_tokens = sorted(set(re.findall(
            r"(480p|720p|1080p|2k|4k)", unesc, re.I)))
        entry["resolution_tokens"] = res_tokens

        # -- creation video_model JSON echo ---------------------------------
        vm_echoes = []
        for m in list(re.finditer(r"video_model\\?\":\\?\"(\{.{50,}?)\\?\",",
                                  unesc))[:6]:
            blob = m.group(1)
            try:
                obj = json.loads(blob.replace('\\\\"', '"').replace('\\\\"',
                                  '"'))
            except Exception:
                obj = None
            keys = sorted(obj.keys()) if isinstance(obj, dict) else []
            vm_echoes.append({"len": len(blob), "top_keys": keys})
        entry["video_model_echoes"] = vm_echoes

        report["captures"][name] = entry

    out = PKG / "V2_019_PHASEA_CAPTURE_FORENSICS.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(json.dumps({"saved": str(out),
                      "captures": {k: {"events": v["events"],
                                       "options": len(v.get(
                                           "composer_option_keys", [])),
                                       "ws": v.get("ws_frames")}
                                   for k, v in report["captures"].items()}},
                     indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
