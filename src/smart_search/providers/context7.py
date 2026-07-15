import json
import re
import time
from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_random_exponential

from .base import BaseSearchProvider
from ..config import config
from ..logger import log_info


RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
MCP_PROTOCOL_VERSION = "2024-11-05"
_REDIRECT_PATTERN = re.compile(r"redirect(?:ed)?\s+(?:to|target(?:\s+is)?)\s+`?(/[^\s`]+)", re.IGNORECASE)
_LIBRARY_FIELD_PATTERN = re.compile(r"^- (?P<field>Title|Context7-compatible library ID|Description|Code Snippets|Trust Score|Benchmark Score):\s*(?P<value>.*)$", re.MULTILINE)


class _Context7Error(Exception):
    def __init__(self, error_type: str, message: str, redirected_library_id: str = ""):
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.redirected_library_id = redirected_library_id


class _Context7ProtocolError(_Context7Error):
    def __init__(self, message: str):
        super().__init__("protocol_error", message)


class _Context7ToolError(_Context7Error):
    def __init__(self, message: str = "Context7 tool returned an error."):
        super().__init__("provider_error", message)


class _Context7LibraryRedirect(_Context7Error):
    def __init__(self, target: str):
        super().__init__("library_redirected", "Context7 library ID was redirected.", target)


def _is_retryable_exception(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS_CODES
    return False


def _normalize_library(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id") or item.get("libraryId") or "",
        "title": item.get("title") or item.get("name") or "",
        "description": item.get("description") or "",
        "trust_score": item.get("trustScore"),
        "benchmark_score": item.get("benchmarkScore"),
        "total_snippets": item.get("totalSnippets"),
        "stars": item.get("stars"),
        "provider": "context7",
    }


def _parse_sse(text: str) -> list[Any]:
    messages: list[Any] = []
    data_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
            continue
        if not line.strip() and data_lines:
            payload = "\n".join(data_lines)
            try:
                messages.append(json.loads(payload))
            except json.JSONDecodeError as error:
                raise _Context7ProtocolError("Context7 returned invalid SSE JSON.") from error
            data_lines = []
    if data_lines:
        payload = "\n".join(data_lines)
        try:
            messages.append(json.loads(payload))
        except json.JSONDecodeError as error:
            raise _Context7ProtocolError("Context7 returned invalid SSE JSON.") from error
    if not messages:
        raise _Context7ProtocolError("Context7 returned an empty SSE response.")
    return messages


def _response_messages(response: httpx.Response) -> list[Any]:
    content_type = response.headers.get("content-type", "").lower()
    if "text/event-stream" in content_type:
        return _parse_sse(response.text)
    try:
        payload = response.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise _Context7ProtocolError("Context7 returned invalid JSON-RPC JSON.") from error
    return payload if isinstance(payload, list) else [payload]


def _response_result(response: httpx.Response, request_id: int) -> dict[str, Any]:
    for message in _response_messages(response):
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            raise _Context7ProtocolError("Context7 returned an invalid JSON-RPC message.")
        if message.get("id") != request_id:
            continue
        if "error" in message:
            raise _Context7ProtocolError("Context7 returned a JSON-RPC error.")
        result = message.get("result")
        if not isinstance(result, dict):
            raise _Context7ProtocolError("Context7 returned a JSON-RPC response without a result.")
        return result
    raise _Context7ProtocolError("Context7 response did not match the JSON-RPC request.")


def _content_data(result: dict[str, Any]) -> tuple[dict[str, Any], str]:
    data = result.get("structuredContent")
    if not isinstance(data, dict):
        data = {}
    text_parts: list[str] = []
    for item in result.get("content") or []:
        if not isinstance(item, dict) or item.get("type") != "text":
            continue
        text = item.get("text")
        if not isinstance(text, str):
            continue
        text_parts.append(text)
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            data = {**parsed, **data}
    return data, "\n".join(text_parts).strip()


def _redirect_target(data: Any, text: str = "") -> str:
    if isinstance(data, dict):
        for key in ("redirectedLibraryId", "redirected_library_id", "redirectTarget", "redirect_target"):
            value = data.get(key)
            if isinstance(value, str) and value.startswith("/"):
                return value
        for value in data.values():
            target = _redirect_target(value)
            if target:
                return target
    elif isinstance(data, list):
        for value in data:
            target = _redirect_target(value)
            if target:
                return target
    match = _REDIRECT_PATTERN.search(text)
    return match.group(1) if match else ""


def _library_results(data: dict[str, Any], text: str) -> list[dict[str, Any]]:
    for key in ("results", "libraries", "items"):
        raw_results = data.get(key)
        if isinstance(raw_results, list):
            return [item for item in raw_results if isinstance(item, dict)]
    results: list[dict[str, Any]] = []
    for block in re.split(r"\n-{4,}\n", text):
        fields = {match.group("field"): match.group("value").strip() for match in _LIBRARY_FIELD_PATTERN.finditer(block)}
        library_id = fields.get("Context7-compatible library ID", "")
        if not library_id.startswith("/"):
            continue
        result: dict[str, Any] = {
            "id": library_id,
            "title": fields.get("Title", ""),
            "description": fields.get("Description", ""),
        }
        for label, key in (("Code Snippets", "totalSnippets"), ("Trust Score", "trustScore"), ("Benchmark Score", "benchmarkScore")):
            value = fields.get(label, "")
            if value:
                try:
                    result[key] = float(value) if "." in value else int(value.replace(",", ""))
                except ValueError:
                    result[key] = value
        results.append(result)
    return results


class Context7Provider(BaseSearchProvider):
    """Narrow Remote MCP client for the two Context7 documentation tools."""

    def __init__(self, api_url: str, api_key: str, timeout: float = 30.0):
        super().__init__(api_url.rstrip("/"), api_key)
        self.timeout = timeout
        self._next_request_id = 0

    def get_provider_name(self) -> str:
        return "Context7"

    async def search(self, query: str, max_results: int = 5) -> str:
        return await self.library(query)

    def _headers(self, session_id: str = "") -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "X-Context7-Source": "smart-search",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if session_id:
            headers["Mcp-Session-Id"] = session_id
        return headers

    def _request(self, method: str, params: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        self._next_request_id += 1
        request_id = self._next_request_id
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        return request_id, payload

    async def _post_with_retry(self, client: httpx.AsyncClient, payload: dict[str, Any], session_id: str = "") -> httpx.Response:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(config.retry_max_attempts + 1),
            wait=wait_random_exponential(multiplier=config.retry_multiplier, max=config.retry_max_wait),
            retry=retry_if_exception(_is_retryable_exception),
            reraise=True,
        ):
            with attempt:
                response = await client.post(self.api_url, headers=self._headers(session_id), json=payload)
                if response.status_code in {401, 403}:
                    raise _Context7Error("auth_error", f"Context7 authentication failed (HTTP {response.status_code}).")
                if response.status_code >= 400:
                    if response.status_code not in RETRYABLE_STATUS_CODES:
                        raise _Context7ProtocolError(f"Context7 Remote MCP rejected the request (HTTP {response.status_code}).")
                    response.raise_for_status()
                return response
        raise _Context7ProtocolError("Context7 request did not return a response.")

    async def _start_session(self, client: httpx.AsyncClient) -> str:
        request_id, payload = self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "smart-search", "version": "1.0"},
            },
        )
        response = await self._post_with_retry(client, payload)
        _response_result(response, request_id)
        session_id = response.headers.get("mcp-session-id", "").strip()
        if not session_id:
            raise _Context7ProtocolError("Context7 initialize response did not include an MCP session.")
        initialized = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        notification = await self._post_with_retry(client, initialized, session_id)
        if notification.status_code not in {200, 202, 204}:
            raise _Context7ProtocolError("Context7 rejected the initialized notification.")
        return session_id

    async def _call_tool(self, client: httpx.AsyncClient, session_id: str, tool: str, arguments: dict[str, Any]) -> tuple[dict[str, Any], str]:
        request_id, payload = self._request("tools/call", {"name": tool, "arguments": arguments})
        response = await self._post_with_retry(client, payload, session_id)
        result = _response_result(response, request_id)
        if result.get("isError"):
            raise _Context7ToolError()
        data, text = _content_data(result)
        target = _redirect_target(data, text)
        if target:
            raise _Context7LibraryRedirect(target)
        return data, text

    @staticmethod
    def _error_output(error: Exception, base: dict[str, Any]) -> str:
        if isinstance(error, _Context7Error):
            base.update({"error_type": error.error_type, "error": error.message})
            if error.redirected_library_id:
                base["redirected_library_id"] = error.redirected_library_id
        elif isinstance(error, httpx.TimeoutException):
            base.update({"error_type": "timeout", "error": "Context7 request timed out."})
        elif isinstance(error, httpx.HTTPStatusError):
            base.update({"error_type": "network_error", "error": f"Context7 request failed (HTTP {error.response.status_code})."})
        elif isinstance(error, (httpx.NetworkError, httpx.ConnectError)):
            base.update({"error_type": "network_error", "error": "Context7 network request failed."})
        else:
            base.update({"error_type": "protocol_error", "error": "Context7 MCP request failed."})
        return json.dumps(base, ensure_ascii=False, indent=2)

    async def library(self, name: str, query: str = "", ctx=None) -> str:
        request_query = f"{name} {query}".strip()
        await log_info(ctx, f"Context7 library: {request_query}", config.debug_enabled)
        start_time = time.time()
        base = {"ok": False, "query": request_query, "provider": "context7"}
        try:
            timeout = httpx.Timeout(connect=6.0, read=self.timeout, write=10.0, pool=None)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                session_id = await self._start_session(client)
                data, text = await self._call_tool(
                    client,
                    session_id,
                    "resolve-library-id",
                    {"libraryName": name, "query": query},
                )
            results = [_normalize_library(item) for item in _library_results(data, text)]
            base.update({"ok": True, "results": results, "total": len(results), "elapsed_ms": round((time.time() - start_time) * 1000, 2)})
            return json.dumps(base, ensure_ascii=False, indent=2)
        except Exception as error:
            base["elapsed_ms"] = round((time.time() - start_time) * 1000, 2)
            return self._error_output(error, base)

    async def docs(self, library_id: str, query: str, ctx=None) -> str:
        await log_info(ctx, f"Context7 docs: {library_id} {query}", config.debug_enabled)
        start_time = time.time()
        base = {"ok": False, "library_id": library_id, "query": query, "provider": "context7"}
        try:
            timeout = httpx.Timeout(connect=6.0, read=self.timeout, write=10.0, pool=None)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                session_id = await self._start_session(client)
                data, text = await self._call_tool(
                    client,
                    session_id,
                    "query-docs",
                    {"libraryId": library_id, "query": query},
                )
            snippets = data.get("codeSnippets") or data.get("code_snippets") or []
            info = data.get("infoSnippets") or data.get("info_snippets") or []
            content = data.get("content") if isinstance(data.get("content"), str) else text
            if not content:
                content = json.dumps(data, ensure_ascii=False)
            base.update(
                {
                    "ok": True,
                    "code_snippets": snippets,
                    "info_snippets": info,
                    "results": list(snippets) + list(info),
                    "total": len(snippets) + len(info),
                    "content": content,
                    "elapsed_ms": round((time.time() - start_time) * 1000, 2),
                }
            )
            return json.dumps(base, ensure_ascii=False, indent=2)
        except Exception as error:
            base["elapsed_ms"] = round((time.time() - start_time) * 1000, 2)
            return self._error_output(error, base)
