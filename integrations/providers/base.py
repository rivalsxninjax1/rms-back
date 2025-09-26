from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, rpm: int = 60):
        self.rpm = max(1, rpm)
        self._interval = 60.0 / self.rpm
        self._last = 0.0

    def wait(self):
        now = time.monotonic()
        delta = now - self._last
        if delta < self._interval:
            time.sleep(self._interval - delta)
        self._last = time.monotonic()


def backoff(retries: int = 5, base: float = 0.5, factor: float = 2.0, retriable: Optional[Callable[[int], bool]] = None):
    retriable = retriable or (lambda code: code >= 500 or code in (429,))

    def wrapper(fn):
        def inner(*args, **kwargs):
            delay = base
            for attempt in range(retries):
                try:
                    return fn(*args, **kwargs)
                except requests.HTTPError as e:
                    resp = e.response
                    code = resp.status_code if resp is not None else 0
                    if attempt < retries - 1 and retriable(code):
                        logger.warning("Retrying %s due to HTTP %s in %ss", fn.__name__, code, round(delay, 2))
                        time.sleep(delay)
                        delay *= factor
                        continue
                    raise
                except requests.RequestException:
                    if attempt < retries - 1:
                        logger.warning("Retrying %s due to network error in %ss", fn.__name__, round(delay, 2))
                        time.sleep(delay)
                        delay *= factor
                        continue
                    raise
        return inner
    return wrapper


@dataclass
class APIResponse:
    ok: bool
    status: int
    data: Any
    error: Optional[str] = None


class BaseClient:
    def __init__(self, base_url: str, headers: Optional[Dict[str, str]] = None, rpm: int = 60):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(headers or {})
        self.limiter = RateLimiter(rpm=rpm)

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _request(self, method: str, path: str, **kwargs) -> APIResponse:
        self.limiter.wait()
        url = self._url(path)
        try:
            resp = self.session.request(method, url, timeout=20, **kwargs)
            if resp.status_code >= 400:
                try:
                    err = resp.json()
                except Exception:
                    err = resp.text
                resp.raise_for_status()
            try:
                data = resp.json()
            except Exception:
                data = resp.text
            return APIResponse(True, resp.status_code, data)
        except requests.HTTPError as e:
            r = e.response
            payload = None
            try:
                payload = r.json()
            except Exception:
                payload = r.text if r is not None else None
            logger.exception("HTTP error calling %s %s: %s", method, url, payload)
            return APIResponse(False, r.status_code if r else 0, None, error=str(payload))
        except requests.RequestException as e:
            logger.exception("Network error calling %s %s: %s", method, url, e)
            return APIResponse(False, 0, None, error=str(e))

