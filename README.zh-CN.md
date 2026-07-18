# smart-search

简体中文 | [English](README.md)

`smart-search` 是一个给 AI 助手和命令行用户使用的 CLI-first 网页研究工具。它把普通联网搜索、来源发现、网页正文抓取、站点 map、配置检查、Deep Research 离线规划和 live Deep Research 执行统一成一个可复现的命令层。

<p>
  <a href="https://www.npmjs.com/package/@jfmoe/smart-search">
    <img src="https://img.shields.io/npm/v/@jfmoe/smart-search?label=npm%20latest" alt="npm latest">
  </a>
</p>

![Star History Chart](https://api.star-history.com/svg?repos=jfmoe/smartsearch&type=Date)

## 它到底是什么

它不是 MCP Server，而是一个普通命令行工具。AI 工具通过 `smart-search-cli` skill 调它，脚本和终端用户也可以直接调它：

```powershell
smart-search search "今天 OpenAI Responses API 有什么新变化" --format json
smart-search fetch "https://example.com/article" --format markdown
smart-search deep "OpenAI Responses API web_search 和 Chat Completions 联网搜索怎么选" --format json
smart-search research "OpenAI Responses API web_search 和 Chat Completions 联网搜索怎么选" --format markdown
```

当前架构分两层：

| 层 | 负责什么 |
| --- | --- |
| CLI 执行层 | 稳定执行命令、provider 路由、同能力兜底、JSON/Markdown 输出、本机配置、smoke/regression |
| Skill / AI 编排层 | 判断用户意图，决定普通搜索还是 Deep Research，按计划执行 CLI 积木，最后写出有来源支撑的回答 |

`smart-search search` 保持快速、直接联网。`smart-search deep` 是显式 Deep Research 离线规划入口：默认不联网、不跑 provider、不抓网页，只输出 `research_plan`。真正联网可以由 AI 或用户继续执行 `steps[].command`，也可以交给新的 `smart-search research` live 执行器完成。`research` 会按 plan -> discover -> fetch/read -> gap check -> evidence-only synthesis 执行。

现在意图路由单独成了一层。可以把它理解成“更聪明的分诊台”：先判断用户到底需要哪些能力，再让已有 provider 注册表在同一能力内兜底，而不是让模型直接乱选 provider：

```text
用户问题
 -> 规则路由：URL、文档/实时/抓取/垂直搜索硬信号、strict 校验
 -> 语义路由：可选 embeddings，对典型例句做相似度
 -> 模型路由：可选小模型输出结构化能力分类
 -> 合并成 required_capabilities
 -> 在 docs_search / web_search / web_fetch / vertical_search 内选择 provider 和兜底
```

`smart-search route "query"` 只解释这次会需要哪些能力，不执行搜索、文档查询、网页抓取或 provider 调用。`smart-search deep` 仍保持离线 planner 契约，只使用本地/rules 信号。

## 安装

稳定版：

```powershell
npm install -g @jfmoe/smart-search@latest
smart-search --version
smart-search setup
```

测试版：

```powershell
npm install -g @jfmoe/smart-search@next
smart-search --version
```

npm 包安装时会自动创建隔离的 Python 运行环境。npm 或其他包管理器安装不会写入 Skill Container；
你平时只需要使用 `smart-search` 这个命令。CLI 版本变化时，同步发生在版本变化后的首次普通 CLI 调用，
而不是包安装阶段。

前置条件：

- 已安装 Node.js 18 或更新版本及 npm。
- 已安装 Python 3.10 或更新版本，并且终端里能运行 `python3`。
- 0.2.0 正式支持范围仅为 macOS；其他平台即使可运行部分检查，也不构成支持承诺。

## 快速开始

1. 配置 provider：

```powershell
smart-search setup
smart-search doctor --format json
```

2. 普通快速搜索：

```powershell
smart-search search "今天有什么值得关注的 AI 新闻？" --validation balanced --extra-sources 2 --format json
```

3. 只看意图路由，不调用 provider：

```powershell
smart-search route "React useEffect API docs" --format markdown
smart-search route "请核验这个链接里的说法 https://example.com/source" --format json
```

4. 抓取关键网页正文：

```powershell
smart-search fetch "https://example.com/source" --format markdown --output evidence.md
```

5. 生成 Deep Research 计划：

```powershell
smart-search deep "深度搜索一下最近的比特币行情" --budget standard --format json
```

6. 让 CLI 直接执行 live Deep Research：

```powershell
smart-search research "深度搜索一下最近的比特币行情" --budget deep --format markdown
```

7. 安装 Skill 并保存完整的 Skill Container 集合：

```powershell
smart-search skills install
smart-search skills install agents claude hermes "D:\AI Tools\skills"
```

无参数时只选择 Agents Skill Target（`~/.agents/skills`）。交互式 `smart-search setup` 使用相同默认值，
并在最后的 Skill 提示中接受 `agents`、`claude`、`hermes` 与自定义 Skill Container。
使用 `--skip-skills` 可让交互 setup 不写任何 Skill 并保留已有偏好；非交互 setup 永不改变 Skill 偏好。
内置名严格只有 `agents`、`claude`、
`hermes`；其他 positional 参数都是自定义 Skill Container。Smart Search 会追加 `smart-search-cli`
子目录，将规范化的容器路径保存到 `config.json`，并保留现有 provider 配置。

8. 检查或手动修复已同步的 Skill：

```powershell
smart-search skills status --format json
smart-search skills update --format json
smart-search skills clear --format json
```

`skills status` 和 `skills update` 只操作已保存的 Skill Installation Preference。`skills clear`
通过保存空路径集合停止后续管理，但不卸载文件。更新会覆盖内置托管文件，但保留用户添加和已废弃的额外文件。
除交互式 setup 中明确的 Skill 选择步骤外，provider setup 不会改变 Skill 偏好。

Automatic Skill Sync 会在首次普通命令前比较当前 CLI 版本与最后完整同步版本；只要 CLI 版本字符串精确不等，
无论升级、降级或切换 release channel，都会同步全部已保存容器；完全相等时不执行写入。后台成功保持静默，
不会污染 JSON/content stdout。部分写入失败或有界锁等待超时会保持 pending，只把简洁修复指引写到标准错误输出，
且不改变原命令的 stdout 或退出码；可运行 `smart-search skills update --format json` 修复。
help、version、setup 和所有 `skills` 管理命令都会跳过后台同步。若 structured preference 缺失，
首次普通命令只初始化 Agents Skill Target，不扫描或迁移 legacy 目录。

## 当前架构

| 能力 | 主要命令 | Provider | 负责什么 |
| --- | --- | --- | --- |
| `main_search` | `search` | xAI Responses、OpenAI-compatible Chat Completions | 综合回答、快速搜索、初步总结 |
| `docs_search` | `context7-library`、`context7-docs`、`exa-search` | Context7、Exa | 官方文档、SDK、API、框架/库文档 |
| `web_search` | `zhipu-search`、`zhipu-mcp-search`、`search` 内部意图补强 | 智谱 Web Search API、智谱 Coding Plan MCP、Tavily、Firecrawl | 中文、国内、时效、域名过滤、补充来源 |
| `web_fetch` | `fetch`、`zhipu-mcp-reader` | Tavily、Jina Reader、智谱 Coding Plan MCP Reader、Firecrawl | 已知 URL 正文抓取、证据提取 |
| `vertical_search` | 意图路由的无域 `anysearch-search` | AnySearch（实验） | 明确垂直意图下的 Vertical Discovery，绝不进入 Web Search 兜底 |
| AnySearch Acceptance Surface | `anysearch-domains`、`anysearch-search`、`anysearch-extract`、`anysearch-batch` | AnySearch（实验） | 显式验收 Domain Discovery、无域/域级搜索、Batch Discovery 与 AnySearch Extraction |
| `site_map` | `map` | Tavily | 文档站、产品站、目录型站点结构 |
| `deep_planner` | `deep` / `dr` | 本地 planner | 离线生成 Deep Research 计划，不默认联网 |
| `research_executor` | `research` / `rs` | 按 capability 注册的 provider | live 深度研究执行：规划、发现、抓取/读取、gap check、仅基于证据综合 |

同能力兜底关系：

| 能力 | 兜底链 |
| --- | --- |
| `main_search` | xAI Responses -> OpenAI-compatible |
| `docs_search` | Context7 处理库/API/文档意图；Exa 处理官方域名、论文、产品页、可信站点发现 |
| `web_search` | 智谱 Web Search API -> 智谱 Coding Plan MCP `web_search_prime` -> Tavily -> Firecrawl |
| `web_fetch` | Tavily -> 带 `JINA_API_KEY` 的 Jina Reader -> 智谱 Coding Plan MCP `webReader` -> Firecrawl |

AnySearch 仍是可选、实验能力，不进入 `web_search` 兜底链，也不是 `standard` 最低配置要求。只有无域 Vertical Discovery 属于 `vertical_search` Capability Seam；Domain Discovery、Batch Discovery、AnySearch Extraction 都只是 provider 验收操作，其中 extraction 不是 Web Fetch。

默认 `search` 只有在主搜索成功、validation 为 `balanced` 或 `strict`、本地路由识别出垂直意图、provider filter 允许 AnySearch 且配置了 `ANYSEARCH_API_KEY` 时，才自动执行 Vertical Discovery。`research` 在 balanced 意图路由选中 `vertical_search` 且已配置 AnySearch 时复用同一无域语义；它没有单独的 provider-filter 参数或主搜索门禁。这个 key 同时表示 Configured AnySearch 和允许两条自动路径；没有 key 时，只有显式 AnySearch Acceptance Surface 命令可以匿名尝试。自动调用始终使用无域 `search`：Smart Search 不选择 domain/sub_domain，也不构造 Sub-domain Parameters。`--extra-sources 0` 只关闭 `search` 的 Tavily/Firecrawl 横向补充，不会关闭已满足门禁的 Vertical Discovery。

只有可规范化的 HTTP(S) 候选才会从 Vertical Discovery 进入 `extra_sources`。无 URL 的结构化响应保留在 `vertical_discovery` provider 结果中，绝不伪装成 source、citation 或 evidence。provider 失败会通过 `vertical_discovery` 和 `provider_attempts` 保留 operation、上游 tool 与错误类别，但不会改变成功主结果。无域响应不会声明或验收具体域。本地重点回归意图包括 academic、gaming 攻略和 travel 行程；普通“游戏”用法或比喻性的“旅行”不会命中。

Jina Reader 只属于 `web_fetch`，不是通用搜索 provider。只有配置 `JINA_API_KEY` 后，它才可以满足 `SMART_SEARCH_MINIMUM_PROFILE=standard`；匿名 `r.jina.ai` 只能当显式/实验抓取能力，不能让最低配置检查放松。

这里有一个重要边界：兜底只在同一类能力里发生。不会用 Context7 去查普通新闻，也不会用 Firecrawl 假装做文档语义检索。

输出里会保留可观测字段：

| 字段 | 作用 |
| --- | --- |
| `routing_decision` | 为什么触发了某些补强路径 |
| `provider_attempts` | 每个 provider 的尝试结果 |
| `providers_used` | 最终用到哪些 provider |
| `fallback_used` | 是否触发同能力兜底 |
| `primary_sources` | 主搜索回答里带出的来源 |
| `extra_sources` | Tavily / Firecrawl 等额外发现的候选来源 |
| `vertical_discovery` | AnySearch 无域调用的完整 provider 结果；无 URL 内容只保留在这里 |
| `source_warning` | 来源和回答之间可能存在的证据边界提醒 |

`routing_decision` 会保留旧字段：`docs_intent`、`zh_current_intent`、`web_current_intent`、`fetch_intent`、`supplemental_paths`；同时新增统一路由字段：`intent_router_mode`、`required_capabilities`、`intent_signals`、`confidence`、`router_engines_used`、`degraded_reason`。

`extra_sources` 只是候选来源，不等于自动事实校验。新闻、政策、财经、医疗、严肃评测、工具选型等高风险问题，建议先发现来源，再 `fetch` 关键网页正文，最后只基于抓到的正文写结论。

搜索引擎选择速记：先用 `search` 做宽泛探索和综合；想让 CLI 执行完整证据流时用 `research`；中文、国内、政策、公告、当前新闻优先补 `zhipu-search`；只有明确要用 Coding Plan 额度时才走 `zhipu-mcp-*`；库/API/框架文档优先用 Context7；官方域名、论文、产品页、可信站点和低噪声发现再用 Exa；Tavily/Firecrawl 通过 `search --extra-sources` 做横向候选，通过 `fetch` 做正文证据；Jina 用于已知 URL 正文抓取；AnySearch 只在明确要实验性垂直搜索时使用。

## Deep Research 深度搜索

普通问题用：

```powershell
smart-search search "React useEffect cleanup 文档" --format json
```

需要先拆解、规划、再由你或 AI 分步执行时用：

```powershell
smart-search deep "OpenAI Responses API web_search 和 Chat Completions 联网搜索怎么选" --budget deep --format json
smart-search dr "https://example.com/source" --format json
```

Deep Research 不是固定题材配方。行情、选型、技术文档、新闻政策、真假核验、用户给 URL 这些只是用户语言示例，不是 schema 枚举。它会先抽取 `intent_signals`，再生成 `decomposition` 和 `capability_plan`。

计划里会包含：

- `mode="deep_research"` 和 `query_mode="deep"`；
- `intent_signals`：是否强时效、是否 docs/API、是否给 URL、是否高风险、是否需要权威来源、是否需要交叉验证；
- `decomposition`：复杂问题拆成 1-6 个子问题；
- `capability_plan`：选择需要的能力；
- `steps[]`：每一步的 `tool`、`purpose`、`command`、`output_path`、`subquestion_id`；
- `evidence_policy="fetch_before_claim"`；
- `gap_check`：关键结论没有正文证据就继续抓，或者降级成未验证候选。
- `usage_boundary`：说明 `search` 是直接联网，`deep` 是离线规划，真正执行发生在计划命令里。

Deep Research 只允许组合现有 CLI 积木：

```text
search, exa-search, exa-similar, zhipu-search, context7-library, context7-docs, fetch, map
```

`doctor` 是 preflight 配置预检，不是 research step。`smart-search deep` 这一步本身是离线 planner；后续执行计划里的 `steps[].command` 时才会联网。

换句话说，`doctor` 只是配置预检；它帮助 AI 判断当前 provider 是否可用，但不算 Deep Research 的取证步骤。

如果你希望 CLI 直接执行完整 live Deep Research，用：

```powershell
smart-search research "OpenAI Responses API web_search 和 Chat Completions 联网搜索怎么选" --budget deep --fallback auto --format json
smart-search rs "https://example.com/source" --fallback off --format markdown
```

`research` 会执行 plan -> discover -> fetch/read -> gap check -> evidence-only synthesis。默认 `--fallback auto`，会在同一 capability 内兜底；`--fallback off` 只尝试每个 capability 选中的第一个 provider，适合手动调试某个 provider。

`research` JSON 会包含 `final_answer`、`citations`、`evidence_items`、`gap_check`、`provider_attempts`、`fallback_used`、`degraded`、`route_policy_version` 和 `evidence_dir`。发现阶段的 snippet 只是候选，不会直接变成 citation；只有 fetch/read 到正文的来源才会被引用。兜底仍然补不齐证据时，`research` 会降级输出 gap，不会编造结论。

`research` 的路由是 capability-first 加 provider 优势：

- Context7 优先处理库/API/框架文档，Exa 用于官方域名、论文、产品页、可信站点和低噪声发现。
- 智谱 Web Search API 优先处理中文、国内、时效、政策、公告搜索。
- 智谱 Coding Plan MCP 仍是单独额度路线，通过 `web_search_prime` 和 `webReader` 加入对应 capability。
- Jina 优先用于已知公开 URL、PDF、arXiv 正文抽取；ReaderLM-v2 仍要求 `JINA_API_KEY`。
- Firecrawl 优先用于 JS-heavy、动态页面、浏览器式抽取、OCR/PDF 或强兜底抓取。
- AnySearch 只在垂直意图清楚时加入，包括重点回归的 academic、gaming 攻略、travel 行程规则，以及既有 CVE、金融、法律、代码库/仓库信号；调用始终是无域 Vertical Discovery，由上游选择内部数据源。

高级路由覆盖项是 `SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS` 和 `SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS`。它们只能在 provider 已支持的 capability 内调整顺序或禁用，不能把 provider 移到另一个 capability。

可以用这些标准问题测试是否进入深搜模式：

```powershell
smart-search deep "深度搜索一下最近的比特币行情" --format json
smart-search deep "OpenAI Responses API web_search 和 Chat Completions 联网搜索怎么选" --budget deep --format json
smart-search deep "帮我核验这个说法是真是假：某某工具已经完全替代 Tavily 做 AI 搜索了" --format json
smart-search deep "https://example.com/source" --format json
```

看到输出里有 `mode=deep_research`、`decomposition`、多步 `steps`、`evidence_policy=fetch_before_claim`、`preflight.executed_by_deep_command=false`，就说明已经进入 Deep Research 计划模式。

## API 和 Key 申请入口

普通用户优先用 `smart-search setup` 配置。环境变量仍然支持 CI 和高级用户。
默认交互式 setup 已包含可选智能意图路由小节，可以直接配置 embeddings 和 classifier 路由，不需要进入 `--advanced`。

| Provider / 路线 | 用途 | 主要配置项 | 官方文档 | Key / 控制台 |
| --- | --- | --- | --- | --- |
| xAI Responses API | 主搜索，走 `web_search,x_search` 工具 | `XAI_API_KEY`、`XAI_API_URL`、`XAI_MODEL`、`XAI_TOOLS` | [docs.x.ai](https://docs.x.ai/docs) | [xAI API keys](https://console.x.ai/team/default/api-keys) |
| OpenAI-compatible Chat Completions | 主搜索，适合 OpenAI 官方或兼容中转；这里不会发送 xAI search tools | `OPENAI_COMPATIBLE_API_URL`、`OPENAI_COMPATIBLE_API_KEY`、`OPENAI_COMPATIBLE_MODEL`、`OPENAI_COMPATIBLE_STREAM` | [OpenAI platform docs](https://platform.openai.com/docs) | [OpenAI API keys](https://platform.openai.com/api-keys) 或你的兼容服务商 |
| Exa | 官方文档、API、论文、产品页、可信网页的低噪声发现 | `EXA_API_KEY` | [Exa docs](https://docs.exa.ai/) | [Exa API keys](https://dashboard.exa.ai/api-keys) |
| Context7 Remote MCP | SDK、库、框架、API 文档兜底 | `CONTEXT7_API_KEY`、`CONTEXT7_MCP_API_URL`（默认 `https://mcp.context7.com/mcp`） | [Context7 docs](https://context7.com/docs) | [Context7](https://context7.com/) |
| 智谱 Web Search API | 中文、国内、时效、域名过滤类来源发现 | `ZHIPU_API_KEY`、`ZHIPU_API_URL`、`ZHIPU_SEARCH_ENGINE` | [智谱联网搜索文档](https://docs.bigmodel.cn/cn/guide/tools/web-search) | [智谱 API keys](https://open.bigmodel.cn/usercenter/apikeys) |
| 智谱 Coding Plan Remote MCP | 使用 Coding Plan 额度做联网搜索、网页读取、开源仓库发现 | `ZHIPU_MCP_API_KEY`、`ZHIPU_MCP_SEARCH_API_URL`、`ZHIPU_MCP_READER_API_URL`、`ZHIPU_MCP_ZREAD_API_URL` | [联网搜索 MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/search-mcp-server)、[网页读取 MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/reader-mcp-server)、[zread MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/zread-mcp-server) | [智谱 API keys](https://open.bigmodel.cn/usercenter/apikeys) |
| Tavily | 额外来源、URL fetch、站点 map | `TAVILY_API_URL`、`TAVILY_API_KEY` | [Tavily docs](https://docs.tavily.com/) | [Tavily app](https://app.tavily.com/home) |
| Jina Reader | 已知 URL 正文抓取；满足 standard 最低配置必须有 key | `JINA_API_KEY`、`JINA_READER_API_URL`、`JINA_RESPOND_WITH`、`JINA_TIMEOUT_SECONDS` | [Jina Reader](https://jina.ai/reader/) | [Jina AI](https://jina.ai/) |
| Firecrawl | fetch 兜底、补充网页来源 | `FIRECRAWL_API_URL`、`FIRECRAWL_API_KEY` | [Firecrawl docs](https://docs.firecrawl.dev/) | [Firecrawl API keys](https://www.firecrawl.dev/app/api-keys) |
| AnySearch | 实验垂直搜索验收入口，不是默认兜底 | `ANYSEARCH_API_URL`、`ANYSEARCH_API_KEY`、`ANYSEARCH_TIMEOUT_SECONDS` | [AnySearch 文档](https://www.anysearch.com/docs) | [AnySearch API keys](https://www.anysearch.com/console/api-keys) |

意图路由配置：

| 配置项 | 用途 |
| --- | --- |
| `SMART_SEARCH_INTENT_ROUTER` | `hybrid`、`rules` 或 `off`，默认 `hybrid` |
| `INTENT_EMBEDDING_API_URL` | 可选 OpenAI-compatible embeddings endpoint，用于语义能力路由；推荐 setup preset 使用 `https://api.siliconflow.cn/v1/embeddings` |
| `INTENT_EMBEDDING_API_KEY` | 可选 embeddings key；`doctor` 和 config 输出会脱敏 |
| `INTENT_EMBEDDING_MODEL` | embeddings 模型名；推荐 setup preset 使用 `Qwen/Qwen3-Embedding-8B` |
| `INTENT_EMBEDDING_THRESHOLD` | 语义路由阈值，默认 `0.74`；推荐 8B setup 值是 `0.475`；这是模型相关参数 |
| `INTENT_EMBEDDING_MARGIN` | top1 与第二名分数差阈值，默认 `0.05`；推荐 8B setup 值是 `0.053`；差距不足时只记录 ambiguous 信号，不直接加 capability |
| `INTENT_CLASSIFIER_API_URL` | 可选 OpenAI-compatible chat-completions endpoint，用于结构化意图分类 |
| `INTENT_CLASSIFIER_API_KEY` | 可选 classifier key；`doctor` 和 config 输出会脱敏 |
| `INTENT_CLASSIFIER_MODEL` | classifier 模型名 |
| `INTENT_ROUTER_TIMEOUT_SECONDS` | 可选远程路由调用超时，默认 `8` |

默认 `hybrid` 是 fail-open：embeddings 或 classifier 没配置、超时或失败时，会在 `degraded_reason` 里说明，然后自动退回本地规则。语义路由只有在 top1 相似度达到 `INTENT_EMBEDDING_THRESHOLD`，并且 top1 与第二名差值达到 `INTENT_EMBEDDING_MARGIN` 时，才会直接添加 capability；否则只记录 ambiguous 信号。classifier 可以补充 capability，但未知 capability 和 provider 名会被忽略；provider 仍然只能由 capability-first 注册表选择。

Context7 只使用 Remote MCP endpoint。`CONTEXT7_BASE_URL` 已废弃，绝不会被当作 MCP 地址解释；如果它是唯一的 Context7 endpoint 配置，命令会 fail closed。请设置 `CONTEXT7_MCP_API_URL`（或移除旧键以使用默认地址）后再试。

普通用户推荐直接使用 Qwen3-Embedding-8B preset：`INTENT_EMBEDDING_API_URL=https://api.siliconflow.cn/v1/embeddings`、`INTENT_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B`、`INTENT_EMBEDDING_THRESHOLD=0.475`、`INTENT_EMBEDDING_MARGIN=0.053`。选择 8B 模型且没有手动配置 threshold/margin 时，`smart-search setup` 会自动补齐这两个推荐值。

embedding 余弦分数强依赖模型。`route-calibrate` 保留给高级复验：换 `INTENT_EMBEDDING_MODEL`、换 embedding endpoint，或者后续加入真实 query 校准集后再运行：

```powershell
smart-search route-calibrate --models "Qwen/Qwen3-Embedding-8B" --format markdown
```

再按报告推荐值设置 `INTENT_EMBEDDING_THRESHOLD` 和 `INTENT_EMBEDDING_MARGIN`。校准主指标是 semantic-only Macro-F1；full-route Macro-F1 只用来验证 rules/classifier 兜底后的真实路由表现。

几个容易混淆的点：

- xAI 官方联网搜索路线是 Responses API `/responses`，只通过 `XAI_*` 配置。兼容中转/网关走 Chat Completions `/chat/completions`，只通过 `OPENAI_COMPATIBLE_*` 配置。
- `OPENAI_COMPATIBLE_STREAM=true` 或 `smart-search search --stream` 只会给 OpenAI-compatible 的 `search` 和 provider 侧 `fetch` 设置 `stream=true`。它是中转长请求兼容开关，不改变 xAI Responses、URL 描述和来源排序行为。
- 旧的 `SMART_SEARCH_API_URL`、`SMART_SEARCH_API_KEY`、`SMART_SEARCH_API_MODE`、`SMART_SEARCH_MODEL`、`SMART_SEARCH_XAI_TOOLS` 不再是受支持配置项。请显式使用 `XAI_*` 或 `OPENAI_COMPATIBLE_*`。
- 不要给 OpenAI-compatible Chat Completions 中转强塞 xAI 的 `web_search` / `x_search` 工具或旧 `search_parameters`。
- `zhipu-search` 对应的是智谱 Web Search API，不是 Chat Completions `tools=[web_search]`，不是 Search Agent，也不是 MCP Server。
- 智谱 Coding Plan 是单独的 Remote MCP 路线：`web_search_prime` 对应 `web_search`，`webReader` 对应 `web_fetch`，zread 工具对应显式仓库/文档发现命令。它不会混进现有 `/paas/v4/web_search` 智谱 REST provider。
- 智谱 Coding Plan MCP 需要单独的 Coding Plan 权益。普通 `ZHIPU_API_KEY` 能用 Web Search API，不代表能用 `zhipu-mcp-search` 或 zread。未配置或未授权 `ZHIPU_MCP_API_KEY` 时，Smart Search 会跳过这些 MCP provider；`standard` 最低配置和同 capability 兜底仍会通过已配置的 REST/search/fetch provider 工作。
- Jina Reader 不是通用搜索 provider。只有配置 `JINA_API_KEY` 后才计入 `standard`；`JINA_RESPOND_WITH=readerlm-v2` 也必须配置 `JINA_API_KEY`。
- `ZHIPU_SEARCH_ENGINE` 默认是 `search_std`。官方值包括 `search_std`、`search_pro`、`search_pro_sogou`、`search_pro_quark`；`config set` 仍允许自定义值，方便官方以后新增服务。
- `TAVILY_API_URL` 只影响 Tavily，不会代理智谱。Tavily Hikari / 号池用 `https://<host>/api/tavily`；setup 会把根域名或 `/mcp` 输入规范化成这个 REST base。
- `FIRECRAWL_API_URL` 默认是 `https://api.firecrawl.dev/v2`。
- AnySearch 默认走 `https://api.anysearch.com/mcp` 的 JSON-RPC 2.0 `tools/call`。`anysearch-domains DOMAIN` 只调用 `get_sub_domains`，不会探测 `tools/list`、猜别名或回退 `list_domains`。没有 key 时显式 Acceptance Surface 仍可匿名尝试；配置 key 才表示 configured 并允许自动 Vertical Discovery。HTTP 200 但 `result.isError=true` 会按 provider error 处理，不能当成功证据。
- `doctor` 和 `route` 会报告 intent router 的配置状态、embedding 模型、threshold、margin、配置来源、超时和是否可降级，不会暴露 router API key。

非交互配置示例：

```powershell
smart-search setup --non-interactive `
  --xai-api-key "your-xai-key" `
  --xai-model "grok-4-fast" `
  --openai-compatible-api-url "https://api.openai.com/v1" `
  --openai-compatible-api-key "your-openai-or-relay-key" `
  --openai-compatible-model "gpt-4.1" `
  --openai-compatible-stream "false" `
  --validation-level "balanced" `
  --fallback-mode "auto" `
  --minimum-profile "standard" `
  --intent-router "hybrid" `
  --intent-embedding-api-url "https://api.siliconflow.cn/v1/embeddings" `
  --intent-embedding-api-key "your-siliconflow-key" `
  --intent-embedding-model "Qwen/Qwen3-Embedding-8B" `
  --intent-embedding-threshold "0.475" `
  --intent-embedding-margin "0.053" `
  --exa-key "your-exa-key" `
  --context7-key "your-context7-key" `
  --zhipu-key "your-zhipu-key" `
  --zhipu-api-url "https://open.bigmodel.cn/api" `
  --zhipu-search-engine "search_pro_sogou" `
  --zhipu-mcp-key "your-zhipu-coding-plan-key" `
  --jina-key "your-jina-key" `
  --tavily-api-url "https://api.tavily.com" `
  --tavily-key "your-tavily-key" `
  --firecrawl-api-url "https://api.firecrawl.dev/v2" `
  --firecrawl-key "your-firecrawl-key"
```

默认最低配置是 `SMART_SEARCH_MINIMUM_PROFILE=standard`，至少需要：

- `main_search`：xAI Responses 或 OpenAI-compatible 二选一；
- `docs_search`：Exa 或 Context7 二选一；
- `web_fetch`：Tavily、带 `JINA_API_KEY` 的 Jina、智谱 Coding Plan MCP Reader、Firecrawl 四选一。

缺少任一最低能力时，`doctor` 和 `search` 会 fail closed 并返回缺失 capability。`SMART_SEARCH_MINIMUM_PROFILE=off` 只建议本地实验使用。

AnySearch 是可选实验配置，不满足也不改变 `standard` 最低配置：

```powershell
smart-search setup --non-interactive --anysearch-api-url "https://api.anysearch.com/mcp" --anysearch-key "your-anysearch-key"
smart-search anysearch-domains security --format json
smart-search anysearch-search "旅行灵感" --max-results 3 --format json
smart-search anysearch-search "CVE-2024-3094" --domain security --sub-domain vuln --sub-domain-params '{"product":"xz"}' --max-results 3 --format json
smart-search anysearch-extract "https://example.com/source" --format json
smart-search anysearch-batch "AAPL" "RAG papers" --max-results 2 --format json
```

无域 `anysearch-search` 是显式 Vertical Discovery。域级搜索必须分别提供 `--domain` 和 `--sub-domain`，并可通过单个 `--sub-domain-params` JSON object 原样嵌套到上游 `sub_domain_params` 字段；输出只回显参数键。`security.cve` 等点号简写、旧子域别名、缺半边组合、非法/非 object JSON 和覆盖保留字段都会在联网前返回带迁移提示的 `parameter_error`。只有可靠、版本化的 Verified Domain Contract 才用于 required/type/enum 校验，实时 discovery schema 仍只是验收证据；没有该契约时稳定返回 `schema_validation.status=unavailable`，不隐式 discovery，直接交给上游。

受版本控制的 Verified Domain Manifest 是支持声明的唯一依据。当前 verified 集合为空：`academic.search`、`security.vuln`、`finance.fundamental`、`code.doc` 都仍是 discovered/unverified，并明确记录 live 与稳定性缺口。`doctor` 分别公开 configured 状态、自动 Vertical Discovery 开关、独立的 operation-live 状态、verified domains 与候选评估。详见[首批领域矩阵](docs/anysearch-verified-domain-manifest.md)；mock fixture 或一次 live 成功都不会自动晋级领域。

这些术语必须严格区分：**Vertical Discovery** 是无域的 `vertical_search` capability 调用；**显式域搜索** 是用户指定 `domain`/`sub_domain` 的 Acceptance Surface 调用；**Provider Acceptance Operations** 包括 Domain Discovery、显式 Vertical Discovery/域搜索、Batch Discovery 与 AnySearch Extraction；**Automatic Domain Search** 尚未实现。无 key 时显式操作仍可匿名尝试；只有 `ANYSEARCH_API_KEY` 同时控制 Configured AnySearch 与自动 Vertical Discovery。`--extra-sources 0` 不会关闭该自动调用，而 Batch Discovery 和 AnySearch Extraction 永远不会自动运行。

静态 `capability_status.vertical_search` 完全离线，分别报告 `configured`、`automatic_vertical_discovery`、`experimental`、manifest 驱动的 `verified_domains` 和五项 `operation_live`。`doctor` 将每项保留为 `not_run`，不会用一个 `ok` 推断整个 provider 可用。`smart-search smoke --mock` 离线覆盖完整契约；`smart-search smoke --live` 只有在进程环境显式提供 `ANYSEARCH_API_KEY` 时，才运行 Domain Discovery、Vertical Discovery、Batch Discovery、AnySearch Extraction 和至少一个 `academic.search` 显式域搜索，否则各项如实为 `not_run`；endpoint 与 timeout 仍遵循“环境变量 → 保存配置 → 默认值”的既有优先级。可用 `ANYSEARCH_LIVE_ACCEPTANCE=academic.search,security.vuln` 或 `all` 选择显式候选域。live 输出按操作及每个已选域分别报告 `passed`、`failed`、`not_run`，稳定包含 `operation`、上游 `tool`、`error_type`，且绝不晋级 manifest。

本机配置文件位置：

- Windows 默认：`%LOCALAPPDATA%\smart-search\config.json`。
- Linux/macOS 默认：`~/.config/smart-search/config.json`。
- `SMART_SEARCH_CONFIG_DIR` 是高级覆盖项，适合 CI、容器、沙箱或便携安装。
- 更早的 Windows 源码默认路径曾是 `~\.config\smart-search\config.json`，但有些安装会通过 `SMART_SEARCH_CONFIG_DIR` 提前固定到 `%LOCALAPPDATA%\smart-search`。如果新版默认位置还没有配置，但旧 home 路径存在配置，Smart Search 会以 `legacy_windows_home` 方式继续读取旧配置，避免升级后配置丢失；`doctor` 会同时报告当前生效路径、默认路径、旧 home 路径、`SMART_SEARCH_CONFIG_DIR` 的值，以及这个覆盖项是不是只是等于当前默认路径。

常用环境变量：

| 变量 | 用途 |
| --- | --- |
| `XAI_API_KEY` | xAI Responses provider key |
| `XAI_API_URL` | xAI API 地址，默认 `https://api.x.ai/v1` |
| `XAI_MODEL` | xAI 模型名 |
| `XAI_TOOLS` | xAI Responses 工具列表，通常 `web_search,x_search` |
| `OPENAI_COMPATIBLE_API_URL` | OpenAI-compatible `/v1` base URL |
| `OPENAI_COMPATIBLE_API_KEY` | OpenAI-compatible key |
| `OPENAI_COMPATIBLE_MODEL` | 兼容模型名 |
| `OPENAI_COMPATIBLE_STREAM` | OpenAI-compatible 中转兼容开关，接受 `true/1/yes`，默认 `false` |
| `ANYSEARCH_API_URL` | AnySearch JSON-RPC endpoint，默认 `https://api.anysearch.com/mcp` |
| `ANYSEARCH_API_KEY` | 可选 AnySearch key |
| `ANYSEARCH_TIMEOUT_SECONDS` | AnySearch 请求超时，默认 `30` |
| `SMART_SEARCH_INTENT_ROUTER` | 意图路由模式：`hybrid`、`rules`、`off`，默认 `hybrid` |
| `INTENT_EMBEDDING_API_URL` | 可选 embeddings endpoint，用于语义路由 |
| `INTENT_EMBEDDING_API_KEY` | 可选 embeddings key |
| `INTENT_EMBEDDING_MODEL` | embeddings 模型名 |
| `INTENT_EMBEDDING_THRESHOLD` | 语义路由阈值，默认 `0.74`，换模型后用 `route-calibrate` 校准 |
| `INTENT_EMBEDDING_MARGIN` | top1 与第二名分数差阈值，默认 `0.05` |
| `INTENT_CLASSIFIER_API_URL` | 可选 classifier chat-completions endpoint |
| `INTENT_CLASSIFIER_API_KEY` | 可选 classifier key |
| `INTENT_CLASSIFIER_MODEL` | classifier 模型名 |
| `INTENT_ROUTER_TIMEOUT_SECONDS` | 可选路由调用超时，默认 `8` |
| `EXA_API_KEY` | Exa key |
| `CONTEXT7_API_KEY` | Context7 key |
| `ZHIPU_API_KEY` | 智谱 Web Search key |
| `ZHIPU_API_URL` | 智谱 API 地址，默认 `https://open.bigmodel.cn/api` |
| `ZHIPU_SEARCH_ENGINE` | 智谱搜索服务，例如 `search_pro_sogou` |
| `ZHIPU_MCP_API_KEY` | 智谱 Coding Plan Remote MCP key |
| `ZHIPU_MCP_SEARCH_API_URL` | 智谱 Coding Plan 联网搜索 MCP endpoint |
| `ZHIPU_MCP_READER_API_URL` | 智谱 Coding Plan 网页读取 MCP endpoint |
| `ZHIPU_MCP_ZREAD_API_URL` | 智谱 Coding Plan zread MCP endpoint |
| `ZHIPU_MCP_TIMEOUT_SECONDS` | 智谱 Coding Plan MCP 请求超时，默认 `30` |
| `JINA_API_KEY` | Jina Reader key；满足 standard 必须配置 |
| `JINA_READER_API_URL` | Jina Reader endpoint，默认 `https://r.jina.ai` |
| `JINA_RESPOND_WITH` | Jina Reader 响应模式，例如 `readerlm-v2`；需要 `JINA_API_KEY` |
| `JINA_TIMEOUT_SECONDS` | Jina Reader 请求超时，默认 `30` |
| `TAVILY_API_URL` | Tavily REST base |
| `TAVILY_API_KEY` | Tavily key |
| `TAVILY_TIMEOUT_SECONDS` | Tavily 连通性检查超时，默认 `30`；公益站/号池较慢时可调大 |
| `FIRECRAWL_API_URL` | Firecrawl REST base |
| `FIRECRAWL_API_KEY` | Firecrawl key |
| `SMART_SEARCH_VALIDATION_LEVEL` | `fast`、`balanced`、`strict` |
| `SMART_SEARCH_FALLBACK_MODE` | `auto` 或 `off` |
| `SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS` | `research` 路由优先 provider CSV，只能在同 capability 内调整顺序 |
| `SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS` | `research` 禁用 provider CSV，不能改变 provider capability 边界 |
| `SMART_SEARCH_CONFIG_DIR` | 指定本机配置和日志根目录 |

## 常用命令

| 命令 | 简写 | 用途 |
| --- | --- | --- |
| `search` | `s` | 快速联网搜索和综合回答 |
| `route` | `rt` | 只解释需要哪些 capability，不调用 provider |
| `deep` | `dr` | Deep Research 离线计划 |
| `research` | `rs` | live Deep Research 执行 |
| `fetch` | `f` | 抓一个 URL 正文 |
| `map` | `m` | 读取站点结构 |
| `exa-search` | `exa`、`x` | Exa 来源发现 |
| `exa-similar` | `xs` | 从一个 URL 找相似页面 |
| `zhipu-search` | `z`、`zp` | 智谱 Web Search API |
| `zhipu-mcp-search` | `zmcp-search` | 智谱 Coding Plan MCP `web_search_prime` |
| `zhipu-mcp-reader` | `zmcp-reader` | 智谱 Coding Plan MCP `webReader` |
| `zhipu-mcp-search-doc` | `zmcp-doc` | 通过 zread MCP 搜开源仓库文档 |
| `zhipu-mcp-repo-structure` | `zmcp-tree` | 通过 zread MCP 读仓库结构 |
| `zhipu-mcp-read-file` | `zmcp-file` | 通过 zread MCP 读单个仓库文件 |
| `anysearch-domains` | `as-domains` | 要求父 domain，通过 `get_sub_domains` 执行 Domain Discovery |
| `anysearch-search` | `as-search`、`as` | Vertical Discovery 或显式拆分 domain/sub-domain 搜索 |
| `anysearch-extract` | `as-extract` | 显式 AnySearch Extraction，不是 Web Fetch |
| `anysearch-batch` | `as-batch` | 显式 Batch Discovery，最多 5 条无域查询 |
| `context7-library` | `c7`、`ctx7` | 查 Context7 库候选 |
| `context7-docs` | `c7d`、`c7docs`、`ctx7-docs` | 抓 Context7 文档 |
| `route-calibrate` | `route-cal`、`rcal` | 评测 embedding 路由模型并推荐 threshold/margin |
| `doctor` | `d` | 配置和连通性检查 |
| `setup` | `init` | 配置向导 |
| `skills` | `skill` | 安装、检查、更新或清空已保存的 Skill Container |
| `config` | `cfg` | 本机配置读写 |
| `model` | `mdl` | 查看显式 provider 模型；修改请用 `config set XAI_MODEL` 或 `OPENAI_COMPATIBLE_MODEL` |
| `smoke` | `sm` | provider 路由冒烟测试 |
| `regression` | `reg` | 离线回归测试 |

示例：

```powershell
smart-search search "query" --validation balanced --extra-sources 3 --timeout 180 --format json --output result.json
smart-search route "React useEffect API docs" --format markdown
smart-search route-calibrate --models "Qwen/Qwen3-Embedding-8B" --format markdown
smart-search research "query" --budget deep --fallback auto --format json --output research.json
smart-search search "query" --stream --format json
smart-search search "query" --no-stream --format json
smart-search search "nba战报" --format content
smart-search exa-search "OpenAI Responses API documentation" --include-domains platform.openai.com developers.openai.com --num-results 5 --include-text --format json
smart-search context7-library "react" "hooks" --format json
smart-search context7-docs "/facebook/react" "useEffect cleanup" --format json
smart-search zhipu-search "今天国内 AI 新闻" --search-engine search_pro_sogou --count 5 --format json
smart-search zhipu-mcp-search "今天国内 AI 新闻" --count 5 --format json
smart-search zhipu-mcp-reader "https://example.com/source" --format json
smart-search zhipu-mcp-search-doc "owner/repo" "install" --format json
smart-search anysearch-search "CVE-2024-3094" --domain security --sub-domain vuln --sub-domain-params '{"product":"xz"}' --max-results 3 --format json
smart-search anysearch-extract "https://example.com/source" --format json
smart-search exa-similar "https://example.com/source" --num-results 5 --format json
smart-search fetch "https://example.com/source" --format markdown --output page.md
smart-search map "https://docs.example.com" --instructions "Find API reference pages" --max-depth 1 --limit 50 --format json
smart-search doctor --format markdown
smart-search smoke --mock --format json
smart-search regression
```

## 输出和证据策略

AI 和脚本解析优先用 JSON：

```powershell
smart-search search "query" --format json
smart-search doctor --format json
```

给人看连接状态、详细排障报告、冒烟结果、来源列表、网页正文时用 Markdown：

```powershell
smart-search doctor --format markdown
smart-search smoke --mock --format markdown
smart-search exa-search "OpenAI Responses API documentation" --format markdown
smart-search fetch "https://example.com" --format markdown
```

终端快速扫正文或摘要用 content：

```powershell
smart-search search "nba战报" --format content
smart-search doctor --format content
```

`content` 刻意保持很短，只适合快速看结论。完整排障给人看用 `doctor --format markdown`，给脚本和 AI 解析用 `doctor --format json`。

多来源研究建议显式指定稳定目录保存证据文件。默认使用平台临时目录，以 Windows 显式路径为例：

```powershell
smart-search exa-search "Reuters Iran Hormuz latest" --format json --output C:\tmp\smart-search-evidence\iran-hormuz\01-exa.json
smart-search fetch "https://example.com/source" --format markdown --output C:\tmp\smart-search-evidence\iran-hormuz\02-fetch.md
```

写 claim-level 结论时建议流程：

1. 用 `search`、`exa-search`、`zhipu-search` 或 `exa-similar` 找候选 URL。
2. 用 `fetch` 抓关键 URL 正文。
3. 最终回答只引用 fetch 正文能支撑的事实。
4. 没有 fetch 的来源标为未验证候选。

## 排障

如果 `doctor` 返回 `config_error`：

```powershell
smart-search setup
smart-search config list --format json
smart-search doctor --format markdown
```

如果搜索慢：

- 降低 `--extra-sources`；
- 把大问题拆成多个小问题；
- 先用 `exa-search` 或 `zhipu-search` 找来源，再 `fetch` 关键网页。

如果想确认安装是否正常：

```powershell
smart-search --help
smart-search --version
smart-search regression
smart-search smoke --mock --format json
```

Windows npm/mise 安装后建议验证中文 JSON 管道：

```powershell
smart-search deep "深度搜索一下最近的比特币行情" --format json | ConvertFrom-Json
```

## 开发验证

```powershell
.\.venv\Scripts\python.exe -m compileall -q src tests
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m smart_search.cli regression
.\.venv\Scripts\python.exe -m smart_search.cli smoke --mock --format json
npm test
npm pack --dry-run
```

## 0.3.0 发行线

`@jfmoe/smart-search@0.3.0` 是个人发行线。Node 是唯一承诺的 JavaScript
启动入口，macOS 是唯一正式支持的平台。公共 Skill 只在
`skills/smart-search-cli` 中维护，包内镜像由 `scripts/sync-skill.py` 生成。

## 发布通道

- 普通 `main` push 只运行 `npm test`，绝不会发布。
- preview 只能由 `workflow_dispatch` 触发；必须输入不可移动的完整
  40-character commit SHA，版本必须是检出 `package.json` 版本的 prerelease，
  且只发布到 npm `next`。
- stable 只能由精确 `vX.Y.Z` tag 触发。发布 npm `latest` 前，workflow 会
  验证 tag、npm 元数据、Python 元数据、lockfile 和 `npm version` 都严格等于
  `X.Y.Z`。

每个公开版本都对应不可变源码：不得移动发行 tag，不得 rebase 或 force-push 已发行
`main` 历史，也不能覆盖已发布的 npm 版本。打 stable tag 前先准备
`.github/releases/vX.Y.Z.md`，workflow 会以它创建 GitHub Release。

当前只读 upstream baseline 记录在 `docs/release/upstream-baseline.md`。
上游变更只能通过独立 sync PR 挑选合并；发行工作不会抓取、合并或发布上游。

## License

MIT
