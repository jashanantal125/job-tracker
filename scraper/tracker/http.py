"""Tiny stdlib HTTP client with retries and a global run deadline.

Stdlib only, so the GitHub Actions job needs no `pip install` and stays
under one billed minute.
"""

from __future__ import annotations

import gzip
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"
)
DEFAULT_TIMEOUT = 15.0

_deadline: float | None = None


class HttpError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class DeadlineExceeded(HttpError):
    pass


def set_deadline(seconds_from_now: float | None) -> None:
    global _deadline
    _deadline = None if seconds_from_now is None else time.monotonic() + seconds_from_now


def remaining() -> float | None:
    return None if _deadline is None else _deadline - time.monotonic()


def _decode(body: bytes, encoding: str | None) -> bytes:
    if encoding == "gzip":
        return gzip.decompress(body)
    if encoding == "deflate":
        return zlib.decompress(body)
    return body


def request(
    url: str,
    *,
    method: str = "GET",
    params: dict | None = None,
    json_body: object | None = None,
    headers: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = 2,
) -> bytes:
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    data = None
    hdrs = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    }
    if json_body is not None:
        data = json.dumps(json_body).encode()
        hdrs["Content-Type"] = "application/json"
    hdrs.update(headers or {})

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        left = remaining()
        if left is not None and left <= 1:
            raise DeadlineExceeded("run deadline reached")
        t = timeout if left is None else min(timeout, left)
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=t) as resp:
                return _decode(resp.read(), resp.headers.get("Content-Encoding"))
        except urllib.error.HTTPError as e:
            last_error = HttpError(f"HTTP {e.code} for {url}", e.code)
            # 4xx (except 429) won't get better by retrying.
            if e.code < 500 and e.code != 429:
                raise last_error from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last_error = HttpError(f"{type(e).__name__}: {e} for {url}")
        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def get_json(url: str, **kw) -> object:
    return json.loads(request(url, **kw))


def post_json(url: str, body: object, **kw) -> object:
    return json.loads(request(url, method="POST", json_body=body, **kw))


def get_text(url: str, **kw) -> str:
    return request(url, **kw).decode("utf-8", errors="replace")
