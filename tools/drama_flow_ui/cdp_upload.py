"""Upload local files into an open Flow tab through its Upload button, over raw CDP.

Why: Claude in Chrome cannot upload on Flow (no input[type=file]; Upload opens the OS picker) and the
NO-JS rule forbids page JavaScript. This tool runs no page JavaScript and never enables the Runtime
domain: it finds the button with DOM.performSearch (XPath), clicks it with Input events, intercepts
the native file chooser (Page.setInterceptFileChooserDialog) and fills it with DOM.setFileInputFiles.

Usage:
  python cdp_upload.py --port 65204 --url-part 6f8e24af --dry            # find tab + button only
  python cdp_upload.py --port 65204 --url-part 6f8e24af FILE [FILE ...]  # upload
The CDP port is the GPM profile's --remote-debugging-port. Never reads cookies or page text.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

import websocket

XPATH = ('//button[contains(normalize-space(.), "{t}")] | '
         '//*[@role="button" and contains(normalize-space(.), "{t}")] | '
         '//*[@aria-label and contains(@aria-label, "{t}")]')


class CDP:
    def __init__(self, ws_url: str) -> None:
        self.ws = websocket.create_connection(ws_url, timeout=60, suppress_origin=True)
        self.n = 0
        self.events: list[dict] = []

    def call(self, method: str, **params) -> dict:
        self.n += 1
        mid = self.n
        self.ws.settimeout(60)
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error'].get('message')}")
                return msg.get("result", {})
            if "method" in msg:
                self.events.append(msg)

    def wait_event(self, name: str, timeout: float) -> dict | None:
        end = time.time() + timeout
        while True:
            for i, event in enumerate(self.events):
                if event["method"] == name:
                    return self.events.pop(i)
            left = end - time.time()
            if left <= 0:
                return None
            self.ws.settimeout(left)
            try:
                msg = json.loads(self.ws.recv())
            except websocket.WebSocketTimeoutException:
                return None
            if "method" in msg:
                self.events.append(msg)


def find_target(port: int, url_part: str) -> dict:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=20) as resp:
        pages = [t for t in json.loads(resp.read()) if t.get("type") == "page" and url_part in t.get("url", "")]
    if len(pages) != 1:
        sys.exit(f"STOP: {len(pages)} tabs match {url_part!r}; keep exactly one Flow project tab open")
    return pages[0]


def find_button(cdp: CDP, text: str) -> tuple[float, float]:
    cdp.call("DOM.getDocument", depth=0)
    found = cdp.call("DOM.performSearch", query=XPATH.format(t=text))
    sid, count = found["searchId"], found["resultCount"]
    try:
        ids = cdp.call("DOM.getSearchResults", searchId=sid, fromIndex=0, toIndex=count)["nodeIds"] if count else []
    finally:
        cdp.call("DOM.discardSearchResults", searchId=sid)
    boxes = []
    for node in ids:
        try:
            quads = cdp.call("DOM.getContentQuads", nodeId=node)["quads"]
        except RuntimeError:
            continue
        if quads:
            q = quads[0]
            w, h = max(q[0::2]) - min(q[0::2]), max(q[1::2]) - min(q[1::2])
            if w > 4 and h > 4:
                boxes.append((sum(q[0::2]) / 4, sum(q[1::2]) / 4, w * h))
    if not boxes:
        sys.exit(f"STOP: no visible element with text/label {text!r} ({count} DOM matches)")
    x, y, _ = min(boxes, key=lambda b: b[2])   # the smallest visible match is the button itself
    return x, y


def click(cdp: CDP, x: float, y: float) -> None:
    cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
    time.sleep(0.3)
    cdp.call("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", clickCount=1)
    cdp.call("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button="left", clickCount=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--url-part", required=True)
    ap.add_argument("--button", default="Upload")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--settle", type=float, default=20.0, help="seconds to wait after each chooser fill")
    ap.add_argument("files", nargs="*")
    args = ap.parse_args()
    files = [str(Path(f).resolve()) for f in args.files]
    missing = [f for f in files if not Path(f).is_file()]
    if missing:
        sys.exit(f"STOP: missing files: {missing}")
    target = find_target(args.port, args.url_part)
    cdp = CDP(target["webSocketDebuggerUrl"])
    x, y = find_button(cdp, args.button)
    print(f"tab ok; button {args.button!r} at ({x:.0f},{y:.0f})")
    if args.dry or not files:
        return
    cdp.call("Page.enable")
    cdp.call("Page.setInterceptFileChooserDialog", enabled=True)
    try:
        queue = list(files)
        while queue:
            x, y = find_button(cdp, args.button)
            click(cdp, x, y)
            event = cdp.wait_event("Page.fileChooserOpened", 15)
            if event is None:
                sys.exit(f"STOP: no file chooser after clicking {args.button!r}; {len(queue)} files not uploaded")
            params = event["params"]
            batch = queue if params.get("mode") == "selectMultiple" else queue[:1]
            cdp.call("DOM.setFileInputFiles", files=batch, backendNodeId=params["backendNodeId"])
            print(f"filled chooser ({params.get('mode')}) with {len(batch)} file(s)")
            queue = queue[len(batch):]
            time.sleep(args.settle)
    finally:
        cdp.call("Page.setInterceptFileChooserDialog", enabled=False)
        cdp.call("Page.disable")
    print(f"uploaded {len(files)} file(s); check the tiles in the tab before using them")


if __name__ == "__main__":
    main()
