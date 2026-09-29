"""
Resilient HTTP client for service-to-service calls.

Wraps ``requests.request`` with a circuit breaker and exponential-backoff
retry logic so that transient downstream failures do not cascade across
the ecosystem.

Usage
-----
Standalone function::

    from lozzalingo.core.resilience import resilient_request

    resp = resilient_request('GET', 'http://localhost:7216/api/contacts')

Base class for service clients::

    from lozzalingo.core.resilience import ServiceClient

    class CRMClient(ServiceClient):
        def __init__(self, base_url, api_key):
            super().__init__('crm', base_url, api_key)

        def list_contacts(self):
            return self.get('/api/contacts')
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

# Re-use the infrastructure circuit breaker that already lives in the repo.
# When installed as a framework package the caller can inject their own, but
# the default import path matches the infrastructure layout.
try:
    from infrastructure.circuit_breaker import CircuitBreaker, CircuitOpenError
except ImportError:
    # Fallback: if infrastructure is not on sys.path, pull from a vendored
    # copy or re-implement a minimal version.
    try:
        from lozzalingo.core._vendor_circuit_breaker import CircuitBreaker, CircuitOpenError
    except ImportError:
        # Inline minimal implementation so the module always works.
        import functools
        import threading
        from enum import Enum

        class _State(Enum):
            CLOSED = "closed"
            OPEN = "open"
            HALF_OPEN = "half-open"

        class CircuitOpenError(Exception):
            pass

        class CircuitBreaker:
            def __init__(self, name="default", failure_threshold=5, recovery_timeout=30.0):
                self.name = name
                self.failure_threshold = failure_threshold
                self.recovery_timeout = recovery_timeout
                self._state = _State.CLOSED
                self._failure_count = 0
                self._last_failure: float | None = None
                self._lock = threading.Lock()

            @property
            def state(self):
                with self._lock:
                    if (
                        self._state == _State.OPEN
                        and self._last_failure is not None
                        and (time.monotonic() - self._last_failure) >= self.recovery_timeout
                    ):
                        self._state = _State.HALF_OPEN
                    return self._state

            def call(self, fn, *args, **kwargs):
                current = self.state
                if current == _State.OPEN:
                    raise CircuitOpenError(f"Circuit '{self.name}' is open.")
                try:
                    result = fn(*args, **kwargs)
                except Exception:
                    with self._lock:
                        self._failure_count += 1
                        self._last_failure = time.monotonic()
                        if self._failure_count >= self.failure_threshold:
                            self._state = _State.OPEN
                    raise
                else:
                    with self._lock:
                        self._state = _State.CLOSED
                        self._failure_count = 0
                        self._last_failure = None
                    return result

            def reset(self):
                with self._lock:
                    self._state = _State.CLOSED
                    self._failure_count = 0
                    self._last_failure = None


logger = logging.getLogger("lozzalingo.resilience")

# ---------------------------------------------------------------------------
# Module-level circuit breaker registry (one breaker per logical service name)
# ---------------------------------------------------------------------------
_breakers: dict[str, CircuitBreaker] = {}


def _get_breaker(name: str) -> CircuitBreaker:
    """Return (or create) a circuit breaker for *name*."""
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(
            name=name,
            failure_threshold=5,
            recovery_timeout=30.0,
        )
    return _breakers[name]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Status codes that trigger a retry (service temporarily unavailable).
_RETRYABLE_STATUS_CODES = {503}

# Backoff schedule in seconds for each retry attempt.
_BACKOFF_SCHEDULE = [1, 2, 4]

# Default request timeout in seconds.
DEFAULT_TIMEOUT = 10


def resilient_request(
    method: str,
    url: str,
    *,
    breaker_name: str = "default",
    retries: int = 3,
    timeout: int | float = DEFAULT_TIMEOUT,
    **kwargs: Any,
) -> requests.Response | None:
    """Send an HTTP request with circuit-breaker protection and retry logic.

    Parameters
    ----------
    method:
        HTTP method (GET, POST, PUT, DELETE, etc.).
    url:
        Fully-qualified URL to call.
    breaker_name:
        Logical name for the circuit breaker. Calls to the same downstream
        service should share a breaker name so that failures are tracked
        together.
    retries:
        Maximum number of attempts (including the first). Defaults to 3.
    timeout:
        Per-request timeout in seconds. Defaults to 10.
    **kwargs:
        Passed through to ``requests.request`` (headers, json, data, etc.).

    Returns
    -------
    requests.Response or None
        The response object on success, or ``None`` when the circuit is open
        (graceful degradation).
    """
    breaker = _get_breaker(breaker_name)

    # If the circuit is already open, degrade gracefully.
    if breaker.state.value == "open":
        logger.warning("[Resilience] Circuit '%s' is open - returning None.", breaker_name)
        return None

    kwargs.setdefault("timeout", timeout)

    last_exc: Exception | None = None

    for attempt in range(retries):
        try:
            response = breaker.call(requests.request, method, url, **kwargs)

            # Treat 503 as a retryable failure.
            if response.status_code in _RETRYABLE_STATUS_CODES:
                logger.warning(
                    "[Resilience] %s %s returned %d (attempt %d/%d).",
                    method.upper(),
                    url,
                    response.status_code,
                    attempt + 1,
                    retries,
                )
                if attempt < retries - 1:
                    time.sleep(_BACKOFF_SCHEDULE[min(attempt, len(_BACKOFF_SCHEDULE) - 1)])
                    continue
                return response

            return response

        except CircuitOpenError:
            logger.warning("[Resilience] Circuit '%s' opened - returning None.", breaker_name)
            return None

        except (requests.Timeout, requests.ConnectionError) as exc:
            last_exc = exc
            logger.warning(
                "[Resilience] %s %s failed (%s, attempt %d/%d).",
                method.upper(),
                url,
                type(exc).__name__,
                attempt + 1,
                retries,
            )
            if attempt < retries - 1:
                time.sleep(_BACKOFF_SCHEDULE[min(attempt, len(_BACKOFF_SCHEDULE) - 1)])
            continue

        except Exception as exc:
            logger.error("[Resilience] %s %s unexpected error: %s", method.upper(), url, exc)
            return None

    logger.error(
        "[Resilience] %s %s exhausted all %d retries. Last error: %s",
        method.upper(),
        url,
        retries,
        last_exc,
    )
    return None


# ---------------------------------------------------------------------------
# ServiceClient base class
# ---------------------------------------------------------------------------


class ServiceClient:
    """Base class for typed service clients.

    Subclass this to build thin wrappers around downstream services::

        class BlogClient(ServiceClient):
            def __init__(self, base_url, api_key):
                super().__init__('blog', base_url, api_key)

            def list_articles(self, site_id):
                resp = self.get(f'/api/articles?site_id={site_id}')
                if resp and resp.ok:
                    return resp.json()
                return []
    """

    def __init__(self, service_name: str, base_url: str, api_key: str = "") -> None:
        self.service_name = service_name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    # -- convenience methods -----------------------------------------------

    def _headers(self, extra: dict | None = None) -> dict:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if extra:
            headers.update(extra)
        return headers

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def get(self, path: str, **kwargs: Any) -> requests.Response | None:
        return resilient_request(
            "GET",
            self._url(path),
            breaker_name=self.service_name,
            headers=self._headers(kwargs.pop("headers", None)),
            **kwargs,
        )

    def post(self, path: str, **kwargs: Any) -> requests.Response | None:
        return resilient_request(
            "POST",
            self._url(path),
            breaker_name=self.service_name,
            headers=self._headers(kwargs.pop("headers", None)),
            **kwargs,
        )

    def put(self, path: str, **kwargs: Any) -> requests.Response | None:
        return resilient_request(
            "PUT",
            self._url(path),
            breaker_name=self.service_name,
            headers=self._headers(kwargs.pop("headers", None)),
            **kwargs,
        )

    def delete(self, path: str, **kwargs: Any) -> requests.Response | None:
        return resilient_request(
            "DELETE",
            self._url(path),
            breaker_name=self.service_name,
            headers=self._headers(kwargs.pop("headers", None)),
            **kwargs,
        )
