"""Fixtures for the S2-lite tests: a film package + Muse film dir in tmp, a real broker database with a Muse lease, a
prepared job, and writers for fake lane outputs (lane_result.json, clips, receipts, the film ledger). No Muse process, no
network."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from film_pipeline.agentic import lane_jobs as LJ
from film_pipeline.agentic.broker import AdmitRequest, Broker, Child

NO_CAPS = {"machine_caps": {}, "provider_caps": {}}
FILM_ID = "f1"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class World:
    tmp: Path
    film: Path
    muse: Path
    broker: Broker
    store: LJ.JobStore
    job: dict[str, Any]
    request: dict[str, Any]
    token: str
    lease_key: str = "L-w1"
    clips: dict[str, bytes] = field(default_factory=dict)

    @property
    def job_dir(self) -> Path:
        return Path(self.job["job_dir_path"])

    @property
    def slots(self) -> list[dict[str, Any]]:
        return self.request["slots"]

    def slot(self, i: int) -> dict[str, Any]:
        return self.slots[i]

    # ---- the broker side ------------------------------------------------------------------------------------------
    def check(self, *indexes: int, incarnation: str = "inc-1") -> dict[str, Any]:
        keys = [self.slot(i)["child_key"] for i in indexes]
        return self.broker.before_enter(self.lease_key, lease_token=self.token, child_keys=keys, epoch=1,
                                        incarnation=incarnation)

    def settle_not_sent(self, i: int) -> dict[str, Any]:
        return self.broker.settle_not_sent(self.slot(i)["child_key"], evidence="test: proven unsent")

    def child_row(self, i: int) -> dict[str, Any]:
        import sqlite3
        with sqlite3.connect(self.broker.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return dict(conn.execute("SELECT * FROM lease_children WHERE child_key = ?",
                                     (self.slot(i)["child_key"],)).fetchone())

    # ---- the lane side --------------------------------------------------------------------------------------------
    def attempt(self, i: int, status: str = "UNCONFIRMED", **over: Any) -> dict[str, Any]:
        s = self.slot(i)
        base = {"film_id": FILM_ID, "wave_id": self.request["wave_id"], "batch_id": self.request["batch_id"],
                "slot_id": s["slot_id"], "child_key": s["child_key"], "request_id": s["request_id"],
                "shot_id": s["shot_id"], "shot_version": s["shot_version"], "take_index": s["take_index"],
                "account_id": self.request["account_id"], "input_digest": s["input_digest"],
                "recorded_at": "2026-11-21T10:00:00Z", "status": status, "reason": "", "result_eligible": True,
                "fenced": False, "history": []}
        return {**base, **over}

    def write_ledger(self, attempts: list[dict[str, Any]] | None, *, raw: str | None = None) -> None:
        path = self.muse / "film_send_ledger.json"
        if raw is not None:
            path.write_text(raw, encoding="utf-8")
            return
        entries = [{"take_identity": {k: a[k] for k in ("shot_id", "shot_version", "take_index")}, "attempts": [a]}
                   for a in attempts or []]
        path.write_text(json.dumps({"entries": entries}, indent=2), encoding="utf-8")

    def read_ledger(self) -> dict[str, Any]:
        return json.loads((self.muse / "film_send_ledger.json").read_text(encoding="utf-8"))

    def batch_dir(self) -> Path:
        d = self.job_dir / "BATCHES_V2" / self.request["batch_id"]
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_clip(self, i: int, data: bytes | None = None, *, name: str | None = None, sub: str = "") -> str:
        s = self.slot(i)
        data = data if data is not None else f"clip-{s['slot_id']}".encode() * 50
        target = self.batch_dir() / sub
        target.mkdir(parents=True, exist_ok=True)
        (target / (name or f"{s['slot_id']}.mp4")).write_bytes(data)
        self.clips[s["slot_id"]] = data
        return sha(data)

    def write_receipt(self, i: int, digest: str | None = None, *, drop: tuple[str, ...] = (), name: str | None = None,
                      **over: Any) -> Path:
        s = self.slot(i)
        rec = {"batch_id": self.request["batch_id"], "shot_id": s["shot_id"], "slot_id": s["slot_id"],
               "request_id": s["request_id"], "sha256": digest if digest is not None else sha(self.clips[s["slot_id"]]),
               "status": "ok", **over}
        for key in drop:
            rec.pop(key, None)
        path = self.batch_dir() / (name or f"{s['slot_id']}_receipt.json")
        path.write_text(json.dumps(rec), encoding="utf-8")
        return path

    def write_lane_result(self, children: list[dict[str, Any]], **extra: Any) -> None:
        body = {"status": "COMPLETED", "muse_tag": self.request["muse_tag"], "muse_commit": "abc123",
                "incarnation_id": "inc-1", "halt_publication": None, "children": children, **extra}
        (self.job_dir / "lane_result.json").write_text(json.dumps(body), encoding="utf-8")

    def lane_child(self, i: int, custody: str = "RESULT", **over: Any) -> dict[str, Any]:
        s = self.slot(i)
        return {"slot_id": s["slot_id"], "child_key": s["child_key"], "request_id": s["request_id"],
                "custody": custody, "reason": "", "evidence": {}, **over}

    def good_slot(self, i: int, status: str = "UNCONFIRMED") -> dict[str, Any]:
        """Everything a clean lane leaves for slot ``i`` (clip, receipt, ledger attempt, lane child); the caller checks
        the broker child and writes the ledger / lane_result once for all slots."""
        self.write_clip(i)
        self.write_receipt(i)
        return self.attempt(i, status)

    def clean_run(self, n: int | None = None) -> None:
        """A fully successful lane: every slot checked, sent, received."""
        idx = list(range(n if n is not None else len(self.slots)))
        assert self.check(*idx)["go"]
        attempts = [self.good_slot(i) for i in idx]
        self.write_ledger(attempts)
        self.write_lane_result([self.lane_child(i) for i in idx])


def make_world(tmp_path: Path, n: int = 2, *, wave: str = "w1") -> World:
    film = tmp_path / "afp" / FILM_ID
    muse = tmp_path / "muse" / FILM_ID
    film.mkdir(parents=True)
    muse.mkdir(parents=True)
    (film / "film.json").write_text(json.dumps({"film_id": FILM_ID}), encoding="utf-8")
    ff = tmp_path / "first_frame.png"
    ff.write_bytes(b"png-bytes")
    broker = Broker(tmp_path / "pool.sqlite3", min_reserve_credits=0.0, cooldown_s=0.0, require_owner=False, **NO_CAPS)
    broker.register_account("acc_1", provider="muse", quota_mode="probed")
    broker.record_probe("acc_1", 80.0)
    lease_key = f"L-{wave}"
    children = [Child(f"c{i}", 1.0, take_id=f"t{i}", shot_key=f"S{i}:v1") for i in range(1, n + 1)]
    out = broker.admit(AdmitRequest(lease_key=lease_key, children=children, unit="muse_requests", provider="muse",
                                    job_kind="video", film_id=FILM_ID, account_id="acc_1", epoch=1, holder="lane"))
    assert out["ok"], out
    token = out["lease"]["lease_token"]
    store = LJ.JobStore(tmp_path / "jobs.sqlite3")
    spec = {"film_root": str(film), "muse_film": str(muse), "wave_id": wave, "kind": "video", "account_id": "acc_1",
            "lease_key": lease_key, "epoch": 1, "muse_tag": "muse-v1.0-r15", "quality": "max",
            "slots": [{"slot_id": f"shot_{i:02d}", "child_key": f"c{i}", "shot_id": f"S{i}", "shot_version": 1,
                       "take_index": 1, "input_digest": sha(f"fp{i}".encode()), "prompt_text": f"prompt {i}",
                       "inputs": [{"role": "first_frame", "path": str(ff)}]} for i in range(1, n + 1)]}
    res = LJ.prepare_job(spec, store=store)
    assert res["ok"], res
    job = store.find_job(res["job_key"])
    request = json.loads((Path(job["job_dir_path"]) / "batch_request.json").read_text(encoding="utf-8"))
    return World(tmp_path, film, muse, broker, store, job, request, token, lease_key)
