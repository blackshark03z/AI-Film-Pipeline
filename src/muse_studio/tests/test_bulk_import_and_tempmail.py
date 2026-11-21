import json
import re
import shutil
import tempfile
from pathlib import Path
import pytest

from core.account_manager import AccountManager
from core.tempmail_client import TempMailClient

@pytest.fixture
def temp_account_mgr():
    temp_dir = Path(tempfile.mkdtemp())
    storage_file = temp_dir / "test_accounts.json"
    profiles_dir = temp_dir / "profiles"
    mgr = AccountManager(storage_file=storage_file, profiles_dir=profiles_dir)
    yield mgr
    shutil.rmtree(temp_dir, ignore_errors=True)

def test_cookie_parser_semicolon():
    cookie_str = "session_token=abc123xyz; user_id=98765; theme=dark"
    parsed = AccountManager.parse_cookie_string(cookie_str, default_domain=".muse.ai")
    assert len(parsed) == 3
    assert parsed[0]["name"] == "session_token"
    assert parsed[0]["value"] == "abc123xyz"
    assert parsed[0]["domain"] == ".muse.ai"
    assert parsed[1]["name"] == "user_id"
    assert parsed[1]["value"] == "98765"

def test_cookie_parser_json():
    json_cookies = json.dumps([
        {"name": "auth", "value": "secret_token", "domain": ".muse.ai", "path": "/"},
        {"name": "locale", "value": "vi"}
    ])
    parsed = AccountManager.parse_cookie_string(json_cookies)
    assert len(parsed) == 2
    assert parsed[0]["name"] == "auth"
    assert parsed[0]["value"] == "secret_token"
    assert parsed[1]["name"] == "locale"
    assert parsed[1]["value"] == "vi"

def test_bulk_import_accounts(temp_account_mgr):
    raw_text = """
    user1@mailto.plus|INVITE_01|Pass123@|session=token1; uid=101
    user2@fexpost.com|INVITE_02|Pass456@|[{"name": "token", "value": "token2"}]
    # Line comment should be ignored
    user3@mailbox.in.ua|INVITE_03|Pass789@|auth=token3|127.0.0.1:8080
    """
    res = temp_account_mgr.bulk_import_accounts(raw_text)
    assert res["success"] is True
    assert res["imported_count"] == 3
    assert res["updated_count"] == 0

    accs = temp_account_mgr.list_accounts()
    assert len(accs) == 3
    assert accs[0]["email"] == "user1@mailto.plus"
    assert accs[0]["invite_code"] == "INVITE_01"
    assert accs[0]["password"] == "Pass123@"
    assert "session=token1" in accs[0]["raw_cookie"]
    assert accs[2]["proxy"] == "127.0.0.1:8080"

    # Test update existing when email matches
    update_text = """
    user1@mailto.plus|NEW_INVITE|NewPass@|session=updated_token
    """
    res2 = temp_account_mgr.bulk_import_accounts(update_text)
    assert res2["imported_count"] == 0
    assert res2["updated_count"] == 1

    acc1 = temp_account_mgr.get_account_by_email("user1@mailto.plus")
    assert acc1 is not None
    assert acc1["invite_code"] == "NEW_INVITE"
    assert acc1["password"] == "NewPass@"
    assert "updated_token" in acc1["raw_cookie"]

def test_otp_regex_extraction():
    sample_subject = "Your Muse verification code is 849201"
    match = re.search(r"\b(\d{6})\b", sample_subject)
    assert match is not None
    assert match.group(1) == "849201"

    sample_html = "<p>Hello,</p><p>Use code <strong>123456</strong> to complete your sign in.</p>"
    match2 = re.search(r"\b(\d{6})\b", sample_html)
    assert match2 is not None
    assert match2.group(1) == "123456"
