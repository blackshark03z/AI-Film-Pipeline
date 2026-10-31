"""Shared pytest configuration.

Hermetic-suite guard
--------------------
Many evidence/regression tests re-read *local* production evidence under
``projects/`` (git-ignored by design: media, ledgers, provider receipts) or
need the optional browser extra (``patchright``/``playwright``). On the
Owner's workstation those inputs exist and the tests run normally. On a clean
clone / CI runner they do not, and previously ~280 tests errored, which hid
real regressions in the ~1100 hermetic tests.

This hook re-classifies ONLY those well-defined "local input missing"
outcomes as SKIPPED with an explicit reason. Any other failure is untouched.

Set ``FILM_STRICT_LOCAL_EVIDENCE=1`` to disable the reclassification (the
Owner workstation / release gate should run strict so a missing evidence file
is a hard failure there).
"""
from __future__ import annotations

import os
import sqlite3

import pytest

_STRICT = os.environ.get("FILM_STRICT_LOCAL_EVIDENCE") == "1"
_OPTIONAL_MODULES = {"patchright", "playwright", "PIL"}
# patchright/playwright installed but `patchright install chromium` not run
_MISSING_BROWSER = "Executable doesn't exist"
_LOCAL_MARKERS = ("projects/", "projects\\", "Flow-Claude-Clean-Profile",
                  "OWNER_REVIEW")
_LOCAL_VALUE_ERRORS = ("qualified synthetic reference source unavailable",)


def _missing_local_input(excinfo: pytest.ExceptionInfo) -> str | None:
    exc = excinfo.value
    if isinstance(exc, ModuleNotFoundError) and exc.name in _OPTIONAL_MODULES:
        return f"optional dependency '{exc.name}' not installed (pip install .[flow])"
    if type(exc).__module__.startswith(("patchright", "playwright")) and \
            _MISSING_BROWSER in str(exc):
        return "browser binary not installed (patchright install chromium)"
    if isinstance(exc, FileNotFoundError):
        target = str(exc.filename or exc)
        if any(marker in target for marker in _LOCAL_MARKERS):
            return f"git-ignored local evidence missing: {target}"
    if isinstance(exc, ValueError) and str(exc) in _LOCAL_VALUE_ERRORS:
        return f"git-ignored local evidence missing: {exc}"
    if isinstance(exc, sqlite3.OperationalError) and "unable to open database" in str(exc):
        # sqlite3.connect() on a path whose git-ignored parent dir is absent
        return "git-ignored local runtime database missing"
    return None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    if _STRICT or call.excinfo is None:
        return
    reason = _missing_local_input(call.excinfo)
    if reason is None:
        return
    report = outcome.get_result()
    if report.failed:
        report.outcome = "skipped"
        report.longrepr = (str(item.path), item.location[1] or 0,
                           f"LOCAL_INPUT_MISSING: {reason}")


def pytest_collectreport(report):
    """Collection-time import of git-ignored evidence -> skip, not error."""
    if _STRICT or not report.failed:
        return
    text = str(report.longrepr)
    if ("FileNotFoundError" in text and any(m in text for m in _LOCAL_MARKERS)) or \
            any(f"No module named '{m}'" in text for m in _OPTIONAL_MODULES):
        report.outcome = "skipped"
        report.longrepr = (str(report.fspath), 0,
                           "LOCAL_INPUT_MISSING: collection needs local evidence/optional extra")
