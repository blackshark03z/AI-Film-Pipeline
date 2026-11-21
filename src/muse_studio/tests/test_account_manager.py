import os
import shutil
import tempfile
from pathlib import Path
import pytest
from core.account_manager import AccountManager

@pytest.fixture
def temp_account_mgr():
    temp_dir = Path(tempfile.mkdtemp())
    storage_file = temp_dir / "test_accounts.json"
    profiles_dir = temp_dir / "profiles"
    mgr = AccountManager(storage_file=storage_file, profiles_dir=profiles_dir)
    yield mgr
    shutil.rmtree(temp_dir, ignore_errors=True)

def test_add_and_list_accounts(temp_account_mgr):
    acc1 = temp_account_mgr.add_account("Muse_User_01", proxy="127.0.0.1:8080")
    assert acc1["name"] == "Muse_User_01"
    assert acc1["proxy"] == "127.0.0.1:8080"
    assert acc1["status"] == "UNCHECKED"

    acc_list = temp_account_mgr.list_accounts()
    assert len(acc_list) == 1
    assert acc_list[0]["id"] == acc1["id"]

def test_proxy_parser():
    # 4 tokens: host:port:user:pass
    p1 = AccountManager.parse_proxy("192.168.1.10:8000:admin:secret")
    assert p1 == {"server": "http://192.168.1.10:8000", "username": "admin", "password": "secret"}

    # 2 tokens: host:port
    p2 = AccountManager.parse_proxy("192.168.1.10:8000")
    assert p2 == {"server": "http://192.168.1.10:8000"}

    # URI format
    p3 = AccountManager.parse_proxy("socks5://user:pwd@proxy.com:1080")
    assert p3 == {"server": "socks5://proxy.com:1080", "username": "user", "password": "pwd"}

def test_update_and_delete_account(temp_account_mgr):
    acc = temp_account_mgr.add_account("Test_Acc")
    aid = acc["id"]

    updated = temp_account_mgr.update_account(aid, status="READY", total_rendered=5)
    assert updated["status"] == "READY"
    assert updated["total_rendered"] == 5

    ok = temp_account_mgr.delete_account(aid)
    assert ok is True
    assert len(temp_account_mgr.list_accounts()) == 0
