"""PRE-TAG M3 (lane contract v8 s5): one OS lock across reload -> mutate -> replace for every accounts.json writer.

Only a tmp storage file is used here: the real `muse_studio/data/accounts.json*` is never opened.
"""
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

import muse_studio.core.account_manager as am
from muse_studio.core.account_manager import AccountManager, AccountStoreLockTimeout, AccountStoreUnreadable

REPO_ROOT = Path(am.__file__).resolve().parents[2]

WRITER = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from muse_studio.core.account_manager import AccountManager
mgr = AccountManager(storage_file=Path(sys.argv[2]), profiles_dir=Path(sys.argv[3]))
ids, rounds, tag = sys.argv[4].split(","), int(sys.argv[5]), sys.argv[6]
for i in range(rounds):
    for aid in ids:
        assert mgr.update_account(aid, **{"f_" + tag: i}) is not None
for k in range(int(sys.argv[7])):
    mgr.add_account(name="added_" + tag + "_" + str(k))
"""


def _mgr(tmp_path: Path) -> AccountManager:
    return AccountManager(storage_file=tmp_path / "accounts.json", profiles_dir=tmp_path / "profiles")


def test_threads_processes_and_ui_edit_lose_nothing(tmp_path: Path):
    mgr = _mgr(tmp_path)
    ids = [mgr.add_account(name=f"Acc_{i}")["id"] for i in range(4)]
    rounds, procs, threads_n, adds = 12, 3, 3, 2
    script = tmp_path / "writer.py"
    script.write_text(WRITER, encoding="utf-8")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "MUSE_ACCOUNTS_LOCK_TIMEOUT_S": "60"}
    popens = [
        subprocess.Popen([sys.executable, str(script), str(REPO_ROOT), str(tmp_path / "accounts.json"),
                          str(tmp_path / "profiles"), ",".join(ids), str(rounds), f"p{n}", str(adds)],
                         env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for n in range(procs)
    ]
    errors = []

    def thread_writer(n: int):
        try:
            m = _mgr(tmp_path)  # its own manager: the OS lock, not the in-process RLock, must serialise it
            for i in range(rounds):
                for aid in ids:
                    m.update_account(aid, **{f"f_t{n}": i})
            for k in range(adds):
                m.add_account(name=f"added_t{n}_{k}")
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(repr(exc))

    def ui_edit():
        """The web UI edits name / status / proxy while the others write other fields."""
        try:
            m = _mgr(tmp_path)
            for i in range(rounds):
                for aid in ids:
                    m.update_account(aid, name=f"ui_{aid[-4:]}", status="CHECKING" if i % 2 else "READY",
                                     proxy=f"proxy-{i}")
        except Exception as exc:  # pragma: no cover
            errors.append(repr(exc))

    ts = [threading.Thread(target=thread_writer, args=(n,)) for n in range(threads_n)] + [
        threading.Thread(target=ui_edit)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=240)
    for p in popens:
        out, err = p.communicate(timeout=240)
        assert p.returncode == 0, err.decode("utf-8", "replace")[-800:]
    assert not errors, errors

    data = json.loads((tmp_path / "accounts.json").read_text(encoding="utf-8"))  # still valid JSON
    assert len(data) == 4 + (procs + threads_n) * adds, "an added account was lost"
    by_id = {a["id"]: a for a in data}
    for aid in ids:
        acc = by_id[aid]
        for tag in [f"p{n}" for n in range(procs)] + [f"t{n}" for n in range(threads_n)]:
            assert acc.get(f"f_{tag}") == rounds - 1, f"{aid}: field f_{tag} was lost ({acc.get(f'f_{tag}')})"
        assert acc["name"] == f"ui_{aid[-4:]}" and acc["proxy"] == f"proxy-{rounds - 1}"
        assert acc["status"] == ("CHECKING" if (rounds - 1) % 2 else "READY")
    assert not list(tmp_path.glob(".accounts.json.tmp.*")), "a tmp file was left behind"


def test_unreadable_store_raises_and_nothing_is_saved(tmp_path: Path):
    mgr = _mgr(tmp_path)
    mgr.add_account(name="keep")
    store = tmp_path / "accounts.json"
    for bad in (b'[{"id": "a", "name": ', b'{"not": "a list"}', b"\x00\x01garbage"):
        store.write_bytes(bad)
        with pytest.raises(AccountStoreUnreadable):
            mgr.list_accounts()
        with pytest.raises(AccountStoreUnreadable):
            mgr.get_account("a")
        with pytest.raises(AccountStoreUnreadable):
            mgr.add_account(name="would overwrite everything")
        with pytest.raises(AccountStoreUnreadable):
            mgr.update_account("a", status="READY")
        with pytest.raises(AccountStoreUnreadable):
            mgr.delete_account("a")
        assert store.read_bytes() == bad, "an unreadable accounts file was overwritten"
    # a fresh manager must not replace it either
    assert _mgr(tmp_path).storage_file.read_bytes() == b"\x00\x01garbage"


def test_missing_or_empty_store_is_an_empty_list(tmp_path: Path):
    mgr = _mgr(tmp_path)
    store = tmp_path / "accounts.json"
    store.write_text("", encoding="utf-8")
    assert mgr.list_accounts() == []
    store.write_text("  \n", encoding="utf-8")
    assert mgr.list_accounts() == []
    store.unlink()
    assert mgr.list_accounts() == []
    assert mgr.add_account(name="first")["name"] == "first"
    assert len(mgr.list_accounts()) == 1


def test_never_writes_fewer_accounts_than_were_read_unless_delete(tmp_path: Path):
    mgr = _mgr(tmp_path)
    ids = [mgr.add_account(name=f"A{i}")["id"] for i in range(3)]
    before = (tmp_path / "accounts.json").read_bytes()
    with pytest.raises(RuntimeError, match="refusing to write"):
        with mgr._locked_update() as accounts:
            accounts.pop()  # not an explicit delete
    assert (tmp_path / "accounts.json").read_bytes() == before
    assert mgr.delete_account(ids[0], remove_profile=False) is True  # an explicit delete may shrink
    assert [a["id"] for a in mgr.list_accounts()] == ids[1:]
    assert mgr.delete_account("nope") is False and len(mgr.list_accounts()) == 2


def test_replace_is_retried_on_a_sharing_violation(tmp_path: Path, monkeypatch):
    mgr = _mgr(tmp_path)
    aid = mgr.add_account(name="x")["id"]
    real, calls = os.replace, {"n": 0}

    def flaky(src, dst, *a, **k):
        if str(dst).endswith("accounts.json") and calls["n"] < 2:
            calls["n"] += 1
            raise PermissionError("simulated sharing violation")
        return real(src, dst, *a, **k)

    monkeypatch.setattr(am.os, "replace", flaky)
    assert mgr.update_account(aid, status="READY")["status"] == "READY"
    assert calls["n"] == 2 and mgr.get_account(aid)["status"] == "READY"


def test_lock_timeout_fails_without_writing(tmp_path: Path, monkeypatch):
    holder, other = _mgr(tmp_path), _mgr(tmp_path)
    aid = holder.add_account(name="x")["id"]
    monkeypatch.setenv("MUSE_ACCOUNTS_LOCK_TIMEOUT_S", "0.3")
    before = (tmp_path / "accounts.json").read_bytes()
    with holder._os_lock():
        with pytest.raises(AccountStoreLockTimeout):
            other.update_account(aid, status="READY")
    assert (tmp_path / "accounts.json").read_bytes() == before
    assert other.update_account(aid, status="READY")["status"] == "READY"  # free again
    assert (tmp_path / "accounts.lock").exists()  # next to the storage file


def test_every_writer_goes_through_the_locked_update():
    """No account writer may reload and save outside the lock: `_save_all` is gone."""
    src = Path(am.__file__).read_text(encoding="utf-8")
    assert "_save_all" not in src and src.count("_locked_update(") >= 3


def test_ui_reads_show_an_error_for_an_unreadable_store_and_never_save(tmp_path: Path, monkeypatch):
    import asyncio

    from fastapi import HTTPException

    import muse_studio.app as app_mod

    mgr = _mgr(tmp_path)
    mgr.add_account(name="x")
    store = tmp_path / "accounts.json"
    monkeypatch.setattr(app_mod, "account_mgr", mgr)

    ok = app_mod._init_state_payload()
    assert ok["type"] == "init_state" and len(ok["data"]["accounts"]) == 1 and "accounts_error" not in ok["data"]

    store.write_bytes(b"{broken")
    bad = app_mod._init_state_payload()
    assert bad["data"]["accounts"] == [] and "unreadable" in bad["data"]["accounts_error"]
    json.dumps(bad)  # serialisable for the websocket
    with pytest.raises(HTTPException) as ei:
        asyncio.run(app_mod.get_accounts())
    assert ei.value.status_code == 503
    assert store.read_bytes() == b"{broken", "a read-only UI path saved over an unreadable accounts file"
