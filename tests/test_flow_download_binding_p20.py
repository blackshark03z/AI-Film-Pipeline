import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/drama_flow_ui"))
import flow_reconcile as F

A = "aaaaaaaa-2222-3333-4444-555555555555"
B = "bbbbbbbb-2222-3333-4444-555555555555"
HOME = "https://flow.google.com/project/owned"
PROMPT = "Two fictional people speak quietly in the empty diner."


@pytest.mark.parametrize("opened,owned,success", [(A, True, True), (B, True, False), (A, False, False)])
def test_download_binds_captured_source_to_opened_identity_before_get_or_promotion(tmp_path, opened, owned, success):
    page = SimpleNamespace(url=HOME, mouse=SimpleNamespace(move=AsyncMock()), wait_for_timeout=AsyncMock())
    async def evaluate(script, *args):
        if script == F.fs.JS_MARK_NTH:
            return True
        if script == F.JS_MARKED_CENTRE:
            return [10, 10]
        if script == F.JS_CAPTURE_AND_OPEN:
            if not owned:
                return None
            page.url = HOME + "/edit/" + opened
            return "https://temporary.invalid/signed-video-url"
        if script == "document.body.innerText":
            return PROMPT
    async def goto(url, **kwargs):
        page.url = url
    page.evaluate, page.goto = evaluate, goto
    response = SimpleNamespace(status=200, headers={"content-type": "video/mp4"}, body=AsyncMock(return_value=b"bound clip"))
    get = AsyncMock(return_value=response)
    ctx = SimpleNamespace(request=SimpleNamespace(get=get))
    out = tmp_path / "clip.mp4"
    if not success:
        out.write_bytes(b"protected previous bytes")
    result = asyncio.run(F.download_nth(page, ctx, 0, out, media_id=A, prompt=PROMPT))
    assert (result is None) is success
    assert out.read_bytes() == (b"bound clip" if success else b"protected previous bytes")
    assert get.await_count == (1 if success else 0)


@pytest.mark.skipif(not Path("C:/Program Files/Google/Chrome/Application/chrome.exe").is_file(), reason="Windows Chrome not installed")
def test_dom_capture_cannot_use_an_overlapping_neighbour_player():
    from patchright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        try:
            page = browser.new_page()
            page.set_content("""<flow-grid-tile-container data-vp-n='1'><flow-video-tile id='chosen'></flow-video-tile></flow-grid-tile-container>
                <flow-grid-tile-container><flow-video-tile><video src='data:video/mp4;base64,AAAA'></video></flow-video-tile></flow-grid-tile-container>""")
            page.evaluate("() => { window.afpOpened=false; document.querySelector('#chosen').onclick=()=>{window.afpOpened=true}; }")
            assert page.evaluate(F.JS_CAPTURE_AND_OPEN) is None
            assert not page.evaluate("window.afpOpened")
            page.evaluate("document.querySelector('#chosen').innerHTML='<video src=\"data:video/mp4;base64,BBBB\"></video>'")
            assert page.evaluate(F.JS_CAPTURE_AND_OPEN) == "data:video/mp4;base64,BBBB"
            assert page.evaluate("window.afpOpened")
        finally:
            browser.close()
