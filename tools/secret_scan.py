#!/usr/bin/env python3
"""Secret scanner for the M3 merge (M3_MERGE_PLAN section 2.2). Standard library only.

Modes (exactly one):
  --staged  <repo>   the index: files from `git diff --cached --name-only --diff-filter=ACMR`, content of the staged blob
  --history <repo>   every blob of every commit reachable from any ref (`git rev-list --all`, plus refs that point straight at a tree or blob), one scan per distinct blob
  --tree    <dir>    plain files under a directory (the `.git` directory is skipped)

Rules:
  path rules      account / cookie / session / profile / lease / halt / env / sqlite files, browser-profile markers,
                  media files above --max-mb, any blob above --max-mb
  content rules   text blobs only (a blob with a NUL byte is binary and is judged by path and size alone):
                  Cookie / Set-Cookie header with a value, bearer or basic auth header with a token, vendor-style API
                  keys (sk-, AKIA, ghp_, xox*-, AIza), private-key blocks, key-like names assigned a long
                  hex/base64 value, password / otp / secret / token assigned a literal value, an e-mail address within
                  ~80 characters of a credential word, Muse account-schema keys ("cookies" + "email", "invite_code",
                  "storage_state", "raw_cookie") appearing together as JSON keys

Output: the path, the commit (or "index" / "tree"), the rule name and the line number. NEVER the matched text: not on the
console, not in the report. The scanner only reads: git is run with GIT_OPTIONAL_LOCKS=0 and no write command.

Exit code: 0 clean, 1 hits, 2 error.

--allow <file>: lines `path|rule|reason` (path is an fnmatch glob over the repo-relative path, rule may be `*`, the reason
is required). An allowed hit is listed in the report with its reason and does not count towards the exit code.
"""
from __future__ import annotations

import argparse
import bisect
import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

DEFAULT_MAX_MB = 5.0
CONTENT_SCAN_CAP = 50 * 1024 * 1024  # larger blobs are reported by size and not read
BINARY_SNIFF = 8000

MEDIA_EXT = {".mp4", ".mov", ".mkv", ".webm", ".wav", ".mp3", ".png", ".jpg", ".jpeg", ".webp", ".zip"}
CODE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".c", ".cc", ".cpp", ".h",
            ".hpp", ".cs", ".kt", ".swift", ".rb", ".php"}

RULES = (
    "path-accounts-json", "path-backup", "path-profiles-dir", "path-lane-leases", "path-halt-file",
    "path-cookie-file", "path-session-json", "path-env-file", "path-sqlite", "path-browser-credential-file",
    "path-chromium-profile", "large-media", "large-blob",
    "content-cookie-header", "content-auth-header", "content-api-key", "content-api-key-assignment",
    "content-private-key", "content-credential-assignment", "content-email-near-credential",
    "content-muse-accounts-schema", "content-cookie-export",
)


class ScanError(RuntimeError):
    """Anything that stops the scan (exit code 2)."""


@dataclass(frozen=True)
class Finding:
    path: str  # repo-relative, forward slashes
    commit: str  # short sha, "index" or "tree"
    rule: str
    line: int = 0  # 0 = the whole file (path and size rules)


@dataclass
class AllowEntry:
    path_glob: str
    rule: str
    reason: str

    def matches(self, f: Finding) -> bool:
        return (self.rule in ("*", f.rule)) and fnmatch.fnmatchcase(f.path, self.path_glob)


@dataclass
class ScanResult:
    mode: str
    target: str
    findings: List[Finding] = field(default_factory=list)
    allowed: List[Tuple[Finding, str]] = field(default_factory=list)
    blobs_scanned: int = 0
    commits: int = 0
    files: int = 0
    max_mb: float = DEFAULT_MAX_MB


# ----------------------------------------------------------------------------------------------------------- path rules
def _norm(path: str) -> str:
    return path.replace("\\", "/").lstrip("/")


# `cookies.json`, `cookies.txt`, `my-cookies.txt`, `cookie.jar`, `cookies.json.tmp`: the names browser exporters use.
RE_COOKIE_EXPORT_NAME = re.compile(r"(?:^|[._-])cookies?\.(?:json|txt|jar)(?:$|[._-])")


def path_rules(path: str) -> List[str]:
    """Rule names a repo-relative path trips, from the name alone."""
    p = _norm(path)
    parts = [c for c in p.split("/") if c]
    if not parts:
        return []
    base, low = parts[-1], parts[-1].lower()
    dirs = parts[:-1]
    out: List[str] = []
    if fnmatch.fnmatchcase(low.lstrip("."), "accounts.json*"):  # also the hidden temp `.accounts.json.tmp.<pid>.<thread>`
        out.append("path-accounts-json")
    if fnmatch.fnmatchcase(low, "*.bak*"):
        out.append("path-backup")
    if any(c.lower() == "profiles" for c in dirs):
        out.append("path-profiles-dir")
    if fnmatch.fnmatchcase(low, "lane_leases.json*"):
        out.append("path-lane-leases")
    if fnmatch.fnmatchcase(low, "muse_halt.json*"):
        out.append("path-halt-file")
    if fnmatch.fnmatchcase(low, "*.cookie*") or RE_COOKIE_EXPORT_NAME.search(low):
        out.append("path-cookie-file")
    if fnmatch.fnmatchcase(low, "*session*.json*") or fnmatch.fnmatchcase(low, "*session*.txt*"):
        out.append("path-session-json")
    if low.startswith(".env"):
        out.append("path-env-file")
    if fnmatch.fnmatchcase(low, "*.sqlite*"):
        out.append("path-sqlite")
    if low in ("cookies", "login data", "local state"):
        out.append("path-browser-credential-file")
    if "Default" in dirs or "Network" in dirs or base == "Preferences":
        out.append("path-chromium-profile")
    return out


def size_rules(path: str, size: int, max_bytes: int) -> List[str]:
    if size <= max_bytes:
        return []
    return ["large-media" if Path(_norm(path)).suffix.lower() in MEDIA_EXT else "large-blob"]


# -------------------------------------------------------------------------------------------------------- content rules
_I = re.IGNORECASE
RE_SET_COOKIE = re.compile(r"\bset-cookie\s*:\s*\S", _I)
# Every quantifier below is bounded or exact: only the match START is used, and an open-ended `{n,}` makes a long run of
# word characters (a minified blob, "x" * 2_000_000) quadratic because each start position rescans the whole run.
RE_COOKIE = re.compile(r"(?<![\w-])cookie\s*:\s*[\w.%-]{1,256}=[^\s;\"']{6}", _I)
RE_BEARER = re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{16}", _I)
RE_BASIC = re.compile(r"\bauthorization\s*[:=]\s*[\"']?basic\s+[A-Za-z0-9+/=]{12}", _I)
RE_VENDOR_KEY = re.compile(
    r"\bsk-[A-Za-z0-9_-]{20}|\bAKIA[0-9A-Z]{16}\b|\bghp_[A-Za-z0-9]{30}|\bgithub_pat_[A-Za-z0-9_]{30}"
    r"|\bxox[baprs]-[A-Za-z0-9-]{10}|\bAIza[0-9A-Za-z_-]{35}\b")
RE_PRIVATE_KEY = re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY(?: BLOCK)?-----")
RE_KEY_ASSIGN = re.compile(
    r"(?<![A-Za-z])(?:api[_-]?key|apikey|access[_-]?key|secret[_-]?key|auth[_-]?token|private[_-]?key|client[_-]?secret)"
    r"[\"']?\s*[:=]\s*[rbf]?[\"']?(?P<v>[A-Za-z0-9+/_=-]{24,256})", _I)
_NAME = (r"(?<![A-Za-z0-9_.-])(?P<name>[A-Za-z0-9_.-]*?(?:password|passwd|(?<![A-Za-z])pwd(?![A-Za-z])|(?<![A-Za-z])otp(?![A-Za-z])"
         r"|secret|token)(?P<suffix>[A-Za-z0-9_-]{0,128}+))")  # possessive: no shorter suffix can be followed by [:=], so no backtracking
RE_CRED_QUOTED = re.compile(_NAME + r"[\"']?\s*[:=]\s*[rbf]?(?P<q>[\"'])(?P<v>[^\"'\s]{4,})(?P=q)", _I)
RE_CRED_BARE = re.compile(r"^[ 	]*" + _NAME + r"[ 	]*[:=][ 	]*(?P<v>[^\s\"'#]{4,})[ 	]*(?:#.*)?\r?$", _I | re.MULTILINE)
RE_EMAIL = re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){0,8}"
                      r"\.[A-Za-z]{2,24}")
RE_CRED_WORD = re.compile(r"password|passwd|(?<![A-Za-z])pwd(?![A-Za-z])|(?<![A-Za-z])otp(?![A-Za-z])|secret|token"
                          r"|cookie|credential|api[_-]?key", _I)
EMAIL_WINDOW = 80
RE_JSON_OBJECT = re.compile(r"\{[^{}]{1,2000}\}")  # innermost objects only; each start scans a bounded stretch
RE_OBJ_NAME = re.compile(r"[\"']name[\"']\s*:\s*[\"'][^\"']{1,100}[\"']", _I)
RE_OBJ_DOMAIN = re.compile(r"[\"']domain[\"']\s*:\s*[\"'][^\"']{1,255}[\"']", _I)
RE_OBJ_VALUE = re.compile(r"[\"']value[\"']\s*:\s*[\"'](?P<v>[^\"']{8,})[\"']", _I)
RE_KEY_COOKIES = re.compile(r"[\"']cookies[\"']\s*:", _I)
RE_KEY_EMAIL = re.compile(r"[\"']email[\"']\s*:", _I)
RE_KEY_SINGLE = re.compile(r"[\"'](?:invite_code|storage_state|raw_cookie)[\"']\s*:", _I)

# the value after a name is not a secret when it is a placeholder or a reference
_PLACEHOLDER = re.compile(r"^(?:x{3,}|\*+|\.{3,}|<.*>|\$\{?\w.*|\{\{.*\}\}|\{.*\}|%[sd]|%\(.*\)s|none|null|true|false"
                          r"|changeme|change_me|your[_-].*|redacted|placeholder|example|dummy|todo)$", _I)
_NON_SECRET_SUFFIX = {"type", "types", "count", "counts", "limit", "limits", "len", "length", "url", "uri", "file",
                      "path", "ttl", "expiry", "expires", "field", "name", "header", "env", "var", "var_name",
                      "key_name", "label", "placeholder", "hint", "prompt", "text", "id", "kind", "mode", "format",
                      "endpoint", "param", "params", "regex", "pattern", "status", "state", "error", "message"}
_REFERENCE_HEAD = {"self", "os", "args", "arg", "cfg", "config", "env", "settings", "request", "data", "kwargs", "opts",
                   "options", "params", "ctx", "context", "secrets", "st", "process"}


def _suffix_is_benign(suffix: str) -> bool:
    s = re.sub(r"^[_-]+", "", suffix)
    if not s:
        return False
    last = re.split(r"[_-]", s)[-1].lower()
    camel = re.findall(r"[A-Z][a-z]+|[a-z]+", s)
    return last in _NON_SECRET_SUFFIX or (bool(camel) and camel[-1].lower() in _NON_SECRET_SUFFIX) or \
        s.lower() in _NON_SECRET_SUFFIX


def _literal_value_ok(name: str, value: str, quoted: bool) -> bool:
    low = value.lower()
    if _PLACEHOLDER.match(value):
        return False
    if value.isdigit() and len(value) <= 9 and name.lower().endswith("tokens"):
        return False  # a count (`max_tokens = "4096"`), not a credential
    if low == name.lower() or low in ("password", "passwd", "secret", "token", "otp", "pwd"):
        return False
    if not quoted:
        if re.search(r"[()\[\]${}<>]", value):
            return False
        if re.match(r"^[A-Za-z_]\w*(?:\.\w+)+$", value) and value.split(".")[0].lower() in _REFERENCE_HEAD:
            return False
    return True


def _json_has_cookie_object(text: str) -> bool:
    """True when `text` parses as JSON that holds a {name, domain, value} object with a real value, at any depth.

    The regex path above only sees objects up to 2000 characters, so a long cookie value slipped past it; this one is
    exact. Iterative walk (no recursion limit), linear in the size of the document. Values are never returned."""
    head = text.lstrip()[:1]
    if head not in ("[", "{"):
        return False
    try:
        doc = json.loads(text)
    except (ValueError, RecursionError):
        return False
    stack = [doc]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            name, domain, value = node.get("name"), node.get("domain"), node.get("value")
            if (isinstance(name, str) and name and isinstance(domain, str) and domain
                    and isinstance(value, str) and len(value) >= 8 and not _PLACEHOLDER.match(value)):
                return True
            stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
        elif isinstance(node, list):
            stack.extend(v for v in node if isinstance(v, (dict, list)))
    return False


class _LineIndex:
    def __init__(self, text: str):
        self.starts = [0] + [m.end() for m in re.finditer(r"\n", text)]

    def line(self, offset: int) -> int:
        return bisect.bisect_right(self.starts, offset)


def scan_text(text: str, path: str) -> List[Tuple[str, int]]:
    """(rule, line) for every content rule that fires. The matched text is never returned."""
    idx = _LineIndex(text)
    seen: Dict[Tuple[str, int], None] = {}

    def hit(rule: str, offset: int) -> None:
        seen.setdefault((rule, idx.line(offset)), None)

    for m in RE_SET_COOKIE.finditer(text):
        hit("content-cookie-header", m.start())
    for m in RE_COOKIE.finditer(text):
        hit("content-cookie-header", m.start())
    for m in RE_BEARER.finditer(text):
        hit("content-auth-header", m.start())
    for m in RE_BASIC.finditer(text):
        hit("content-auth-header", m.start())
    for m in RE_VENDOR_KEY.finditer(text):
        hit("content-api-key", m.start())
    for m in RE_PRIVATE_KEY.finditer(text):
        hit("content-private-key", m.start())
    for m in RE_KEY_ASSIGN.finditer(text):
        if not _PLACEHOLDER.match(m.group("v")):
            hit("content-api-key-assignment", m.start())
    for m in RE_CRED_QUOTED.finditer(text):
        if not _suffix_is_benign(m.group("suffix")) and _literal_value_ok(m.group("name"), m.group("v"), True):
            hit("content-credential-assignment", m.start())
    if Path(_norm(path)).suffix.lower() not in CODE_EXT:
        for m in RE_CRED_BARE.finditer(text):
            if not _suffix_is_benign(m.group("suffix")) and _literal_value_ok(m.group("name"), m.group("v"), False):
                hit("content-credential-assignment", m.start())
    for m in RE_EMAIL.finditer(text):
        addr = m.group(0).lower()
        if addr.startswith("noreply@") or addr.startswith("no-reply@") or re.search(r"@example\.(?:com|org|net)$", addr):
            continue
        lo, hi = max(0, m.start() - EMAIL_WINDOW), min(len(text), m.end() + EMAIL_WINDOW)
        if RE_CRED_WORD.search(text[lo:m.start()]) or RE_CRED_WORD.search(text[m.end():hi]):
            hit("content-email-near-credential", m.start())
    for m in RE_JSON_OBJECT.finditer(text):  # a browser cookie export: [{"name": .., "value": .., "domain": ..}, ..]
        body = m.group(0)
        v = RE_OBJ_VALUE.search(body)
        if v and not _PLACEHOLDER.match(v.group("v")) and RE_OBJ_NAME.search(body) and RE_OBJ_DOMAIN.search(body):
            hit("content-cookie-export", m.start())
    if _json_has_cookie_object(text):  # same rule for objects the 2000-char regex above cannot reach
        hit("content-cookie-export", 0)
    single = RE_KEY_SINGLE.search(text)
    cookies, email = RE_KEY_COOKIES.search(text), RE_KEY_EMAIL.search(text)
    if single:
        hit("content-muse-accounts-schema", single.start())
    elif cookies and email:
        hit("content-muse-accounts-schema", min(cookies.start(), email.start()))
    return sorted(seen)


def decode_text(data: bytes) -> Optional[str]:
    """Text of a blob, or None when it is binary (NUL byte in the first 8000 bytes, git's own heuristic)."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    if b"\x00" in data[:BINARY_SNIFF]:
        return None
    return data.decode("utf-8", errors="replace")


# ------------------------------------------------------------------------------------------------------------------ git
def _git_env() -> Dict[str, str]:
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"  # no opportunistic index refresh: the scan writes nothing
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _git(repo: Path, *args: str, stdin: Optional[bytes] = None) -> bytes:
    try:
        proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, env=_git_env(), input=stdin)
    except OSError as exc:
        raise ScanError(f"E_GIT: cannot run git ({exc.__class__.__name__})") from exc
    if proc.returncode != 0:  # git's own stderr can echo config values: only the operation and the exit code are kept
        raise ScanError(f"E_GIT: git {args[0]} failed (exit {proc.returncode})")
    return proc.stdout


class BlobReader:
    """`git cat-file --batch`: one process for all blob reads."""

    def __init__(self, repo: Path):
        try:
            self.proc = subprocess.Popen(["git", "-C", str(repo), "cat-file", "--batch"], stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=_git_env())
        except OSError as exc:
            raise ScanError(f"E_GIT: cannot run git ({exc.__class__.__name__})") from exc

    def read(self, sha: str, max_bytes: int) -> Tuple[int, Optional[bytes]]:
        """(size, content). Content is None when the blob is larger than max_bytes (it is skipped, not buffered)."""
        assert self.proc.stdin and self.proc.stdout
        self.proc.stdin.write(sha.encode("ascii") + b"\n")
        self.proc.stdin.flush()
        header = self.proc.stdout.readline().split()
        if len(header) != 3 or header[1] != b"blob":
            raise ScanError(f"object {sha[:12]} is not readable as a blob")
        size = int(header[2])
        if size > max_bytes:
            left = size
            while left > 0:
                chunk = self.proc.stdout.read(min(left, 1 << 20))
                if not chunk:
                    raise ScanError("git cat-file ended early")
                left -= len(chunk)
            self.proc.stdout.read(1)
            return size, None
        data = self.proc.stdout.read(size)
        self.proc.stdout.read(1)
        if len(data) != size:
            raise ScanError("git cat-file ended early")
        return size, data

    def close(self) -> None:
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()


def _check_repo(repo: Path) -> None:
    if not repo.is_dir():
        raise ScanError(f"not a directory: {repo}")
    _git(repo, "rev-parse", "--git-dir")


# ----------------------------------------------------------------------------------------------------------- scanning
class _Collector:
    def __init__(self, allow: Sequence[AllowEntry], result: ScanResult):
        self.allow, self.result = allow, result
        self._seen: set = set()

    def add(self, f: Finding, dedupe_key: object = None) -> None:
        key = (f, dedupe_key)
        if key in self._seen:
            return
        self._seen.add(key)
        for entry in self.allow:
            if entry.matches(f):
                self.result.allowed.append((f, entry.reason))
                return
        self.result.findings.append(f)


def _scan_blob(col: _Collector, path: str, commit: str, size: int, max_bytes: int,
               load: Callable[[], Optional[bytes]], content_cache: Optional[Dict[Tuple[str, bool], List[Tuple[str, int]]]] = None,
               blob_key: Optional[str] = None, dedupe_key: object = None) -> None:
    """Path rules, size rules, then (text blobs only) the content rules. `load` is called at most once and only when
    needed; `content_cache` lets one distinct blob be read once however many commits or paths hold it."""
    p = _norm(path)
    for rule in path_rules(p) + size_rules(p, size, max_bytes):
        col.add(Finding(p, commit, rule, 0), dedupe_key)
    if Path(p).suffix.lower() in MEDIA_EXT or size > CONTENT_SCAN_CAP:
        return
    # The rules depend on the file type (a bare `name = value` line is skipped in code files), so one blob read as
    # `a.py` and as `b.ini` is two different scans: the cache key carries the code/config kind.
    ckey = None if blob_key is None else (blob_key, Path(p).suffix.lower() in CODE_EXT)
    if content_cache is not None and ckey is not None and ckey in content_cache:
        hits = content_cache[ckey]
    else:
        data = load()
        text = None if data is None else decode_text(data)
        hits = [] if text is None else scan_text(text, p)
        col.result.blobs_scanned += 1
        if content_cache is not None and ckey is not None:
            content_cache[ckey] = hits
    for rule, line in hits:
        col.add(Finding(p, commit, rule, line), dedupe_key)


def scan_staged(repo: Path, allow: Sequence[AllowEntry] = (), max_mb: float = DEFAULT_MAX_MB) -> ScanResult:
    _check_repo(repo)
    result = ScanResult("staged", str(repo), max_mb=max_mb)
    col, max_bytes = _Collector(allow, result), int(max_mb * 1024 * 1024)
    names = [n for n in _git(repo, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split(b"\0") if n]
    wanted = {n.decode("utf-8", "replace") for n in names}
    shas: Dict[str, str] = {}
    for rec in _git(repo, "ls-files", "-s", "-z").split(b"\0"):
        if not rec:
            continue
        meta, _, name = rec.partition(b"\t")
        mode, sha, _stage = meta.decode("ascii").split()
        n = name.decode("utf-8", "replace")
        if n in wanted and mode != "160000":
            shas[n] = sha
    reader = BlobReader(repo)
    cache: Dict[Tuple[str, bool], List[Tuple[str, int]]] = {}
    try:
        for n in sorted(shas):
            sha = shas[n]
            media = Path(_norm(n)).suffix.lower() in MEDIA_EXT
            size, data = reader.read(sha, 0 if media else CONTENT_SCAN_CAP)  # media: size only, never buffered
            result.files += 1
            _scan_blob(col, n, "index", size, max_bytes, lambda d=data: d, cache, sha)
    finally:
        reader.close()
    return result


_RE_OBJECT_ID = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")


def _unwalked_blobs(repo: Path, walked: set, commits: set) -> Dict[str, Tuple[str, int]]:
    """{blob sha: (name, size)} for reachable blobs that no commit tree holds."""
    names: Dict[str, str] = {}
    for line in _git(repo, "rev-list", "--objects", "--all").decode("utf-8", "replace").splitlines():
        sha, _, name = line.partition(" ")
        if _RE_OBJECT_ID.fullmatch(sha) and sha not in walked and sha not in commits and sha not in names:
            names[sha] = name.strip()
    if not names:
        return {}
    out: Dict[str, Tuple[str, int]] = {}
    checked = _git(repo, "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)",
                   stdin=("\n".join(names) + "\n").encode("ascii"))
    for line in checked.decode("ascii", "replace").splitlines():
        bits = line.split()
        if len(bits) == 3 and bits[1] == "blob":
            out[bits[0]] = (names.get(bits[0], ""), int(bits[2]))
    return out


def scan_history(repo: Path, allow: Sequence[AllowEntry] = (), max_mb: float = DEFAULT_MAX_MB) -> ScanResult:
    _check_repo(repo)
    result = ScanResult("history", str(repo), max_mb=max_mb)
    col, max_bytes = _Collector(allow, result), int(max_mb * 1024 * 1024)
    commits = _git(repo, "rev-list", "--all").decode("ascii").split()
    result.commits = len(commits)
    reader = BlobReader(repo)
    cache: Dict[Tuple[str, bool], List[Tuple[str, int]]] = {}
    seen_blob_path: set = set()
    in_commit_trees: set = set()
    try:
        for commit in commits:
            for rec in _git(repo, "ls-tree", "-r", "-l", "-z", commit).split(b"\0"):
                if not rec:
                    continue
                meta, _, name = rec.partition(b"\t")
                parts = meta.decode("ascii").split()
                if len(parts) < 4 or parts[1] != "blob":
                    continue  # submodule commit links are not blobs
                sha, size = parts[2], int(parts[3])
                in_commit_trees.add(sha)
                path = name.decode("utf-8", "replace")
                result.files += 1  # every tree entry inspected, so `blobs_scanned < files` shows the dedupe at work
                if (sha, path) in seen_blob_path:
                    continue  # the same blob at the same path in another commit: already reported at its first commit
                seen_blob_path.add((sha, path))

                def load(sha=sha) -> Optional[bytes]:
                    return reader.read(sha, CONTENT_SCAN_CAP)[1]

                _scan_blob(col, path, commit[:12], size, max_bytes, load, cache, sha, dedupe_key=sha)
        # A ref (or an annotated tag) can point straight at a tree or a blob: that object is reachable but no commit
        # walk sees it. `rev-list --objects --all` names every reachable object; take the blobs the walk missed.
        for sha, (name, size) in _unwalked_blobs(repo, in_commit_trees, set(commits)).items():
            result.files += 1

            def load_extra(sha=sha) -> Optional[bytes]:
                return reader.read(sha, CONTENT_SCAN_CAP)[1]

            _scan_blob(col, name or f"(ref-object)/{sha[:12]}", "ref-only", size, max_bytes, load_extra, cache, sha,
                       dedupe_key=sha)
    finally:
        reader.close()
    return result


def scan_tree(root: Path, allow: Sequence[AllowEntry] = (), max_mb: float = DEFAULT_MAX_MB) -> ScanResult:
    if not root.is_dir():
        raise ScanError(f"not a directory: {root}")
    result = ScanResult("tree", str(root), max_mb=max_mb)
    col, max_bytes = _Collector(allow, result), int(max_mb * 1024 * 1024)
    def walk_error(exc: OSError) -> None:  # os.walk swallows scandir errors by default: an unlisted folder is never CLEAN
        name = getattr(exc, "filename", None)
        try:
            rel = Path(name).relative_to(root).as_posix() if name else "?"
        except ValueError:
            rel = "?"
        raise ScanError(f"E_TREE_LIST: cannot list {rel or '.'} ({exc.__class__.__name__})") from exc

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False, onerror=walk_error):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        for fn in sorted(filenames):
            full = Path(dirpath) / fn
            rel = full.relative_to(root).as_posix()
            try:
                if full.is_symlink():
                    continue
                size = full.stat().st_size
            except OSError as exc:
                raise ScanError(f"E_TREE_STAT: cannot stat {rel} ({exc.__class__.__name__})") from exc
            result.files += 1

            def load(full=full) -> Optional[bytes]:
                try:
                    return full.read_bytes()
                except OSError as exc:
                    raise ScanError(f"E_TREE_READ: cannot read {rel} ({exc.__class__.__name__})") from exc

            _scan_blob(col, rel, "tree", size, max_bytes, load)
    return result


# --------------------------------------------------------------------------------------------------------- allow list
_RE_ASSIGNMENT = re.compile(r"\w\s*=\s*\S")
_RE_OPAQUE_WORD = re.compile(r"[A-Za-z0-9_+/=-]{24,}")


def _reason_is_unsafe(reason: str) -> bool:
    """A reason is copied into the report, so it must be prose: no content-rule hit, no `name=value`, no long opaque
    word holding a digit (a pasted key or token)."""
    if scan_text(reason, "reason.txt") or _RE_ASSIGNMENT.search(reason):
        return True
    return any(any(c.isdigit() for c in w.group(0)) for w in _RE_OPAQUE_WORD.finditer(reason))


def load_allow(path: Path) -> List[AllowEntry]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ScanError(f"E_ALLOW_READ: cannot read the allow file ({exc.__class__.__name__})") from exc
    out: List[AllowEntry] = []
    for n, line in enumerate(raw.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = [x.strip() for x in s.split("|", 2)]
        if len(parts) != 3 or not all(parts):
            raise ScanError(f"E_ALLOW_FORMAT: allow file line {n}: expected `path|rule|reason`, all non-empty")
        glob, rule, reason = parts
        if rule != "*" and rule not in RULES:  # the rule text is never echoed: a mis-typed field may be a credential
            raise ScanError(f"E_ALLOW_RULE: allow file line {n}: unknown rule")
        if _reason_is_unsafe(reason):
            raise ScanError(f"E_ALLOW_REASON: allow file line {n}: the reason looks like credential text; "
                            f"say why in plain words")
        out.append(AllowEntry(_norm(glob), rule, reason))
    return out


# ------------------------------------------------------------------------------------------------------------ output
def _row(f: Finding) -> str:
    where = f"line {f.line}" if f.line else "file"
    return f"{f.path} | {f.commit} | {f.rule} | {where}"


def summary_lines(r: ScanResult) -> List[str]:
    out = [f"secret_scan {r.mode} {r.target}: {len(r.findings)} hit(s), {len(r.allowed)} allowed, "
           f"{r.files} file(s), {r.blobs_scanned} blob(s) read" + (f", {r.commits} commit(s)" if r.mode == "history" else "")]
    out += [_row(f) for f in r.findings]
    return out


def render_report(r: ScanResult) -> str:
    L = [f"# Secret scan: {r.mode}", "",
         f"- target: `{r.target}`", f"- time: {datetime.now().isoformat(timespec='seconds')}",
         f"- size limit: {r.max_mb:g} MB", f"- files checked: {r.files}; blobs read: {r.blobs_scanned}"
         + (f"; commits: {r.commits}" if r.mode == "history" else ""),
         f"- result: **{'CLEAN' if not r.findings else 'HITS'}** ({len(r.findings)} hit(s), {len(r.allowed)} allowed)",
         "", "Matched text is never printed here: only the path, the commit, the rule and the line number.", ""]
    L += ["## Hits", ""]
    if r.findings:
        L += ["| path | commit | rule | line |", "|---|---|---|---|"]
        L += [f"| `{f.path}` | `{f.commit}` | {f.rule} | {f.line or '-'} |" for f in r.findings]
        by_rule: Dict[str, int] = {}
        for f in r.findings:
            by_rule[f.rule] = by_rule.get(f.rule, 0) + 1
        L += ["", "By rule: " + ", ".join(f"{k} {v}" for k, v in sorted(by_rule.items()))]
    else:
        L.append("none")
    L += ["", "## Allowed (explained)", ""]
    if r.allowed:
        L += ["| path | commit | rule | line | reason |", "|---|---|---|---|---|"]
        L += [f"| `{f.path}` | `{f.commit}` | {f.rule} | {f.line or '-'} | {reason.replace('|', '/')} |"
              for f, reason in r.allowed]
    else:
        L.append("none")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------------------------------------------- CLI
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Scan a git index, a git history or a folder for secrets "
                                             "(never prints the matched text). Exit 0 clean, 1 hits, 2 error.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--staged", metavar="REPO", help="scan the staged blobs of a repo")
    g.add_argument("--history", metavar="REPO", help="scan every blob of every reachable commit")
    g.add_argument("--tree", metavar="DIR", help="scan plain files under a directory")
    ap.add_argument("--max-mb", type=float, default=DEFAULT_MAX_MB, help="size limit per blob / media file (default 5)")
    ap.add_argument("--out", metavar="FILE", help="write a markdown report here")
    ap.add_argument("--allow", metavar="FILE", help="explained hits to accept: lines `path|rule|reason`")
    return ap


def run(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.max_mb <= 0:
            raise ScanError("--max-mb must be positive")
        allow = load_allow(Path(args.allow)) if args.allow else []
        if args.staged:
            result = scan_staged(Path(args.staged), allow, args.max_mb)
        elif args.history:
            result = scan_history(Path(args.history), allow, args.max_mb)
        else:
            result = scan_tree(Path(args.tree), allow, args.max_mb)
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(render_report(result), encoding="utf-8")
    except ScanError as exc:
        print(f"secret_scan ERROR: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"secret_scan ERROR: {exc.__class__.__name__} on {getattr(exc, 'filename', '?')}", file=sys.stderr)
        return 2
    print("\n".join(summary_lines(result)))
    return 1 if result.findings else 0


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    sys.exit(run())


if __name__ == "__main__":
    main()
