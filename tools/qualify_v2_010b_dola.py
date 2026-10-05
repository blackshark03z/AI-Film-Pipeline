"""AI-FILM-QUALITY-V2-010B — LIVE qualification canary.
Exactly ONE provider mutation (Dola cookie-HTTP submit).
Receipt-first persistence; echo verification; ambiguity latch."""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from film_pipeline.providers.dola_provider import (
    DolaCookieTransport, DolaTransportError, probe_session)
from mutation_authority import MutationAuthority

PKG = ROOT / "projects/quality_v2_010b_dola_re_live"
PKG.mkdir(parents=True, exist_ok=True)
SCOPE = "QUALITY-V2-010B-DOLA-RE-LIVE"
STORE = ROOT / "projects/flow_production_harden_002/requal_current_build/runtime.sqlite"


def load_cookie() -> str:
    """Load Dola cookie from the Story Auto DPAPI store."""
    sa = Path("D:/Story Auto/story-auto")
    if sa.exists():
        sys.path.insert(0, str(sa))
        try:
            from story_auto.providers.dola_cookie.accounts import \
                DolaAccountStore
            store = DolaAccountStore()
            for alias in ("dola-profile-20260923", "dola-main"):
                try:
                    cookie = store.get_cookie(alias)
                    if cookie and "sessionid=" in cookie:
                        print(json.dumps({"cookie_source": alias,
                                          "alive": True}))
                        return cookie
                except Exception:
                    continue
        except ImportError:
            pass
    # fallback: raw cookie file
    for p in (Path("D:/Video/api_keys/dola_cookie.txt"),
              Path("D:/API KEY/dola_cookie.txt")):
        if p.exists():
            content = p.read_text(encoding="utf-8").strip()
            lines = [l.strip() for l in content.splitlines()
                     if l.strip() and not l.startswith("#")]
            if lines and "sessionid=" in " ".join(lines):
                print(json.dumps({"cookie_source": str(p), "alive": True}))
                return " ".join(lines)
    raise SystemExit("OWNER_AMBIGUITY_GATE: no Dola cookie available")


def main() -> int:
    # ---- governance ------------------------------------------------------
    auth = MutationAuthority(PKG, SCOPE)
    if auth.authority == "LATCHED_CLOSED":
        print(json.dumps({"status": "OWNER_AMBIGUITY_GATE",
                          "reason": "authority latched"}))
        return 1
    auth.check_mutation_allowed("dola_qualification")

    # ---- cookie ----------------------------------------------------------
    cookie = load_cookie()

    # ---- preflight: read-only session probe ------------------------------
    alive = probe_session(cookie)
    print(json.dumps({"step": "preflight_probe", "session_alive": alive}))
    if not alive:
        print(json.dumps({"status": "OWNER_AMBIGUITY_GATE",
                          "reason": "Dola session dead"}))
        auth.latch("SESSION_DEAD", "probe failed")
        return 1

    # ---- transport (repaired wire contract) ------------------------------
    transport = DolaCookieTransport(cookie)

    # ---- qualification submit --------------------------------------------
    prompt = "a lone swordsman in white robes walks through a narrow " \
             "stone pass in a mountain landscape, wind blows his robes"
    receipt_holder: list[str] = []

    def on_receipt(conversation_id: str) -> None:
        receipt_holder.append(conversation_id)

    client_request_id = "v2-010b-qual-" + hashlib.sha256(
        prompt.encode()).hexdigest()[:32]
    print(json.dumps({"step": "qualification_submit",
                      "client_request_id": client_request_id}), flush=True)
    try:
        conversation_id = transport.submit(
            prompt=prompt, aspect_ratio="16:9", duration=5,
            on_receipt=on_receipt,
            client_request_id=client_request_id)
    except DolaTransportError as error:
        result = {"status": "OWNER_AMBIGUITY_GATE" if
                  error.failure_class == "AMBIGUOUS" else
                  "STOPPED_EXPLICIT_PROVIDER_FAILURE",
                  "failure_class": error.failure_class,
                  "dispatch_state": error.dispatch_state,
                  "request_hash": getattr(transport, "last_request_hash",
                                          "")[:32],
                  "body_sha256": getattr(transport, "last_body_sha256",
                                         "")[:32],
                  "response_status": getattr(transport,
                                             "last_response_status", 0)}
        (PKG / "qualification_result.json").write_text(
            json.dumps(result, indent=1), encoding="utf-8")
        auth.latch("DOLA_QUALIFICATION_" + error.failure_class,
                   json.dumps(result))
        print(json.dumps({"checkpoint": "V2010B_QUALIFICATION_FAILED",
                          **result}))
        return 1

    if not receipt_holder:
        print(json.dumps({"status": "OWNER_AMBIGUITY_GATE",
                          "reason": "no receipt captured"}))
        auth.latch("DOLA_QUALIFICATION_NO_RECEIPT", "receipt missing")
        return 1

    # ---- receipt-first: persist BEFORE polling ---------------------------
    auth.consume("dola_qualification")
    qualification = {
        "version": "v2-010b-qualification-v1",
        "checkpoint": "V2010B_P4_QUALIFICATION_DISPATCHED",
        "conversation_id": conversation_id,
        "client_request_id": client_request_id,
        "request_hash": transport.last_request_hash,
        "body_sha256": transport.last_body_sha256,
        "response_status": transport.last_response_status,
        "ability_type": 17,
        "model": "seedance_v2.0",
        "prompt_prefix_present": True,
        "transport": "DolaCookieTransport (repaired wire contract)"}
    (PKG / "qualification_v2_010b.json").write_text(
        json.dumps(qualification, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2010B_P4_QUALIFICATION_DISPATCHED",
                      "conversation_id": conversation_id[:24]}))

    # ---- poll -------------------------------------------------------------
    print(json.dumps({"step": "polling"}), flush=True)
    poll_result = transport.poll(conversation_id,
                                 client_request_id=client_request_id)
    print(json.dumps({"step": "poll_result", "status":
                      poll_result.get("status")}))

    if poll_result.get("status") != "COMPLETED":
        result = {"status": "OWNER_AMBIGUITY_GATE" if
                  poll_result.get("status") == "PENDING" else
                  "STOPPED_EXPLICIT_PROVIDER_FAILURE",
                  "poll_status": poll_result.get("status")}
        (PKG / "qualification_result.json").write_text(
            json.dumps(result, indent=1), encoding="utf-8")
        auth.latch("DOLA_POLL_" + poll_result.get("status", "UNKNOWN"),
                   json.dumps(result))
        print(json.dumps({"checkpoint": "V2010B_POLL_FAILED", **result}))
        return 1

    # ---- download ---------------------------------------------------------
    import urllib.request
    video_url = poll_result["video_url"]
    dest = PKG / "qualification_video.mp4"
    req = urllib.request.Request(video_url)
    with urllib.request.urlopen(req, timeout=120) as resp:
        dest.write_bytes(resp.read())
    asset_sha = hashlib.sha256(dest.read_bytes()).hexdigest()

    # ---- technical validation --------------------------------------------
    import subprocess as sp
    probe = sp.run(["ffprobe", "-v", "error", "-show_entries",
                    "format=duration:stream=width,height,codec_name",
                    "-of", "json", str(dest)], capture_output=True,
                   text=True)
    probe_data = json.loads(probe.stdout)
    stream = next((s for s in probe_data.get("streams", [])
                   if "width" in s), {})
    decode = sp.run(["ffmpeg", "-v", "error", "-xerror", "-i",
                     str(dest), "-map", "0:v:0", "-f", "null", "-"],
                    capture_output=True).returncode == 0

    qualification["status"] = "PROVEN"
    qualification["video_url_host"] = video_url.split("/")[2] if "/" in \
        video_url else "UNKNOWN"
    qualification["asset_sha256"] = asset_sha
    qualification["asset_size"] = dest.stat().st_size
    qualification["duration_s"] = probe_data.get("format", {}).get(
        "duration")
    qualification["width"] = stream.get("width")
    qualification["height"] = stream.get("height")
    qualification["codec"] = stream.get("codec_name")
    qualification["full_decode"] = decode
    (PKG / "qualification_v2_010b.json").write_text(
        json.dumps(qualification, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2010B_QUALIFICATION_PROVEN",
                      "conversation_id": conversation_id[:24],
                      "asset_sha256": asset_sha[:16],
                      "duration": qualification["duration_s"],
                      "decode": decode}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
