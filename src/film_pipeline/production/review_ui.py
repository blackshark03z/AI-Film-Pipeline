"""Local self-contained HTML Batch Dailies Reviewer (advisory triage + fast human batch QC)."""
from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any

from film_pipeline.production.qc_model import TAKE_GROUPS, answer_group
from film_pipeline.production.takes import _relation_questions, load_log, script_dialogue


_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Dailies Batch Review — __TITLE__</title>
<style>
  :root { --bg: #0f141a; --card: #182029; --border: #2b3744; --text: #e6edf3; --muted: #93a1b1; --pass: #2ea043; --warn: #d29922; --fail: #f85149; --accent: #58a6ff; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; background: var(--bg); color: var(--text); }
  header { position: sticky; top: 0; z-index: 10; background: #121820; border-bottom: 1px solid var(--border); padding: 12px 18px; display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
  header h1 { font-size: 16px; margin: 0 12px 0 0; }
  .toolbar-group { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
  input, select, button, textarea { background: #0d1117; color: var(--text); border: 1px solid var(--border); border-radius: 6px; padding: 6px 10px; font-size: 13px; }
  button { cursor: pointer; font-weight: 600; }
  button.primary { background: var(--accent); color: #081018; border-color: var(--accent); }
  button.good { background: var(--pass); color: #fff; border-color: var(--pass); }
  button.bad { background: var(--fail); color: #fff; border-color: var(--fail); }
  button.active { outline: 2px solid var(--accent); }
  main { padding: 16px; display: grid; grid-template-columns: repeat(auto-fill, minmax(460px, 1fr)); gap: 14px; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 12px; display: flex; flex-direction: column; gap: 10px; }
  .card.hidden { display: none; }
  .card-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
  .badge { font-size: 11px; padding: 2px 7px; border-radius: 99px; font-weight: 700; text-transform: uppercase; background: #26313d; }
  .badge.clean { background: rgba(46,160,67,.2); color: #7ee787; }
  .badge.flagged { background: rgba(210,153,34,.22); color: #f2cc60; }
  .badge.accepted { background: rgba(88,166,255,.2); color: #79c0ff; }
  .badge.rejected { background: rgba(248,81,73,.2); color: #ffa198; }
  video { width: 100%; border-radius: 6px; background: #000; max-height: 270px; }
  .dialogue { font-size: 13px; color: #dbe6f3; background: #10161d; padding: 8px; border-radius: 6px; white-space: pre-wrap; }
  .triage-box { font-size: 12px; color: var(--muted); }
  .rel-box { background: #111820; border: 1px solid var(--border); border-radius: 6px; padding: 8px; display: flex; flex-direction: column; gap: 6px; }
  .rel-q label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 3px; }
  .rel-q input { width: 100%; }
  .checks-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 4px; font-size: 11px; }
  .chk { display: flex; justify-content: space-between; align-items: center; background: #10161d; padding: 3px 6px; border-radius: 4px; }
  .chk select { padding: 2px 4px; font-size: 11px; }
  .actions { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
  .status-line { font-size: 12px; color: var(--muted); margin-left: auto; }
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <div class="toolbar-group">
    <label>Reviewer <input id="reviewer" value="human:Owner" size="18"></label>
    <label>Speed
      <select id="speed">
        <option value="1">1x</option>
        <option value="1.5" selected>1.5x</option>
        <option value="2">2x</option>
      </select>
    </label>
    <label>Scene
      <select id="sceneFilter"><option value="">All Scenes</option></select>
    </label>
  </div>
  <div class="toolbar-group" id="filterBtns">
    <button data-filter="pending" class="active">Pending</button>
    <button data-filter="clean_pending">Clean Pending</button>
    <button data-filter="flagged">Flagged</button>
    <button data-filter="all">All</button>
  </div>
  <div class="toolbar-group">
    <button id="markCleanBtn" class="good">Mark All Clean Pending PASS</button>
    <button id="exportBtn" class="primary">Export Batch Review JSON</button>
  </div>
  <div class="status-line" id="summaryLine"></div>
</header>
<main id="grid"></main>
<script>
const ITEMS = __DATA__;
const GROUPS = __GROUPS__;
let activeFilter = "pending";
const decisions = new Map();

for (const item of ITEMS) {
  decisions.set(item.take_id, {
    mode: "UNASSESSED",
    evidence: `${item.output_file}: batch visual+audio review`,
    severity: "P1",
    cause: "PROMPT",
    groups: Object.fromEntries(GROUPS.map(g => [g, item.status === "ACCEPTED" ? "PASS" : (item.status === "REJECTED" ? "FAIL" : "UNASSESSED")])),
    answers: {}
  });
}

const sceneSel = document.getElementById("sceneFilter");
for (const sid of [...new Set(ITEMS.map(x => x.scene_id).filter(Boolean))]) {
  const opt = document.createElement("option");
  opt.value = sid;
  opt.textContent = sid;
  sceneSel.appendChild(opt);
}

function isPending(item) {
  return item.status === "GENERATED" || item.status === "INCOMPLETE";
}

function renderGrid() {
  const grid = document.getElementById("grid");
  grid.innerHTML = "";
  const wantScene = sceneSel.value;
  let shown = 0;
  for (const item of ITEMS) {
    if (wantScene && item.scene_id !== wantScene) continue;
    if (activeFilter === "pending" && !isPending(item)) continue;
    if (activeFilter === "clean_pending" && !(isPending(item) && item.triage_status === "CLEAN")) continue;
    if (activeFilter === "flagged" && !(item.triage_status === "FLAGGED" || (item.triage_flags && item.triage_flags.length))) continue;
    shown++;
    const st = decisions.get(item.take_id);
    const card = document.createElement("section");
    card.className = "card";
    const statusCls = item.status === "ACCEPTED" ? "accepted" : (item.status === "REJECTED" ? "rejected" : "");
    const triageCls = item.triage_status === "CLEAN" ? "clean" : (item.triage_status === "FLAGGED" ? "flagged" : "");
    card.innerHTML = `
      <div class="card-head">
        <strong>${item.take_id} (${item.scene_id || "-"} / ${item.coverage || ""})</strong>
        <div>
          <span class="badge ${statusCls}">${item.status}</span>
          <span class="badge ${triageCls}">${item.triage_status}</span>
        </div>
      </div>
      <video controls preload="metadata" src="${item.video_rel}"></video>
      <div class="dialogue">${(item.dialogue || "(silent shot)").replace(/</g, "&lt;")}</div>
      <div class="triage-box">SHA: ${item.output_sha256.slice(0, 12)} | Trim hint: ${item.trim_hint || "-"} | Flags: ${(item.triage_flags || []).map(f => f.code).join(", ") || "none"}</div>
      ${(item.triage_flags && item.triage_flags.length) ? `<div class="triage-box" style="color:#f2cc60">${item.triage_flags.map(f => `${f.code}: ${(f.detail || "").replace(/</g, "&lt;")}`).join(" · ")}</div>` : ""}
      ${item.relation_questions.length ? `<div class="rel-box">${item.relation_questions.map(q => `
        <div class="rel-q"><label>${q.id}: ${q.question.replace(/</g, "&lt;")}</label>
        <input data-tid="${item.take_id}" data-qid="${q.id}" value="${(st.answers[q.id] || "").replace(/"/g, "&quot;")}" placeholder="Required short answer..."></div>`).join("")}</div>` : ""}
      <div class="actions">
        <button data-act="pass" data-tid="${item.take_id}" class="good">PASS All Groups</button>
        <button data-act="fail" data-tid="${item.take_id}" class="bad">FAIL Technical/Visual (P1)</button>
        <button data-act="clear" data-tid="${item.take_id}">Reset</button>
      </div>
      <div class="checks-grid">${GROUPS.map(g => `
        <div class="chk"><span>${g}</span>
          <select data-tid="${item.take_id}" data-grp="${g}">
            ${["UNASSESSED", "PASS", "FAIL", "WARN"].map(r => `<option value="${r}" ${st.groups[g] === r ? "selected" : ""}>${r}</option>`).join("")}
          </select>
        </div>`).join("")}
      </div>
      <input data-ev-tid="${item.take_id}" value="${st.evidence.replace(/"/g, "&quot;")}" placeholder="Evidence note">
    `;
    grid.appendChild(card);
  }
  applySpeed();
  const judgedCount = ITEMS.filter(x => Object.values(decisions.get(x.take_id).groups).some(v => v === "PASS" || v === "FAIL") && isPending(x)).length;
  document.getElementById("summaryLine").textContent = `Showing ${shown}/${ITEMS.length} | Marked Pending: ${judgedCount}`;
}

function applySpeed() {
  const rate = parseFloat(document.getElementById("speed").value || "1");
  document.querySelectorAll("video").forEach(v => { v.playbackRate = rate; });
}

document.getElementById("speed").addEventListener("change", applySpeed);
sceneSel.addEventListener("change", renderGrid);
document.getElementById("filterBtns").addEventListener("click", (e) => {
  if (!e.target.dataset.filter) return;
  activeFilter = e.target.dataset.filter;
  document.querySelectorAll("#filterBtns button").forEach(b => b.classList.toggle("active", b === e.target));
  renderGrid();
});

document.getElementById("grid").addEventListener("click", (e) => {
  const tid = e.target.dataset.tid;
  const act = e.target.dataset.act;
  if (!tid || !act) return;
  const st = decisions.get(tid);
  if (act === "pass") {
    GROUPS.forEach(g => st.groups[g] = "PASS");
    st.mode = "PASS";
  } else if (act === "fail") {
    GROUPS.forEach(g => st.groups[g] = "PASS");
    st.groups.visual = "FAIL";
    st.mode = "FAIL";
  } else if (act === "clear") {
    GROUPS.forEach(g => st.groups[g] = "UNASSESSED");
    st.mode = "UNASSESSED";
  }
  renderGrid();
});

document.getElementById("grid").addEventListener("input", (e) => {
  if (e.target.dataset.qid) {
    decisions.get(e.target.dataset.tid).answers[e.target.dataset.qid] = e.target.value;
  } else if (e.target.dataset.evTid) {
    decisions.get(e.target.dataset.evTid).evidence = e.target.value;
  } else if (e.target.dataset.grp) {
    decisions.get(e.target.dataset.tid).groups[e.target.dataset.grp] = e.target.value;
  }
});

document.getElementById("markCleanBtn").addEventListener("click", () => {
  const wantScene = sceneSel.value;
  for (const item of ITEMS) {
    if (wantScene && item.scene_id !== wantScene) continue;
    if (isPending(item) && item.triage_status === "CLEAN") {
      const st = decisions.get(item.take_id);
      GROUPS.forEach(g => { st.groups[g] = "PASS"; });
      st.mode = "PASS";
    }
  }
  renderGrid();
});

document.getElementById("exportBtn").addEventListener("click", () => {
  const reviewer = (document.getElementById("reviewer").value || "").trim();
  if (!/^(human|agent):[A-Za-z0-9_.\\-]+$/.test(reviewer)) {
    alert("Reviewer must match human:<Name> or agent:<Name>");
    return;
  }
  const batch = [];
  for (const item of ITEMS) {
    if (!isPending(item)) continue;
    const st = decisions.get(item.take_id);
    const hasVerdict = GROUPS.some(g => st.groups[g] === "PASS" || st.groups[g] === "FAIL");
    if (!hasVerdict) continue;
    for (const q of item.relation_questions) {
      if (!(st.answers[q.id] || "").trim()) {
        alert(`Missing required answer ${q.id} for ${item.take_id}`);
        return;
      }
    }
    const checks = GROUPS.map(g => {
      const res = st.groups[g];
      if (res === "UNASSESSED") return { group: g, result: "UNASSESSED" };
      const c = { group: g, result: res, level: "FULL_MOTION", reviewer, evidence: st.evidence.trim() || item.output_file };
      if (res === "FAIL") c.severity = st.severity || "P1";
      const qAnswers = {};
      for (const q of item.relation_questions) {
        if (q.group === g && (st.answers[q.id] || "").trim()) qAnswers[q.id] = st.answers[q.id].trim();
      }
      if (Object.keys(qAnswers).length) c.answers = qAnswers;
      return c;
    });
    const entry = {
      take_id: item.take_id,
      generation_id: item.generation_id,
      output_sha256: item.output_sha256,
      required_answers: item.relation_questions.map(q => q.id),
      checks
    };
    if (checks.some(c => c.result === "FAIL")) entry.cause = st.cause || "PROMPT";
    batch.push(entry);
  }
  if (!batch.length) {
    alert("No pending takes have been marked yet.");
    return;
  }
  const blob = new Blob([JSON.stringify(batch, null, 2) + "\\n"], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "batch_reviews.json";
  a.click();
  URL.revokeObjectURL(url);
});

renderGrid();
</script>
</body>
</html>
"""


def build_review_ui(
    pkg: Any,
    *,
    out_dir: Path | None = None,
    scene_id: str | None = None,
    run_triage: bool = False,
    clips_dir: Path | None = None,
) -> dict[str, Any]:
    """Build a self-contained local HTML dailies reviewer page without touching stage/review files."""
    shots = pkg.typed.get("shots")
    pre = pkg.typed.get("preprod")
    if shots is None or pre is None:
        raise ValueError("review_ui needs valid 03_preprod.json and 04_shots.json")

    root = Path(pkg.root)
    target_dir = Path(out_dir) if out_dir is not None else root / "media" / "review_ui"
    target_dir.mkdir(parents=True, exist_ok=True)
    take_clips_dir = Path(clips_dir) if clips_dir is not None else root / "media" / "takes"
    log = load_log(root, pkg.header.film_id)
    by_gid = {g.generation_id: g for g in shots.generations}
    lines = script_dialogue(pkg)

    from film_pipeline.production.dailies_triage import load_cached_triage, triage_batch

    eligible_entries = []
    clip_paths: dict[str, Path] = {}
    for entry in log.takes:
        decl = by_gid.get(entry.generation_id)
        if decl is None or (scene_id is not None and decl.scene_id != scene_id):
            continue
        clip_path = take_clips_dir / Path(entry.output_file).name
        if not clip_path.is_file():
            clip_path = take_clips_dir / entry.output_file
        eligible_entries.append((entry, decl))
        clip_paths[entry.take_id] = clip_path

    triage_map: dict[str, dict[str, Any]] = {}
    if run_triage:
        present_ids = [e.take_id for e, _ in eligible_entries if clip_paths[e.take_id].is_file()]
        triage_map = triage_batch(pkg, present_ids, clips_dir=clips_dir)
    elif clips_dir is None:
        for entry, _ in eligible_entries:
            cached = load_cached_triage(root, entry.take_id, entry.output_sha256)
            if cached is not None:
                triage_map[entry.take_id] = cached

    items: list[dict[str, Any]] = []
    pending_count = 0
    clean_pending_count = 0
    flagged_pending_count = 0

    for entry, decl in eligible_entries:
        clip_path = clip_paths[entry.take_id]
        try:
            video_rel = os.path.relpath(clip_path.resolve(), target_dir.resolve()).replace("\\", "/")
        except ValueError:
            video_rel = clip_path.as_posix()

        rel_qs = _relation_questions(pre, decl, lines)
        rel_payload = [
            {"id": q["id"], "group": answer_group(q["id"]), "question": q["question"]}
            for q in rel_qs
        ]
        dialogue = "\n".join(lines.get(ln, f"line {ln}") for ln in decl.dialogue)

        triage_status = "NOT_RUN"
        triage_flags: list[dict[str, Any]] = []
        trim_hint = ""
        tri = triage_map.get(entry.take_id)
        if tri is not None:
            triage_flags = list(tri.get("warnings") or tri.get("flags") or [])
            triage_status = "FLAGGED" if triage_flags else "CLEAN"
            metrics = tri.get("metrics") or {}
            if "suggested_src_in_s" in metrics and "suggested_src_out_s" in metrics:
                trim_hint = f"{metrics['suggested_src_in_s']}s..{metrics['suggested_src_out_s']}s"

        if entry.status in ("GENERATED", "INCOMPLETE"):
            pending_count += 1
            if triage_status == "CLEAN":
                clean_pending_count += 1
            elif triage_status == "FLAGGED":
                flagged_pending_count += 1

        items.append({
            "take_id": entry.take_id,
            "generation_id": entry.generation_id,
            "scene_id": decl.scene_id,
            "coverage": decl.coverage,
            "status": entry.status,
            "output_file": entry.output_file,
            "output_sha256": entry.output_sha256,
            "video_rel": video_rel,
            "dialogue": dialogue,
            "relation_questions": rel_payload,
            "triage_status": triage_status,
            "triage_flags": triage_flags,
            "trim_hint": trim_hint,
        })

    data_json = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    groups_json = json.dumps(list(TAKE_GROUPS))
    html_text = (
        _TEMPLATE
        .replace("__TITLE__", html.escape(f"{pkg.header.film_id} — {pkg.header.title}"))
        .replace("__DATA__", data_json)
        .replace("__GROUPS__", groups_json)
    )
    html_path = target_dir / "index.html"
    html_path.write_text(html_text, encoding="utf-8")
    return {
        "ok": True,
        "film_id": pkg.header.film_id,
        "html": str(html_path),
        "total_takes": len(items),
        "pending_count": pending_count,
        "clean_pending_count": clean_pending_count,
        "flagged_pending_count": flagged_pending_count,
    }
