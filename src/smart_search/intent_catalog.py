from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping


@dataclass(frozen=True)
class RuleTermGroup:
    name: str
    terms: tuple[str, ...]
    localized: bool = False


@dataclass(frozen=True)
class IntentCapability:
    id: str
    description: str
    select_when: str
    do_not_select_when: str
    rule_terms: tuple[RuleTermGroup, ...]
    semantic_examples: tuple[str, ...]
    calibration_examples: tuple[str, ...]


@dataclass(frozen=True)
class CalibrationCase:
    id: str
    query: str
    expected_capabilities: tuple[str, ...]


_DOCS_CALIBRATION = (
    "React useEffect official docs", "Next.js app router caching docs", "Python pathlib Path API reference",
    "TypeScript compiler options documentation", "LangChain retriever integration guide", "OpenAI Responses API parameters",
    "Prisma migration CLI docs", "Vue watchEffect API usage", "FastAPI dependency injection docs",
    "Docker compose healthcheck reference", "这个 SDK 怎么接入", "查一下 React hooks 官方文档",
    "Python requests 超时参数怎么配置", "Vite 配置 alias 的文档", "Context7 怎么查 LangChain 文档",
    "OpenAI embeddings API 文档", "Next.js middleware 配置项", "Rust tokio select 文档",
    "Pandas groupby 参数说明", "Tailwind CSS container query docs",
)
_WEB_CALIBRATION = (
    "今天国内 AI 新闻", "latest Nvidia earnings news", "current Bitcoin price movement", "今日人民币汇率变化",
    "NBA score today Lakers", "本周新能源车政策", "recent OpenAI product announcement",
    "latest Windows 11 update issue", "现在上海天气预警", "today stock market close summary",
    "刚刚苹果发布会消息", "最近美国大选民调", "current oil price news", "今日A股收盘行情",
    "latest CVE exploit in the wild", "本月中国芯片政策变化", "today SpaceX launch status",
    "latest Python release announcement", "近期比特币ETF新闻", "NBA今日赛程",
)
_FETCH_CALIBRATION = (
    "summarize https://example.com", "fetch this PDF https://example.com/report.pdf",
    "请读取这个网页 https://example.com/post", "核验这个链接里的说法 https://example.com/source",
    "extract the main text from https://example.org/article", "read this arxiv PDF https://arxiv.org/pdf/2401.00001.pdf",
    "抓取 https://example.com/docs 的正文", "summarize this url: http://example.net/page",
    "请打开链接看看写了什么 https://example.com", "compare the claim in https://example.com/claim",
    "pull metadata from https://example.com/product", "读取这篇博客 https://blog.example.com/a",
    "fetch known URL content https://news.example.com/item", "把这个PDF概括一下 https://example.com/file.pdf",
    "verify source page http://example.org/source", "get text from URL https://developer.example.com/changelog",
    "read webpage content at https://example.edu/paper", "请提取网页正文 https://docs.example.com/install",
    "summarize linked announcement https://company.example.com/news", "fetch this public page https://example.com/about",
)
_VERTICAL_CALIBRATION = (
    "CVE-2026 OpenSSL vulnerability impact", "Search GitHub codebase for auth middleware",
    "legal regulation database search GDPR", "financial filing structured search 10-K revenue",
    "academic paper search transformer retrieval", "漏洞影响范围 CVE-2025", "查找 GitHub 仓库里的配置文件",
    "法规条文数据库检索", "股票财报结构化查询", "医学论文数据库检索", "patent search battery materials",
    "code search repo function name", "SEC filing risk factors search", "法律案例检索 合同纠纷",
    "学术论文 引用 网络 搜索", "NVD vulnerability database query", "vertical domain search for finance filings",
    "repository search for Dockerfile examples", "法律法规 检索 个税", "数据库里查 CVE exploit score",
    "Elden Ring game walkthrough boss guide", "东京自由行路线和酒店攻略",
)
_NONE_CALIBRATION = (
    "帮我把这句话翻译成英文", "写一封请假邮件", "总结下面这段文字", "解释这个错误堆栈的含义",
    "帮我给变量起名", "把这段 JSON 格式化", "生成一个会议纪要模板", "用更礼貌的语气改写这句话",
    "给我一个早餐计划", "计算 37 乘以 19", "explain what recursion means in simple words",
    "write a short haiku about winter", "classify these TODO items by priority", "make this paragraph shorter",
    "帮我润色项目介绍", "不联网也能回答的常识问题", "给代码加一点注释",
    "Python 函数是什么意思，用自己的话解释", "React 是什么，用中文解释", "帮我检查语法和错别字",
)


_CATALOG = {
    "docs_search": IntentCapability(
        id="docs_search",
        description="Search external library, SDK, API, framework, and official technical documentation.",
        select_when="The request needs authoritative documentation, API reference, configuration, or integration details.",
        do_not_select_when="The request is general technical knowledge or merely mentions a technology without needing its documentation.",
        rule_terms=(
            RuleTermGroup("general", ("api", "sdk", "library", "framework", "docs", "documentation", "reference", "react", "next.js", "vue", "python", "prisma", "langchain", "openai", "context7")),
            RuleTermGroup("zh", ("接口", "文档", "库", "框架", "函数", "参数", "配置", "接入"), localized=True),
        ),
        semantic_examples=("React useEffect API docs", "how to integrate this SDK", "Python function parameters reference", "OpenAI API documentation", "这个 SDK 怎么接入", "查一下框架官方文档和配置参数"),
        calibration_examples=_DOCS_CALIBRATION,
    ),
    "web_search": IntentCapability(
        id="web_search",
        description="Discover supplemental web sources for current, news, regional, policy, market, or cross-validation needs.",
        select_when="The request needs recent or live information, locale-specific discovery, policy/news/market updates, or source reinforcement.",
        do_not_select_when="The request is timeless, already has a known URL to read, or only needs documentation search; this capability is not main_search.",
        rule_terms=(
            RuleTermGroup("general", ("nba", "today", "latest", "current", "realtime", "live", "recent")),
            RuleTermGroup("zh", ("今天", "今日", "最新", "国内", "中国", "政策", "新闻", "实时", "刚刚", "当前", "现在", "本周", "本月", "战报", "比分", "赛程", "赛果", "季后赛", "比赛", "足球", "篮球"), localized=True),
        ),
        semantic_examples=("today China AI news", "latest policy announcement", "current market update", "NBA score today", "今天国内 AI 新闻", "最近有什么最新变化"),
        calibration_examples=_WEB_CALIBRATION,
    ),
    "web_fetch": IntentCapability(
        id="web_fetch",
        description="Read, extract, or verify the body of a known HTTP(S) URL or PDF.",
        select_when="The request supplies a known URL/PDF or explicitly asks to read, extract, summarize, or verify linked content.",
        do_not_select_when="The request needs link discovery rather than content from a known URL; provider acceptance extraction is not this capability.",
        rule_terms=(RuleTermGroup("url_scheme", ("http://", "https://")),),
        semantic_examples=("verify the claim in this URL https://example.com", "summarize this webpage", "fetch this PDF", "请核验这个链接里的说法 https://example.com", "抓取这个网页正文"),
        calibration_examples=_FETCH_CALIBRATION,
    ),
    "vertical_search": IntentCapability(
        id="vertical_search",
        description="Discover results for explicit vertical-domain intent, including security, finance, legal, academic, code, gaming-guide, and travel-itinerary lookup.",
        select_when="The request clearly targets a structured or specialized vertical domain covered by local routing terms.",
        do_not_select_when="The request is ordinary broad web search, uses generic game/travel words, or asks for an unverified automatic domain search.",
        rule_terms=(
            RuleTermGroup("general", ("cve", "vulnerability", "vulnerabilities", "finance", "financial", "legal", "law", "academic", "paper", "repo", "repository", "github", "gitlab", "codebase", "code search", "code docs", "game guide", "game walkthrough", "gaming guide", "travel itinerary", "travel guide", "trip itinerary")),
            RuleTermGroup("zh", ("安全漏洞", "漏洞", "股票", "基金", "财报", "法律", "法规", "论文", "代码", "代码库", "开源仓库", "游戏攻略", "游戏资料", "游戏数据库", "旅行攻略", "旅游攻略", "自由行路线"), localized=True),
        ),
        semantic_examples=("CVE-2026 OpenSSL vulnerability impact", "financial filing structured search", "legal regulation database search", "GitHub codebase search", "漏洞影响范围", "垂直领域结构化检索", "Elden Ring game walkthrough", "Tokyo travel itinerary"),
        calibration_examples=_VERTICAL_CALIBRATION,
    ),
}

CAPABILITY_IDS = tuple(_CATALOG)
INTENT_ROUTING_CATALOG: Mapping[str, IntentCapability] = MappingProxyType(_CATALOG)


def ordered_capabilities(capabilities: Iterable[str]) -> list[str]:
    selected = set(capabilities)
    return [capability_id for capability_id in CAPABILITY_IDS if capability_id in selected]


def rule_terms(capability_id: str, *, localized_only: bool = False) -> frozenset[str]:
    capability = INTENT_ROUTING_CATALOG[capability_id]
    return frozenset(
        term
        for group in capability.rule_terms
        if not localized_only or group.localized
        for term in group.terms
    )


def semantic_examples(capability_id: str) -> tuple[str, ...]:
    return INTENT_ROUTING_CATALOG[capability_id].semantic_examples


def calibration_query_map() -> dict[str, tuple[str, ...]]:
    return {
        **{capability_id: capability.calibration_examples for capability_id, capability in INTENT_ROUTING_CATALOG.items()},
        "none": _NONE_CALIBRATION,
    }


def calibration_cases() -> tuple[CalibrationCase, ...]:
    cases = []
    for capability_id, queries in calibration_query_map().items():
        expected = () if capability_id == "none" else (capability_id,)
        cases.extend(
            CalibrationCase(f"{capability_id}-{index:02d}", query, expected)
            for index, query in enumerate(queries, 1)
        )
    return tuple(cases)


def classifier_prompt_material() -> dict[str, object]:
    return {
        "allowed_capabilities": list(CAPABILITY_IDS),
        "capability_definitions": [
            {
                "id": capability.id,
                "description": capability.description,
                "select_when": capability.select_when,
                "do_not_select_when": capability.do_not_select_when,
                "examples": list(capability.semantic_examples),
            }
            for capability in INTENT_ROUTING_CATALOG.values()
        ],
    }


def render_skill_capability_reference() -> str:
    lines = [
        "# Intent Routing Capabilities",
        "",
        "Use this reference only when deciding which retrieval capabilities a request needs. Select capabilities, never providers; `main_search` is not selectable here.",
        "",
    ]
    for capability in INTENT_ROUTING_CATALOG.values():
        lines.extend(
            [
                f"## `{capability.id}`",
                "",
                capability.description,
                "",
                f"- Select when: {capability.select_when}",
                f"- Do not select when: {capability.do_not_select_when}",
                "",
            ]
        )
    lines.extend(
        [
            "## Decision caveats",
            "",
            "Judge the complete set independently for the request: multiple capabilities or an empty set are valid. Provider selection, fallback, thresholds, strict validation, URL extraction, and routing merge behavior remain runtime-owned.",
            "",
        ]
    )
    return "\n".join(lines)
