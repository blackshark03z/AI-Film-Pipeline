"""Provider browser session shell (Package-010 T2/T3).

A reusable browser/session SHELL that never weakens per-shot custody:

- reusable: browser process, authenticated profile, project navigation;
- per-shot and NEVER reused: intent, marker, catalog baseline, reference
  selection, output binding, mutation guard, ProviderJob, authority check.

The shell is OBSERVATIONAL + REFUSAL-only. It can raise
SESSION_STATE_UNQUALIFIED; it can never authorize a mutation. Every
mutation authorization stays in the durable MutationAuthority plus the
per-shot OneGenerateGuard chain (unchanged).
"""
from __future__ import annotations

from ..core import sha256

SESSION_STATE_UNQUALIFIED = "SESSION_STATE_UNQUALIFIED"


class SessionStateUnqualified(RuntimeError):
    """The shared shell cannot prove per-shot state freshness: no Generate."""

    def __init__(self, check: str, detail: str = ""):
        self.check = check
        super().__init__(f"{SESSION_STATE_UNQUALIFIED}: {check}"
                         + (f" ({detail})" if detail else ""))


class SessionStateRequirements:
    """Frozen per-shot expectations for the shared shell (T2 contract)."""

    def __init__(self, *, project_id: str, prompt: str, marker: str,
                 model: str, aspect: int, duration_s: int, output_count: int,
                 reference_media_id: str, catalog_fingerprint: str,
                 stage: str, verify_model_and_settings: bool = True):
        # verify_model_and_settings=False is lawful ONLY at the live
        # before_generate stage, where model/settings freshness is already
        # proven by the per-shot ui preflight report + verify_chip +
        # PROMPT_CHANGED_AT_MUTATION_BOUNDARY (proven chain).
        if stage not in ("before_prepare", "before_generate"):
            raise ValueError("unknown session state stage")
        if stage == "before_generate" and marker not in prompt:
            raise ValueError("marker must be inside the frozen prompt")
        self.project_id = project_id
        self.prompt = prompt
        self.marker = marker
        self.model = model
        self.aspect = aspect
        self.duration_s = duration_s
        self.output_count = output_count
        self.reference_media_id = reference_media_id
        self.catalog_fingerprint = catalog_fingerprint
        self.stage = stage
        self.verify_model_and_settings = verify_model_and_settings

    def digest(self) -> str:
        return sha256({
            "project_id": self.project_id, "prompt": self.prompt,
            "marker": self.marker, "model": self.model,
            "aspect": self.aspect, "duration_s": self.duration_s,
            "output_count": self.output_count,
            "reference_media_id": self.reference_media_id,
            "catalog_fingerprint": self.catalog_fingerprint,
            "stage": self.stage})


def _require(condition: bool, check: str, detail: str = "") -> None:
    if not condition:
        raise SessionStateUnqualified(check, detail[:160])


def verify_shot_page_state(page_view, requirements: SessionStateRequirements) -> dict:
    """Deterministic state verification over a minimal observable surface.

    ``page_view`` must expose: url(), wiz_ready(), overlay_present(),
    prompt_text(), selected_reference_ids(), model_value(), settings()
    (dict with aspect/duration_s/output_count), catalog_fingerprint().
    Fail-closed: ANY unverifiable property refuses the shot.
    """
    stage = requirements.stage
    url = page_view.url()
    _require(requirements.project_id in url, "exact_project", url)
    _require(page_view.wiz_ready(), "session_authenticated")
    _require(not page_view.overlay_present(), "no_blocking_overlay")
    fingerprint = page_view.catalog_fingerprint()
    _require(fingerprint == requirements.catalog_fingerprint,
             "catalog_baseline_fresh", str(fingerprint))
    if stage == "before_prepare":
        _require(page_view.prompt_text() in ("", None),
                 "no_stale_prompt", str(page_view.prompt_text())[:60])
        _require(page_view.selected_reference_ids() == [],
                 "no_stale_selected_media",
                 str(page_view.selected_reference_ids()))
        model = page_view.model_value()
        _require(model in (None, "", requirements.model),
                 "no_stale_model", str(model))
        settings = page_view.settings() or {}
        _require(settings.get("duration_s") in (None, requirements.duration_s),
                 "no_stale_duration", str(settings.get("duration_s")))
        _require(settings.get("output_count") in (None,
                                                  requirements.output_count),
                 "no_stale_count", str(settings.get("output_count")))
        _require(settings.get("aspect") in (None, requirements.aspect),
                 "no_stale_aspect", str(settings.get("aspect")))
    else:  # before_generate: exact frozen state at the mutation boundary
        _require(page_view.prompt_text() == requirements.prompt,
                 "exact_frozen_prompt")
        _require(page_view.selected_reference_ids() ==
                 [requirements.reference_media_id],
                 "exact_reference_selection",
                 str(page_view.selected_reference_ids()))
        if requirements.verify_model_and_settings:
            _require(page_view.model_value() == requirements.model,
                     "exact_model", str(page_view.model_value()))
            settings = page_view.settings() or {}
            _require((settings.get("duration_s"), settings.get("output_count"),
                      settings.get("aspect")) ==
                     (requirements.duration_s, requirements.output_count,
                      requirements.aspect), "exact_settings", str(settings))
    return {"stage": stage, "checks_passed": True,
            "requirements_digest": requirements.digest()}


class ProviderBrowserShell:
    """One persistent Playwright context for MANY shots (live adapter).

    Real browser lifecycle only; all state semantics live in
    ``verify_shot_page_state`` (fake-page testable offline).
    """

    def __init__(self, *, profile: str, project_url: str):
        self.profile = profile
        self.project_url = project_url
        self._driver = None
        self._context = None
        self.page = None

    def __enter__(self) -> "ProviderBrowserShell":
        from playwright.sync_api import sync_playwright
        self._driver = sync_playwright().start()
        self._context = self._driver.chromium.launch_persistent_context(
            self.profile, channel="chrome", headless=False,
            args=["--no-first-run", "--no-default-browser-check",
                  "--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"], viewport=None)
        self.page = self._context.pages[0] if self._context.pages \
            else self._context.new_page()
        return self

    def __exit__(self, *_):
        context, driver = self._context, self._driver
        self._context = self._driver = self.page = None
        try:
            if context is not None:
                context.close()
        except Exception:
            pass
        try:
            if driver is not None:
                driver.stop()
        except Exception:
            pass

    def reset_for_shot(self, requirements: SessionStateRequirements) -> dict:
        """Between-shot reset + state verification. Refuses stale state."""
        page = self.page
        page.goto(self.project_url, timeout=60000)
        page.wait_for_timeout(8000)
        view = _PlaywrightPageView(page)
        return verify_shot_page_state(view, requirements)

    def before_generate_check(self,
                              requirements: SessionStateRequirements) -> dict:
        view = _PlaywrightPageView(self.page)
        return verify_shot_page_state(view, requirements)


class _PlaywrightPageView:
    """Minimal observable surface over a real Flow page."""

    def __init__(self, page):
        self._page = page

    def url(self) -> str:
        return self._page.url

    def wiz_ready(self) -> bool:
        try:
            return bool(self._page.evaluate(
                "() => !!globalThis.WIZ_global_data?.SNlM0e && "
                "!!globalThis.grecaptcha?.enterprise?.execute"))
        except Exception:
            return False

    def overlay_present(self) -> bool:
        try:
            return bool(self._page.locator(
                "div[role='dialog'], .modal-overlay, "
                "div[aria-label*='Sign in']").count())
        except Exception:
            return True  # unreadable page = refuse (fail closed)

    def prompt_text(self) -> str | None:
        try:
            editor = self._page.locator(
                'div.ProseMirror[contenteditable="true"]')
            return editor.inner_text() if editor.count() == 1 else None
        except Exception:
            return None

    def selected_reference_ids(self) -> list[str]:
        try:
            chips = self._page.locator("[data-test-id='media-chip']")
            ids = []
            for index in range(chips.count()):
                ids.append(chips.nth(index).get_attribute("data-media-id")
                           or "")
            return ids
        except Exception:
            return ["unreadable"]  # fail closed

    def model_value(self) -> str | None:
        try:
            chip = self._page.locator("[data-test-id='model-chip']")
            return chip.inner_text() if chip.count() == 1 else None
        except Exception:
            return None

    def settings(self) -> dict:
        try:
            return self._page.evaluate(
                "() => ({aspect: globalThis.__film_aspect ?? null, "
                "duration_s: globalThis.__film_duration ?? null, "
                "output_count: globalThis.__film_count ?? null})") or {}
        except Exception:
            return {"aspect": "unreadable", "duration_s": "unreadable",
                    "output_count": "unreadable"}  # fail closed

    def catalog_fingerprint(self) -> str | None:
        return getattr(self._page, "catalog_fingerprint", None)
