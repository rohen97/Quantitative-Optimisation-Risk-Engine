from io import BytesIO
from http.client import IncompleteRead
from urllib.error import HTTPError

from src.data_ingestion.http_client import HttpClient, HttpClientConfig


class _SuccessResponse:
    status = 200
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return b'{"ok":true}'


def test_post_retry_preserves_byte_payload(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.data, timeout))
        assert isinstance(request.data, bytes)
        if len(calls) == 1:
            raise HTTPError(
                request.full_url,
                503,
                "temporary",
                {},
                BytesIO(b'{"error":"temporary"}'),
            )
        return _SuccessResponse()

    monkeypatch.setattr("src.data_ingestion.http_client.urlopen", fake_urlopen)
    response = HttpClient(
        HttpClientConfig(retry_attempts=2, retry_backoff_seconds=0)
    ).post_json("https://example.test/graphql", {"query": "{ ok }"})
    assert response.json() == {"ok": True}
    assert len(calls) == 2
    assert calls[0][0] == calls[1][0]


def test_incomplete_response_body_is_retried(monkeypatch):
    calls = []

    class IncompleteResponse(_SuccessResponse):
        def read(self):
            raise IncompleteRead(b"partial")

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        return IncompleteResponse() if len(calls) == 1 else _SuccessResponse()

    monkeypatch.setattr("src.data_ingestion.http_client.urlopen", fake_urlopen)
    response = HttpClient(
        HttpClientConfig(retry_attempts=2, retry_backoff_seconds=0)
    ).get("https://example.test/data")
    assert response.json() == {"ok": True}
    assert len(calls) == 2
