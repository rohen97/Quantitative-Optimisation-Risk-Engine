from __future__ import annotations

import json
import time
from dataclasses import dataclass
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


SENSITIVE_QUERY_KEYS = frozenset(
    {"api_key", "apikey", "api_token", "token", "access_key", "secret", "client_secret"}
)


def redact_url(url: str) -> str:
    """Mask credential-like query parameters before logging or raising errors."""
    parts = urlsplit(url)
    redacted_query = urlencode(
        [
            (key, "***REDACTED***" if key.lower() in SENSITIVE_QUERY_KEYS else value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
        ],
        doseq=True,
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, redacted_query, parts.fragment))


class DataSourceRequestError(RuntimeError):
    """Raised when an external data source cannot return a usable response."""


@dataclass(frozen=True)
class HttpResponse:
    body: bytes
    status: int
    headers: dict[str, str]
    url: str

    def json(self) -> object:
        return json.loads(self.body.decode("utf-8"))

    def text(self) -> str:
        return self.body.decode("utf-8-sig")


@dataclass(frozen=True)
class HttpClientConfig:
    timeout_seconds: int = 30
    retry_attempts: int = 3
    retry_backoff_seconds: float = 1.0
    user_agent: str = "wolf-quant-model/1.0"


class HttpClient:
    """Small dependency-light HTTP client with bounded retries."""

    def __init__(self, config: HttpClientConfig | None = None) -> None:
        self.config = config or HttpClientConfig()

    def get(
        self,
        url: str,
        params: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        return self._request("GET", url, params=params, headers=headers)

    def post_json(
        self,
        url: str,
        payload: object,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        request_headers = {"Content-Type": "application/json", **(headers or {})}
        return self._request(
            "POST",
            url,
            headers=request_headers,
            body=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        )

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> HttpResponse:
        query = urlencode(
            [(key, str(value)) for key, value in (params or {}).items() if value is not None],
            doseq=True,
        )
        request_url = f"{url}{'&' if '?' in url else '?'}{query}" if query else url
        request_headers = {"Accept": "application/json", "User-Agent": self.config.user_agent}
        request_headers.update(headers or {})
        last_error: Exception | None = None
        safe_url = redact_url(request_url)

        for attempt in range(max(self.config.retry_attempts, 1)):
            try:
                request = Request(
                    request_url,
                    data=body,
                    headers=request_headers,
                    method=method.upper(),
                )
                with urlopen(request, timeout=self.config.timeout_seconds) as response:
                    return HttpResponse(
                        body=response.read(),
                        status=int(response.status),
                        headers={str(key): str(value) for key, value in response.headers.items()},
                        url=request_url,
                    )
            except HTTPError as exc:
                error_body = exc.read().decode("utf-8", errors="replace")
                if exc.code < 500 and exc.code != 429:
                    raise DataSourceRequestError(
                        f"HTTP {exc.code} from {safe_url}: {error_body}"
                    ) from exc
                last_error = exc
            except (URLError, TimeoutError, OSError, HTTPException) as exc:
                last_error = exc

            if attempt + 1 < max(self.config.retry_attempts, 1):
                time.sleep(self.config.retry_backoff_seconds * (2**attempt))

        raise DataSourceRequestError(f"Request failed after retries: {safe_url}: {last_error}") from last_error
