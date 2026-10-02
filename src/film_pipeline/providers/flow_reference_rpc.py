"""Bounded, cookie-owned Flow reference-video RPC session.

Adapted from Story Auto's rpc_transport.py and cookie_session.py. The browser
holds authentication and executes ordinary reCAPTCHA; BrowserContext.request
performs the observed private batchexecute calls. No challenge bypass or
story_auto runtime import is used. Raw authenticated bodies stay in memory.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from . import flow_rpc_contract as contract
from .flow_reference_upload import OwnerAmbiguityGate


ORIGIN = "https://flow.google.com"
SITE_KEY = "6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV"
MAX_COOKIE_BYTES = 1024 * 1024
MAX_MEDIA_BYTES = 256 * 1024 * 1024


class FlowReferenceRpcDrift(RuntimeError):
    pass


class OwnerAuthRequired(RuntimeError):
    pass


def read_cookie_export(path: Path) -> list[dict]:
    """Validate an explicit local cookie export without displaying its values."""
    try:
        with Path(path).open("rb") as stream:
            encoded = stream.read(MAX_COOKIE_BYTES + 1)
        if len(encoded) > MAX_COOKIE_BYTES:
            raise ValueError()
        raw = json.loads(encoded.decode("utf-8-sig"))
        if isinstance(raw, dict):
            raw = raw["cookies"]
        if not isinstance(raw, list) or not 1 <= len(raw) <= 500:
            raise ValueError()
        rows, identities = [], set()
        for candidate in raw:
            if not isinstance(candidate, dict):
                raise ValueError()
            name, value, domain = (candidate.get(key) for key in
                                   ("name", "value", "domain"))
            if not all(isinstance(item, str) and item for item in (name, value, domain)):
                raise ValueError()
            domain = domain.lower()
            if domain.lstrip(".") != "google.com" and not domain.endswith(".google.com"):
                continue
            if domain.startswith(".."):
                raise ValueError()
            path_value = candidate.get("path", "/")
            if not isinstance(path_value, str) or not path_value.startswith("/"):
                raise ValueError()
            identity = (name, domain.lstrip("."), path_value)
            if identity in identities:
                raise ValueError()
            identities.add(identity)
            row = {"name": name, "value": value, "domain": domain,
                   "path": path_value}
            for key in ("secure", "httpOnly"):
                if key in candidate:
                    if not isinstance(candidate[key], bool):
                        raise ValueError()
                    row[key] = candidate[key]
            same = candidate.get("sameSite")
            if same is not None:
                mapping = {"none": "None", "no_restriction": "None",
                    "lax": "Lax", "strict": "Strict", "unspecified": None}
                if not isinstance(same, str) or same.lower() not in mapping:
                    raise ValueError()
                if mapping[same.lower()] is not None:
                    row["sameSite"] = mapping[same.lower()]
            expiry = candidate.get("expires", candidate.get("expirationDate"))
            if expiry is not None:
                if (isinstance(expiry, bool) or not isinstance(expiry, (int, float))
                        or not math.isfinite(expiry)):
                    raise ValueError()
                if expiry != -1 and expiry <= time.time():
                    continue
                row["expires"] = expiry
            if candidate.get("partitionKey") is not None:
                raise ValueError()
            rows.append(row)
        if not rows:
            raise ValueError()
        return rows
    except Exception:
        raise ValueError("Flow cookie export invalid") from None


class FlowReferenceRpcSession:
    """One short-lived plain Playwright browser on one exact Flow project."""

    def __init__(self, *, cookie_path: Path | None = None, project_id: str,
                 native_ui: bool = False, profile_path: Path | None = None):
        if not contract.UUID_RE.fullmatch(project_id):
            raise ValueError("Flow project ID invalid")
        if (cookie_path is None) == (profile_path is None):
            raise ValueError('exactly one explicit session source required')
        self.cookie_path = Path(cookie_path) if cookie_path is not None else None
        self.profile_path = Path(profile_path) if profile_path is not None else None
        self.project_id = project_id
        self.native_ui = native_ui
        self.project_url = f"{ORIGIN}/project/{project_id}"
        self._driver = None
        self._browser = None
        self.page = None
        self.catalog_fingerprint = None
        self.rpc_call_counts = {}

    def __enter__(self):
        from playwright.sync_api import sync_playwright

        try:
            cookies = read_cookie_export(self.cookie_path) if self.cookie_path else None
        except ValueError:
            raise OwnerAuthRequired('OWNER_AUTH_REQUIRED: valid standard Google Flow cookie export') from None
        try:
            self._driver = sync_playwright().start()
            if self.profile_path:
                if not self.native_ui or not self.profile_path.is_dir():
                    raise ValueError('existing native Chrome profile required')
                context = self._driver.chromium.launch_persistent_context(
                    str(self.profile_path), channel='chrome', headless=True,
                    viewport={"width": 1440, "height": 900})
                self._browser = context
            else:
                self._browser = self._driver.chromium.launch(headless=True,
                    **({'channel': 'chrome'} if self.native_ui else {}))
                context = self._browser.new_context(viewport={"width": 1440, "height": 900})
                context.add_cookies(cookies)
            self.page = context.new_page()
            self.page.goto(self.project_url, wait_until="domcontentloaded", timeout=45000)
            self.page.wait_for_function(
                "() => !!globalThis.WIZ_global_data?.SNlM0e && "
                "!!globalThis.grecaptcha?.enterprise?.execute", timeout=15000)
            self.metadata()
            return self
        except Exception:
            auth_required = False
            if self.page is not None:
                try:
                    auth_required = self.page.evaluate("""() =>
                        location.hostname === 'accounts.google.com' ||
                        (location.hostname === 'flow.google.com' && location.pathname === '/about') ||
                        !!document.querySelector('input[type="email"],input[type="password"]') ||
                        /sign in|đăng nhập/i.test(document.body?.innerText || '')""")
                except Exception:
                    pass
            self.__exit__(None, None, None)
            if auth_required:
                raise OwnerAuthRequired('OWNER_AUTH_REQUIRED: standard Google Flow sign-in') from None
            raise FlowReferenceRpcDrift("FLOW_REFERENCE_RPC_SESSION_NOT_READY") from None

    def __exit__(self, *_):
        browser, driver = self._browser, self._driver
        self._browser = self._driver = self.page = None
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if driver is not None:
            try:
                driver.stop()
            except Exception:
                pass

    def metadata(self) -> dict:
        try:
            data = self.page.evaluate("""() => {const w=globalThis.WIZ_global_data||{};return {
                host:location.host,source:location.pathname,at:w.SNlM0e||'',
                sid:w.FdrFJe||'',bl:w.cfb2h||'',
                hl:(document.documentElement.lang||'en').split('-')[0],
                captcha:!!(globalThis.grecaptcha?.enterprise?.execute)}}""")
            contract.validate_session(data, self.project_id)
            return data
        except Exception:
            raise FlowReferenceRpcDrift("FLOW_REFERENCE_RPC_METADATA_DRIFT") from None

    def captcha(self, action: str) -> str:
        if action not in {"IMAGE_GENERATION", "VIDEO_GENERATION"}:
            raise ValueError("unsupported Flow action")
        self.metadata()
        try:
            token = self.page.evaluate(
                "async x => await grecaptcha.enterprise.execute(x.key,{action:x.action})",
                {"key": SITE_KEY, "action": action})
        except Exception:
            raise FlowReferenceRpcDrift("FLOW_REFERENCE_RPC_CAPTCHA_UNAVAILABLE") from None
        if not isinstance(token, str) or len(token) < 500:
            raise FlowReferenceRpcDrift("FLOW_REFERENCE_RPC_CAPTCHA_UNAVAILABLE")
        return token

    def rpc(self, rpc_id: str, body: str, *, on_http_response=None, on_submission_diagnostics=None):
        text = self._rpc_body(rpc_id, body, on_http_response=on_http_response,
                              on_submission_diagnostics=on_submission_diagnostics)
        try:
            return contract.parse_rpc(text, rpc_id)
        except Exception:
            raise FlowReferenceRpcDrift("FLOW_REFERENCE_RPC_RESPONSE_UNQUALIFIED") from None

    def catalog(self, *, contract_version: str = contract.CONTRACT_VERSION) -> list[list]:
        try:
            body = self._rpc_body(
                contract.RPC_CATALOG, contract.build_catalog(self.project_id)
            )
            if contract_version == contract.CONTRACT_VERSION_2026_10_01:
                records = contract.catalog_records_v2026_10_01(body, self.project_id)
            else:
                records = contract.catalog_records(body, self.project_id)
            self.catalog_fingerprint = contract.validate_catalog_baseline(
                self.metadata(), records, self.project_id)
            return records
        except Exception:
            raise FlowReferenceRpcDrift("FLOW_REFERENCE_RPC_CATALOG_DRIFT") from None

    def _rpc_body(self, rpc_id: str, body: str, *, on_http_response=None,
                  on_submission_diagnostics=None) -> str:
        """Return only for strict catalog parser, still never persist raw bytes."""
        meta = self.metadata()
        query = urlencode({"rpcids": rpc_id, "source-path": meta["source"],
            "bl": meta["bl"], "f.sid": meta["sid"], "hl": meta["hl"], "rt": "c"})
        try:
            self.rpc_call_counts[rpc_id] = self.rpc_call_counts.get(rpc_id, 0) + 1
            response = self.page.context.request.post(
                ORIGIN + "/_/AiSandboxAngularFrontend/data/batchexecute?" + query,
                data=urlencode({"f.req": body, "at": meta["at"]}),
                headers={"content-type": "application/x-www-form-urlencoded;charset=UTF-8",
                         "x-same-domain": "1", "origin": ORIGIN,
                         "referer": self.project_url},
                timeout=60000, max_redirects=0, max_retries=0)
            try:
                text = response.text()
                if on_http_response:
                    on_http_response(response.status, len(text.encode("utf-8")))
                if rpc_id == contract.RPC_VIDEO and on_submission_diagnostics:
                    on_submission_diagnostics(contract.submission_diagnostics(text))
                if response.status != 200:
                    raise ValueError("HTTP status")
                if len(text.encode("utf-8")) > 8 * 1024 * 1024:
                    raise ValueError("response size")
                return text
            finally:
                response.dispose()
        except Exception:
            raise FlowReferenceRpcDrift("FLOW_REFERENCE_RPC_READ_UNAVAILABLE") from None

    def media_payload(self, media_id: str):
        """One read-only as29s payload observation for an exact media id.

        ``None`` means the qualified RPC frame carried a null payload — the
        observed pending/not-yet-resolved signature. A non-None payload is
        returned uninterpreted; only the flow_media contract decides whether
        it is a usable media resource. No bytes are downloaded here."""
        return self.rpc(contract.RPC_MEDIA, contract.build_media(media_id))

    def media(self, media_id: str, kind: str) -> bytes | None:
        return self.bound_media(media_id, kind).data

    def bound_media(self, media_id: str, kind: str):
        from .flow_media import parse_media_resource, bind_media_bytes
        if kind not in {"image", "video"}:
            raise ValueError("media kind invalid")
        payload = self.rpc(contract.RPC_MEDIA, contract.build_media(media_id))
        resource = parse_media_resource(payload, media_id=media_id,
            project_id=self.project_id, kind=kind)
        try:
            response = self.page.context.request.get(resource.url,
                timeout=60000, max_redirects=0, max_retries=0)
            try:
                if response.status != 200:
                    raise ValueError("media unavailable")
                size = int(response.headers.get("content-length", "0"))
                if size > MAX_MEDIA_BYTES:
                    raise ValueError("media too large")
                data = response.body()
                if not data or len(data) > MAX_MEDIA_BYTES:
                    raise ValueError("media invalid")
                return bind_media_bytes(resource, data=data, response_url=response.url,
                    status=response.status, headers=response.headers)
            finally:
                response.dispose()
        except Exception:
            raise FlowReferenceRpcDrift("FLOW_REFERENCE_RPC_MEDIA_UNAVAILABLE") from None

    def upload_reference(self, source_bytes: bytes, request_id: str, *,
                         before_post, on_http_response, on_identified) -> str:
        """Prepare/arm one POST, then persist identity before any media readback."""
        if not all(callable(callback) for callback in
                   (before_post, on_http_response, on_identified)):
            raise ValueError('durable reference lifecycle callbacks required')
        body = contract.build_upload(self.project_id, source_bytes,
                                     self.captcha('IMAGE_GENERATION'), request_id)
        before_post(hashlib.sha256(body.encode('utf-8')).hexdigest())
        payload = self.rpc(contract.RPC_UPLOAD, body, on_http_response=on_http_response)
        if (not isinstance(payload, list) or not payload
                or not isinstance(payload[0], list) or not payload[0]
                or not isinstance(payload[0][0], str)
                or not contract.UUID_RE.fullmatch(payload[0][0])):
            raise OwnerAmbiguityGate("reference upload response shape unqualified")
        media_id = payload[0][0]
        metadata_ids = {self.project_id.lower(), request_id.lower(),
            contract._new_uuid(request_id, 'upload-client').lower(),
            contract._new_uuid(request_id, 'upload-session').lower()}
        if media_id.lower() in metadata_ids:
            raise OwnerAmbiguityGate("reference upload primary identity is project or correlation metadata")
        # Only a sibling record's primary slot can supply another resource ID.
        # Nested metadata UUIDs are not identities. Unknown resource-like siblings
        # still fail closed; never resolve a conflict by gallery/record ordering.
        for sibling in payload[1:]:
            if (isinstance(sibling, list) and sibling
                    and isinstance(sibling[0], str)
                    and contract.UUID_RE.fullmatch(sibling[0])
                    and sibling[0].lower() not in metadata_ids
                    and sibling[0].lower() != media_id.lower()):
                raise OwnerAmbiguityGate("reference upload returned conflicting primary identities")
        on_identified(media_id)
        return media_id

    def submit_once(self, prompt: str, reference_id: str, request_id: str,
                    *, before_post=None, on_diagnostics=None) -> None:
        """Call only after durable ProviderJob reservation."""
        body = contract.build_video(self.project_id, prompt, reference_id,
                                    self.captcha("VIDEO_GENERATION"), request_id)
        if not callable(before_post):
            raise ValueError("durable request journal callback required")
        before_post(hashlib.sha256(body.encode("utf-8")).hexdigest())
        # The qualified transport treats an HTTP 200 with one parsed RPC frame
        # as an acknowledgement only. A null payload is valid; the exact
        # catalog record, never this response, proves acceptance and ownership.
        self.rpc(contract.RPC_VIDEO, body, on_submission_diagnostics=on_diagnostics)
