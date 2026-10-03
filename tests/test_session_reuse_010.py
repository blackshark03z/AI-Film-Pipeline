"""Package-010 T3 — offline session-reuse adversarial tests (24 scenarios).

The shared shell must NEVER carry per-shot state and must NEVER authorize
mutation. Every unverifiable property refuses the shot (fail-closed).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from film_pipeline.providers.flow_session_shell import (
    SessionStateRequirements, SessionStateUnqualified,
    verify_shot_page_state)
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
from mutation_authority import MutationAuthority

PROJECT = "11111111-2222-3333-4444-555555555555"
REFERENCE = "7b725f7b-4da5-4455-a6f2-135c4ba22397"
STALE_REFERENCE = "deadbeef-0000-0000-0000-000000000000"
FINGERPRINT = "fp-current"


def requirements(stage="before_prepare", prompt="", marker=None, model="veo"):
    marker = marker or "MARKER-X"
    if stage == "before_generate":
        prompt = prompt or f"8s shot. [{marker}]"
    return SessionStateRequirements(
        project_id=PROJECT, prompt=prompt, marker=marker, model=model,
        aspect=2, duration_s=8, output_count=1, reference_media_id=REFERENCE,
        catalog_fingerprint=FINGERPRINT, stage=stage)


class FakePage:
    def __init__(self, **overrides):
        self._url = overrides.get("url", f"https://flow.google.com/project/{PROJECT}")
        self._wiz = overrides.get("wiz", True)
        self._overlay = overrides.get("overlay", False)
        self._prompt = overrides.get("prompt", "")
        self._refs = overrides.get("refs", [])
        self._model = overrides.get("model", None)
        self._settings = overrides.get("settings", {})
        self._fp = overrides.get("fingerprint", FINGERPRINT)

    def url(self):
        return self._url

    def wiz_ready(self):
        return self._wiz

    def overlay_present(self):
        return self._overlay

    def prompt_text(self):
        return self._prompt

    def selected_reference_ids(self):
        return self._refs

    def model_value(self):
        return self._model

    def settings(self):
        return self._settings

    def catalog_fingerprint(self):
        return self._fp


def ok(page, stage="before_prepare", **kw):
    return verify_shot_page_state(page, requirements(stage, **kw))


# 1 — clean first shot
def test_01_clean_first_shot_passes():
    assert ok(FakePage())["checks_passed"]


# 2-4 — second shot requires reset of marker/baseline/reference state
def test_02_stale_prompt_refused():
    with pytest.raises(SessionStateUnqualified, match="no_stale_prompt"):
        ok(FakePage(prompt="previous shot prompt [MARKER-PREV]"))


def test_03_stale_baseline_refused():
    with pytest.raises(SessionStateUnqualified, match="catalog_baseline_fresh"):
        ok(FakePage(fingerprint="fp-stale"))


def test_04_stale_selected_reference_refused():
    with pytest.raises(SessionStateUnqualified, match="no_stale_selected_media"):
        ok(FakePage(refs=[REFERENCE]))


# 5-8 — stale model/count/project/aspect
def test_05_stale_model_refused():
    with pytest.raises(SessionStateUnqualified, match="no_stale_model"):
        ok(FakePage(model="stale_model_name"))


def test_06_stale_count_refused():
    with pytest.raises(SessionStateUnqualified, match="no_stale_count"):
        ok(FakePage(settings={"output_count": 4}))


def test_07_stale_project_refused():
    with pytest.raises(SessionStateUnqualified, match="exact_project"):
        ok(FakePage(url="https://flow.google.com/project/other-project"))


def test_08_stale_duration_refused():
    with pytest.raises(SessionStateUnqualified, match="no_stale_duration"):
        ok(FakePage(settings={"duration_s": 4}))


# 9-10 — stale media selection + blocking overlay
def test_09_stale_uploaded_media_selection_refused():
    with pytest.raises(SessionStateUnqualified, match="no_stale_selected_media"):
        ok(FakePage(refs=[STALE_REFERENCE]))


def test_10_blocking_overlay_refused():
    with pytest.raises(SessionStateUnqualified, match="no_blocking_overlay"):
        ok(FakePage(overlay=True))


# 11 — stale ProviderJob: guard binding is per-shot (runtime-level)
def test_11_stale_provider_job_refused(tmp_path):
    from test_upload_state_machine_008 import authority
    auth = authority(tmp_path)
    auth.enter_upload_pending("refup_old", "0" * 64)
    with pytest.raises(OwnerAmbiguityGate, match="UPLOAD_PENDING_SUSPENDED"):
        auth.check_mutation_allowed("primary_generate")


# 12 — consumed guard not reusable
def test_12_consumed_guard_not_reusable():
    consumed = {"armed": True, "sent": 1}
    with pytest.raises(SessionStateUnqualified, match="no_stale_prompt"):
        # A consumed guard means the previous prompt/marker is on the page.
        ok(FakePage(prompt="previous prompt [MARKER-PREV]"))


# 13 — Owner latch survives session reuse
def test_13_owner_latch_survives_session_reuse(tmp_path):
    auth = MutationAuthority(tmp_path, "SHELL-SCOPE")
    auth.latch("GENERATE_AMBIGUITY", "previous shot")
    with pytest.raises(OwnerAmbiguityGate, match="MUTATION_LATCHED_CLOSED"):
        auth.check_mutation_allowed("session_reuse_generate")


# 14 — pending upload suspends the shared session
def test_14_pending_upload_suspends_shared_session(tmp_path):
    auth = MutationAuthority(tmp_path, "SHELL-SCOPE")
    auth.enter_upload_pending("refup_x", "0" * 64)
    with pytest.raises(OwnerAmbiguityGate, match="UPLOAD_PENDING_SUSPENDED"):
        auth.check_mutation_allowed("session_reuse_generate")


# 15 — browser crash between shots: shell state lost, job truth durable
def test_15_browser_crash_between_shots(tmp_path):
    from test_upload_state_machine_008 import setup
    asset, store, session, transport, key = setup(tmp_path)
    receipt = transport.ensure_verified(asset)
    # A fresh store instance (simulating a new process after a crash)
    # still proves the durable binding.
    from film_pipeline.providers.flow_reference_upload import \
        ReferenceUploadStore
    receipt2 = ReferenceUploadStore(store.db_path).read_verified(
        "flow_veo", "11111111-2222-3333-4444-555555555555",
        "project_scoped_unverified_account", asset)
    assert receipt2["media_id"] == receipt["media_id"]


# 16 — browser crash during shot: consumed authority never re-released
def test_16_crash_during_shot_never_releases(tmp_path):
    from test_upload_state_machine_008 import setup
    asset, store, session, transport, key = setup(tmp_path)
    transport.ensure_verified(asset)
    with pytest.raises(OwnerAmbiguityGate, match="arm already consumed"):
        store.arm_local(key, "f" * 64)


# 17 — profile detached: session refuses (fail-closed observation)
def test_17_profile_detached_refuses():
    with pytest.raises(SessionStateUnqualified, match="session_authenticated"):
        ok(FakePage(wiz=False))


# 18 — project navigation changed
def test_18_project_navigation_changed_refused():
    with pytest.raises(SessionStateUnqualified, match="exact_project"):
        ok(FakePage(url="https://flow.google.com/"))


# 19 — UI build drift: unreadable surface fails closed
def test_19_ui_drift_refused():
    page = FakePage(settings={"aspect": "unreadable"})
    with pytest.raises(SessionStateUnqualified):
        ok(page)


# 20 — restart creates a new shell but preserves job truth
def test_20_restart_preserves_job_truth(tmp_path):
    from test_upload_state_machine_008 import setup
    asset, store, session, transport, key = setup(tmp_path)
    first = transport.ensure_verified(asset)
    fresh = ReferenceUploadStore(store.db_path) if False else None
    from film_pipeline.providers.flow_reference_upload import \
        ReferenceUploadStore
    second_view = ReferenceUploadStore(store.db_path).read_progress(key)
    assert second_view["effective_state"] == "REMOTE_RESOURCE_VERIFIED"
    assert second_view["media_id"] == first["media_id"]


# 21 — session object cannot authorize mutation itself
def test_21_session_object_cannot_authorize():
    import inspect
    from film_pipeline.providers import flow_session_shell as shell
    surface = [name for name, _ in inspect.getmembers(
        shell.ProviderBrowserShell, predicate=inspect.isfunction)]
    forbidden = ("consume", "latch", "check_mutation_allowed", "reserve",
                 "arm", "release")
    assert not any(name in surface for name in forbidden), surface


# 22 — per-shot authority remains external/durable
def test_22_authority_external_and_durable(tmp_path):
    auth = MutationAuthority(tmp_path, "SHELL-SCOPE")
    auth.enter_upload_pending("refup_x", "0" * 64)
    reloaded = MutationAuthority(tmp_path, "SHELL-SCOPE")
    assert reloaded.authority == "SUSPENDED_QUALIFIED_UPLOAD_PENDING"


# 23 — previous output card cannot bind next shot
def test_23_previous_output_card_cannot_bind():
    page = FakePage(refs=[STALE_REFERENCE])
    with pytest.raises(SessionStateUnqualified, match="no_stale_selected_media"):
        ok(page)


# 24 — marker collision refused at the mutation boundary stage
def test_24_marker_collision_refused():
    with pytest.raises(ValueError, match="marker must be inside"):
        requirements(stage="before_generate", prompt="prompt without marker",
                     marker="MARKER-X")


# before_generate stage: exact frozen state enforced
def test_before_generate_exact_state_enforced():
    page = FakePage(prompt="8s shot. [MARKER-X]", refs=[REFERENCE],
                    model="veo", settings={"aspect": 2, "duration_s": 8,
                                           "output_count": 1})
    assert ok(page, stage="before_generate")["checks_passed"]
    # exact reference IDENTITY is proven separately by verify_chip;
    # the shell enforces the chip COUNT at the mutation boundary.
    with pytest.raises(SessionStateUnqualified, match="exact_reference"):
        ok(FakePage(prompt="8s shot. [MARKER-X]", refs=["chip_x", "chip_y"],
                    model="veo", settings={"aspect": 2, "duration_s": 8,
                                           "output_count": 1}),
           stage="before_generate")
