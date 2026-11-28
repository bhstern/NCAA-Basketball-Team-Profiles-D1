"""
Torvik HTTP helper.

barttorvik.com fronts its pages with a "Verifying your browser" form that a browser
auto-submits. Since late Nov 2026 the form is a small proof-of-work challenge: hidden
fields bt_n (nonce), bt_t, bt_s, plus bt_a, which the page's JavaScript fills with the
first integer n such that the top 14 bits of SHA-256("<bt_n>:<n>") are zero (~16k hashes).
We do the same: read the hidden fields, solve for bt_a, POST them all once, and reuse the
session cookie. The older one-field form (js_test_submitted=1 only) still works too.

Requests are spaced out to stay polite — a refresh run makes only a handful of requests.
The page itself refuses more than 2 verifications per 30 seconds, so retries wait longer.
"""

import hashlib
import re
import time

import requests

BASE = "https://barttorvik.com/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
VERIFY_MARKER = "Verifying your browser"
REQUEST_GAP_SECONDS = 1.5
RETRY_WAIT_SECONDS = 20          # x attempt; keeps us under the page's 2-per-30s limit

HIDDEN_INPUT = re.compile(r'<input[^>]*type="hidden"[^>]*>', re.I)
ATTR = re.compile(r'(\w+)="([^"]*)"')
POW_PREFIX = re.compile(r'var\s+prefix\s*=\s*"([^"]*)"')
POW_MASK = re.compile(r'&\s*(0x[0-9a-fA-F]+)\)\s*===\s*0')
DEFAULT_MASK = 0xFFFC0000
MAX_POW_TRIES = 50_000_000


class TorvikFetchError(RuntimeError):
    pass


def challenge_form(html):
    """The verification form's hidden fields, as a dict (bt_a solved if a challenge is present)."""
    fields = {}
    for tag in HIDDEN_INPUT.findall(html):
        attrs = dict(ATTR.findall(tag))
        if "name" in attrs:
            fields[attrs["name"]] = attrs.get("value", "")
    if "bt_a" in fields:
        m = POW_PREFIX.search(html)
        prefix = m.group(1) if m else f"{fields.get('bt_n', '')}:"
        mm = POW_MASK.search(html)
        mask = int(mm.group(1), 16) if mm else DEFAULT_MASK
        fields["bt_a"] = str(solve_pow(prefix, mask))
    fields.setdefault("js_test_submitted", "1")
    return fields


def solve_pow(prefix, mask=DEFAULT_MASK):
    """First n with (first 32 bits of SHA-256(prefix + n)) & mask == 0 — same as the page's JS."""
    for n in range(MAX_POW_TRIES):
        h0 = int.from_bytes(hashlib.sha256(f"{prefix}{n}".encode()).digest()[:4], "big")
        if h0 & mask == 0:
            return n
    raise TorvikFetchError(f"proof-of-work not solved within {MAX_POW_TRIES} tries")


class TorvikSession:

    def __init__(self, retries=3, timeout=60):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.retries = retries
        self.timeout = timeout
        self._last_request = 0.0

    def _pace(self):
        wait = REQUEST_GAP_SECONDS - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def _request(self, method, url, **kwargs):
        self._pace()
        r = self.session.request(method, url, timeout=self.timeout, **kwargs)
        r.raise_for_status()
        return r

    def get(self, path):
        """GET a Torvik page/file, passing the browser check if presented."""
        url = path if path.startswith("http") else BASE + path
        last_err = None
        for attempt in range(1, self.retries + 1):
            try:
                r = self._request("GET", url)
                if VERIFY_MARKER in r.text:
                    r = self._request("POST", url, data=challenge_form(r.text))
                if VERIFY_MARKER in r.text:
                    raise TorvikFetchError(f"Still on browser-check page after POST: {url}")
                return r
            except (requests.RequestException, TorvikFetchError) as e:
                last_err = e
                if attempt < self.retries:
                    time.sleep(RETRY_WAIT_SECONDS * attempt)
        raise TorvikFetchError(f"Failed after {self.retries} attempts: {url} ({last_err})")

    def get_json(self, path):
        r = self.get(path)
        try:
            return r.json()
        except ValueError as e:
            raise TorvikFetchError(f"Expected JSON from {path}, got: {r.text[:200]!r}") from e
