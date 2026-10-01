"""Native UI inputs bound to a backend catalog identity, with one guarded POST.

The browser surface is transport only: it may prepare and release exactly one
qualified request, and never establishes provider acceptance. Locale labels,
selector text and the wire model string are transport detail; they live in the
`NativeUiProfile` and never enter Film Core.
"""
import json
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlsplit

from ..core import sha256
from . import flow_rpc_contract as contract
from .flow_dispatch_network import generate_request_metadata
from .flow_reference_upload import OwnerAmbiguityGate


@dataclass(frozen=True)
class NativeUiProfile:
    """Locale-dependent native-UI literals for one qualified settings envelope."""

    settings_tokens: tuple[str, ...] = ('Video', '·', '720p', '8', 'giây', 'crop_16_9', 'x1')
    model_group_aria: str = 'Chọn nhóm mô hình'
    checked_toggles: frozenset[str] = frozenset({
        'videocam\nVideo', 'chrome_extension\nThành phần', 'crop_16_9\n16:9', 'x1'})
    model_label: str = 'Veo 3.1 - Lite'
    wire_model: str = 'veo_3_1_r2v_lite'
    contract_tag: str = 'native-ui-r2v-canonical-20261001-v1'


DEFAULT_NATIVE_UI = NativeUiProfile()


def thumbnail_path(url):
    p = urlsplit(url)
    if (p.scheme != 'https' or p.netloc not in {'lh3.googleusercontent.com', 'flow.google.com'}
            or p.query or p.fragment or not p.path.startswith('/asb/')):
        raise OwnerAmbiguityGate('UNQUALIFIED_REFERENCE_THUMBNAIL')
    path = p.path.removesuffix('=s1600-rw')
    if '=' in path or len(path) < 80:
        raise OwnerAmbiguityGate('UNQUALIFIED_REFERENCE_THUMBNAIL_TRANSFORM')
    return path


def reference_thumbnail(records, media_id, project_id):
    contract._validate_catalog_rows(records, project_id)
    matches = [r for r in records if r[0] == media_id]
    if len(matches) != 1 or len(matches[0]) != 7:
        raise OwnerAmbiguityGate('REFERENCE_CATALOG_IDENTITY_AMBIGUOUS')
    row = matches[0]
    paths = {thumbnail_path(v) for v in (row[5][5], row[5][10], row[6][1][3])}
    if len(paths) != 1:
        raise OwnerAmbiguityGate('REFERENCE_THUMBNAIL_CONFLICT')
    path = paths.pop()
    if any(thumbnail_path(r[5][5]) == path for r in records if r[0] != media_id):
        raise OwnerAmbiguityGate('REFERENCE_THUMBNAIL_NOT_UNIQUE')
    return path


def verify_chip(page, media_id):
    chips = page.locator('button.chip-container img.chip-image')
    if chips.count() != 1:
        raise OwnerAmbiguityGate('UI_REFERENCE_CHIP_IDENTITY_MISMATCH')
    from .flow_media import exact_resource
    try:
        exact_resource(chips.get_attribute('src'), media_id, 'image')
    except contract.ContractError:
        raise OwnerAmbiguityGate('UI_REFERENCE_CHIP_IDENTITY_MISMATCH')


def verify_settings(page, profile=DEFAULT_NATIVE_UI):
    summary = page.locator('button.settings-trigger-button')
    if summary.count() != 1 or summary.inner_text().split() != list(profile.settings_tokens):
        raise OwnerAmbiguityGate('UI_OUTPUT_SETTINGS_MISMATCH')
    summary.click()
    try:
        page.locator('.cdk-overlay-pane button[aria-label="' + profile.model_group_aria + '"]').wait_for(timeout=10000)
        selected = page.locator('.cdk-overlay-pane mat-button-toggle.mat-button-toggle-checked').all_inner_texts()
        if {s.strip() for s in selected} != set(profile.checked_toggles):
            raise OwnerAmbiguityGate('UI_MODE_OR_COUNT_MISMATCH')
        models = page.locator('.cdk-overlay-pane button[aria-label="' + profile.model_group_aria + '"]')
        if models.count() != 1 or profile.model_label not in models.inner_text():
            raise OwnerAmbiguityGate('UI_MODEL_MISMATCH')
    finally:
        summary.click()


def prepare_inputs(session, records, *, media_id, prompt, profile=DEFAULT_NATIVE_UI):
    page = session.page
    path = reference_thumbnail(records, media_id, session.project_id)
    if page.locator('button.chip-container img.chip-image').count():
        verify_chip(page, media_id)
    else:
        page.locator('button.add-menu-trigger').click()
        image = page.locator('img[src="https://flow.google.com' + path + '=s1600-rw"]')
        option = page.locator('button.asset-item').filter(has=image)
        if option.count() != 1:
            raise OwnerAmbiguityGate('UI_REFERENCE_OPTION_NOT_UNIQUE')
        option.click()
        page.locator('button.detail-add-to-prompt-btn').click()
        page.locator('button.chip-container img.chip-image').wait_for(timeout=10000)
        verify_chip(page, media_id)
    verify_settings(page)
    editor = page.locator('div.ProseMirror[contenteditable="true"]')
    if editor.count() != 1:
        raise OwnerAmbiguityGate('UI_PROMPT_EDITOR_NOT_UNIQUE')
    editor.fill(prompt)
    if editor.inner_text() != prompt:
        raise OwnerAmbiguityGate('UI_PROMPT_READBACK_MISMATCH')
    verify_chip(page, media_id)
    button = page.locator('button.generate-icon-button')
    if button.count() != 1 or not button.is_enabled():
        raise OwnerAmbiguityGate('UI_GENERATE_CONTROL_UNAVAILABLE')
    return {'media_id': media_id, 'thumbnail_path_sha256': sha256(path),
        'prompt_sha256': sha256(prompt), 'model': profile.wire_model, 'output_count': 1,
        'duration_s': 8, 'resolution': '720p', 'aspect_ratio': '16:9'}


def validate_native_request(method, url, body, *, project_id, reference_id, prompt,
                            profile=DEFAULT_NATIVE_UI):
    """Inspect the browser-created request without creating or rewriting it."""
    metadata = generate_request_metadata(method, url, body, project_id, prompt)
    if metadata is None:
        raise OwnerAmbiguityGate('NATIVE_GENERATE_REQUEST_UNQUALIFIED')
    try:
        envelope = json.loads(parse_qs(body)['f.req'][0])
        payload = json.loads(envelope[0][0][1])
        requests = payload[0]
        if len(requests) != 1:
            raise OwnerAmbiguityGate('NATIVE_OUTPUT_COUNT_MISMATCH')
        request = requests[0]
        if (request[0] != [None, None, [[[prompt]]]]
                or request[1] != [[None, reference_id]] or request[2] != profile.wire_model
                or request[3] != 2 or payload[1][5] != project_id):
            raise OwnerAmbiguityGate('NATIVE_REFERENCE_MODEL_PROJECT_MISMATCH')
    except (IndexError, KeyError, TypeError, ValueError):
        raise OwnerAmbiguityGate('NATIVE_REQUEST_SHAPE_DRIFT') from None
    return {**metadata, 'contract': profile.contract_tag}


class OneGenerateGuard:
    """Deny uploads and all duplicate/mismatched browser generation requests."""
    def __init__(self, store, job, project_id, reference_id, profile=DEFAULT_NATIVE_UI):
        self.store, self.job = store, job
        self.project_id, self.reference_id = project_id, reference_id
        self.profile = profile
        self.armed = False
        self.seen = self.sent = 0
        self.error = None

    def route(self, route):
        r = route.request
        if r.method != 'POST':
            return route.continue_()
        body = r.post_data or ''
        if 'maseQ' in r.url or 'maseQ' in body:
            self.error = 'UPLOAD_FORBIDDEN'
            return route.abort()
        if 'MZZa6b' not in r.url and 'MZZa6b' not in body:
            return route.continue_()
        self.seen += 1
        try:
            current = self.store.read_provider_job(self.job.provider_job_id)
            if not self.armed or self.seen != 1 or current.dispatch_count != 1:
                raise OwnerAmbiguityGate('UNRESERVED_OR_DUPLICATE_NATIVE_GENERATE')
            metadata = validate_native_request(r.method, r.url, body,
                project_id=self.project_id, reference_id=self.reference_id,
                prompt=self.job.correlation_evidence['prompt'], profile=self.profile)
            self.store.record_dispatch_fact(self.job.provider_job_id, 'GENERATE_REQUEST_OBSERVED', metadata)
            self.sent += 1
            route.continue_()
        except Exception:
            self.error = 'NATIVE_GENERATE_BLOCKED_REQUIRES_OWNER'
            route.abort()
