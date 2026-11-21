"""Tests for tools/secret_scan.py. Tmp git repos only: nothing here touches D:\\Muse or any real repo.

Every fake secret is assembled at run time from pieces, so this file holds no literal that the scanner itself would flag
(the scanner is run over tools/ at the M6 commit, and one test below scans a copy of both files).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import secret_scan as ss  # noqa: E402


def j(*parts: str) -> str:
    return "".join(parts)


# obviously fake values, split so no literal in this file looks like a secret
FAKE = {
    "cookie": j("Coo", "kie: sess", "ion_id=FAKEFAKEFAKE1234"),
    "setcookie": j("Set-", "Cookie: ", "sid=FAKEFAKEFAKE9876; Path=/"),
    "bearer": j("Authorization: Bea", "rer FAKEFAKEFAKEFAKEFAKE1234"),
    "basic": j("authorization: Ba", "sic RkFLRUZBS0U6RkFLRUZBS0U="),
    "sk": j("s", "k-", "FAKEFAKEFAKEFAKEFAKEFAKE1234"),
    "akia": j("AK", "IA", "FAKEFAKEFAKEFAKE"),
    "ghp": j("gh", "p_", "FAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE12"),
    "keyassign": j("API_", "KEY = ", "FAKEFAKEFAKEFAKEFAKEFAKE1234"),
    "privkey": j("-----BEGIN RSA PRIV", "ATE KEY-----"),
    "pwd": j("pass", "word = ", '"hunter2-fake"'),
    "pwdjson": j('"pass', 'word": ', '"hunter2-fake"'),
    "tokenq": j("tok", "en = ", "'fakefaketoken9999'"),
    "secretq": j("client_", "secret=", '"fakefakesecret77"'),
    "otpq": j("my_", "otp = ", '"482913"'),
    "email": j("jane.fake@", "mailhost-fake.net"),
    "cookiejson": j('[{"na', 'me": "sid", "val', 'ue": "FAKEFAKEFAKE1234", "dom', 'ain": ".example.com"}]'),
}


@pytest.fixture(autouse=True)
def _hermetic_git(monkeypatch, tmp_path):
    for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for k, v in (("GIT_AUTHOR_NAME", "Fake Author"), ("GIT_AUTHOR_EMAIL", "author@example.com"),
                 ("GIT_COMMITTER_NAME", "Fake Author"), ("GIT_COMMITTER_EMAIL", "author@example.com")):
        monkeypatch.setenv(k, v)


class Repo:
    def __init__(self, root: Path):
        assert "Muse" not in root.parts or "pytest-of" in str(root), "tests must use a tmp repo"
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "commit.gpgsign", "false")

    def git(self, *args: str) -> str:
        p = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, text=True, encoding="utf-8")
        assert p.returncode == 0, p.stderr
        return p.stdout.strip()

    def write(self, rel: str, content="", binary=False) -> Path:
        f = self.root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes) or binary:
            f.write_bytes(content if isinstance(content, bytes) else content.encode())
        else:
            f.write_text(content, encoding="utf-8")
        return f

    def stage(self, *rels: str) -> None:
        self.git("add", "-f", "--", *rels)

    def commit(self, msg="c") -> str:
        self.git("commit", "-q", "-m", msg)
        return self.git("rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path) -> Repo:
    r = Repo(tmp_path / "repo")
    r.write("README.md", "hello\n")
    r.write("src/app.py", "print('ok')\n")
    r.stage("README.md", "src/app.py")
    r.commit("init")
    return r


def rules(findings, path=None):
    return sorted({f.rule for f in findings if path is None or f.path == path})


def staged(repo: Repo, **kw):
    return ss.scan_staged(repo.root, **kw)


def history(repo: Repo, **kw):
    return ss.scan_history(repo.root, **kw)


# ======================================================================================================== clean / exit codes
def test_clean_repo_is_clean_in_every_mode(repo, capsys):
    repo.write("docs/notes.md", "nothing secret here\n")
    repo.stage("docs/notes.md")
    assert staged(repo).findings == []
    assert history(repo).findings == []
    assert ss.scan_tree(repo.root).findings == []
    for flag in ("--staged", "--history", "--tree"):
        assert ss.run([flag, str(repo.root)]) == 0
    assert "0 hit(s)" in capsys.readouterr().out


def test_exit_codes_0_1_2(repo, tmp_path, capsys):
    assert ss.run(["--staged", str(repo.root)]) == 0
    repo.write("accounts.json", "[]")
    repo.stage("accounts.json")
    assert ss.run(["--staged", str(repo.root)]) == 1
    capsys.readouterr()
    assert ss.run(["--staged", str(tmp_path / "does-not-exist")]) == 2
    plain = tmp_path / "plain"
    plain.mkdir()
    assert ss.run(["--history", str(plain)]) == 2  # not a git repo
    assert "ERROR" in capsys.readouterr().err
    assert ss.run(["--tree", str(tmp_path / "nope")]) == 2
    assert ss.run(["--staged", str(repo.root), "--max-mb", "0"]) == 2
    with pytest.raises(SystemExit) as ei:
        ss.run([])  # a mode is required
    assert ei.value.code == 2


def test_empty_repo_history_is_clean(tmp_path):
    r = Repo(tmp_path / "empty")
    res = ss.scan_history(r.root)
    assert res.findings == [] and res.commits == 0
    assert ss.scan_staged(r.root).findings == []


def test_cli_entry_point_exit_code(repo, tmp_path):
    cmd = [sys.executable, str(HERE / "secret_scan.py"), "--tree", str(repo.root)]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    assert subprocess.run(cmd, capture_output=True, env=env).returncode == 0
    repo.write(".env", "X=1\n")
    p = subprocess.run(cmd, capture_output=True, env=env, text=True, encoding="utf-8")
    assert p.returncode == 1 and ".env" in p.stdout and "path-env-file" in p.stdout


# ============================================================================================================== path rules
PATH_CASES = [
    ("muse_studio/data/accounts.json", "path-accounts-json"),
    ("accounts.json.bak", "path-accounts-json"),
    ("data/accounts.json.20261120", "path-accounts-json"),
    ("notes.bak", "path-backup"),
    ("notes.bak.1", "path-backup"),
    ("data/state.json.bak-2026", "path-backup"),
    ("muse_studio/data/profiles/acc_1/x.txt", "path-profiles-dir"),
    ("profiles/readme.txt", "path-profiles-dir"),
    ("muse_studio/data/lane_leases.json", "path-lane-leases"),
    ("lane_leases.json.tmp", "path-lane-leases"),
    ("muse_studio/data/muse_halt.json", "path-halt-file"),
    ("muse_halt.json.lock", "path-halt-file"),
    ("export.cookie", "path-cookie-file"),
    ("a.cookies.txt", "path-cookie-file"),
    ("browser.cookie.json", "path-cookie-file"),
    ("session.json", "path-session-json"),
    ("flow_session_state.json", "path-session-json"),
    ("cookies.json", "path-cookie-file"),
    ("cookies.txt", "path-cookie-file"),
    ("my-cookies.txt", "path-cookie-file"),
    ("session.txt", "path-session-json"),
    ("session_state.json.tmp", "path-session-json"),
    ("muse_studio/data/.accounts.json.tmp.123.456", "path-accounts-json"),
    (".env", "path-env-file"),
    (".env.local", "path-env-file"),
    ("cfg/.env.production", "path-env-file"),
    ("cache.sqlite", "path-sqlite"),
    ("cache.sqlite-wal", "path-sqlite"),
    ("data.sqlite3", "path-sqlite"),
    ("Cookies", "path-browser-credential-file"),
    ("some/dir/Login Data", "path-browser-credential-file"),
    ("Local State", "path-browser-credential-file"),
    ("Default/notes.txt", "path-chromium-profile"),
    ("chrome/Preferences", "path-chromium-profile"),
    ("chrome/Network/x.txt", "path-chromium-profile"),
]


@pytest.mark.parametrize("rel,rule", PATH_CASES)
def test_path_rule_fires_staged(repo, rel, rule):
    repo.write(rel, "harmless\n")
    repo.stage(rel)
    got = staged(repo).findings
    assert rule in rules(got, rel), (rel, got)
    assert all(f.commit == "index" and f.path == rel for f in got if f.rule == rule)


@pytest.mark.parametrize("rel", ["src/accounts.py", "docs/accounts_json_notes.md", "backup.txt", "profile.md",
                                 "sessions.md", "environment.md", "default/readme.txt", "network.py", "Cookbook.md",
                                 "tools/secret_scan.py", "muse_studio/tests/test_x.py", "preferences.py"])
def test_innocent_names_do_not_trip_path_rules(repo, rel):
    repo.write(rel, "harmless\n")
    repo.stage(rel)
    assert staged(repo).findings == []


def test_path_rule_function_directly():
    assert ss.path_rules("a\\b\\profiles\\c.txt") == ["path-profiles-dir"]  # a backslash path is normalised
    assert ss.path_rules("") == []
    assert ss.path_rules("ACCOUNTS.JSON") == ["path-accounts-json"]  # case-insensitive on Windows names
    assert ss.path_rules("x/Default/y") == ["path-chromium-profile"]


# ============================================================================================================== size rules
def test_media_above_the_limit_fails_and_below_passes(repo):
    repo.write("clips/big.png", b"\x89PNG" + b"\x00" * (1_300_000), binary=True)
    repo.write("clips/small.mp4", b"\x00" * 1000, binary=True)
    repo.write("clips/big.zip", b"PK" + b"\x01" * (1_300_000), binary=True)
    repo.stage("clips/big.png", "clips/small.mp4", "clips/big.zip")
    got = staged(repo, max_mb=1).findings
    assert [(f.path, f.rule) for f in got] == [("clips/big.png", "large-media"), ("clips/big.zip", "large-media")]
    assert staged(repo, max_mb=2).findings == []  # the limit is a parameter


def test_any_blob_above_the_limit_fails(repo):
    repo.write("data/dump.txt", "x" * 1_300_000)
    repo.write("data/dump.bin", b"\x01\x02\x00" * 500_000, binary=True)
    repo.write("data/tiny.txt", "x")
    repo.stage("data/dump.txt", "data/dump.bin", "data/tiny.txt")
    got = staged(repo, max_mb=1).findings
    assert [(f.path, f.rule) for f in got] == [("data/dump.bin", "large-blob"), ("data/dump.txt", "large-blob")]


def test_default_limit_is_5_mb(repo):
    repo.write("a.webp", b"\x00" * (4 * 1024 * 1024), binary=True)
    repo.write("b.webp", b"\x00" * (5 * 1024 * 1024 + 10), binary=True)
    repo.stage("a.webp", "b.webp")
    assert [(f.path, f.rule) for f in staged(repo).findings] == [("b.webp", "large-media")]


# ========================================================================================================== content rules
CONTENT_CASES = [
    ("cookie", "content-cookie-header"),
    ("setcookie", "content-cookie-header"),
    ("bearer", "content-auth-header"),
    ("basic", "content-auth-header"),
    ("sk", "content-api-key"),
    ("akia", "content-api-key"),
    ("ghp", "content-api-key"),
    ("keyassign", "content-api-key-assignment"),
    ("privkey", "content-private-key"),
    ("pwd", "content-credential-assignment"),
    ("pwdjson", "content-credential-assignment"),
    ("tokenq", "content-credential-assignment"),
    ("secretq", "content-credential-assignment"),
    ("otpq", "content-credential-assignment"),
    ("cookiejson", "content-cookie-export"),
]


@pytest.mark.parametrize("key,rule", CONTENT_CASES)
def test_content_rule_fires_with_its_line_number(repo, key, rule):
    repo.write("notes/x.txt", f"line one\nline two\n{FAKE[key]}\nline four\n")
    repo.stage("notes/x.txt")
    got = [f for f in staged(repo).findings if f.rule == rule]
    assert got and all(f.path == "notes/x.txt" and f.line == 3 and f.commit == "index" for f in got), got


def test_credential_assignment_in_source_code_needs_a_quoted_literal(repo):
    repo.write("src/a.py", "password = pw_from_form\ntoken = self.token\nauth_token = fetch()\n")
    repo.write("src/b.py", f"{FAKE['pwd']}\n")
    repo.write("conf/c.ini", f"{j('pass', 'word')}={j('hunter2', '-fake')}\n")
    repo.write("conf/d.env.txt", f"{j('SEC', 'RET')}: {j('fakefake', 'secret99')}\n")
    repo.stage("src/a.py", "src/b.py", "conf/c.ini", "conf/d.env.txt")
    got = {f.path for f in staged(repo).findings if f.rule == "content-credential-assignment"}
    assert got == {"src/b.py", "conf/c.ini", "conf/d.env.txt"}


def test_credential_rule_line_number_for_an_unquoted_config_line(repo):
    repo.write("conf/c.ini", f"[db]\n\n{j('pass', 'word')}={j('hunter2', '-fake')}\n")
    repo.stage("conf/c.ini")
    assert [(f.rule, f.line) for f in staged(repo).findings] == [("content-credential-assignment", 3)]


FALSE_POSITIVES = [
    'password = os.environ["MUSE_PASSWORD"]',
    "token = None",
    'token = ""',
    '"password": "",',
    '"password": null',
    "password: ${DB_PASSWORD}",
    'password = "<your password>"',
    'password = "changeme"',
    'password = "password"',
    'token_type = "bearer"',
    'max_tokens = "4096"',
    'secret_file = "secrets.txt"',
    'footprint = "abcdefgh"',
    "token = self.token",
    "# Cookie: handling is described in the doc",
    "headers['Set-Cookie'] is not used here",
    "Authorization: Bearer <token>",
    "the bearer of this message",
    "sha256 = " + "ab12" * 16,
    "commit " + "0123456789abcdef" * 2 + "01234567",
    'API_KEY = "YOUR_API_KEY_HERE"',
    "api_key = os.environ.get('K')",
    'otp_digits = "6"',
    "contact: noreply@example.com about the password policy",
]


@pytest.mark.parametrize("line", FALSE_POSITIVES)
def test_common_non_secrets_do_not_fire(repo, line):
    repo.write("docs/x.md", line + "\n")
    repo.write("conf/y.ini", line + "\n")
    repo.stage("docs/x.md", "conf/y.ini")
    assert staged(repo).findings == [], line


def test_email_near_a_credential_word(repo):
    near = f"login for {FAKE['email']} uses the pass{'word'} in the vault\n"
    far = f"{FAKE['email']} " + "-" * 120 + f" pass{'word'}\n"
    plain = f"contact {FAKE['email']} for the schedule\n"
    placeholder = f"pass{'word'} reset mail goes to someone@example.com\n"
    before = f"api_{'key'}: abc\n{FAKE['email']}\n"
    repo.write("a/near.txt", near)
    repo.write("a/far.txt", far)
    repo.write("a/plain.txt", plain)
    repo.write("a/example.txt", placeholder)
    repo.write("a/before.txt", before)
    repo.stage("a/near.txt", "a/far.txt", "a/plain.txt", "a/example.txt", "a/before.txt")
    got = {(f.path, f.rule, f.line) for f in staged(repo).findings}
    assert got == {("a/near.txt", "content-email-near-credential", 1),
                   ("a/before.txt", "content-email-near-credential", 2)}, got


def test_muse_accounts_schema_keys(repo):
    both = json.dumps([{"id": "a1", "name": "n", j("coo", "kies"): [], "email": FAKE["email"]}], indent=2)
    repo.write("a/both.json", both)
    repo.write("a/invite.json", json.dumps({j("invite", "_code"): "ZZZZ"}))
    repo.write("a/state.json", json.dumps({j("storage", "_state"): {"origins": []}}))
    repo.write("a/rawc.json", json.dumps({j("raw", "_cookie"): "k=v"}))
    repo.write("a/email_only.json", json.dumps({"email": "x"}))
    repo.write("a/cookies_only.json", json.dumps({j("coo", "kies"): []}))
    repo.stage(*[f"a/{n}" for n in ("both.json", "invite.json", "state.json", "rawc.json", "email_only.json",
                                    "cookies_only.json")])
    got = {f.path for f in staged(repo).findings if f.rule == "content-muse-accounts-schema"}
    assert got == {"a/both.json", "a/invite.json", "a/state.json", "a/rawc.json"}


def test_binary_blobs_are_judged_by_path_and_size_only(repo):
    blob = b"\x00\x01\x02" + FAKE["sk"].encode() + b"\x00" + FAKE["cookie"].encode()
    repo.write("assets/blob.dat", blob, binary=True)
    repo.write("assets/pic.png", blob, binary=True)
    repo.stage("assets/blob.dat", "assets/pic.png")
    assert staged(repo).findings == []


def test_utf16_text_is_still_scanned(repo):
    repo.write("notes/u16.txt", ("ok\n" + FAKE["sk"] + "\n").encode("utf-16"), binary=True)
    repo.stage("notes/u16.txt")
    assert [(f.rule, f.line) for f in staged(repo).findings] == [("content-api-key", 2)]


def test_every_rule_in_the_catalogue_has_a_test_that_fires_it(repo):
    """The catalogue and the fixtures must not drift apart."""
    fired = set()
    for rel, rule in PATH_CASES:
        fired.add(rule)
    fired |= {rule for _k, rule in CONTENT_CASES} | {"content-email-near-credential", "content-muse-accounts-schema",
                                                     "large-media", "large-blob"}
    assert fired == set(ss.RULES)


# ======================================================================================================== staged semantics
def test_staged_reads_the_index_not_the_worktree(repo):
    repo.write("notes/a.txt", FAKE["sk"] + "\n")
    repo.stage("notes/a.txt")
    repo.write("notes/a.txt", "clean now\n")  # edited after staging: the commit would still carry the secret
    assert rules(staged(repo).findings) == ["content-api-key"]
    repo.write("notes/b.txt", "clean\n")
    repo.stage("notes/b.txt")
    repo.write("notes/b.txt", FAKE["sk"] + "\n")  # in the worktree only: would not be committed
    assert [f.path for f in staged(repo).findings] == ["notes/a.txt"]


def test_staged_ignores_unstaged_and_deleted_files(repo):
    repo.write("accounts.json", "[]")  # not staged
    repo.write("notes/c.txt", FAKE["sk"])  # not staged
    assert staged(repo).findings == []
    repo.write("accounts.json", "[]")
    repo.stage("accounts.json")
    repo.commit("oops")
    repo.git("rm", "-q", "--cached", "accounts.json")  # staged deletion: the new commit would not hold it
    assert staged(repo).findings == []
    assert "path-accounts-json" in rules(history(repo).findings)  # but history still does


def test_staged_modified_file_is_scanned(repo):
    repo.write("src/app.py", "print('ok')\n" + FAKE["pwd"] + "\n")
    repo.stage("src/app.py")
    assert [(f.rule, f.line) for f in staged(repo).findings] == [("content-credential-assignment", 2)]


def test_scan_does_not_change_the_repo(repo):
    repo.write("accounts.json", "[]")
    repo.write("notes/a.txt", FAKE["sk"])
    repo.stage("accounts.json", "notes/a.txt")
    repo.commit("c2")
    repo.write("notes/b.txt", FAKE["sk"])
    repo.stage("notes/b.txt")
    snap = lambda: ((repo.root / ".git" / "index").read_bytes(), repo.git("rev-parse", "HEAD"),
                    repo.git("status", "--porcelain"), sorted(p.name for p in (repo.root / ".git").iterdir()))
    before = snap()
    staged(repo)
    history(repo)
    ss.scan_tree(repo.root)
    assert snap() == before
    assert not (repo.root / ".git" / "index.lock").exists()


# ======================================================================================================= history semantics
def test_history_finds_a_secret_removed_in_a_later_commit(repo):
    repo.write("notes/a.txt", f"x\n{FAKE['sk']}\n")
    repo.stage("notes/a.txt")
    leak = repo.commit("add secret")
    repo.write("notes/a.txt", "x\n")
    repo.stage("notes/a.txt")
    repo.commit("remove it")
    assert staged(repo).findings == []  # HEAD and the index are clean
    got = history(repo).findings
    assert [(f.path, f.rule, f.line, f.commit) for f in got] == [("notes/a.txt", "content-api-key", 2, leak[:12])]


def test_history_covers_every_ref_not_only_head(repo):
    repo.git("checkout", "-q", "-b", "side")
    repo.write("side.txt", FAKE["akia"] + "\n")
    repo.stage("side.txt")
    sha = repo.commit("side work")
    repo.git("checkout", "-q", "main")
    got = history(repo).findings
    assert [(f.path, f.commit) for f in got] == [("side.txt", sha[:12])]


def test_history_reports_one_blob_once_however_many_commits_hold_it(repo):
    repo.write("notes/a.txt", FAKE["sk"] + "\n")
    repo.stage("notes/a.txt")
    first = repo.commit("add")
    for i in range(3):
        repo.write(f"other{i}.txt", str(i))
        repo.stage(f"other{i}.txt")
        repo.commit(f"more {i}")
    res = history(repo)
    assert len(res.findings) == 1 and res.commits == 5
    assert res.blobs_scanned < res.files  # an unchanged blob is read once
    assert res.findings[0].commit == first[:12] or len(res.findings[0].commit) == 12


def test_history_same_blob_at_two_paths_reports_both_paths(repo):
    repo.write("a/one.txt", FAKE["sk"] + "\n")
    repo.write("b/two.txt", FAKE["sk"] + "\n")  # identical content, identical blob
    repo.stage("a/one.txt", "b/two.txt")
    repo.commit("dup")
    assert sorted(f.path for f in history(repo).findings) == ["a/one.txt", "b/two.txt"]


def test_history_changed_content_at_one_path_reports_each_version(repo):
    repo.write("notes/a.txt", FAKE["sk"] + "\n")
    repo.stage("notes/a.txt")
    repo.commit("v1")
    repo.write("notes/a.txt", FAKE["akia"] + "\n")
    repo.stage("notes/a.txt")
    repo.commit("v2")
    assert len(history(repo).findings) == 2


def test_history_path_rule_and_size_rule(repo):
    repo.write("muse_studio/data/accounts.json", "[]")
    repo.write("clips/big.mp4", b"\x00" * 1_300_000, binary=True)
    repo.stage("muse_studio/data/accounts.json", "clips/big.mp4")
    repo.commit("add")
    got = {(f.path, f.rule) for f in history(repo, max_mb=1).findings}
    assert got == {("muse_studio/data/accounts.json", "path-accounts-json"), ("clips/big.mp4", "large-media")}


def test_history_scans_text_larger_than_the_limit_for_content_too(repo):
    repo.write("data/dump.txt", FAKE["sk"] + "\n" + "x" * 1_300_000)
    repo.stage("data/dump.txt")
    repo.commit("big")
    assert rules(history(repo, max_mb=1).findings) == ["content-api-key", "large-blob"]


# =================================================================================================================== tree
def test_tree_mode_scans_plain_files_and_skips_dot_git(repo, tmp_path):
    root = tmp_path / "plain"
    (root / ".git").mkdir(parents=True)
    (root / ".git" / "accounts.json").write_text("[]")  # inside .git: never reported
    (root / "sub").mkdir()
    (root / "sub" / "Cookies").write_text("x")
    (root / "sub" / "n.txt").write_text("a\n" + FAKE["bearer"] + "\n", encoding="utf-8")
    got = {(f.path, f.rule, f.line, f.commit) for f in ss.scan_tree(root).findings}
    assert got == {("sub/Cookies", "path-browser-credential-file", 0, "tree"),
                   ("sub/n.txt", "content-auth-header", 2, "tree")}


# ====================================================================================================== never print text
def _all_fake_values():
    vals = set()
    for k in ("sk", "akia", "ghp", "email"):
        vals.add(FAKE[k])
    vals |= {"hunter2-fake", "fakefaketoken9999", "fakefakesecret77", "482913", "FAKEFAKEFAKE1234", "FAKEFAKEFAKE9876",
             "FAKEFAKEFAKEFAKEFAKE1234", "RkFLRUZBS0U6RkFLRUZBS0U=", "FAKEFAKEFAKEFAKEFAKEFAKE1234", "ZZZZ",
             "PRIVATE KEY", "mailhost-fake", "jane.fake", "Bearer", "Set-Cookie"[:3] + "t-"}
    return {v for v in vals if len(v) > 3}


def _plant_everything(repo: Repo) -> None:
    for i, (k, v) in enumerate(FAKE.items()):
        repo.write(f"leak/{i:02d}_{k}.txt", f"a\n{v}\nb\n")
    repo.write("leak/accounts.json", json.dumps([{"name": "n", "email": FAKE["email"], j("coo", "kies"): []}]))
    repo.write("leak/ml.json", json.dumps({j("invite", "_code"): "ZZZZ"}))
    repo.stage("leak")


def test_output_and_report_never_contain_matched_text(repo, tmp_path, capsys):
    _plant_everything(repo)
    repo.commit("leaks")
    out_s, out_h, out_t = tmp_path / "r" / "s.md", tmp_path / "r" / "h.md", tmp_path / "r" / "t.md"
    chunks = []
    for flag, out in (("--staged", out_s), ("--history", out_h), ("--tree", out_t)):
        capsys.readouterr()
        rc = ss.run([flag, str(repo.root), "--out", str(out)])
        cap = capsys.readouterr()
        # staged is clean after the commit; history and tree must hit
        assert rc == (0 if flag == "--staged" else 1)
        chunks += [cap.out, cap.err, out.read_text(encoding="utf-8")]
    # and while the files are still staged
    repo.write("leak2/x.txt", FAKE["sk"])
    repo.stage("leak2/x.txt")
    rc = ss.run(["--staged", str(repo.root), "--out", str(out_s)])
    cap = capsys.readouterr()
    assert rc == 1
    chunks += [cap.out, cap.err, out_s.read_text(encoding="utf-8")]
    blob = "\n".join(chunks)
    assert len(blob) > 500
    for secret in _all_fake_values():
        assert secret not in blob, "matched text leaked into the output or the report"
    for key in FAKE:  # also the full planted lines
        assert FAKE[key] not in blob
    assert "content-api-key" in blob and "leak/" in blob


def test_findings_carry_no_text_fields():
    assert set(ss.Finding.__dataclass_fields__) == {"path", "commit", "rule", "line"}


def test_errors_do_not_echo_content(repo, tmp_path, capsys):
    allow = tmp_path / "allow.txt"
    allow.write_text(f"leak/*|content-api-key|fake value in a test\nbadline-without-fields\n", encoding="utf-8")
    assert ss.run(["--staged", str(repo.root), "--allow", str(allow)]) == 2
    err = capsys.readouterr().err
    assert "line 2" in err and FAKE["sk"] not in err  # the offending line number, not its text


# =================================================================================================================== report
def test_report_file_layout(repo, tmp_path):
    repo.write("muse_studio/data/accounts.json", "[]")
    repo.write("notes/a.txt", f"1\n2\n{FAKE['sk']}\n")
    repo.stage("muse_studio/data/accounts.json", "notes/a.txt")
    out = tmp_path / "deep" / "er" / "scan_x.md"
    assert ss.run(["--staged", str(repo.root), "--out", str(out)]) == 1
    md = out.read_text(encoding="utf-8")
    assert md.startswith("# Secret scan: staged") and "**HITS**" in md
    assert "| `muse_studio/data/accounts.json` | `index` | path-accounts-json | - |" in md
    assert "| `notes/a.txt` | `index` | content-api-key | 3 |" in md
    assert "By rule:" in md and "## Allowed (explained)" in md
    clean = tmp_path / "clean.md"
    r2 = Repo(tmp_path / "r2")
    assert ss.run(["--staged", str(r2.root), "--out", str(clean)]) == 0
    assert "**CLEAN**" in clean.read_text(encoding="utf-8")


def test_unicode_path_is_reported(repo, tmp_path, capsys):
    rel = "Phim Viet/Kịch bản/accounts.json"
    repo.write(rel, "[]")
    repo.stage(rel)
    out = tmp_path / "u.md"
    assert ss.run(["--staged", str(repo.root), "--out", str(out)]) == 1
    assert "Kịch bản" in out.read_text(encoding="utf-8")
    assert [f.path for f in staged(repo).findings] == [rel]


# ================================================================================================================ allow list
def _allow(tmp_path, text) -> Path:
    p = tmp_path / "allow.txt"
    p.write_text(text, encoding="utf-8")
    return p


def test_allow_entry_accepts_one_hit_and_lists_it_with_the_reason(repo, tmp_path, capsys):
    repo.write("tests/fixture.py", FAKE["pwd"] + "\n")
    repo.write("notes/a.txt", FAKE["sk"] + "\n")
    repo.stage("tests/fixture.py", "notes/a.txt")
    allow = _allow(tmp_path, "# explained hits\n\ntests/fixture.py|content-credential-assignment|test fixture, fake value\n")
    out = tmp_path / "r.md"
    assert ss.run(["--staged", str(repo.root), "--allow", str(allow), "--out", str(out)]) == 1  # notes/a.txt remains
    md = out.read_text(encoding="utf-8")
    assert "| `tests/fixture.py` | `index` | content-credential-assignment | 1 | test fixture, fake value |" in md
    assert "`notes/a.txt`" in md.split("## Allowed")[0]
    repo.stage("tests/fixture.py")
    repo.git("rm", "-q", "--cached", "notes/a.txt")
    capsys.readouterr()
    assert ss.run(["--staged", str(repo.root), "--allow", str(allow)]) == 0
    assert "1 allowed" in capsys.readouterr().out


def test_allow_matches_rule_and_path_exactly(repo, tmp_path):
    repo.write("a/accounts.json", "[]")
    repo.write("b/accounts.json", FAKE["sk"])
    repo.stage("a/accounts.json", "b/accounts.json")
    allow = _allow(tmp_path, "a/accounts.json|path-accounts-json|empty list, no accounts\n")
    res = ss.scan_staged(repo.root, ss.load_allow(allow))
    assert sorted((f.path, f.rule) for f in res.findings) == [("b/accounts.json", "content-api-key"),
                                                              ("b/accounts.json", "path-accounts-json")]
    assert [(f.path, r) for f, r in res.allowed] == [("a/accounts.json", "empty list, no accounts")]
    wrong_rule = ss.load_allow(_allow(tmp_path, "a/accounts.json|content-api-key|wrong rule\n"))
    assert len(ss.scan_staged(repo.root, wrong_rule).findings) == 3


def test_allow_glob_and_star_rule(repo, tmp_path):
    repo.write("tests/data/a.cookie", "x")
    repo.write("tests/data/b.cookie", FAKE["cookie"])
    repo.write("src/c.cookie", "x")
    repo.stage("tests/data/a.cookie", "tests/data/b.cookie", "src/c.cookie")
    allow = ss.load_allow(_allow(tmp_path, "tests/data/*|*|fixtures for the cookie parser, fake values\n"))
    res = ss.scan_staged(repo.root, allow)
    assert [f.path for f in res.findings] == ["src/c.cookie"] and len(res.allowed) == 3


def test_allow_applies_to_history_findings(repo, tmp_path):
    repo.write("notes/a.txt", FAKE["sk"])
    repo.stage("notes/a.txt")
    repo.commit("leak")
    allow = ss.load_allow(_allow(tmp_path, "notes/a.txt|content-api-key|fake value from a past test\n"))
    res = ss.scan_history(repo.root, allow)
    assert res.findings == [] and len(res.allowed) == 1


@pytest.mark.parametrize("text", ["a.txt|content-api-key\n", "a.txt|content-api-key|\n", "|content-api-key|why\n",
                                  "a.txt|no-such-rule|why\n", "just text\n"])
def test_bad_allow_file_is_an_error(repo, tmp_path, text, capsys):
    assert ss.run(["--staged", str(repo.root), "--allow", str(_allow(tmp_path, text))]) == 2
    assert "ERROR" in capsys.readouterr().err
    assert ss.run(["--staged", str(repo.root), "--allow", str(tmp_path / "missing.txt")]) == 2


# ==================================================================================================== scanner scans itself
def test_the_scanner_and_its_tests_are_clean(tmp_path):
    r = Repo(tmp_path / "self")
    for name in ("secret_scan.py", "test_secret_scan.py"):
        r.write(f"tools/{name}", (HERE / name).read_text(encoding="utf-8"))
    r.stage("tools")
    res = ss.scan_staged(r.root)
    assert res.findings == [], [(f.path, f.rule, f.line) for f in res.findings]
    r.commit("tools")
    assert ss.scan_history(r.root).findings == []


# ---- r15b: no quadratic regexes, no content scan of a blob that is already over the size limit ----------------------
@pytest.mark.parametrize("payload", ["x" * 2_000_000, "a@" * 500_000], ids=["x_run", "at_sign_run"])
def test_scan_text_is_linear_on_long_runs(payload):
    import time
    t0 = time.perf_counter()
    ss.scan_text(payload, "blob.txt")
    assert time.perf_counter() - t0 < 2.0


def test_crlf_config_line_is_still_a_credential():
    assert ss.scan_text("pass" + "word=hunter2-fake" + chr(13) + chr(10), "conf/c.ini") == [("content-credential-assignment", 1)]


def test_long_names_and_emails_still_detected():
    assert ("content-credential-assignment", 1) in ss.scan_text("my_" + "a" * 100 + j("_pass", "word = ", '"hunter2-fake"'), "x.py")
    assert ("content-email-near-credential", 1) in ss.scan_text(j("pass", "word: ", "someone.real@", "gmail.com"), "x.txt")


# ---- r15c: findings 5-10 -----------------------------------------------------------------------------------------------
def test_tree_mode_fails_closed_when_a_folder_cannot_be_listed(repo, tmp_path, monkeypatch, capsys):
    root = tmp_path / "plain"
    (root / "locked").mkdir(parents=True)
    (root / "ok").mkdir()
    (root / "ok" / "n.txt").write_text("fine\n", encoding="utf-8")
    real = os.scandir

    def deny(path="."):
        if Path(path).name == "locked":
            raise PermissionError(13, "denied", str(path))
        return real(path)

    monkeypatch.setattr(os, "scandir", deny)
    with pytest.raises(ss.ScanError, match="E_TREE_LIST"):
        ss.scan_tree(root)
    assert ss.run(["--tree", str(root)]) == 2
    assert "E_TREE_LIST" in capsys.readouterr().err


def test_one_blob_is_scanned_per_file_type_not_once_per_sha(repo):
    line = j("pass", "word = hunter2fake") + "\n"  # a bare assignment: skipped in code files, a hit in config files
    repo.write("a.py", line)
    repo.write("b.ini", line)
    repo.stage("a.py", "b.ini")
    got = {(f.path, f.rule) for f in staged(repo).findings}
    assert got == {("b.ini", "content-credential-assignment")}
    repo.commit("same blob twice")
    hist = {(f.path, f.rule) for f in history(repo).findings}
    assert ("b.ini", "content-credential-assignment") in hist and ("a.py", "content-credential-assignment") not in hist


def test_history_scans_a_blob_that_only_a_ref_points_at(repo):
    p = subprocess.run(["git", "-C", str(repo.root), "hash-object", "-w", "--stdin"], input=FAKE["sk"] + "\n",
                       capture_output=True, text=True, check=True)
    blob = p.stdout.strip()
    assert history(repo).findings == []  # no commit holds it and no ref names it yet
    repo.git("update-ref", "refs/tags/loose-blob", blob)
    got = history(repo).findings
    assert [(f.rule, f.line, f.commit) for f in got] == [("content-api-key", 1, "ref-only")]
    # a blob that IS in a commit is still reported once, under its commit
    repo.write("notes/a.txt", FAKE["sk"] + "\n")
    repo.stage("notes/a.txt")
    sha = repo.commit("leak")
    assert [(f.path, f.commit) for f in history(repo).findings] == [("notes/a.txt", sha[:12])]


def test_cookie_export_json_is_found_by_content_and_a_plain_object_is_not(repo):
    repo.write("exports/c.json", FAKE["cookiejson"])
    repo.write("exports/ok.json", json.dumps([{"name": "theme", "value": "dark", "domain": "x"}]))
    repo.write("exports/ph.json", json.dumps([{"name": "n", "value": "<fake value>", "domain": "x"}]))
    repo.stage("exports")
    assert {f.path for f in staged(repo).findings if f.rule == "content-cookie-export"} == {"exports/c.json"}


@pytest.mark.parametrize("reason", [j("pass", "word=hunter2fake"), FAKE["sk"], "see token 4f9a8c1d2b7e6a5f3c0d9e8b7a6f5e4d",
                                    "the " + FAKE["bearer"]])
def test_allow_reason_that_looks_like_a_credential_is_refused(repo, tmp_path, reason, capsys):
    allow = _allow(tmp_path, f"notes/a.txt|content-api-key|{reason}\n")
    assert ss.run(["--staged", str(repo.root), "--allow", str(allow)]) == 2
    err = capsys.readouterr().err
    assert "E_ALLOW_REASON" in err and "line 1" in err
    assert not any(part in err for part in ("hunter2fake", "FAKEFAKE", "4f9a8c1d"))


def test_allow_reason_in_plain_words_is_still_accepted(tmp_path):
    for reason in ("test fixture, fake value", "documented example, not a real key", "fixtures for the parser"):
        assert ss.load_allow(_allow(tmp_path, f"a.txt|content-api-key|{reason}\n"))


def test_errors_never_echo_a_raw_allow_rule_or_git_stderr(repo, tmp_path, monkeypatch, capsys):
    marker = "MARKER" + "-" + "7731"
    allow = _allow(tmp_path, f"a.txt|{marker}|why\n")
    assert ss.run(["--staged", str(repo.root), "--allow", str(allow)]) == 2
    err = capsys.readouterr().err
    assert marker not in err and "E_ALLOW_RULE" in err and "line 1" in err

    class Proc:
        returncode = 128
        stdout = b""
        stderr = f"fatal: bad config value {marker}".encode()

    monkeypatch.setattr(ss.subprocess, "run", lambda *a, **k: Proc())
    assert ss.run(["--staged", str(repo.root)]) == 2
    err = capsys.readouterr().err
    assert marker not in err and "E_GIT" in err and str(repo.root) not in err


# ---- r15d: a cookie array whose objects are longer than the regex bound -------------------------------------------------
def test_long_cookie_array_json_is_found_at_a_neutral_name(repo, capsys):
    big = "Ab1Cd2Ef3" * 240  # a 2160-char cookie value, over the 2000-char object bound of the regex path
    repo.write("exports/c.json", json.dumps([{"name": "sid", "value": big, "domain": ".example.com"}]))
    repo.write("exports/nested.json", json.dumps({j("coo", "kies"): [{"name": "sid", "value": big, "domain": ".example.com"}]}))
    repo.write("exports/ok.json", json.dumps([{"name": "theme", "value": big, "label": "no domain, not a cookie"}]))
    repo.write("exports/short.json", json.dumps([{"name": "n", "value": "<fake value>", "domain": "x"}]))
    repo.stage("exports")
    found = {f.path for f in staged(repo).findings if f.rule == "content-cookie-export"}
    assert found == {"exports/c.json", "exports/nested.json"}
    assert big not in repr(staged(repo).findings), "a finding must never carry the value"
