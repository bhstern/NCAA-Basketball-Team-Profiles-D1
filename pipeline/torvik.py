"""
Torvik HTTP helper.

barttorvik.com fronts its pages with a one-field "Verifying your browser" form that a
browser auto-submits (POST js_test_submitted=1 -> sets a js_verified cookie). We do the
same single POST, then reuse the session. Requests are spaced out to stay polite —
a refresh run makes only a handful of requests.
"""

import time

import requests

BASE = "https://barttorvik.com/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
VERIFY_MARKER = "Verifying your browser"
REQUEST_GAP_SECONDS = 1.5


class TorvikFetchError(RuntimeError):
    pass


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
                    r = self._request("POST", url, data={"js_test_submitted": "1"})
                if VERIFY_MARKER in r.text:
                    raise TorvikFetchError(f"Still on browser-check page after POST: {url}")
                return r
            except (requests.RequestException, TorvikFetchError) as e:
                last_err = e
                if attempt < self.retries:
                    time.sleep(5 * attempt)
        raise TorvikFetchError(f"Failed after {self.retries} attempts: {url} ({last_err})")

    def get_json(self, path):
        r = self.get(path)
        try:
            return r.json()
        except ValueError as e:
            raise TorvikFetchError(f"Expected JSON from {path}, got: {r.text[:200]!r}") from e
