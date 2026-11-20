"""Multi-account CDP runner for Film08 on Google Flow (accounts 02, 03, 04, 571).

Ported from the verified single-shot controller (`flow08_live_v2.py`) with:
- fixed per-account email / GPM profile / Flow project mapping
- per-account uploaded-stills ledger and isolated audit directories
- scoped `cdp_scope` checks via `generate.build_payload(..., cdp_scope=...)`
  and `recovery.pending_receipts(..., cdp_scope=...)`
- short cross-process file locks around `LOOP_BACKLOG.md` / `R.reconcile` and
  `~/Downloads` MP4 capture so accounts can execute in parallel safely
- automatic local Faster-Whisper ASR (`audio-qc.json`) upon `acquire`.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import msvcrt
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any
import unicodedata
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener

from websockets.sync.client import connect

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from film_pipeline.production import generate as G  # noqa: E402
from film_pipeline.production import recovery as R  # noqa: E402
from film_pipeline.production import takes as T  # noqa: E402
from film_pipeline.production.halt import is_halted, read_halt, set_halt  # noqa: E402
from film_pipeline.production.package import load_package  # noqa: E402
from film_pipeline.production.runtime import atomic_json  # noqa: E402


@dataclass(frozen=True)
class AccountConfig:
    name: str
    email: str
    profile: str
    project: str
    min_credits: int
    legacy_uploaded: str

    @property
    def project_id(self) -> str:
        return self.project.rsplit("/", 1)[-1]


ACCOUNTS: dict[str, AccountConfig] = {
    "02": AccountConfig(
        name="02",
        email="khoicaesar02@gmail.com",
        profile="5db03bd5-23da-439d-8d1f-7ab2ba5b7a18",
        project="https://flow.google.com/project/d766c3be-a94b-4c44-b339-77eb64f09a95",
        min_credits=20,
        legacy_uploaded="uploaded-stills.json",
    ),
    "03": AccountConfig(
        name="03",
        email="khoicaesar03@gmail.com",
        profile="9db991c3-bed0-47b7-81a2-4ac2d5bcec4f",
        project="https://flow.google.com/project/1f023648-69d2-421f-9bbb-3ee32198b25a",
        min_credits=20,
        legacy_uploaded="uploaded-stills-03.json",
    ),
    "04": AccountConfig(
        name="04",
        email="khoicaesar04@gmail.com",
        profile="7d411b88-7957-4c29-8b24-f5090cb5ab61",
        project="https://flow.google.com/project/f1eb5302-267e-45f3-a45f-f017ef233e18",
        min_credits=20,
        legacy_uploaded="uploaded-stills-04.json",
    ),
    "571": AccountConfig(
        name="571",
        email="khoia1k571@gmail.com",
        profile="ab721728-1a41-4951-af9d-5d1478526fbf",
        project="https://flow.google.com/project/6bcdbef4-86c6-44e7-8449-0f8b8720e509",
        min_credits=20,
        legacy_uploaded="uploaded-stills-571.json",
    ),
}

POOL_ROOT = Path(r"C:\Temp\FILM08_POOL_20261118")
LEGACY_ROOT = Path(r"D:\AI FILM MAKER\_exports\FILM08_CONTINUE_20261117")
LOCK_WRITER = Path(r"C:\Temp\afp-flow-writer.lock")
LOCK_DOWNLOAD = Path(r"C:\Temp\afp-flow-download.lock")
WHISPER_PYTHON = Path(r"C:\Users\ADMIN\AppData\Local\Programs\Python\Python311\python.exe")

WARN_RE = re.compile(
    r"unusual activity|hoạt động bất thường|verify (?:you are|that you are|it.s you)|xác minh bạn là người",
    re.I,
)
FAILURE_RE = re.compile(
    r"^thất bại$|^failed$|^không thành công$|^error$|tạo .*thất bại|vi phạm.*chính sách|policy",
    re.I,
)
UUID_RE = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", re.I)

_NO_PROXY_OPENER = build_opener(ProxyHandler({}))


def _ts() -> datetime:
    return datetime.now().astimezone()


def _http_json(url: str, timeout: int = 8) -> dict[str, Any]:
    with _NO_PROXY_OPENER.open(url, timeout=timeout) as resp:
        return json.load(resp)


@contextmanager
def file_lock(lock_path: Path, timeout_s: float = 25.0):
    """Cross-process Windows non-blocking retry lock kept around short critical sections."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    deadline = time.monotonic() + timeout_s
    acquired = False
    try:
        while True:
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                acquired = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out waiting for lock {lock_path}")
                time.sleep(0.25)
        yield
    finally:
        if acquired:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        handle.close()


class FlowTab:
    """Thin loopback CDP driver bound to one Flow project tab."""

    def __init__(self, cfg: AccountConfig, gpm_port: int = 9495) -> None:
        self.cfg = cfg
        resp = _http_json(f"http://127.0.0.1:{gpm_port}/api/v1/profiles/start/{cfg.profile}", timeout=25)
        if resp.get("success") is not True:
            raise RuntimeError(f"GPM failed to attach account {cfg.name}: {resp.get('message') or resp}")
        data = resp["data"]
        if data.get("remote_debugging_port"):
            self.port = int(data["remote_debugging_port"])
        elif data.get("remote_debugging_address"):
            addr = str(data["remote_debugging_address"])
            parsed = urlsplit(addr if "://" in addr else f"http://{addr}")
            if parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or not parsed.port:
                raise ValueError(f"Unexpected remote_debugging_address for {cfg.name}: {addr!r}")
            self.port = int(parsed.port)
        else:
            raise KeyError(f"Missing CDP port in GPM response for {cfg.name}")
        self.local = f"http://127.0.0.1:{self.port}"
        pages = [a for a in _http_json(f"{self.local}/json/list") if a.get("type") == "page"]
        tabs = [a for a in pages if a.get("url", "").partition("?")[0].rstrip("/") == cfg.project]
        edit_tabs = [a for a in pages if a.get("url", "").partition("?")[0].startswith(cfg.project + "/edit/")]
        if len(tabs) == 0 and len(edit_tabs) == 1:
            self.tab = edit_tabs[0]
            ws_url = str(self.tab["webSocketDebuggerUrl"])
            u = urlsplit(ws_url)
            if u.scheme != "ws" or u.hostname not in {"127.0.0.1", "localhost", "::1"} or u.port != self.port:
                raise ValueError(f"Unsafe websocket URL for {cfg.name}: {ws_url!r}")
            self.ws = ws_url
            self.press_escape()
            time.sleep(0.2)
            back_btns = self.visible("Nút quay lại để quay về trang trước")
            if len(back_btns) == 1:
                self.click(back_btns[0])
            else:
                self.api("Page.navigate", {"url": cfg.project})
            for _ in range(12):
                time.sleep(0.35)
                pages = [a for a in _http_json(f"{self.local}/json/list") if a.get("type") == "page"]
                tabs = [a for a in pages if a.get("url", "").partition("?")[0].rstrip("/") == cfg.project]
                if len(tabs) == 1:
                    break
            if len(tabs) == 0:
                self.api("Page.navigate", {"url": cfg.project})
                for _ in range(12):
                    time.sleep(0.35)
                    pages = [a for a in _http_json(f"{self.local}/json/list") if a.get("type") == "page"]
                    tabs = [a for a in pages if a.get("url", "").partition("?")[0].rstrip("/") == cfg.project]
                    if len(tabs) == 1:
                        break
        if len(tabs) != 1:
            seen = [a.get("url", "").partition("?")[0] for a in pages]
            raise ValueError(f"Expected 1 Flow tab on {cfg.email} ({cfg.project}); got {len(tabs)}. Open URLs: {seen}")
        self.tab = tabs[0]
        ws_url = str(self.tab["webSocketDebuggerUrl"])
        u = urlsplit(ws_url)
        if u.scheme != "ws" or u.hostname not in {"127.0.0.1", "localhost", "::1"} or u.port != self.port:
            raise ValueError(f"Unsafe websocket URL for {cfg.name}: {ws_url!r}")
        self.ws = ws_url

    def api(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        with connect(self.ws, open_timeout=6) as conn:
            conn.send(json.dumps({"id": 1, "method": method, "params": params or {}}))
            limit = time.monotonic() + 9.0
            while time.monotonic() < limit:
                msg = json.loads(conn.recv(timeout=max(0.01, limit - time.monotonic())))
                if msg.get("id") == 1:
                    if "error" in msg:
                        raise ValueError(f"{method} {str(msg['error'].get('message', ''))[:140]}")
                    return msg.get("result", {})
            raise TimeoutError(method)

    @staticmethod
    def call(conn: Any, method: str, params: dict[str, Any] | None = None,
             events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        ident = time.monotonic_ns() % 2_000_000_000
        conn.send(json.dumps({"id": ident, "method": method, "params": params or {}}))
        while True:
            out = json.loads(conn.recv(timeout=9))
            if out.get("id") == ident:
                if "error" in out:
                    raise ValueError(f"{method} {str(out['error'].get('message', ''))[:140]}")
                return out.get("result", {})
            if events is not None and "method" in out:
                events.append(out)

    @staticmethod
    def val(node: dict[str, Any], key: str) -> str:
        return unicodedata.normalize("NFC", str(node.get(key, {}).get("value", "")))

    @staticmethod
    def assert_safe(nodes: list[tuple[str, str, Any]]) -> None:
        hit = next((s for _, s, _ in nodes if WARN_RE.search(s)), None)
        if hit:
            # Owner rule: any account warning stops ALL sending on this machine until a human/agent clears it.
            set_halt(f"ACCOUNT_WARNING_OR_CAPTCHA: {hit[:160]}", source="flow_pool_runner", evidence=hit[:160])
            raise RuntimeError(f"ACCOUNT_WARNING_OR_CAPTCHA: {hit[:160]}")

    def tree(self) -> list[dict[str, Any]]:
        nodes = [x for x in self.api("Accessibility.getFullAXTree")["nodes"] if not x.get("ignored")]
        self.assert_safe([(self.val(x, "role"), self.val(x, "name"), x.get("backendDOMNodeId")) for x in nodes])
        return nodes

    def snap(self) -> list[tuple[str, str, Any]]:
        rows = [(self.val(n, "role"), self.val(n, "name"), n.get("backendDOMNodeId")) for n in self.tree()]
        return rows

    def over(self, backend_id: int) -> tuple[float, float]:
        pts = self.api("DOM.getBoxModel", {"backendNodeId": backend_id})["model"]["border"]
        return sum(pts[::2]) / 4.0, sum(pts[1::2]) / 4.0

    def mouse(self, kind: str, x: float, y: float, **kwargs: Any) -> dict[str, Any]:
        return self.api("Input.dispatchMouseEvent", dict(type=kind, x=x, y=y, **kwargs))

    def click(self, backend_id: int) -> None:
        self.api("DOM.scrollIntoViewIfNeeded", {"backendNodeId": backend_id})
        x, y = self.over(backend_id)
        for evt in ("mousePressed", "mouseReleased"):
            self.mouse(evt, x, y, button="left", clickCount=1)

    def press_escape(self) -> None:
        for evt in ("keyDown", "keyUp"):
            self.api("Input.dispatchKeyEvent", {"type": evt, "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})

    def visible(self, regex: str, roles: tuple[str, ...] = ("button",)) -> list[tuple[str, int]]:
        return [(n, k) for r, n, k in self.snap() if r in roles and k and re.fullmatch(regex, n, re.I)]

    def find_node(self, regex: str, roles: tuple[str, ...] = ("button",)) -> int:
        matches = {k for r, n, k in self.snap() if r in roles and k and re.fullmatch(regex, n, re.I)}
        if len(matches) != 1:
            raise ValueError(f"Expected 1 control for {regex!r} (roles={roles}); got {len(matches)}")
        return matches.pop()

    def focused_value(self, backend_id: int) -> str:
        return next(self.val(n, "value").strip() for n in self.tree() if n.get("backendDOMNodeId") == backend_id)

    def balance(self) -> int:
        if not self.visible("Đóng bảng điều khiển tài khoản"):
            self.click(self.find_node("Thông tin về tài khoản"))
        for _ in range(8):
            time.sleep(0.3)
            nodes = self.snap()
            if any(self.cfg.email.lower() in s.lower() for _, s, _ in nodes):
                vals = {
                    m[1] for _, s, _ in nodes
                    for m in [re.fullmatch(r"\s*([\d .,]+) tín dụng Google Flow\s*", s, re.I)] if m
                }
                if len(vals) == 1:
                    return int(re.sub(r"[^0-9]", "", vals.pop()))
        raise ValueError(f"Unable to verify account {self.cfg.email} and read credit balance")

    def close_account_panel(self) -> None:
        if self.visible("Đóng bảng điều khiển tài khoản"):
            self.click(self.find_node("Đóng bảng điều khiển tài khoản"))
            time.sleep(0.2)

    def current_settings(self) -> None:
        nodes = self.tree()

        def selected(regex: str, prop: str = "checked", expected: str = "true") -> bool:
            return any(
                re.fullmatch(regex, self.val(x, "name"), re.I)
                and any(p["name"] == prop and p.get("value", {}).get("value") == expected for p in x.get("properties", []))
                for x in nodes
            )

        for item in ("Video", "Khung hình", "16:9", "360p.*", "x1"):
            if not selected(item):
                raise ValueError(f"Composer setting not selected: {item}")
        if not selected("Tác nhân", "pressed", "false"):
            raise ValueError("Composer setting 'Tác nhân' must be off")
        names = {self.val(x, "name") for x in nodes}
        required = {"6 tín dụng", "6 giây", "Omni 1.2 Flash"}
        if not required.issubset(names):
            raise ValueError(f"Model or quoted credits changed; missing {required - names}")

    def cards(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        with connect(self.ws, open_timeout=6) as conn:
            root_id = self.call(conn, "DOM.getDocument", {"depth": 1})["root"]["nodeId"]
            tiles = self.call(conn, "DOM.querySelectorAll", {"nodeId": root_id, "selector": "flow-grid-tile-container"})["nodeIds"]
            for tile_id in tiles[:20]:
                attrs = self.call(conn, "DOM.getAttributes", {"nodeId": tile_id})["attributes"]
                data = dict(zip(attrs[::2], attrs[1::2]))
                inner = self.call(conn, "DOM.getOuterHTML", {"nodeId": tile_id})["outerHTML"]
                vid = self.call(conn, "DOM.querySelectorAll", {"nodeId": tile_id, "selector": "flow-video-tile"})["nodeIds"]
                result.append({
                    "title": data.get("aria-label", ""),
                    "video": bool(vid),
                    "backend_id": self.call(conn, "DOM.describeNode", {"nodeId": vid[0]})["node"]["backendNodeId"] if vid else None,
                    "ids": sorted(set(UUID_RE.findall(inner))),
                })
        return result

    def upload_file(self, path: Path) -> None:
        btn = self.find_node("Tải nội dung nghe nhìn lên")
        x, y = self.over(btn)
        with connect(self.ws, open_timeout=6) as conn:
            self.call(conn, "Page.enable")
            self.call(conn, "Page.setInterceptFileChooserDialog", {"enabled": True})
            try:
                events: list[dict[str, Any]] = []
                for evt in ("mousePressed", "mouseReleased"):
                    self.call(conn, "Input.dispatchMouseEvent",
                              {"type": evt, "x": x, "y": y, "button": "left", "clickCount": 1}, events=events)
                while not any(e.get("method") == "Page.fileChooserOpened" for e in events):
                    events.append(json.loads(conn.recv(timeout=6)))
                ids = [e["params"].get("backendNodeId") for e in events if e.get("method") == "Page.fileChooserOpened"]
                if len(ids) != 1 or not ids[0]:
                    raise RuntimeError(f"Unexpected fileChooserOpened ids: {ids}")
                self.call(conn, "DOM.setFileInputFiles", {"files": [str(path)], "backendNodeId": ids[0]})
            finally:
                self.call(conn, "Page.setInterceptFileChooserDialog", {"enabled": False})


def _uploaded_map_path(cfg: AccountConfig) -> Path:
    path = POOL_ROOT / f"uploaded-stills-{cfg.name}.json"
    if not path.exists():
        POOL_ROOT.mkdir(parents=True, exist_ok=True)
        seed = LEGACY_ROOT / cfg.legacy_uploaded
        if seed.is_file():
            shutil.copyfile(seed, path)
        else:
            atomic_json(path, {})
    return path


def _current_pointer(cfg: AccountConfig) -> Path:
    return POOL_ROOT / cfg.name / "current.json"


def _resolve_audit(cfg: AccountConfig, gid: str | None) -> tuple[str, Path]:
    ptr = _current_pointer(cfg)
    if not ptr.is_file():
        raise FileNotFoundError(f"No active prepared shot for account {cfg.name} ({ptr})")
    cur = json.loads(ptr.read_text(encoding="utf-8"))
    if gid and cur["gid"] != gid:
        raise ValueError(f"Account {cfg.name} active shot is {cur['gid']}, not {gid}")
    return str(cur["gid"]), Path(cur["audit_dir"])


def _run_asr(voice_wav: Path, out_json: Path) -> dict[str, Any]:
    if not WHISPER_PYTHON.is_file():
        raise FileNotFoundError(f"Faster-Whisper interpreter not found at {WHISPER_PYTHON}")
    code = (
        "import json, sys; from pathlib import Path; "
        "from faster_whisper import WhisperModel; "
        "from faster_whisper.audio import decode_audio; "
        "from faster_whisper.vad import VadOptions, get_speech_timestamps; "
        "wav = Path(sys.argv[1]); out = Path(sys.argv[2]); "
        "cache = Path.home() / '.cache/huggingface/hub/models--Systran--faster-whisper-small.en/snapshots'; "
        "saved = next(d for d in cache.iterdir() if (d / 'model.bin').is_file()); "
        "model = WhisperModel(str(saved), device='cpu', compute_type='int8', local_files_only=True, cpu_threads=2); "
        "pcm = decode_audio(str(wav)); "
        "vad = get_speech_timestamps(pcm, VadOptions(min_speech_duration_ms=180)); "
        "segs, _ = model.transcribe(pcm, language='en', beam_size=5, vad_filter=True, word_timestamps=True); "
        "s = [{'text': x.text.strip(), 'start': x.start, 'end': x.end, "
        "'words': [{'word': y.word, 'start': y.start, 'end': y.end} for y in x.words]} for x in segs]; "
        "res = {'vad_samples_16khz': vad, 'segments': s}; "
        "out.write_text(json.dumps(res, indent=2) + '\\n', encoding='utf-8'); "
        "print(json.dumps([{'text': x['text'], 'start': x['start'], 'end': x['end']} for x in s]))"
    )
    proc = subprocess.run([str(WHISPER_PYTHON), "-c", code, str(voice_wav), str(out_json)],
                          capture_output=True, text=True, check=True)
    return {"segments": json.loads(proc.stdout.strip() or "[]"), "audio_qc": str(out_json)}


def do_status(tab: FlowTab, pkg: Any) -> None:
    cfg = tab.cfg
    bal = tab.balance()
    tab.close_account_panel()
    nodes = tab.snap()
    renders = sorted({s for _, s, _ in nodes if re.fullmatch(r"\d{1,3}%", s)})
    failures = sorted({s for _, s, _ in nodes if len(s) < 140 and FAILURE_RE.search(s)})
    ptr = _current_pointer(cfg)
    cur = json.loads(ptr.read_text(encoding="utf-8")) if ptr.is_file() else None
    print(json.dumps({
        "account": cfg.name,
        "email": cfg.email,
        "project_id": cfg.project_id,
        "cdp": tab.local,
        "balance": bal,
        "min_credits": cfg.min_credits,
        "max_sends_available": max(0, (bal - cfg.min_credits) // 6),
        "pending_receipts": R.pending_receipts(pkg, cdp_scope=cfg.project_id),
        "active_renders": renders,
        "visible_failures": failures,
        "current": cur,
        "front_tiles": [(c["title"], c["video"], len(c["ids"])) for c in tab.cards()[:5]],
    }, ensure_ascii=False, indent=2))


def do_prep(tab: FlowTab, pkg: Any, film: Path, gid: str) -> None:
    cfg = tab.cfg
    pending = R.pending_receipts(pkg, cdp_scope=cfg.project_id)
    if pending:
        raise RuntimeError(f"Pending receipts on {cfg.name}: {pending}")
    payload = G.build_payload(pkg, gid, cdp_scope=cfg.project_id)
    if payload["blockers"]:
        raise RuntimeError(f"Blockers for {gid}: {payload['blockers']}")
    if payload["expected_credits"] != 6 or payload["duration_s"] != 6:
        raise ValueError(f"Unexpected price/duration for {gid}: {payload['expected_credits']}cr {payload['duration_s']}s")
    if payload["credits_spent"] + 6 > payload["credit_cap"]:
        raise RuntimeError(f"Film credit cap exceeded for {gid}")
    if "end_frame" in payload:
        raise ValueError(f"End-frame shot {gid} not supported by start-only runner")

    if any(n == "Chọn một hình ảnh khung" for _, n, _ in tab.snap()):
        tab.press_escape()
        time.sleep(0.3)
    bal = tab.balance()
    if bal - 6 < cfg.min_credits:
        raise RuntimeError(f"Account {cfg.name} balance {bal} below floor {cfg.min_credits} + 6")
    tab.close_account_panel()

    if any(re.fullmatch(r"\d{1,3}%", s) for _, s, _ in tab.snap()):
        raise RuntimeError(f"Visible pending render on account {cfg.name}")
    prompt_box = tab.find_node(r"Bạn muốn tạo những gì\?", ("textbox",))
    if tab.focused_value(prompt_box).strip("\u200b\u200c\u200d\ufeff"):
        raise RuntimeError(f"Unexpected non-empty composer prompt on account {cfg.name}")

    start = Path(payload["start_frame"]["file"]).resolve(strict=True)
    if not start.is_relative_to(film) or hashlib.sha256(start.read_bytes()).hexdigest() != payload["start_frame"]["sha256"]:
        raise ValueError(f"Start frame mismatch for {gid}: {start}")

    uploaded_path = _uploaded_map_path(cfg)
    uploaded_raw = json.loads(uploaded_path.read_text(encoding="utf-8"))
    uploaded: dict[str, str] = {}
    asset_uuids: dict[str, set[str]] = {}
    for k, v in uploaded_raw.items():
        if isinstance(v, dict):
            uploaded[k] = str(v["sha256"])
            if v.get("uuids"):
                asset_uuids[k] = set(v["uuids"])
        else:
            uploaded[k] = str(v)
    target_sha = payload["start_frame"]["sha256"]
    verified_names = {k for k, v in uploaded.items() if v == target_sha}

    def _save_uploaded() -> None:
        out_map: dict[str, Any] = {}
        for k, sha in uploaded.items():
            if asset_uuids.get(k):
                out_map[k] = {"sha256": sha, "uuids": sorted(asset_uuids[k])}
            else:
                out_map[k] = sha
        atomic_json(uploaded_path, out_map)

    def _guids(backend_id: int) -> set[str]:
        html = tab.api("DOM.getOuterHTML", {"backendNodeId": backend_id})["outerHTML"]
        return set(UUID_RE.findall(html))

    def attached() -> bool:
        if not verified_names:
            return False
        rows = tab.snap()
        slots = [i for r, n, i in rows if r == "button" and n == "Thành phần tạo hình ảnh" and i]
        if len(slots) != 1 or tab.visible("Bắt đầu"):
            return False
        slot_ids = _guids(slots[0])
        if not slot_ids:
            return False
        for k in verified_names:
            known = asset_uuids.get(k, set())
            if known and (known & slot_ids):
                return True
        names = [i for r, n, i in rows if r == "group" and n in verified_names and i]
        for bid in names:
            common = _guids(bid) & slot_ids
            if common:
                matched_name = next(n for r, n, i in rows if i == bid)
                asset_uuids.setdefault(matched_name, set()).update(common)
                _save_uploaded()
                return True
        return False

    if not attached():
        if not tab.visible("Bắt đầu"):
            tab.api("Page.reload")
            time.sleep(3.5)
        grid_groups = {n for r, n, _ in tab.snap() if r == "group"}
        tab.click(tab.find_node("Bắt đầu"))
        time.sleep(0.35)
        ordered_candidates = ([start.name] if start.name in verified_names else []) + sorted(
            k for k in verified_names if k != start.name
        )
        chosen_asset: str | None = None
        for cand in ordered_candidates:
            can_verify = cand in grid_groups or bool(asset_uuids.get(cand))
            if can_verify and len(tab.visible(re.escape(cand), ("option",))) == 1:
                chosen_asset = cand
                break
        if chosen_asset is None:
            upload_src = start
            upload_name = start.name
            if tab.visible(re.escape(start.name), ("option",)):
                upload_name = f"{start.stem}_{target_sha[:8]}{start.suffix}"
                cache_dir = POOL_ROOT / cfg.name / "_upload_cache"
                cache_dir.mkdir(parents=True, exist_ok=True)
                upload_src = cache_dir / upload_name
                if not upload_src.is_file() or hashlib.sha256(upload_src.read_bytes()).hexdigest() != target_sha:
                    shutil.copyfile(start, upload_src)
            fname = re.escape(upload_name)
            if not tab.visible(fname, ("option",)):
                tab.upload_file(upload_src)
                for _ in range(22):
                    time.sleep(0.6)
                    if len(tab.visible(fname, ("option",))) == 1:
                        break
                else:
                    raise TimeoutError(f"Upload of {upload_name} did not create one exact option")
            uploaded[upload_name] = target_sha
            verified_names.add(upload_name)
            _save_uploaded()
            chosen_asset = upload_name
        fname = re.escape(chosen_asset)
        tab.click(tab.find_node(fname, ("option",)))
        for _ in range(14):
            time.sleep(0.45)
            if attached():
                break
            if any(s == "Bản xem trước của " + chosen_asset for _, s, _ in tab.snap()):
                tab.click(tab.find_node("Thêm vào câu lệnh"))
                time.sleep(0.5)
                continue
        if not attached():
            raise RuntimeError(f"Exact start frame {chosen_asset} did not bind to composer")

    prompt = Path(payload["prompt_file"]).read_text(encoding="utf-8").strip()
    if hashlib.sha256(prompt.encode("utf-8")).hexdigest() != payload["prompt_sha256"]:
        raise ValueError("Prompt hash mismatch during prep")
    prompt_box = tab.find_node(r"Bạn muốn tạo những gì\?", ("textbox",))
    tab.click(prompt_box)
    tab.api("Input.insertText", {"text": prompt})
    time.sleep(0.4)
    if tab.focused_value(prompt_box) != prompt:
        raise RuntimeError("Inserted prompt text mismatch")

    tab.click(tab.find_node("Điều kiện kích hoạt cài đặt"))
    time.sleep(0.32)
    tab.current_settings()

    take_id = payload["take_id"]
    audit_dir = POOL_ROOT / cfg.name / take_id
    audit_dir.mkdir(parents=True, exist_ok=True)
    atomic_json(audit_dir / "prepared.json", {
        "account": cfg.name,
        "gid": gid,
        "take_id": take_id,
        "shot_version": payload["shot_version"],
        "prompt_sha256": payload["prompt_sha256"],
        "balance_before": bal,
        "expected_credits": payload["expected_credits"],
        "project_id": cfg.project_id,
    })
    atomic_json(_current_pointer(cfg), {"gid": gid, "take_id": take_id, "audit_dir": str(audit_dir)})
    print("prepared", cfg.name, take_id, "balance", bal)


def _refuse_if_halted() -> None:
    if is_halted():
        raise RuntimeError(f"PRODUCTION_HALT: {(read_halt() or {}).get('reason', '')}; nothing was submitted")


def do_submit(tab: FlowTab, pkg: Any, film: Path, gid: str | None, cooldown_s: int) -> None:
    cfg = tab.cfg
    _refuse_if_halted()
    pending = R.pending_receipts(pkg, cdp_scope=cfg.project_id)
    if pending:
        raise RuntimeError(f"Pending receipts on {cfg.name}: {pending}")
    active_gid, audit_dir = _resolve_audit(cfg, gid)
    prepared = json.loads((audit_dir / "prepared.json").read_text(encoding="utf-8"))
    take_id = prepared["take_id"]

    # Per-account cooldown based only on manifests recorded against this account's project_id.
    if cooldown_s > 0:
        times: list[datetime] = []
        for mf in (film / "media" / "takes").glob("*.take.json"):
            try:
                m = json.loads(mf.read_text(encoding="utf-8"))
                if m.get("method") == "manual_cdp_ui" and m.get("project") == cfg.project_id and m.get("finished"):
                    dt = datetime.fromisoformat(m["finished"])
                    if dt.tzinfo:
                        times.append(dt)
            except (OSError, ValueError):
                continue
        if times:
            wait = (max(times) + timedelta(seconds=cooldown_s) - _ts()).total_seconds()
            if wait > 25:
                raise RuntimeError(f"WAIT_COOLDOWN: {round(wait)}s remaining on account {cfg.name}")
            if wait > 0:
                print(f"scheduled_wait_s {round(wait)}", flush=True)
                time.sleep(wait + 0.2)

    tab.current_settings()
    tab.press_escape()
    time.sleep(0.2)
    prompt_box = tab.find_node(r"Bạn muốn tạo những gì\?", ("textbox",))
    if hashlib.sha256(tab.focused_value(prompt_box).encode("utf-8")).hexdigest() != prepared["prompt_sha256"]:
        raise RuntimeError("Composer prompt drifted before submit")
    if tab.visible("Bắt đầu"):
        raise RuntimeError("Start frame detached ('Bắt đầu' visible)")
    if any(re.fullmatch(r"\d{1,3}%", s) for _, s, _ in tab.snap()):
        raise RuntimeError("Render already in progress")
    if (film / "takes" / "intents" / f"{take_id}.intent.json").exists():
        raise FileExistsError(f"Intent receipt already exists for {take_id}")
    base = tab.cards()
    if not base:
        raise RuntimeError(f"No existing cards found to anchor before_ids on {cfg.name}")

    def runner(argv: list[str], out: Path, before_submit: Any = None) -> dict[str, Any]:
        if out.stem != take_id:
            raise ValueError(f"Take mismatch: {out.stem} != {take_id}")
        _refuse_if_halted()
        if before_submit is None:   # S1: no broker pre-Enter checkpoint, no click
            raise RuntimeError("NOT_SENT RUNNER_NOT_CHECKPOINTED: no broker pre-Enter check; nothing was submitted")
        send_btn = tab.find_node("Bắt đầu tạo")
        x, y = tab.over(send_btn)
        record: dict[str, Any] = {
            "result": "PENDING",
            "submission_phase": "SUBMITTING",
            "submitting_at": _ts().isoformat(timespec="seconds"),
            "account": cfg.name,
            "project": cfg.project_id,
            "prompt_sha256": prepared["prompt_sha256"],
            "before_ids": sorted({i for v in base for i in v["ids"]}),
            "baseline_titles": [v["title"] for v in base if v["video"]],
            "balance_before": prepared["balance_before"],
            "expected_credits": 6,
            "method": "manual_cdp_ui",
        }
        manifest = out.with_suffix(".take.json")
        if manifest.exists():
            raise FileExistsError(f"Manifest already exists: {manifest}")
        atomic_json(manifest, record)
        if is_halted():   # re-check immediately before the click; nothing was submitted, so drop the pending manifest
            manifest.unlink(missing_ok=True)
            _refuse_if_halted()
        try:   # the broker's pre-Enter check (halt + epoch + lease, one transaction) immediately before the click
            before_submit({"project": cfg.project_id})
        except BaseException:
            manifest.unlink(missing_ok=True)   # NOT_SENT: nothing was submitted
            raise
        for evt in ("mousePressed", "mouseReleased"):
            tab.mouse(evt, x, y, button="left", clickCount=1)
        record.update(submission_phase="SUBMITTED", submitted_at=_ts().isoformat(timespec="seconds"))
        atomic_json(manifest, record)
        return record

    runner.takes_before_submit = True   # type: ignore[attr-defined]
    backlog = REPO_ROOT / "docs" / "production" / "LOOP_BACKLOG.md"
    with file_lock(LOCK_WRITER):
        raw = backlog.read_bytes()
        if len(re.findall(rb"(?m)^OWNER_GO_LIVE: NO\r?$", raw)) != 1:
            raise RuntimeError("LOOP_BACKLOG.md does not have exactly one 'OWNER_GO_LIVE: NO' line")
        go = re.sub(rb"(?m)^OWNER_GO_LIVE: NO(?=\r?$)", b"OWNER_GO_LIVE: YES", raw)
        try:
            backlog.write_bytes(go)
            done = G.generate(pkg, active_gid, dry_run=False, backlog=backlog, runner=runner,
                              auto_resend=0, cdp_scope=cfg.project_id)
        finally:
            if backlog.read_bytes() == go:
                backlog.write_bytes(raw)
            else:
                raise RuntimeError("Backlog drift during send; manual check required")
    print("submit_result", cfg.name, take_id, done.get("manifest_result"), done.get("refused", []))
    if not done.get("sent") or done.get("manifest_result") != "PENDING":
        raise RuntimeError(f"Send did not reach PENDING: {done}")


def do_poll(tab: FlowTab, gid: str | None) -> None:
    cfg = tab.cfg
    rows = tab.snap()
    progress = sorted({s for _, s, _ in rows if re.fullmatch(r"\d{1,3}%", s)})
    failures = sorted({s for _, s, _ in rows if len(s) < 140 and FAILURE_RE.search(s)})
    ptr = _current_pointer(cfg)
    cur = json.loads(ptr.read_text(encoding="utf-8")) if ptr.is_file() else None
    if gid and cur and cur.get("gid") != gid:
        cur = {"note": f"current pointer is {cur.get('gid')}, requested {gid}"}
    print(json.dumps({
        "account": cfg.name,
        "current": cur,
        "progress": progress,
        "failures": failures,
        "front": [(c["title"], c["video"], c["backend_id"]) for c in tab.cards()[:5]],
    }, ensure_ascii=False, indent=2))


def _select_candidate_cards(cards: list[dict[str, Any]], before_ids: set[str], title: str | None) -> list[dict[str, Any]]:
    if title:
        found = [c for c in cards if c["title"] == title and c["video"]]
        if not found:
            raise RuntimeError(f"Missing result video tile for title={title!r}")
        return [found[0]]
    found = [c for c in cards[:8] if c["video"] and (set(c["ids"]) - before_ids)]
    if not found:
        found = [c for c in cards[:3] if c["video"]]
    if not found:
        raise RuntimeError("No finished video tile found in top cards")
    return found


def do_acquire(tab: FlowTab, pkg: Any, film: Path, gid: str | None, title: str | None) -> None:
    cfg = tab.cfg
    _, audit_dir = _resolve_audit(cfg, gid)
    prepared = json.loads((audit_dir / "prepared.json").read_text(encoding="utf-8"))
    take_id = prepared["take_id"]
    manifest = film / "media" / "takes" / f"{take_id}.take.json"
    rec = json.loads(manifest.read_text(encoding="utf-8"))
    if rec.get("result") != "PENDING" or rec.get("submission_phase") != "SUBMITTED":
        raise RuntimeError(f"Take manifest not ready for acquire: {rec.get('result')} {rec.get('submission_phase')}")
    receipt = json.loads((film / "takes" / "intents" / f"{take_id}.intent.json").read_text(encoding="utf-8"))
    prompt_snap = (film / "takes" / "intents" / f"{take_id}.prompt.txt").read_text(encoding="utf-8").strip()
    if not (hashlib.sha256(prompt_snap.encode("utf-8")).hexdigest() == rec["prompt_sha256"] == receipt["prompt_sha256"]):
        raise ValueError("Prompt hash mismatch across snapshot / manifest / receipt")
    if any(re.fullmatch(r"\d{1,3}%", s) for _, s, _ in tab.snap()):
        raise RuntimeError("Render still active in Flow UI")

    used_media = {
        json.loads(f.read_text(encoding="utf-8")).get("media_id")
        for f in (film / "media" / "takes").glob("*.take.json")
        if f != manifest
    }
    before_ids = set(rec["before_ids"])
    candidates = _select_candidate_cards(tab.cards(), before_ids, title)

    chosen: dict[str, Any] | None = None
    expected_ws = " ".join(prompt_snap.split())
    for cand in candidates:
        tab.click(cand["backend_id"])
        time.sleep(0.75)
        target = next(t for t in _http_json(f"{tab.local}/json/list") if t["id"] == tab.tab["id"])
        current = urlsplit(target["url"])
        match = re.fullmatch(urlsplit(cfg.project).path + r"/edit/([a-f0-9-]{36})", current.path)
        if not (current.scheme == "https" and current.hostname == "flow.google.com" and match):
            raise RuntimeError(f"Unexpected detail URL: {target['url']}")
        media = match[1]
        if media in before_ids or media in used_media:
            if len(candidates) == 1:
                raise RuntimeError(f"Candidate media {media} already used or in before_ids")
            tab.click(tab.find_node("Nút quay lại để quay về trang trước"))
            time.sleep(0.5)
            continue
        ax_txt = " ".join(" ".join((tab.val(n, "name"), tab.val(n, "value"))) for n in tab.tree())
        if expected_ws in " ".join(ax_txt.split()):
            chosen = {"media_id": media, "title": cand["title"]}
            break
        if len(candidates) == 1:
            raise ValueError("Result detail prompt does not match sent prompt")
        tab.click(tab.find_node("Nút quay lại để quay về trang trước"))
        time.sleep(0.5)

    if chosen is None:
        raise RuntimeError("No candidate tile matched new media_id and exact sent prompt")

    raw_copy = audit_dir / f"{take_id}.raw.mp4"
    dl_dir = Path.home() / "Downloads"
    with file_lock(LOCK_DOWNLOAD):
        before_files = {x.name: x.stat().st_mtime_ns for x in dl_dir.glob("*.mp4")}
        tab.click(tab.find_node("Tải nội dung nghe nhìn xuống"))
        time.sleep(0.35)
        tab.click(tab.find_node(r"360p .*gốc", ("menuitem",)))
        norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
        want_norm = norm(chosen["title"])
        prefix_norm = want_norm[:16]
        hits: list[Path] = []
        for _ in range(40):
            time.sleep(0.5)
            if any(dl_dir.glob("*.crdownload")):
                continue
            hits = [
                x for x in dl_dir.glob("*.mp4")
                if (not prefix_norm or norm(x.stem).startswith(prefix_norm))
                and x.stat().st_mtime_ns > before_files.get(x.name, 0)
            ]
            if len(hits) == 1:
                break
        if len(hits) != 1:
            raise RuntimeError(f"Download not unique for title={chosen['title']!r}; hits={[h.name for h in hits]}")
        shutil.copyfile(hits[0], raw_copy)
        dl_name = hits[0].name
        if not (raw_copy.is_file() and raw_copy.stat().st_size == hits[0].stat().st_size > 0):
            raise RuntimeError(f"Copied raw clip verification failed for {raw_copy}")
        hits[0].unlink(missing_ok=True)

    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_type,width,height,r_frame_rate,start_time,duration,nb_frames:format=duration",
        "-of", "json", str(raw_copy),
    ]))
    vstream = next(x for x in probe["streams"] if x["codec_type"] == "video")
    if (vstream["width"], vstream["height"], vstream["r_frame_rate"], int(vstream["nb_frames"])) != (640, 360, "24/1", 144):
        raise ValueError(f"Unexpected stream geometry/frames: {vstream}")
    subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(raw_copy), "-f", "null", "NUL"], check=True)

    dl = {
        "media_id": chosen["media_id"],
        "title": chosen["title"],
        "prompt_sha256": rec["prompt_sha256"],
        "download": dl_name,
        "sha256": T.sha256_file(raw_copy),
        "bytes": raw_copy.stat().st_size,
        "probe": probe,
    }
    atomic_json(audit_dir / "download.json", dl)

    tab.click(tab.find_node("Nút quay lại để quay về trang trước"))
    for _ in range(8):
        time.sleep(0.35)
        t = next(x for x in _http_json(f"{tab.local}/json/list") if x["id"] == tab.tab["id"])
        if t["url"].partition("?")[0].rstrip("/") == cfg.project:
            break
    else:
        raise TimeoutError(f"Failed to return to Flow project {cfg.project}")

    after = tab.balance()
    tab.close_account_panel()
    delta = rec["balance_before"] - after
    atomic_json(audit_dir / "download.json", {
        **dl, "balance_before": rec["balance_before"], "balance_after": after, "actual_credits": delta,
    })
    if delta != rec["expected_credits"]:
        raise ValueError(f"Actual debit {delta} != expected {rec['expected_credits']} on {cfg.name}")

    out_mp4 = manifest.with_suffix("").with_suffix(".mp4")
    if out_mp4.exists():
        raise FileExistsError(f"Target take clip already exists: {out_mp4}")
    with raw_copy.open("rb") as src_h, out_mp4.open("xb") as dst_h:
        shutil.copyfileobj(src_h, dst_h)
    if T.sha256_file(out_mp4) != dl["sha256"]:
        raise ValueError("Copied take SHA-256 mismatch")

    rec.update(
        result="PASSED",
        file=out_mp4.name,
        sha256=dl["sha256"],
        bytes=dl["bytes"],
        duration_s=float(probe["format"]["duration"]),
        media_id=chosen["media_id"],
        binding="RECONCILE_PROMPT_MATCH",
        flow_detail_prompt_verified=True,
        balance_after=after,
        actual_credits=delta,
        finished=_ts().isoformat(timespec="seconds"),
    )
    atomic_json(manifest, rec)

    with file_lock(LOCK_WRITER):
        done = R.reconcile(pkg, take_id)
        if not done.get("resolved") or done.get("take", {}).get("take_id") != take_id:
            raise RuntimeError(f"Reconcile failed: {done}")
        if R.pending_receipts(pkg, cdp_scope=cfg.project_id):
            raise RuntimeError(f"Scoped pending receipt still open after reconcile on {cfg.name}")

    voice = audit_dir / "voice.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(out_mp4), "-vn", "-ac", "1", "-ar", "16000", "-y", str(voice)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(out_mp4), "-vf", "fps=2,scale=320:-1,tile=4x3",
                    "-frames:v", "1", "-y", str(audit_dir / "contact.jpg")], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(out_mp4), "-vf", "scale=216:122,tile=8x6",
                    "-frames:v", "3", "-q:v", "3", "-y", str(audit_dir / "motion-%d.jpg")], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(out_mp4), "-vf", "scale=180:101,tile=12x12",
                    "-frames:v", "1", "-q:v", "3", "-y", str(audit_dir / "all144.jpg")], check=True)
    asr = _run_asr(voice, audit_dir / "audio-qc.json")
    print(json.dumps({
        "reconciled": take_id,
        "account": cfg.name,
        "balance_before": rec["balance_before"],
        "balance_after": after,
        "debit": delta,
        "audit_dir": str(audit_dir),
        "asr_segments": asr["segments"],
    }, ensure_ascii=False, indent=2))


RETIRED = ("flow_pool_runner is retired as a sender (upgrade step 4): every Flow send goes through "
           "`afp-film generate --film <film> --gid <generation>` (production/generate.py), which takes an exclusive "
           "account lease from the machine-wide pool (`afp-film lease register --account ID --credits N "
           "[--cdp-endpoint URL] [--project ID]`). Nothing was sent.")


def main(argv: list[str] | None = None) -> int:
    """Retired: refuses to run. The helpers above stay importable (tests use FlowTab.assert_safe)."""
    print(RETIRED, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
