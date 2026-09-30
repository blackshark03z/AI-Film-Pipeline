"""Bounded, cookie-owned Flow reference-video RPC session.

Adapted from Story Auto's rpc_transport.py and cookie_session.py. The browser
holds authentication and executes ordinary reCAPTCHA; BrowserContext.request
performs the observed private batchexecute calls. No challenge bypass or
story_auto runtime import is used. Raw authenticated bodies stay in memory.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from PIL import Image, ImageChops, ImageStat

from . import flow_rpc_contract as contract
from .flow_reference_upload import OwnerAmbiguityGate


ORIGIN = "https://flow.google.com"
SITE_KEY = "6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV"
MAX_COOKIE_BYTES = 1024 * 1024
MAX_MEDIA_BYTES = 256 * 1024 * 1024


class FlowReferenceRpcDrift(RuntimeError):
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

    def __init__(self, *, cookie_path: Path, project_id: str):
        if not contract.UUID_RE.fullmatch(project_id):
            raise ValueError("Flow project ID invalid")
        self.cookie_path = Path(cookie_path)
        self.project_id = project_id
        self.project_url = f"{ORIGIN}/project/{project_id}"
        self._driver = None
        self._browser = None
        self.page = None
        self.catalog_fingerprint = None

    def __enter__(self):
        from playwright.sync_api import sync_playwright

        cookies = read_cookie_export(self.cookie_path)
        try:
            self._driver = sync_playwright().start()
            self._browser = self._driver.chromium.launch(headless=True)
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
            self.__exit__(None, None, None)
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

    def rpc(self, rpc_id: str, body: str):
        meta = self.metadata()
        query = urlencode({"rpcids": rpc_id, "source-path": meta["source"],
            "bl": meta["bl"], "f.sid": meta["sid"], "hl": meta["hl"], "rt": "c"})
        try:
            response = self.page.context.request.post(
                ORIGIN + "/_/AiSandboxAngularFrontend/data/batchexecute?" + query,
                data=urlencode({"f.req": body, "at": meta["at"]}),
                headers={"content-type": "application/x-www-form-urlencoded;charset=UTF-8",
                         "x-same-domain": "1", "origin": ORIGIN,
                         "referer": self.project_url},
                timeout=60000, max_redirects=0, max_retries=0)
            try:
                if response.status != 200:
                    raise ValueError("HTTP status")
                text = response.text()
                if len(text.encode("utf-8")) > 8 * 1024 * 1024:
                    raise ValueError("response size")
                return contract.parse_rpc(text, rpc_id)
            finally:
                response.dispose()
        except Exception:
            # The caller distinguishes prewrite reads from a reserved POST.
            raise FlowReferenceRpcDrift("FLOW_REFERENCE_RPC_RESPONSE_UNQUALIFIED") from None

    def catalog(self) -> list[list]:
        try:
            records = contract.catalog_records(
                self._rpc_body(contract.RPC_CATALOG,
                    contract.build_catalog(self.project_id)), self.project_id)
            self.catalog_fingerprint = contract.validate_catalog_baseline(
                self.metadata(), records, self.project_id)
            return records
        except Exception:
            raise FlowReferenceRpcDrift("FLOW_REFERENCE_RPC_CATALOG_DRIFT") from None

    def _rpc_body(self, rpc_id: str, body: str) -> str:
        """Return only for strict catalog parser, still never persist raw bytes."""
        meta = self.metadata()
        query = urlencode({"rpcids": rpc_id, "source-path": meta["source"],
            "bl": meta["bl"], "f.sid": meta["sid"], "hl": meta["hl"], "rt": "c"})
        try:
            response = self.page.context.request.post(
                ORIGIN + "/_/AiSandboxAngularFrontend/data/batchexecute?" + query,
                data=urlencode({"f.req": body, "at": meta["at"]}),
                headers={"content-type": "application/x-www-form-urlencoded;charset=UTF-8",
                         "x-same-domain": "1", "origin": ORIGIN,
                         "referer": self.project_url},
                timeout=60000, max_redirects=0, max_retries=0)
            try:
                if response.status != 200:
                    raise ValueError("HTTP status")
                text = response.text()
                if len(text.encode("utf-8")) > 8 * 1024 * 1024:
                    raise ValueError("response size")
                return text
            finally:
                response.dispose()
        except Exception:
            raise FlowReferenceRpcDrift("FLOW_REFERENCE_RPC_READ_UNAVAILABLE") from None

    def media(self, media_id: str, kind: str) -> bytes | None:
        if kind not in {"image", "video"}:
            raise ValueError("media kind invalid")
        payload = self.rpc(contract.RPC_MEDIA, contract.build_media(media_id))
        stack, urls = [payload], set()
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                stack.extend(node.values())
            elif isinstance(node, str) and node.startswith("https://"):
                parsed = urlsplit(node)
                if parsed.hostname == "flow-content.google" and parsed.path.startswith(f"/{kind}/"):
                    urls.add(node)
        if not urls:
            return None
        if len(urls) != 1:
            raise OwnerAmbiguityGate("multiple provider media URLs for one identity")
        try:
            response = self.page.context.request.get(next(iter(urls)),
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
                return data
            finally:
                response.dispose()
        except Exception:
            raise FlowReferenceRpcDrift("FLOW_REFERENCE_RPC_MEDIA_UNAVAILABLE") from None

    def upload_once(self, path: Path, request_id: str,
                    expected_sha256: str) -> tuple[str, str]:
        """Call only after durable upload reservation; caller owns ambiguity stop."""
        source_bytes = path.read_bytes()
        if hashlib.sha256(source_bytes).hexdigest() != expected_sha256:
            raise OwnerAmbiguityGate("reference bytes changed after reservation")
        payload = self.rpc(contract.RPC_UPLOAD,
            contract.build_upload(self.project_id, source_bytes,
                                  self.captcha("IMAGE_GENERATION"), request_id))
        if (not isinstance(payload, list) or len(payload) != 1
                or not isinstance(payload[0], list) or not payload[0]
                or not isinstance(payload[0][0], str)
                or not contract.UUID_RE.fullmatch(payload[0][0])):
            raise OwnerAmbiguityGate("reference upload response shape unqualified")
        media_id = payload[0][0]
        if any(isinstance(value, str) and contract.UUID_RE.fullmatch(value)
               and value != media_id for value in payload[0][1:]):
            raise OwnerAmbiguityGate("reference upload returned multiple identities")
        returned = self.media(media_id, "image")
        if returned is None:
            raise OwnerAmbiguityGate("reference upload media readback unavailable")
        try:
            with Image.open(io.BytesIO(source_bytes)) as source, Image.open(io.BytesIO(returned)) as observed:
                left = source.convert("RGB").resize((64, 64))
                right = observed.convert("RGB").resize((64, 64))
                if max(ImageStat.Stat(ImageChops.difference(left, right)).mean) > 8:
                    raise ValueError("image difference")
        except Exception:
            raise OwnerAmbiguityGate("reference upload image readback mismatch") from None
        return media_id, hashlib.sha256(returned).hexdigest()

    def submit_once(self, prompt: str, reference_id: str, request_id: str,
                    *, before_post=None) -> None:
        """Call only after durable ProviderJob reservation."""
        body = contract.build_video(self.project_id, prompt, reference_id,
                                    self.captcha("VIDEO_GENERATION"), request_id)
        if not callable(before_post):
            raise ValueError("durable request journal callback required")
        before_post(hashlib.sha256(body.encode("utf-8")).hexdigest())
        # The qualified transport treats an HTTP 200 with one parsed RPC frame
        # as an acknowledgement only. A null payload is valid; the exact
        # catalog record, never this response, proves acceptance and ownership.
        self.rpc(contract.RPC_VIDEO, body)
