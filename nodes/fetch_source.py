import io
import time

import httpx
import openpyxl
from bs4 import BeautifulSoup

from state import SignalState

MAX_TEXT_CHARS = 8000

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

WORLDBANK_XLSX_URL = (
    "https://carbonpricingdashboard.worldbank.org/"
    "sites/default/files/carbon-pricing-dashboard-data/data_08_2025.xlsx"
)


def fetch_source(state: SignalState) -> dict:
    name = state["source_name"]
    url = state["source_url"]
    try:
        strategy = _STRATEGIES.get(name, _fetch_plain_httpx)
        text = strategy(url)
        block = _detect_bot_block(text)
        if block:
            return {"raw_text": None, "fetch_error": f"bot-blocked: {block}"}
        return {"raw_text": text[:MAX_TEXT_CHARS], "fetch_error": None}
    except Exception as e:
        return {"raw_text": None, "fetch_error": f"{type(e).__name__}: {e}"}


def _detect_bot_block(text: str) -> str | None:
    """Detect well-known WAF challenge/block pages so they don't reach the LLM."""
    if not text:
        return None
    head = text[:1000].lower()
    markers = [
        ("incapsula incident id", "Incapsula"),
        ("access denied", "Akamai/Cloudflare"),
        ("attention required! | cloudflare", "Cloudflare"),
        ("just a moment...", "Cloudflare challenge"),
    ]
    for needle, label in markers:
        if needle in head:
            return label
    return None


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def _fetch_plain_httpx(url: str) -> str:
    response = httpx.get(url, follow_redirects=True, timeout=15)
    response.raise_for_status()
    return _html_to_text(response.text)


def _fetch_with_browser_ua_retry(url: str) -> str:
    """Browser UA + simple retry. Used for sources that 403 on default httpx."""
    headers = {
        "User-Agent": BROWSER_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    last_exc = None
    for attempt in range(3):
        try:
            response = httpx.get(
                url,
                follow_redirects=True,
                timeout=20,
                headers=headers,
            )
            response.raise_for_status()
            return _html_to_text(response.text)
        except Exception as e:
            last_exc = e
            print(f"[fetch_source] attempt {attempt + 1} failed for {url}: {e}")
            time.sleep(1.5 * (attempt + 1))
    raise last_exc


def _fetch_with_playwright(url: str) -> str:
    """Render with headless Chromium for JS-heavy pages (UNFCCC)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser, context = _launch_stealth_context(p)
        try:
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            # Many UNFCCC pages keep long-polling, so networkidle never fires.
            # Give JS a few seconds to clear Incapsula's challenge + hydrate.
            page.wait_for_timeout(6000)
            html = page.content()
        finally:
            browser.close()
    return _html_to_text(html)


_STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = {runtime: {}};
const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
if (originalQuery) {
  window.navigator.permissions.query = (p) =>
    p.name === 'notifications'
      ? Promise.resolve({state: Notification.permission})
      : originalQuery(p);
}
"""


def _launch_stealth_context(playwright):
    """Headless browser with the usual anti-detection patches applied.

    Prefer real Chrome (channel='chrome') if installed — bundled Chromium ships
    with automation flags that Incapsula/Akamai fingerprint. Fall back to
    Chromium if Chrome isn't on the machine.
    """
    launch_args = dict(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--no-sandbox",
        ],
    )
    try:
        browser = playwright.chromium.launch(channel="chrome", **launch_args)
    except Exception as e:
        print(f"[fetch_source] real-Chrome unavailable ({e}); falling back to Chromium")
        browser = playwright.chromium.launch(**launch_args)
    context = browser.new_context(
        user_agent=BROWSER_UA,
        viewport={"width": 1366, "height": 900},
        locale="en-US",
        timezone_id="America/New_York",
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Chromium";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
        },
    )
    context.add_init_script(_STEALTH_INIT_SCRIPT)
    return browser, context


def _fetch_worldbank_xlsx(_url: str) -> str:
    """Ignore the dashboard URL; pull the Excel workbook and list its sheets.

    Akamai 403s plain httpx (TLS fingerprint check), so we download via a real
    Chromium context — same TLS stack as a normal browser. We prime cookies
    against the dashboard first, then fetch the xlsx through page.request.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser, context = _launch_stealth_context(p)
        try:
            page = context.new_page()
            page.goto(
                "https://carbonpricingdashboard.worldbank.org/",
                wait_until="domcontentloaded",
                timeout=60_000,
            )
            page.wait_for_timeout(2000)
            api = context.request
            response = api.get(
                WORLDBANK_XLSX_URL,
                headers={"Referer": "https://carbonpricingdashboard.worldbank.org/"},
                timeout=60_000,
            )
            if not response.ok:
                raise RuntimeError(
                    f"WorldBank xlsx download failed: HTTP {response.status}"
                )
            body = response.body()
        finally:
            browser.close()

    try:
        sheets = wb.sheetnames
    finally:
        wb.close()
    lines = [
        f"World Bank Carbon Pricing Dashboard workbook: {WORLDBANK_XLSX_URL}",
        f"Sheet count: {len(sheets)}",
        "Sheets:",
        *[f"- {name}" for name in sheets],
    ]
    return "\n".join(lines)


_STRATEGIES = {
    "CERC": _fetch_with_browser_ua_retry,
    "UNFCCC_Art64_Rules": _fetch_with_playwright,
    "UNFCCC_CARP_Auth": _fetch_with_playwright,
    "WorldBank_Carbon": _fetch_worldbank_xlsx,
}
