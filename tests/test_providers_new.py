import json

import httpx
import pytest

from smart_search.providers.context7 import Context7Provider
from smart_search.providers.exa import ExaSearchProvider
from smart_search.providers.zhipu import ZhipuWebSearchProvider


@pytest.mark.asyncio
async def test_zhipu_provider_normalizes_search_results(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, timeout, follow_redirects=True):
            self.timeout = timeout
            self.follow_redirects = follow_redirects

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, endpoint, headers, json):
            return httpx.Response(
                200,
                json={
                    "request_id": "r1",
                    "search_result": [
                        {
                            "title": "Title",
                            "content": "Snippet",
                            "link": "https://example.com",
                            "media": "Example",
                            "publish_date": "2026-05-12",
                        }
                    ],
                },
                request=httpx.Request("POST", endpoint),
            )

    monkeypatch.setattr("smart_search.providers.zhipu.httpx.AsyncClient", FakeAsyncClient)
    provider = ZhipuWebSearchProvider("https://open.bigmodel.cn/api", "key")

    data = json.loads(await provider.search("hello"))

    assert data["ok"] is True
    assert data["results"][0]["url"] == "https://example.com"
    assert data["results"][0]["provider"] == "zhipu"


@pytest.mark.asyncio
async def test_zhipu_provider_uses_configured_engine_and_call_override(monkeypatch):
    payloads = []

    class FakeAsyncClient:
        def __init__(self, timeout, follow_redirects=True):
            self.timeout = timeout
            self.follow_redirects = follow_redirects

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, endpoint, headers, json):
            payloads.append(json.copy())
            return httpx.Response(
                200,
                json={"request_id": "r1", "search_result": []},
                request=httpx.Request("POST", endpoint),
            )

    monkeypatch.setattr("smart_search.providers.zhipu.httpx.AsyncClient", FakeAsyncClient)
    provider = ZhipuWebSearchProvider("https://open.bigmodel.cn/api", "key", search_engine="search_pro")

    data = json.loads(await provider.search("hello"))
    override_data = json.loads(await provider.search("hello", search_engine="search_pro_quark"))

    assert data["search_engine"] == "search_pro"
    assert override_data["search_engine"] == "search_pro_quark"
    assert payloads[0]["search_engine"] == "search_pro"
    assert payloads[1]["search_engine"] == "search_pro_quark"


@pytest.mark.asyncio
async def test_zhipu_provider_reports_rate_limit_without_retry(monkeypatch):
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout, follow_redirects=True):
            self.timeout = timeout
            self.follow_redirects = follow_redirects

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, endpoint, headers, json):
            calls.append(endpoint)
            return httpx.Response(
                429,
                json={"error": "rate limited"},
                request=httpx.Request("POST", endpoint),
            )

    monkeypatch.setattr("smart_search.providers.zhipu.httpx.AsyncClient", FakeAsyncClient)
    provider = ZhipuWebSearchProvider("https://open.bigmodel.cn/api", "key")

    data = json.loads(await provider.search("test"))

    assert data["ok"] is False
    assert data["error_type"] == "rate_limited"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_context7_provider_resolves_library_through_remote_mcp_json_session(monkeypatch):
    requests = []

    class FakeAsyncClient:
        def __init__(self, timeout, follow_redirects=False):
            self.timeout = timeout
            self.follow_redirects = follow_redirects

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, endpoint, headers, json):
            requests.append({"endpoint": endpoint, "headers": headers, "json": json})
            method = json["method"]
            if method == "initialize":
                return httpx.Response(
                    200,
                    json={"jsonrpc": "2.0", "id": json["id"], "result": {"protocolVersion": "2024-11-05"}},
                    headers={"content-type": "application/json", "mcp-session-id": "session-1"},
                    request=httpx.Request("POST", endpoint),
                )
            if method == "notifications/initialized":
                return httpx.Response(202, request=httpx.Request("POST", endpoint))
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": json["id"],
                    "result": {
                        "structuredContent": {
                            "results": [
                                {"id": "/facebook/react", "title": "React", "description": "UI"},
                                {"id": "/preactjs/preact", "title": "Preact", "description": "UI"},
                            ]
                        }
                    },
                },
                headers={"content-type": "application/json"},
                request=httpx.Request("POST", endpoint),
            )

    monkeypatch.setattr("smart_search.providers.context7.httpx.AsyncClient", FakeAsyncClient)
    provider = Context7Provider("https://mcp.context7.com/mcp", "context7-test-key")

    data = json.loads(await provider.library("react", "hooks"))

    assert data["ok"] is True
    assert data["results"][0]["id"] == "/facebook/react"
    assert data["results"][0]["provider"] == "context7"
    assert [request["json"]["method"] for request in requests] == [
        "initialize",
        "notifications/initialized",
        "tools/call",
    ]
    assert requests[-1]["json"]["params"] == {
        "name": "resolve-library-id",
        "arguments": {"libraryName": "react", "query": "hooks"},
    }
    assert requests[-1]["headers"]["Mcp-Session-Id"] == "session-1"
    assert requests[-1]["headers"]["Authorization"] == "Bearer context7-test-key"


@pytest.mark.asyncio
async def test_context7_provider_queries_docs_through_remote_mcp_sse(monkeypatch):
    methods = []

    class FakeAsyncClient:
        def __init__(self, timeout, follow_redirects=False):
            self.timeout = timeout
            self.follow_redirects = follow_redirects

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, endpoint, headers, json):
            methods.append(json["method"])
            if json["method"] == "initialize":
                return httpx.Response(
                    200,
                    content=(
                        'event: message\n'
                        f'data: {{"jsonrpc":"2.0","id":{json["id"]},"result":{{"protocolVersion":"2024-11-05"}}}}\n\n'
                    ),
                    headers={"content-type": "text/event-stream", "mcp-session-id": "session-2"},
                    request=httpx.Request("POST", endpoint),
                )
            if json["method"] == "notifications/initialized":
                return httpx.Response(202, request=httpx.Request("POST", endpoint))
            return httpx.Response(
                200,
                content=(
                    'event: message\n'
                    f'data: {{"jsonrpc":"2.0","id":{json["id"]},"result":{{"structuredContent":{{"codeSnippets":[{{"title":"Effect","code":"useEffect()"}}],"infoSnippets":[{{"title":"Cleanup","content":"Return cleanup"}}]}}}}}}\n\n'
                ),
                headers={"content-type": "text/event-stream"},
                request=httpx.Request("POST", endpoint),
            )

    monkeypatch.setattr("smart_search.providers.context7.httpx.AsyncClient", FakeAsyncClient)
    provider = Context7Provider("https://mcp.context7.com/mcp", "context7-test-key")

    data = json.loads(await provider.docs("/facebook/react", "useEffect cleanup"))

    assert data["ok"] is True
    assert data["code_snippets"] == [{"title": "Effect", "code": "useEffect()"}]
    assert data["info_snippets"] == [{"title": "Cleanup", "content": "Return cleanup"}]
    assert methods == ["initialize", "notifications/initialized", "tools/call"]


@pytest.mark.asyncio
async def test_context7_provider_preserves_first_library_from_documented_text_result(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, timeout, follow_redirects=False):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, endpoint, headers, json):
            if json["method"] == "initialize":
                return httpx.Response(
                    200,
                    json={"jsonrpc": "2.0", "id": json["id"], "result": {}},
                    headers={"content-type": "application/json", "mcp-session-id": "session-text"},
                    request=httpx.Request("POST", endpoint),
                )
            if json["method"] == "notifications/initialized":
                return httpx.Response(202, request=httpx.Request("POST", endpoint))
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": json["id"],
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Available Libraries (top matches):\n\n----------\n\n"
                                    "- Title: React\n"
                                    "- Context7-compatible library ID: /facebook/react\n"
                                    "- Description: A UI library\n"
                                    "- Code Snippets: 1234\n"
                                    "- Trust Score: 9.5\n"
                                ),
                            }
                        ]
                    },
                },
                headers={"content-type": "application/json"},
                request=httpx.Request("POST", endpoint),
            )

    monkeypatch.setattr("smart_search.providers.context7.httpx.AsyncClient", FakeAsyncClient)
    provider = Context7Provider("https://mcp.context7.com/mcp", "context7-test-key")

    data = json.loads(await provider.library("react", "hooks"))

    assert data["ok"] is True
    assert data["results"][0]["id"] == "/facebook/react"
    assert data["results"][0]["total_snippets"] == 1234
    assert data["results"][0]["trust_score"] == 9.5


@pytest.mark.asyncio
async def test_context7_provider_classifies_auth_without_retry_or_key_leak(monkeypatch):
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout, follow_redirects=False):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, endpoint, headers, json):
            calls.append(json)
            return httpx.Response(
                401,
                text="authorization rejected: context7-test-key",
                request=httpx.Request("POST", endpoint),
            )

    monkeypatch.setattr("smart_search.providers.context7.httpx.AsyncClient", FakeAsyncClient)
    provider = Context7Provider("https://mcp.context7.com/mcp", "context7-test-key")

    data = json.loads(await provider.library("react"))

    assert data["ok"] is False
    assert data["error_type"] == "auth_error"
    assert len(calls) == 1
    assert "context7-test-key" not in json.dumps(data)


@pytest.mark.asyncio
async def test_context7_provider_reports_redirect_without_following_it(monkeypatch):
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout, follow_redirects=False):
            assert follow_redirects is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, endpoint, headers, json):
            calls.append(json["method"])
            if json["method"] == "initialize":
                return httpx.Response(
                    200,
                    json={"jsonrpc": "2.0", "id": json["id"], "result": {}},
                    headers={"content-type": "application/json", "mcp-session-id": "session-3"},
                    request=httpx.Request("POST", endpoint),
                )
            if json["method"] == "notifications/initialized":
                return httpx.Response(202, request=httpx.Request("POST", endpoint))
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": json["id"],
                    "result": {"structuredContent": {"redirectedLibraryId": "/facebook/react"}},
                },
                headers={"content-type": "application/json"},
                request=httpx.Request("POST", endpoint),
            )

    monkeypatch.setattr("smart_search.providers.context7.httpx.AsyncClient", FakeAsyncClient)
    provider = Context7Provider("https://mcp.context7.com/mcp", "context7-test-key")

    data = json.loads(await provider.docs("/old/react", "hooks"))

    assert data["ok"] is False
    assert data["error_type"] == "library_redirected"
    assert data["redirected_library_id"] == "/facebook/react"
    assert calls == ["initialize", "notifications/initialized", "tools/call"]


@pytest.mark.asyncio
async def test_context7_provider_retries_retryable_http_but_not_protocol_or_tool_errors(monkeypatch):
    calls = []

    class RetryClient:
        def __init__(self, timeout, follow_redirects=False):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, endpoint, headers, json):
            calls.append(json["method"])
            if len(calls) == 1:
                return httpx.Response(429, request=httpx.Request("POST", endpoint))
            if json["method"] == "notifications/initialized":
                return httpx.Response(202, request=httpx.Request("POST", endpoint))
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": json["id"], "result": {}},
                headers={"content-type": "application/json", "mcp-session-id": "session-4"},
                request=httpx.Request("POST", endpoint),
            )

    monkeypatch.setenv("SMART_SEARCH_RETRY_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("SMART_SEARCH_RETRY_MULTIPLIER", "0")
    monkeypatch.setattr("smart_search.providers.context7.httpx.AsyncClient", RetryClient)
    retry_provider = Context7Provider("https://mcp.context7.com/mcp", "context7-test-key")

    retry_data = json.loads(await retry_provider.library("react"))

    assert retry_data["ok"] is True
    assert calls == ["initialize", "initialize", "notifications/initialized", "tools/call"]

    class ToolErrorClient:
        def __init__(self, timeout, follow_redirects=False):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, endpoint, headers, json):
            if json["method"] == "initialize":
                return httpx.Response(
                    200,
                    json={"jsonrpc": "2.0", "id": json["id"], "result": {}},
                    headers={"content-type": "application/json", "mcp-session-id": "session-5"},
                    request=httpx.Request("POST", endpoint),
                )
            if json["method"] == "notifications/initialized":
                return httpx.Response(202, request=httpx.Request("POST", endpoint))
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": json["id"], "result": {"isError": True}},
                headers={"content-type": "application/json"},
                request=httpx.Request("POST", endpoint),
            )

    monkeypatch.setattr("smart_search.providers.context7.httpx.AsyncClient", ToolErrorClient)
    tool_provider = Context7Provider("https://mcp.context7.com/mcp", "context7-test-key")

    tool_data = json.loads(await tool_provider.library("react"))

    assert tool_data["ok"] is False
    assert tool_data["error_type"] == "provider_error"


@pytest.mark.asyncio
async def test_exa_provider_reports_bad_request_as_parameter_error(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, endpoint, headers, json):
            return httpx.Response(
                400,
                json={"error": "invalid includeDomains"},
                request=httpx.Request("POST", endpoint),
            )

    monkeypatch.setattr("smart_search.providers.exa.httpx.AsyncClient", FakeAsyncClient)
    provider = ExaSearchProvider("https://api.exa.ai", "key")

    data = json.loads(await provider.search("test", include_domains=["github.com freertos.org"]))

    assert data["ok"] is False
    assert data["error_type"] == "parameter_error"
    assert "HTTP 400" in data["error"]
    assert "invalid includeDomains" in data["error"]
