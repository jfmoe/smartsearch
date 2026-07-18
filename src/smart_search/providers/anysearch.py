import json
import re
import time
from typing import Any

import httpx

from .base import BaseSearchProvider


_RESERVED_SUB_DOMAIN_FIELDS = {"query", "domain", "sub_domain", "max_results"}
_LEGACY_SUB_DOMAIN_ALIASES = {("security", "cve"): ("security", "vuln")}


def _elapsed(start: float) -> float:
    return round((time.monotonic() - start) * 1000, 2)


def _safe_error(message: Any, secrets: list[Any]) -> str:
    text = str(message or "")
    for secret in secrets:
        if isinstance(secret, str) and secret:
            text = text.replace(secret, "[redacted]")
        elif isinstance(secret, (int, float)):
            text = text.replace(str(secret), "[redacted]")
    text = re.sub(r"(?i)bearer\s+[^\s,;]+", "Bearer [redacted]", text)
    text = re.sub(r"(?i)(api[_-]?key|authorization)(\s*[:=]\s*)[^\s,;]+", r"\1\2[redacted]", text)
    return text[:300]


def _argument_secrets(arguments: dict[str, Any], api_key: str) -> list[Any]:
    secrets: list[Any] = [api_key]

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for nested in value.values():
                collect(nested)
        elif isinstance(value, list):
            for nested in value:
                collect(nested)
        elif isinstance(value, (str, int, float)) and value != "":
            secrets.append(value)

    collect(arguments)
    return secrets


def _extract_text(result: dict[str, Any]) -> str:
    content = result.get("content") or []
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts).strip()
    if isinstance(content, str):
        return content.strip()
    return ""


def _parse_markdown_results(text: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in text.splitlines():
        heading = re.match(r"^###\s+\d+\.\s+(.+?)\s*$", line)
        if heading:
            if current:
                results.append(current)
            current = {"title": heading.group(1).strip(), "url": "", "description": ""}
            continue
        if current is None:
            continue
        url_match = re.match(r"^-\s+\*\*URL\*\*:\s+(\S+)", line)
        if url_match:
            current["url"] = url_match.group(1).strip()
            continue
        if line.strip() and not line.startswith("#") and not line.startswith("- **URL**"):
            current["description"] = (current["description"] + " " + line.strip()).strip()
    if current:
        results.append(current)
    if results:
        return results
    urls = re.findall(r"https?://[^\s)>\]]+", text)
    return [{"title": url, "url": url, "description": ""} for url in dict.fromkeys(urls)]


def _structured_discovery_payload(result: dict[str, Any], text: str) -> Any:
    structured = result.get("structuredContent")
    if structured is not None:
        return structured
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def _discovery_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("sub_domains", "subDomains", "domains", "results", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _discovery_items(value)
            if nested:
                return nested
    return []


def _normalize_discovery(domain: str, result: dict[str, Any], text: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in _discovery_items(_structured_discovery_payload(result, text)):
        sub_domain = item.get("sub_domain") or item.get("subDomain") or item.get("name") or item.get("id")
        if not isinstance(sub_domain, str) or not sub_domain:
            continue
        schema = (
            item.get("parameter_schema")
            or item.get("parameterSchema")
            or item.get("parameters")
            or item.get("inputSchema")
            or {}
        )
        if not isinstance(schema, dict):
            schema = {}
        entry = {
            "domain": domain,
            "sub_domain": sub_domain,
            "description": item.get("description") if isinstance(item.get("description"), str) else "",
            "parameter_schema": schema,
        }
        normalized.append(entry)
    return normalized


def _base_output(operation: str, tool: str, capability: str | None, elapsed: float = 0) -> dict[str, Any]:
    return {
        "ok": False,
        "provider": "anysearch",
        "capability": capability,
        "operation": operation,
        "tool": tool,
        "experimental": True,
        "elapsed": elapsed,
        "elapsed_ms": elapsed,
        "content": "",
        "raw_content": "",
        "results": [],
        "error": "",
        "error_type": "",
        "schema_validation": {"status": "not_applicable", "errors": []},
    }


def _parameter_error(operation: str, tool: str, capability: str | None, message: str) -> dict[str, Any]:
    output = _base_output(operation, tool, capability)
    output.update(error_type="parameter_error", error=message)
    return output


class AnySearchProvider(BaseSearchProvider):
    def __init__(self, api_url: str, api_key: str | None = None, timeout: float = 30.0):
        super().__init__(api_url.rstrip("/"), api_key or "")
        self.timeout = timeout

    def get_provider_name(self) -> str:
        return "AnySearch"

    async def search(self, query: str, max_results: int = 5) -> dict[str, Any]:
        return await self.vertical_search(query, max_results=max_results)

    async def discover_domains(self, domain: str) -> dict[str, Any]:
        if not domain:
            return _parameter_error(
                "discover_domains",
                "get_sub_domains",
                None,
                "discover_domains requires a parent DOMAIN before contacting AnySearch",
            )
        if "." in domain:
            return _parameter_error(
                "discover_domains",
                "get_sub_domains",
                None,
                "DOMAIN must be a parent domain; pass `anysearch-domains security`, not a dotted sub-domain",
            )
        output = await self.call_tool("discover_domains", "get_sub_domains", {"domain": domain}, None)
        output["domain"] = domain
        if output["ok"]:
            output["results"] = _normalize_discovery(domain, output.get("raw_result") or {}, output["raw_content"])
        return output

    async def vertical_search(
        self,
        query: str,
        domain: str = "",
        sub_domain: str = "",
        max_results: int = 5,
        sub_domain_params: dict[str, Any] | str | None = None,
    ) -> dict[str, Any]:
        explicit = bool(domain or sub_domain)
        operation = "vertical_search" if explicit else "vertical_discovery"
        if "." in domain or "." in sub_domain:
            parent, _, child = domain.partition(".")
            migration = f"--domain {parent} --sub-domain {child}" if child else "separate --domain and --sub-domain values"
            return _parameter_error(
                operation,
                "search",
                "vertical_search",
                f"dotted domain shorthand and legacy aliases are unsupported; migrate to `{migration}`",
            )
        if bool(domain) != bool(sub_domain):
            return _parameter_error(
                operation,
                "search",
                "vertical_search",
                "explicit vertical search requires both --domain and --sub-domain; omit both for Vertical Discovery",
            )
        replacement = _LEGACY_SUB_DOMAIN_ALIASES.get((domain, sub_domain))
        if replacement:
            return _parameter_error(
                operation,
                "search",
                "vertical_search",
                "legacy sub-domain aliases are unsupported; migrate to "
                f"`--domain {replacement[0]} --sub-domain {replacement[1]}`",
            )
        if isinstance(sub_domain_params, str):
            try:
                sub_domain_params = json.loads(sub_domain_params)
            except json.JSONDecodeError:
                return _parameter_error(
                    operation,
                    "search",
                    "vertical_search",
                    "--sub-domain-params must be a valid JSON object",
                )
        if sub_domain_params is None:
            sub_domain_params = {}
        if not isinstance(sub_domain_params, dict):
            return _parameter_error(
                operation,
                "search",
                "vertical_search",
                "--sub-domain-params must be a single JSON object",
            )
        reserved = sorted(_RESERVED_SUB_DOMAIN_FIELDS.intersection(sub_domain_params))
        if reserved:
            return _parameter_error(
                operation,
                "search",
                "vertical_search",
                "--sub-domain-params cannot override reserved fields: " + ", ".join(reserved),
            )
        if sub_domain_params and not explicit:
            return _parameter_error(
                operation,
                "search",
                "vertical_search",
                "--sub-domain-params requires both --domain and --sub-domain",
            )

        arguments: dict[str, Any] = {"query": query, "max_results": max_results}
        schema_validation = {"status": "not_applicable", "errors": []}
        if explicit:
            arguments.update(domain=domain, sub_domain=sub_domain, sub_domain_params=sub_domain_params)
            schema_validation = {
                "status": "unavailable",
                "errors": [],
                "message": "No Verified Domain Contract is available; parameters were passed to AnySearch unchanged.",
            }

        output = await self.call_tool(operation, "search", arguments, "vertical_search")
        output["schema_validation"] = schema_validation
        output["max_results"] = max_results
        if explicit:
            output.update(domain=domain, sub_domain=sub_domain)
            output["sub_domain_param_keys"] = sorted(sub_domain_params)
        return output

    async def extract(self, url: str, max_length: int = 20000) -> dict[str, Any]:
        return await self.call_tool(
            "anysearch_extraction",
            "extract",
            {"url": url, "max_length": max_length},
            None,
        )

    async def batch_search(self, queries: list[str], max_results: int = 3) -> dict[str, Any]:
        if len(queries) > 5:
            return _parameter_error(
                "batch_discovery",
                "batch_search",
                None,
                f"Batch Discovery accepts max 5 queries (received {len(queries)})",
            )
        return await self.call_tool(
            "batch_discovery",
            "batch_search",
            {"queries": [{"query": query, "max_results": max_results} for query in queries]},
            None,
        )

    async def call_tool(
        self,
        operation: str,
        tool: str,
        arguments: dict[str, Any],
        capability: str | None,
    ) -> dict[str, Any]:
        start = time.monotonic()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        secrets = _argument_secrets(arguments, self.api_key)

        try:
            timeout = httpx.Timeout(connect=6.0, read=self.timeout, write=10.0, pool=None)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.post(self.api_url, headers=headers, json=payload)
                response.raise_for_status()
                try:
                    data = response.json()
                except (json.JSONDecodeError, ValueError) as exc:
                    output = _base_output(operation, tool, capability, _elapsed(start))
                    output.update(error_type="parse_error", error=_safe_error(exc, secrets) or "Invalid JSON response")
                    return output
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code in {401, 403}:
                error_type = "auth_error"
            elif status_code == 429:
                error_type = "rate_limited"
            else:
                error_type = "network_error"
            body = exc.response.text or exc.response.reason_phrase or ""
            output = _base_output(operation, tool, capability, _elapsed(start))
            output.update(error_type=error_type, error=_safe_error(f"HTTP {status_code}: {body}", secrets))
            return output
        except httpx.TimeoutException:
            output = _base_output(operation, tool, capability, _elapsed(start))
            output.update(error_type="timeout", error="request timed out")
            return output
        except httpx.RequestError as exc:
            output = _base_output(operation, tool, capability, _elapsed(start))
            output.update(error_type="network_error", error=_safe_error(exc, secrets))
            return output
        except Exception as exc:
            output = _base_output(operation, tool, capability, _elapsed(start))
            output.update(error_type="runtime_error", error=_safe_error(exc, secrets))
            return output
        return self._normalize_response(operation, tool, arguments, capability, data, start)

    def _normalize_response(
        self,
        operation: str,
        tool: str,
        arguments: dict[str, Any],
        capability: str | None,
        data: Any,
        start: float,
    ) -> dict[str, Any]:
        output = _base_output(operation, tool, capability, _elapsed(start))
        secrets = _argument_secrets(arguments, self.api_key)
        if not isinstance(data, dict):
            output.update(error_type="parse_error", error="AnySearch JSON-RPC response must be an object")
            return output
        if "error" in data:
            error = data.get("error") or {}
            code = error.get("code") if isinstance(error, dict) else None
            message = error.get("message") if isinstance(error, dict) else error
            output.update(
                error_type="parameter_error" if code == -32602 else "provider_error",
                error=_safe_error(message or "AnySearch JSON-RPC error", secrets),
            )
            return output

        result = data.get("result")
        if not isinstance(result, dict):
            output.update(error_type="parse_error", error="AnySearch JSON-RPC result must be an object")
            return output
        text = _extract_text(result)
        output.update(content=text, raw_content=text, raw_result=result)
        if result.get("isError"):
            safe_message = _safe_error(text or "AnySearch tool returned isError=true", secrets)
            output.pop("raw_result", None)
            output.update(
                content=safe_message,
                raw_content=safe_message,
                error_type="provider_error",
                error=safe_message,
            )
            return output

        parsed_results = _parse_markdown_results(text)
        if text and not parsed_results and operation != "discover_domains":
            parsed_results = [
                {
                    "title": f"{operation} structured result",
                    "url": "",
                    "description": text[:500],
                    "evidence_type": "structured",
                    "raw_content": text,
                }
            ]
        output.update(ok=True, results=parsed_results, total=len(parsed_results))
        return output
