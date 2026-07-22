import httpx
import pytest

from smart_search.providers.xai_responses import XAIResponsesSearchProvider


class DummyResponse:
    def __init__(self, json_data):
        self._json_data = json_data

    def json(self):
        return self._json_data


class DummyStreamResponse:
    def __init__(self, lines):
        self._lines = lines

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        for line in self._lines:
            yield line


def test_xai_responses_search_payload_uses_responses_shape():
    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", "test-model", ["web_search", "x_search"])

    payload = provider._build_search_payload("What is new?", "X")

    assert payload["model"] == "test-model"
    assert payload["instructions"]
    assert payload["stream"] is True
    assert payload["tools"] == [{"type": "web_search"}, {"type": "x_search"}]
    assert payload["input"][0]["role"] == "user"
    assert "What is new?" in payload["input"][0]["content"]
    assert "X" in payload["input"][0]["content"]


@pytest.mark.asyncio
async def test_xai_responses_parse_output_text_and_url_citations():
    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", "test-model", ["web_search"])
    response = DummyResponse(
        {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "Answer [[1]](https://example.com/a).",
                            "annotations": [
                                {
                                    "type": "url_citation",
                                    "url": "https://example.com/a",
                                    "title": "1",
                                    "start_index": 7,
                                    "end_index": 10,
                                },
                                {
                                    "type": "url_citation",
                                    "url": "https://example.com/a",
                                    "title": "duplicate",
                                },
                            ],
                        }
                    ],
                }
            ]
        }
    )

    result = await provider._parse_response(response)

    assert "Answer [[1]](https://example.com/a)." in result
    assert "sources(" in result
    assert result.count("https://example.com/a") == 2


@pytest.mark.asyncio
async def test_xai_responses_parse_stream_uses_completed_response():
    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", "test-model", ["web_search"])
    response = DummyStreamResponse(
        [
            "event: response.output_text.delta",
            'data: {"type":"response.output_text.delta","delta":"partial"}',
            "event: response.completed",
            'data: {"type":"response.completed","response":{"output":[{"content":[{"type":"output_text","text":"final answer","annotations":[{"type":"url_citation","url":"https://example.com/source","title":"Source"}]}]}]}}',
        ]
    )

    result = await provider._parse_streaming_response(response)

    assert "final answer" in result
    assert "partial" not in result
    assert '"url": "https://example.com/source"' in result


@pytest.mark.asyncio
async def test_xai_responses_parse_stream_rejects_incomplete_response():
    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", "test-model", [])
    response = DummyStreamResponse(
        [
            "event: response.output_text.delta",
            'data: {"type":"response.output_text.delta","delta":"partial"}',
        ]
    )

    with pytest.raises(httpx.RemoteProtocolError, match="before response.completed"):
        await provider._parse_streaming_response(response)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stream_body", "error_match"),
    [
        ('data: {"type":"response.failed","error":{"message":"upstream failed"}}\n\n', "upstream failed"),
        ('data: {"type":"response.incomplete","response":{}}\n\n', "response.incomplete"),
    ],
)
async def test_xai_responses_search_retries_terminal_failure_events(monkeypatch, stream_body, error_match):
    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", "test-model", [])
    requests = []
    original_async_client = httpx.AsyncClient

    def handler(request):
        requests.append(request)
        return httpx.Response(200, content=stream_body, headers={"Content-Type": "text/event-stream"})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        "smart_search.providers.xai_responses.httpx.AsyncClient",
        lambda **kwargs: original_async_client(transport=transport, **kwargs),
    )
    monkeypatch.setenv("SMART_SEARCH_RETRY_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("SMART_SEARCH_RETRY_MULTIPLIER", "0")
    monkeypatch.setenv("SMART_SEARCH_RETRY_MAX_WAIT", "0")

    with pytest.raises(httpx.RemoteProtocolError, match=error_match):
        await provider.search("query")

    assert len(requests) == 2


@pytest.mark.asyncio
async def test_xai_responses_execute_posts_to_responses(monkeypatch):
    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", "test-model", [])
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout, follow_redirects, verify):
            self.timeout = timeout
            self.follow_redirects = follow_redirects
            self.verify = verify

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def stream(self, method, url, headers, json):
            calls.append((method, url, headers, json))

            class StreamContext:
                async def __aenter__(self):
                    return DummyStreamResponse(
                        [
                            "event: response.completed",
                            'data: {"type":"response.completed","response":{"output":[{"content":[{"type":"output_text","text":"ok","annotations":[]}]}]}}',
                        ]
                    )

                async def __aexit__(self, exc_type, exc, tb):
                    return None

            return StreamContext()

    monkeypatch.setattr("smart_search.providers.xai_responses.httpx.AsyncClient", FakeAsyncClient)

    result = await provider.search("query")

    assert result == "ok"
    assert calls[0][0] == "POST"
    assert calls[0][1] == "https://api.x.ai/v1/responses"
    assert calls[0][2]["Accept"] == "text/event-stream"
    assert calls[0][3]["stream"] is True
    assert calls[0][3]["tools"] == []
