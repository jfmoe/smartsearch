import httpx
import pytest

from smart_search.providers.anysearch import AnySearchProvider


class FakeAnySearchClient:
    calls = []
    response: httpx.Response | None = None
    exception: Exception | None = None

    def __init__(self, timeout, follow_redirects=True):
        self.timeout = timeout
        self.follow_redirects = follow_redirects

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url, headers, json):
        self.__class__.calls.append({"url": url, "headers": headers, "json": json, "timeout": self.timeout})
        if self.__class__.exception:
            raise self.__class__.exception
        return self.__class__.response


@pytest.fixture(autouse=True)
def reset_fake_client():
    FakeAnySearchClient.calls = []
    FakeAnySearchClient.response = None
    FakeAnySearchClient.exception = None


@pytest.mark.asyncio
async def test_anysearch_jsonrpc_success_parses_markdown_and_auth_header(monkeypatch):
    FakeAnySearchClient.response = httpx.Response(
        200,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": "### 1. React hooks\n- **URL**: https://react.dev/reference/react\nReact Hooks API reference.",
                    }
                ]
            },
        },
        request=httpx.Request("POST", "https://api.anysearch.com/mcp"),
    )
    monkeypatch.setattr("smart_search.providers.anysearch.httpx.AsyncClient", FakeAnySearchClient)

    provider = AnySearchProvider("https://api.anysearch.com/mcp", "as-test-secret", timeout=12)
    data = await provider.vertical_search(
        "React hooks",
        domain="code",
        sub_domain="doc",
        max_results=2,
        sub_domain_params={"language": "python", "tags": ["hooks"]},
    )

    assert data["ok"] is True
    assert data["provider"] == "anysearch"
    assert data["capability"] == "vertical_search"
    assert data["operation"] == "vertical_search"
    assert data["tool"] == "search"
    assert data["domain"] == "code"
    assert data["sub_domain"] == "doc"
    assert data["raw_content"].startswith("### 1. React hooks")
    assert data["results"][0]["url"] == "https://react.dev/reference/react"
    assert data["results"][0]["title"] == "React hooks"
    call = FakeAnySearchClient.calls[0]
    assert call["headers"]["Authorization"] == "Bearer as-test-secret"
    assert call["json"]["method"] == "tools/call"
    assert call["json"]["params"]["name"] == "search"
    assert call["json"]["params"]["arguments"]["max_results"] == 2
    assert call["json"]["params"]["arguments"]["domain"] == "code"
    assert call["json"]["params"]["arguments"]["sub_domain"] == "doc"
    assert call["json"]["params"]["arguments"]["sub_domain_params"] == {
        "language": "python",
        "tags": ["hooks"],
    }
    assert data["sub_domain_param_keys"] == ["language", "tags"]
    assert "language" not in data.get("content", "")
    assert call["timeout"].read == 12.0


@pytest.mark.asyncio
async def test_anysearch_anonymous_request_omits_authorization(monkeypatch):
    FakeAnySearchClient.response = httpx.Response(
        200,
        json={"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "No domains"}]}},
        request=httpx.Request("POST", "https://api.anysearch.com/mcp"),
    )
    monkeypatch.setattr("smart_search.providers.anysearch.httpx.AsyncClient", FakeAnySearchClient)

    provider = AnySearchProvider("https://api.anysearch.com/mcp", None)
    data = await provider.discover_domains("security")

    assert data["ok"] is True
    assert data["operation"] == "discover_domains"
    assert data["tool"] == "get_sub_domains"
    assert "Authorization" not in FakeAnySearchClient.calls[0]["headers"]


@pytest.mark.asyncio
async def test_anysearch_result_is_error_is_provider_error_without_sources(monkeypatch):
    FakeAnySearchClient.response = httpx.Response(
        200,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "isError": True,
                "content": [{"type": "text", "text": "invalid domain https://example.com/should-not-be-source"}],
            },
        },
        request=httpx.Request("POST", "https://api.anysearch.com/mcp"),
    )
    monkeypatch.setattr("smart_search.providers.anysearch.httpx.AsyncClient", FakeAnySearchClient)

    provider = AnySearchProvider("https://api.anysearch.com/mcp", "as-test-secret")
    data = await provider.vertical_search("query", domain="bad", sub_domain="domain")

    assert data["ok"] is False
    assert data["error_type"] == "provider_error"
    assert data["error"].startswith("invalid ")
    assert data["results"] == []
    assert data["raw_content"] == data["error"]


@pytest.mark.asyncio
async def test_anysearch_jsonrpc_error_is_provider_error(monkeypatch):
    FakeAnySearchClient.response = httpx.Response(
        200,
        json={"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "invalid params"}},
        request=httpx.Request("POST", "https://api.anysearch.com/mcp"),
    )
    monkeypatch.setattr("smart_search.providers.anysearch.httpx.AsyncClient", FakeAnySearchClient)

    provider = AnySearchProvider("https://api.anysearch.com/mcp", "as-test-secret")
    data = await provider.extract("https://example.com")

    assert data["ok"] is False
    assert data["error_type"] == "parameter_error"
    assert data["error"] == "invalid params"


@pytest.mark.asyncio
async def test_anysearch_http_forbidden_maps_to_auth_error(monkeypatch):
    FakeAnySearchClient.response = httpx.Response(
        403,
        text="forbidden",
        request=httpx.Request("POST", "https://api.anysearch.com/mcp"),
    )
    monkeypatch.setattr("smart_search.providers.anysearch.httpx.AsyncClient", FakeAnySearchClient)

    provider = AnySearchProvider("https://api.anysearch.com/mcp", "as-test-secret")
    data = await provider.extract("https://example.com")

    assert data["ok"] is False
    assert data["error_type"] == "auth_error"
    assert "HTTP 403" in data["error"]


@pytest.mark.asyncio
async def test_anysearch_timeout_maps_to_timeout(monkeypatch):
    FakeAnySearchClient.exception = httpx.ReadTimeout("too slow", request=httpx.Request("POST", "https://api.anysearch.com/mcp"))
    monkeypatch.setattr("smart_search.providers.anysearch.httpx.AsyncClient", FakeAnySearchClient)

    provider = AnySearchProvider("https://api.anysearch.com/mcp", "as-test-secret")
    data = await provider.extract("https://example.com")

    assert data["ok"] is False
    assert data["error_type"] == "timeout"


@pytest.mark.asyncio
async def test_anysearch_structured_result_without_url_is_preserved(monkeypatch):
    FakeAnySearchClient.response = httpx.Response(
        200,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"content": [{"type": "text", "text": "CVE-2024-3094 severity: critical\nAffected: xz utils"}]},
        },
        request=httpx.Request("POST", "https://api.anysearch.com/mcp"),
    )
    monkeypatch.setattr("smart_search.providers.anysearch.httpx.AsyncClient", FakeAnySearchClient)

    provider = AnySearchProvider("https://api.anysearch.com/mcp", "as-test-secret")
    data = await provider.vertical_search("CVE-2024-3094", domain="security", sub_domain="vuln")

    assert data["ok"] is True
    assert data["total"] == 1
    assert data["results"][0]["evidence_type"] == "structured"
    assert data["results"][0]["url"] == ""
    assert "CVE-2024-3094" in data["results"][0]["raw_content"]


@pytest.mark.asyncio
async def test_anysearch_batch_limit_returns_parameter_error_without_request(monkeypatch):
    monkeypatch.setattr("smart_search.providers.anysearch.httpx.AsyncClient", FakeAnySearchClient)

    provider = AnySearchProvider("https://api.anysearch.com/mcp", "as-test-secret")
    data = await provider.batch_search(["a", "b", "c", "d", "e", "f"])

    assert data["ok"] is False
    assert data["error_type"] == "parameter_error"
    assert "max 5" in data["error"]
    assert FakeAnySearchClient.calls == []


@pytest.mark.asyncio
async def test_anysearch_batch_sends_live_compatible_query_objects(monkeypatch):
    FakeAnySearchClient.response = httpx.Response(
        200,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": "## Query 1: React hooks\n\n### 1. Built-in React Hooks\n- **URL**: https://react.dev/reference/react/hooks",
                    }
                ]
            },
        },
        request=httpx.Request("POST", "https://api.anysearch.com/mcp"),
    )
    monkeypatch.setattr("smart_search.providers.anysearch.httpx.AsyncClient", FakeAnySearchClient)

    provider = AnySearchProvider("https://api.anysearch.com/mcp", "as-test-secret")
    data = await provider.batch_search(["React hooks", "CVE-2024-3094"], max_results=1)

    assert data["ok"] is True
    assert data["operation"] == "batch_discovery"
    assert data["capability"] is None
    call = FakeAnySearchClient.calls[0]
    assert call["json"]["params"]["name"] == "batch_search"
    assert call["json"]["params"]["arguments"]["queries"] == [
        {"query": "React hooks", "max_results": 1},
        {"query": "CVE-2024-3094", "max_results": 1},
    ]
    assert set(call["json"]["params"]["arguments"]) == {"queries"}


@pytest.mark.asyncio
async def test_anysearch_discovery_normalizes_schema_and_preserves_raw_result(monkeypatch):
    structured = {
        "sub_domains": [
            {
                "sub_domain": "vuln",
                "description": "Vulnerability search",
                "parameters": {
                    "type": "object",
                    "required": ["product"],
                    "properties": {"product": {"type": "string"}},
                },
            }
        ]
    }
    FakeAnySearchClient.response = httpx.Response(
        200,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "structuredContent": structured,
                "content": [{"type": "text", "text": "security domains"}],
            },
        },
        request=httpx.Request("POST", "https://api.anysearch.com/mcp"),
    )
    monkeypatch.setattr("smart_search.providers.anysearch.httpx.AsyncClient", FakeAnySearchClient)

    data = await AnySearchProvider("https://api.anysearch.com/mcp").discover_domains("security")

    assert data["raw_result"]["structuredContent"] == structured
    assert data["results"] == [
        {
            "domain": "security",
            "sub_domain": "vuln",
            "description": "Vulnerability search",
            "parameter_schema": structured["sub_domains"][0]["parameters"],
        }
    ]
    assert FakeAnySearchClient.calls[0]["json"]["params"]["name"] == "get_sub_domains"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("domain", "sub_domain", "params", "message"),
    [
        ("security.vuln", "", {}, "--domain security --sub-domain vuln"),
        ("security", "cve", {}, "--domain security --sub-domain vuln"),
        ("security", "", {}, "both --domain and --sub-domain"),
        ("", "vuln", {}, "both --domain and --sub-domain"),
        ("security", "vuln", "[]", "JSON object"),
        ("security", "vuln", "{bad", "valid JSON object"),
        ("security", "vuln", {"query": "leak-me"}, "reserved fields"),
    ],
)
async def test_anysearch_explicit_search_rejects_migration_and_parameter_errors_before_network(
    monkeypatch, domain, sub_domain, params, message
):
    monkeypatch.setattr("smart_search.providers.anysearch.httpx.AsyncClient", FakeAnySearchClient)
    provider = AnySearchProvider("https://api.anysearch.com/mcp")

    data = await provider.vertical_search(
        "query",
        domain=domain,
        sub_domain=sub_domain,
        sub_domain_params=params,
    )

    assert data["ok"] is False
    assert data["operation"] == "vertical_search"
    assert data["error_type"] == "parameter_error"
    assert message in data["error"]
    assert "leak-me" not in str(data)
    assert FakeAnySearchClient.calls == []


@pytest.mark.asyncio
async def test_anysearch_automatic_vertical_discovery_transport_is_domainless(monkeypatch):
    FakeAnySearchClient.response = httpx.Response(
        200,
        json={"jsonrpc": "2.0", "id": 1, "result": {"content": []}},
        request=httpx.Request("POST", "https://api.anysearch.com/mcp"),
    )
    monkeypatch.setattr("smart_search.providers.anysearch.httpx.AsyncClient", FakeAnySearchClient)

    data = await AnySearchProvider("https://api.anysearch.com/mcp", "as-test-secret").vertical_search("travel ideas")

    assert data["operation"] == "vertical_discovery"
    assert data["schema_validation"]["status"] == "not_applicable"
    assert FakeAnySearchClient.calls[0]["headers"]["Authorization"] == "Bearer as-test-secret"
    assert FakeAnySearchClient.calls[0]["json"]["params"]["name"] == "search"
    assert FakeAnySearchClient.calls[0]["json"]["params"]["arguments"] == {
        "query": "travel ideas",
        "max_results": 5,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "exception", "error_type"),
    [
        (httpx.Response(429, text="slow down"), None, "rate_limited"),
        (None, httpx.ConnectError("offline"), "network_error"),
        (httpx.Response(200, text="not-json"), None, "parse_error"),
        (None, RuntimeError("unexpected"), "runtime_error"),
    ],
)
async def test_anysearch_transport_failures_have_stable_error_types(monkeypatch, response, exception, error_type):
    if response is not None:
        response.request = httpx.Request("POST", "https://api.anysearch.com/mcp")
    if isinstance(exception, httpx.RequestError):
        exception._request = httpx.Request("POST", "https://api.anysearch.com/mcp")
    FakeAnySearchClient.response = response
    FakeAnySearchClient.exception = exception
    monkeypatch.setattr("smart_search.providers.anysearch.httpx.AsyncClient", FakeAnySearchClient)

    data = await AnySearchProvider("https://api.anysearch.com/mcp").extract("https://example.com")

    assert data["ok"] is False
    assert data["error_type"] == error_type
    assert set(
        [
            "provider",
            "capability",
            "operation",
            "tool",
            "experimental",
            "elapsed",
            "content",
            "raw_content",
            "results",
            "error",
            "error_type",
            "schema_validation",
        ]
    ).issubset(data)


@pytest.mark.asyncio
async def test_anysearch_live_discovery_schema_does_not_become_a_verified_contract(monkeypatch):
    monkeypatch.setattr("smart_search.providers.anysearch.httpx.AsyncClient", FakeAnySearchClient)
    FakeAnySearchClient.response = httpx.Response(
        200,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "structuredContent": {
                    "sub_domains": [
                        {
                            "sub_domain": "fundamental",
                            "parameters": {
                                "type": "object",
                                "required": ["ticker"],
                                "properties": {"ticker": {"type": "string"}},
                            },
                        }
                    ]
                },
                "content": [],
            },
        },
        request=httpx.Request("POST", "https://schema.example.com/mcp"),
    )
    provider = AnySearchProvider("https://schema.example.com/mcp")
    discovery = await provider.discover_domains("finance")
    assert discovery["results"][0]["parameter_schema"]["required"] == ["ticker"]

    FakeAnySearchClient.response = httpx.Response(
        200,
        json={"jsonrpc": "2.0", "id": 2, "result": {"content": []}},
        request=httpx.Request("POST", "https://schema.example.com/mcp"),
    )

    data = await provider.vertical_search(
        "fundamentals",
        domain="finance",
        sub_domain="fundamental",
        sub_domain_params={"ticker": 123, "period": "daily"},
    )

    assert data["ok"] is True
    assert data["schema_validation"]["status"] == "unavailable"
    assert FakeAnySearchClient.calls[1]["json"]["params"]["arguments"]["sub_domain_params"] == {
        "ticker": 123,
        "period": "daily",
    }


@pytest.mark.asyncio
async def test_anysearch_provider_error_redacts_request_values(monkeypatch):
    FakeAnySearchClient.response = httpx.Response(
        200,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "isError": True,
                "content": [
                    {
                        "type": "text",
                        "text": "query secret-query domain security sub vuln token secret-param",
                    }
                ],
            },
        },
        request=httpx.Request("POST", "https://api.anysearch.com/mcp"),
    )
    monkeypatch.setattr("smart_search.providers.anysearch.httpx.AsyncClient", FakeAnySearchClient)

    data = await AnySearchProvider("https://api.anysearch.com/mcp").vertical_search(
        "secret-query",
        domain="security",
        sub_domain="vuln",
        sub_domain_params={"token": "secret-param"},
    )

    dumped = str(data)
    assert data["error_type"] == "provider_error"
    assert "secret-query" not in dumped
    assert "secret-param" not in dumped
    assert data["raw_content"] == data["error"]
    assert "raw_result" not in data
