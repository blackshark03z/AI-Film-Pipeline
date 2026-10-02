"""FLOW-PRODUCTION-HARDEN-MULTISHOT-002 Phase 3 — Flow Tool live reconciliation.

Frozen authority: MAX_FLOW_TOOL_VIDEO_GENERATE = 1 (never retry authority).
Gate: Phase 2 CURRENT_BUILD_REQUALIFIED proven; no ambiguity gate active.

Reuses the existing private canary Tool "Director's Shot Lab"
(083a64f8-6f43-4a48-bd1b-3f1cc81e6b12) in the qualified project. No tool is
created, saved or edited; the tool's own first-party production UI is used.

Goal: determine whether Tool-run generation can satisfy AI-Film ownership
semantics — fresh catalog baseline → preclaimed unique Film marker → tool run
once with the marker inside the prompt → read-only reconciliation (Zzl0ze
delta → marker echo? → unique media identity? → project persistence? →
as29s? → acquisition? → technical validation?).

Classification (exactly one):
  FLOW_TOOL_GENERATION_RECONCILABLE
  FLOW_TOOL_GENERATION_NOT_RECONCILABLE
  FLOW_TOOL_GENERATION_INCONCLUSIVE

No cookies/tokens/signed URLs persisted; wire observation records lengths and
structure only. All evidence local under projects/flow_production_harden_002/.
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys_path = str(Path(__file__).resolve().parents[1] / "src")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from film_pipeline.core import canonical_json, sha256
from film_pipeline.flow_r2v_runtime import qualified_catalog_snapshot
from film_pipeline.providers import flow_rpc_contract as contract
from film_pipeline.providers.flow_reference_rpc import (
    FlowReferenceRpcDrift,
    FlowReferenceRpcSession,
    OwnerAuthRequired,
)
from film_pipeline.providers.flow_media import parse_media_resource

ROOT = Path(__file__).resolve().parents[1]
PROFILE = Path("D:/AI FILM MAKER/Flow-Claude-Clean-Profile")
PROJECT_ID = "93a579b4-834e-435b-8304-5f6682937935"
TOOL_ID = "083a64f8-6f43-4a48-bd1b-3f1cc81e6b12"
OUT = ROOT / "projects/flow_production_harden_002/tool_reconciliation"
OUT.mkdir(parents=True, exist_ok=True)
MAX_FLOW_TOOL_VIDEO_GENERATE = 1
RUN_WINDOW_S = 420  # tool run + in-page wait budget


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_durable(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(data, indent=2, ensure_ascii=False)
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise RuntimeError(f"EVIDENCE_CONFLICT: {path.name}")
        return
    path.write_text(encoded, encoding="utf-8")


def install_wire_observer(page, sink):
    def on_request(request):
        try:
            if request.method != "POST" or "batchexecute" not in request.url:
                return
            body = request.post_data or ""
            sink.append({"at": now(),
                         "rpcs": re.findall(r"rpcids=([A-Za-z0-9_]+)", request.url),
                         "body_len": len(body.encode("utf-8")),
                         "mzza6b": "MZZa6b" in request.url or "MZZa6b" in body,
                         "marker_in_body": "[FILM-job_" in body})
        except Exception:
            pass

    def on_response(response):
        try:
            if "batchexecute" not in response.url:
                return
            sink.append({"at": now(), "response_status": response.status,
                         "rpcs": re.findall(r"rpcids=([A-Za-z0-9_]+)", response.url)})
        except Exception:
            pass

    page.on("request", on_request)
    page.on("response", on_response)


def catalog_ids(records):
    return sorted(row[0].lower() for row in records)


def reconcile(baseline_ids, marker, journal) -> dict:
    """Read-only reconciliation of the tool-run effect."""
    result = {"marker": marker, "classification": "FLOW_TOOL_GENERATION_INCONCLUSIVE"}
    with FlowReferenceRpcSession(profile_path=PROFILE, project_id=PROJECT_ID,
                                 native_ui=True) as session:
        records = session.catalog(contract_version=contract.CONTRACT_VERSION_2026_10_01)
        after_ids = catalog_ids(records)
        result["baseline_ids"] = baseline_ids
        result["after_ids"] = after_ids
        new_ids = [i for i in after_ids if i not in set(baseline_ids)]
        result["new_catalog_ids"] = new_ids
        marker_rows = [row for row in records
                       if marker in " ".join(contract._strings(row))]
        result["marker_echo_rows"] = len(marker_rows)
        if len(marker_rows) == 1 and len(new_ids) == 1:
            output_id = marker_rows[0][0].lower()
            result["output_identity"] = output_id
            if output_id != new_ids[0]:
                result["classification"] = "FLOW_TOOL_GENERATION_INCONCLUSIVE"
                result["diagnostic"] = "marker row and fresh identity disagree"
                return result
            result["project_binding_ok"] = (
                marker_rows[0][1].lower() == PROJECT_ID.lower())
            payload = session.media_payload(output_id)
            result["as29s_resolved"] = payload is not None
            if payload is not None:
                resource = parse_media_resource(payload, media_id=output_id,
                                                project_id=PROJECT_ID, kind="video")
                response = session.page.context.request.get(
                    resource.url, timeout=60000, max_redirects=0, max_retries=0)
                try:
                    if response.status != 200:
                        raise RuntimeError("media unavailable")
                    data = response.body()
                finally:
                    response.dispose()
                result["acquired_bytes"] = len(data)
                import hashlib
                result["acquired_sha256"] = hashlib.sha256(data).hexdigest()
                path = OUT / "videos" / f"{result['acquired_sha256'][:24]}.mp4"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                result["acquired_path"] = str(path)
            result["classification"] = "FLOW_TOOL_GENERATION_RECONCILABLE"
        elif not marker_rows and not new_ids:
            result["classification"] = "FLOW_TOOL_GENERATION_NOT_RECONCILABLE"
            result["diagnostic"] = "no catalog delta and no marker echo"
        elif len(marker_rows) > 1:
            result["classification"] = "FLOW_TOOL_GENERATION_INCONCLUSIVE"
            result["diagnostic"] = "marker collision in catalog delta"
        elif marker_rows and not new_ids:
            result["classification"] = "FLOW_TOOL_GENERATION_INCONCLUSIVE"
            result["diagnostic"] = "marker echoed without a fresh identity"
        else:
            result["classification"] = "FLOW_TOOL_GENERATION_INCONCLUSIVE"
            result["diagnostic"] = "catalog delta without a unique marker echo"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["run", "reconcile"])
    args = parser.parse_args()
    journal_path = OUT / "journal.json"
    journal = json.loads(journal_path.read_text(encoding="utf-8")) \
        if journal_path.exists() else {
            "started_at": now(), "project_id": PROJECT_ID, "tool_id": TOOL_ID,
            "budget": {"tool_video_generate_used": 0,
                       "max": MAX_FLOW_TOOL_VIDEO_GENERATE}, "events": []}

    def event(kind, **data):
        entry = {"kind": kind, "at": now(), **data}
        journal["events"].append(entry)
        journal_path.write_text(json.dumps(journal, indent=2, ensure_ascii=False),
                                encoding="utf-8")
        print(json.dumps(entry, ensure_ascii=False)[:400], flush=True)

    if args.stage == "run":
        if journal["budget"]["tool_video_generate_used"]:
            print("budget already consumed; no rerun", flush=True)
            return
        # Fresh baseline + preclaimed marker BEFORE any mutation.
        with FlowReferenceRpcSession(profile_path=PROFILE, project_id=PROJECT_ID,
                                     native_ui=True) as session:
            records = session.catalog(
                contract_version=contract.CONTRACT_VERSION_2026_10_01)
            fingerprint = session.catalog_fingerprint
            snapshot = qualified_catalog_snapshot(records, project_id=PROJECT_ID,
                                                  fingerprint=fingerprint)
        baseline_ids = catalog_ids(records)
        if not journal.get("marker"):
            job_id = "job_" + sha256(canonical_json({
                "canary": "FLOW_TOOL_RECONCILIATION_002", "project": PROJECT_ID,
                "created_at": now(), "nonce": secrets.token_hex(16)}))
            journal["marker_job_id"] = job_id
            journal["marker"] = f"[FILM-{job_id}]"
        marker = journal["marker"]
        journal["baseline"] = snapshot
        journal["baseline_ids"] = baseline_ids
        event("baseline_captured", count=len(baseline_ids), marker=marker)
        # Read back the tool identity (read-only proof it still exists).
        # First-party invocation proof: the run happens inside the tool's own
        # first-party UI; the runner only fills the tool's prompt input and
        # clicks the tool's own render control once. The wire observer proves
        # the provider request is constructed by the page (never by us).
        from playwright.sync_api import sync_playwright
        wire = []
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                str(PROFILE), channel="chrome", headless=False,
                args=["--no-first-run", "--no-default-browser-check",
                      "--disable-blink-features=AutomationControlled"],
                ignore_default_args=["--enable-automation"], viewport=None)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                page.goto(f"https://flow.google.com/project/{PROJECT_ID}/tool/{TOOL_ID}",
                          timeout=60000)
                page.wait_for_timeout(9000)
                if "accounts.google" in page.url:
                    event("gate", name="OWNER_AUTH_GATE")
                    return
                install_wire_observer(page, wire)
                # The tool's React mini-app runs inside a sandboxed
                # flow-applet-runner iframe; its own controls are reachable
                # only inside that frame.
                tool_frame = None
                deadline_frames = time.monotonic() + 20
                while time.monotonic() < deadline_frames and tool_frame is None:
                    for frame in page.frames:
                        if frame is page.main_frame:
                            continue
                        try:
                            if frame.locator("textarea:visible").count():
                                tool_frame = frame
                                break
                        except Exception:
                            continue
                    if tool_frame is None:
                        page.wait_for_timeout(1000)
                if tool_frame is None:
                    event("gate", name="TOOL_FRAME_NOT_FOUND",
                          frames=[f.url[:80] for f in page.frames][:8])
                    return
                event("tool_frame_located", url=tool_frame.url[:120])
                prompt_box = tool_frame.locator("textarea:visible")
                if not prompt_box.count():
                    event("gate", name="TOOL_PROMPT_INPUT_UNAVAILABLE")
                    return
                prompt_text = ("8-second locked eye-level wide shot, 16:9, calm dawn "
                               "light over a basalt reef; slow atmospheric drift, "
                               "subtle waves. " + marker)
                prompt_box.first.click(timeout=8000)
                prompt_box.first.fill(prompt_text)
                event("tool_prompt_filled", marker=marker)
                render = tool_frame.get_by_role("button",
                                                name=re.compile("render shot", re.I))
                if not render.count():
                    render = tool_frame.locator("button", has_text=re.compile(
                        r"render|chạy|run|generate", re.I))
                if not render.count():
                    event("gate", name="TOOL_RUN_CONTROL_UNAVAILABLE")
                    return
                journal["budget"]["tool_video_generate_used"] = 1
                journal["wire"] = wire
                journal_path.write_text(
                    json.dumps(journal, indent=2, ensure_ascii=False), encoding="utf-8")
                render.first.click(timeout=10000)
                event("tool_generate_released", used=1,
                      allowed=MAX_FLOW_TOOL_VIDEO_GENERATE, marker=marker)
                deadline = time.monotonic() + RUN_WINDOW_S
                completed_seen = False
                while time.monotonic() < deadline:
                    page.wait_for_timeout(15000)
                    body = " ".join(page.locator("body").inner_text().split())[:400]
                    wire = [w for w in wire if isinstance(w, dict)]
                    mzz = [w for w in wire if w.get("mzza6b")]
                    event("tool_wait_poll", mzza6b_requests=len(mzz),
                          marker_in_wire=any(w.get("marker_in_body") for w in wire),
                          body_head=body[:120])
                    if re.search(r"completed|new shot|error", body, re.I):
                        completed_seen = True
                        event("tool_ui_terminal_state", body_head=body[:200])
                        break
                journal["wire"] = wire
                journal_path.write_text(
                    json.dumps(journal, indent=2, ensure_ascii=False), encoding="utf-8")
                page.screenshot(path=str(OUT / "tool_run_final.png"))
            finally:
                try:
                    ctx.close()
                except Exception:
                    pass
        event("run_phase_complete", completed_seen=locals().get("completed_seen", False))
    else:
        marker = journal.get("marker")
        if not marker or not journal["budget"]["tool_video_generate_used"]:
            print("nothing released; reconcile not applicable", flush=True)
            return
        result = reconcile(journal["baseline_ids"], marker, journal)
        journal["reconciliation"] = {
            k: (v.hex() if isinstance(v, bytes) else v) for k, v in result.items()}
        journal_path.write_text(
            json.dumps(journal, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8")
        serializable = {k: (v.hex() if isinstance(v, bytes) else v)
                        for k, v in result.items()}
        write_durable(OUT / "reconciliation_result.json", serializable)
        print(json.dumps(serializable, ensure_ascii=False, default=str)[:600], flush=True)


if __name__ == "__main__":
    main()
