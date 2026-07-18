# 普通 `search` 中 Context7 结果结构调查

> 调查日期：2026-07-17；当前源码基线：`32fddfc1dc5c84e980df8fd350f1c7fddf8f0672`（0.2.2）。
>
> 性质：供后续 grilling 使用的事实报告；“建议”与“推断”均显式标注，不构成现有契约。

## 执行摘要

明确结论如下。

1. 当前普通 `search` 的 Context7 自动路径只执行 `resolve-library-id`，不执行 `query-docs`。它把所有 library candidates 映射成形如 `context7:/react/react` 的字符串，放进 `extra_sources`，再经兼容合并进入 `sources`。因此这些对象是“库候选”，不是文档正文、可抓取网页或已核验证据。实现证据见 `src/smart_search/service.py:1786-1830`、`src/smart_search/service.py:2282-2324`。
2. `/tmp/react-19-smart-search.json` 中 Context7 transport 成功返回 3 个候选，`provider_attempts` 也记录 `docs_search/context7/status=ok/result_count=3`；本次异常不是 transport 故障。问题发生在成功 resolve 之后的结果投影和字段语义上。artifact 证据见 `/tmp/react-19-smart-search.json:31-46`、`:85-100`、`:210-215`。
3. `docs_search=ok` 在普通 `search` 中只表示“resolve 得到至少一个 library candidate”，不能解释为“文档已查到”或“证据已取得”。`_run_docs_search_fallback` 一得到候选就返回，未调用 `context7_docs`（`src/smart_search/service.py:1815-1830`）。
4. 当前 `research` 是另一条更强的两阶段链：resolve 后取第一候选，再调用 `query-docs`，只有获得 `content` 才创建 docs evidence（`src/smart_search/service.py:1261-1290`）。普通 `search` 与 `research` 对同一 `docs_search` capability 的完成含义不同。
5. 当前 Skill 能告诉模型 Context7 是两阶段工具、自动流程保留第一候选、fallback 只能发生在同一 capability、discovery candidate 不是证据；但它没有说明普通 `search` 会返回 `context7:/...`、会返回所有候选、会把候选塞进 `extra_sources/sources`，也没有说明 `docs_search=ok` 仅代表 resolve。Skill 当前与历史范围内对 literal `context7:/` 的 Git 搜索无匹配；仓库全局历史有匹配，但只来自测试，不来自 Skill。
6. 本问题不是“用户问法不对”。这条 React Release 查询明确限定 React 官方博客或 GitHub Releases；当前规则仍因 `React`、`当前/最新`、`GitHub` 同时触发 `docs_search`、`web_search`、`vertical_search`，路由范围过宽（`src/smart_search/intent_router.py:15-39`、`:41-70`、`:98-126`、`:350-384`）。
7. 修复前必须分开做三个产品决策：普通 `search` 是否只做 resolve；library candidate 应放在哪个字段；`sources` 是否只允许真实、可访问的来源 URL。它们不能被一句“修掉伪 URL”合并成同一决策。

## 调查问题、范围与术语

### 调查问题

- 普通 `search` 为什么返回 `context7:/...`？
- 这些对象是来源、候选、文档还是证据？
- 当前代码、测试、Skill 和历史决策是否一致？
- 是 Context7 Remote MCP transport 故障、问法问题，还是本地投影契约问题？
- 后续 grilling 需要分别决定哪些产品边界？

### 范围

已逐项核验：当前源码、当前测试、`git log/show/blame`、当前与历史 Smart Search Skill、GitHub Issues #4/#10/#12/#15、PR #20，以及 artifact `/tmp/react-19-smart-search.json`。未修改实现，未执行 live Context7 E2E。

### 术语

- **library candidate（库候选）**：`resolve-library-id` 返回的一项库匹配，核心标识是 Context7 library ID，例如 `/reactjs/react.dev`；当前 provider 还可保留 title、description、trust score、benchmark score、snippet count、stars（`src/smart_search/providers/context7.py:51-61`、`:155-179`）。
- **document（文档结果）**：`query-docs` 返回的 `content`、`code_snippets`、`info_snippets` 与合并 `results`（`src/smart_search/providers/context7.py:304-334`）。
- **source URL（来源 URL）**：本报告用来指可交给 HTTP(S) fetch、浏览器或引用系统访问的真实网页 URL。当前代码的 `sources` 合并器只检查字符串非空，并不要求 HTTP(S)（`src/smart_search/sources.py:123-136`）；因此当前字段名并不能保证该性质。
- **evidence（证据）**：已经取得正文、能够支撑 claim-level 结论的材料。当前 Skill 要求重要结论先 fetch，并把 `primary_sources`/`extra_sources` 当作 discovery candidates（`src/smart_search/assets/skills/smart-search-cli/references/deep-research-mode.md:40-50`）。`research` 对 Context7 的例外是直接把 `query-docs` content 建成 docs evidence（`src/smart_search/service.py:1277-1289`）。
- **伪 URL**：本报告对 `context7:/...` 的简称。它能携带 provider-local ID，但不是普通网页 URL；当前 CLI 却会把它渲染成 Markdown 链接（`src/smart_search/cli.py:843-860`），而 `research` 的候选 URL 选择器又明确跳过 `context7:`（`src/smart_search/service.py:786-797`）。

## Artifact 的可观察事实

artifact 查询是：“截至当前，React 19.x 的最新稳定版本是什么？请仅基于 React 官方博客或 GitHub 官方 Releases……”（`/tmp/react-19-smart-search.json:6`）。直接可观察到：

- 顶层 `ok=true`；主回答来自 `xai-responses`。
- `sources_count=8`、`primary_sources_count=3`、`extra_sources_count=6`（`/tmp/react-19-smart-search.json:55`、`:70`、`:109`）。`3 + 6 > 8` 是因为兼容 `sources` 按 URL 去重；`https://react.dev/blog/2025/10/01/react-19-2` 同时存在于 primary 与 extra。
- 3 个 Context7 项分别是 `/react/react`、`/reactjs/react.dev`、`/websites/react_dev`；三者都出现在 `extra_sources`，也都出现在合并后的 `sources`（`/tmp/react-19-smart-search.json:31-46`、`:85-100`）。
- 这些项只有 synthetic `url`、title、description、provider；没有 Context7 docs content、snippet、网页 canonical URL 或 evidence 状态。
- `source_warning` 说 `extra_sources` 是并行取回且未自动用于验证 content（`/tmp/react-19-smart-search.json:110`）。但这 3 个 Context7 项并非 `--extra-sources` 的 Tavily/Firecrawl 并行结果，而是主搜索完成后执行的 supplemental docs route；警告只在“未自动验证”部分准确，在来源类型与执行方式上过度概括。
- 路由选中了 `docs_search`、`web_search`、`vertical_search`（`/tmp/react-19-smart-search.json:116-126`）。原因是 docs/API/library、current/locale/news、vertical-domain 三组规则都命中。
- Context7 attempt 是 `status=ok`、`result_count=3`（`/tmp/react-19-smart-search.json:210-215`），没有 `error_type` 或 `error`。所以本次没有 transport 失败证据。
- `fallback_used=true`（`/tmp/react-19-smart-search.json:227`）不能被解释为 Context7 fallback：artifact 内 Context7 只有一次成功 attempt；同一 `web_search` capability 同时记录了 Tavily 与 Firecrawl，当前 `_fallback_used` 遇到同 capability 的 provider identity 变化就返回 true（`src/smart_search/service.py:517-534`）。

另一个与用户约束有关的事实：primary sources 中含 npm package 页面，而用户要求“仅基于 React 官方博客或 GitHub 官方 Releases”。这说明主回答来源约束与 supplemental routes 是两套并行机制；附加候选不会反向约束或重写已生成的 `content`（`src/smart_search/service.py:2276-2304`）。

## 当前运行链路

### 普通 `search`

```text
search(query)
  -> IntentRouter.route(query)
  -> required_capabilities / supplemental_paths
  -> 先完成 main_search content
  -> balanced/strict 下执行 _run_docs_search_fallback(query)
  -> Context7 context7_library(query, query)
  -> Remote MCP resolve-library-id
  -> 所有 library candidates 投影为 {url: "context7:<id>", ...}
  -> supplemental_sources
  -> extra_sources = merge(extra-source providers, supplemental_sources)
  -> sources = merge(primary_sources, extra_sources)
```

代码逐段对应：

- `search` 调统一 router，并把 `required_capabilities` 当 supplemental paths：`src/smart_search/service.py:2024-2106`。
- balanced/strict 根据 paths 执行 docs/web/fetch/vertical supplemental routes：`src/smart_search/service.py:2282-2301`。
- docs fallback 的 Context7 分支只调用 `context7_library(query, query)`：`src/smart_search/service.py:1815-1817`。
- 每个候选都被投影为 `url=f"context7:{id}"`：`src/smart_search/service.py:1818-1827`。
- 一旦候选非空即记录 `docs_search=ok` 并返回：`src/smart_search/service.py:1828-1830`。
- supplemental 结果并入 `extra_sources`，随后再与 primary 合并为 `sources`：`src/smart_search/service.py:2303-2324`。

因此普通 `search` 的 Context7 路径不是“resolve→第一候选→query-docs”，而是“resolve→投影全部候选→结束”。

### `research` 对照

`research` 先调用同一个 `IntentRouter`，再进入 provider-advantage routes（`src/smart_search/service.py:1213-1233`）。docs 意图下：

1. provider 顺序默认 Context7→Exa（`src/smart_search/service.py:159-167`、`tests/test_service.py:506-513`）；
2. 调 `context7_library`；
3. 明确取 `results[0].id`；
4. 调 `context7_docs(library_id, question)`；
5. 只有 docs `content` 非空才生成 `source_type=docs` 的 evidence item（`src/smart_search/service.py:1261-1290`）；
6. Exa 只产生 discovery sources，随后真实 URL 必须 fetch 才进入 evidence（`src/smart_search/service.py:1298-1307`、`:1357-1385`）。

这条链满足 Issue #4/#10 确认的“第一候选、Context7→Exa 同能力 fallback、候选 fetch 后才是证据”决策；普通 `search` 只满足其中的 resolve/discovery 部分。

## 当前三层返回结构

### 1. `context7-library`：库候选层

成功输出形状为：

```json
{
  "ok": true,
  "query": "react hooks",
  "provider": "context7",
  "results": [
    {
      "id": "/reactjs/react.dev",
      "title": "React",
      "description": "...",
      "trust_score": 9.5,
      "benchmark_score": null,
      "total_snippets": 1234,
      "stars": null,
      "provider": "context7"
    }
  ],
  "total": 1,
  "elapsed_ms": 123.0
}
```

这是 library resolution 结果，不含网页 URL，也不含 docs content。结构来自 `src/smart_search/providers/context7.py:51-61`、`:282-299`；CLI stable field 文档见 `src/smart_search/assets/skills/smart-search-cli/references/cli-core.md:60-73`。

### 2. `context7-docs`：文档内容层

成功输出形状为：

```json
{
  "ok": true,
  "library_id": "/reactjs/react.dev",
  "query": "useEffect cleanup",
  "provider": "context7",
  "code_snippets": [],
  "info_snippets": [],
  "results": [],
  "total": 0,
  "content": "...",
  "elapsed_ms": 123.0
}
```

实现会调用 `query-docs`，并把 structured snippets 与 text/content 规范化为上述字段（`src/smart_search/providers/context7.py:304-334`）。这才是 Context7 文档读取层。

### 3. 自动 `search` projection：兼容来源层

当前 projection 丢弃 candidate 的 trust/benchmark/snippet/stars，只留下：

```json
{
  "url": "context7:/reactjs/react.dev",
  "title": "React",
  "description": "...",
  "provider": "context7"
}
```

它以 `url` 名义承载 library ID，并把所有 candidates 返回，而不是使用第一候选。来源是 `src/smart_search/service.py:1818-1827`。随后它同时出现在 `extra_sources` 与合并 `sources`（`src/smart_search/service.py:2303-2324`）。

## 自动化测试契约与引入时间线

### 当前测试实际锁定了什么

- provider contract：Remote MCP initialize/session、`resolve-library-id` JSON、`query-docs` SSE，见 `tests/test_providers_new.py:120-233`。
- provider parser 保留上游第一项顺序，并能从 documented text 解析 library 元数据，见 `tests/test_providers_new.py:237-291`。
- 认证不重试且不泄露 key、redirect 不自动跟随、429 可重试、tool error 分类，见 `tests/test_providers_new.py:294-444`。
- 普通 search docs query 路由到 docs_search；测试 fixture 明确使用 `context7:/facebook/react`，但只断言路由字段与 attempts，没有断言该 synthetic URL 在 `sources/extra_sources` 中的契约是否合法，见 `tests/test_service.py:1310-1339`。
- IntentRouter 测试同样用 synthetic URL fixture，重点锁定旧/新 route fields，不锁定 result taxonomy，见 `tests/test_intent_router.py:47-77`。
- smoke 锁定 Context7 空结果后回退 Exa，provider 顺序必须是 Context7→Exa，见 `tests/test_smoke.py:149-175`。
- source provenance 测试锁定 `sources = primary + extra`、`source_warning` 与 Tavily extra source，但没有覆盖 Context7 supplemental 被混入 `extra_sources` 的语义，见 `tests/test_service.py:812-863`。
- regression 锁定 public/packaged Skill 镜像以及 MCP 配置文档，见 `tests/test_regression.py:300-314`；没有锁定 Skill 对 `context7:/` projection 的解释。

### 时间线

| 时间 / commit | 事实性变化 | 与本问题的关系 |
|---|---|---|
| 2026-05-12 `55369d3935875c22ac06932faa98a91752f19c2a` | `feat(search): add capability fallback providers`；首次加入 Context7 provider、`_run_docs_search_fallback`、library candidate→`context7:<id>` projection，并把 supplemental sources 合入 extra/sources。`git blame` 仍把 `service.py:1786-1835` 和 `:2282-2303` 归于该 commit。 | 伪 URL 和 resolve-only 自动链的起点；当时 docs 顺序是 Exa→Context7。 |
| 2026-05-13 `c5f38fe934a450c13abc9a6d39a28b6e83f3b4c6` | `fix(cli): add content output and realtime sports routing`；新增/强化 `web_current_intent`、`supplemental_paths`，并加入“docs query 不应误触 current web search”的测试。当前 `tests/test_service.py:1310-1340` 的大部分 blame 来自该 commit。 | 固化了普通 search 的 capability supplemental 模型，但尚未解决候选类型。 |
| 2026-05-26 `33be99bdf629576bd2f635ba8d0ed14a913f295f` | `feat(skills): add standalone skill sync and rebalance search routing`；将 docs/API/library 顺序调整为 Context7→Exa；当前 `service.py:1794-1797` blame 显示 Context7 先于 Exa。该 commit 也把测试 fixture 改成 `context7:/facebook/react`。 | Context7 projection 从 fallback 变成普通 docs intent 的首选返回形态。 |
| 2026-06-06 18:04 `2a95d1566ca3c347ef3d91c54c21b749e9a21fae` | `feat(router): 新增混合意图路由`；统一输出 required capabilities，普通 `search`/`research` 接入 router，增加 route tests。 | 当前 query 的三路扩张来自这套关键词+语义 capability router；projection 本身未改变。 |
| 2026-06-06 03:43 `067b5c86fc07ab7b83bde47cd971dcacc89da80a` | `feat: add research router and provider beta updates`；引入 live `research` staged workflow，Context7 resolve 后取第一候选并 query docs，Exa candidate 再 fetch。当前 `service.py:1261-1307` 的 blame 全部来自此 commit。 | 从此同一 docs capability 存在普通 search 的 resolve-only 与 research 的两阶段 evidence 两种完成语义。时间戳早于 `2a95d156`，但二者均在当前历史中；表按指定 commit 单列，不据排列推断拓扑。 |
| 2026-07-16 `c61a306b625b79a02b0693d40a468829c20a43a7` | `feat(context7): migrate provider to remote MCP (#15)`；把 REST 改成窄 Remote MCP-only adapter，新增 JSON/SSE/session/redirect/error/retry/key-redaction mock contracts。 | 改的是 transport 与 provider 输出规范；没有改普通 search 的 resolve-only projection 或 `extra_sources/sources` 归类。 |

## 原始设计意图与历史决策

### 已确认事实

- **Discovery-only**：普通 `search` 自 55369d3 起只 resolve libraries，不 query docs；现有 Skill 也明确 `primary_sources/extra_sources` 在 fetch 前只是 discovery candidates（`src/smart_search/assets/skills/smart-search-cli/references/deep-research-mode.md:40-50`）。
- **第一候选**：`research` 明确取 `results[0]`（`src/smart_search/service.py:1270-1277`）。[Issue #4 resolution](https://github.com/jfmoe/smartsearch/issues/4#issuecomment-4981766654) 与 [Issue #10 resolution](https://github.com/jfmoe/smartsearch/issues/10#issuecomment-4981625877) 再次确认 0.2.0 保留第一候选，不引入 matcher、confidence 或 ambiguity system。
- **Context7→Exa 同能力 fallback**：capability registry 把二者都定义为 `docs_search`（`src/smart_search/service.py:187-203`），当前 provider order 为 Context7→Exa（`src/smart_search/service.py:159-163`），smoke 锁定空结果 fallback（`tests/test_smoke.py:149-175`）。Issue #4/#10/#12/#15 都强调不允许跨能力 fallback。
- **MCP 迁移边界**：[Issue #10](https://github.com/jfmoe/smartsearch/issues/10) 决定 Remote MCP-only、保留两阶段 CLI、无 REST runtime fallback、窄 adapter、旧配置 fail closed；[Issue #15](https://github.com/jfmoe/smartsearch/issues/15) 将其变成 acceptance criteria；[PR #20](https://github.com/jfmoe/smartsearch/pull/20) 以 commit `c61a306` 实施并已合并。
- **无常规完整 E2E**：Issue #10/#12/#15 均明确常规 CI 只做 mock contract，`smoke --live` 只 resolve，不做完整 `resolve→第一候选→query-docs`；PR #20 的交付评论明确当时未执行需要用户 key 的 live 调用。Issue #12 后续台账记录冻结候选曾在用户授权下做过一次本地 query-docs，但那不是常规 CI 契约。

### 显式推断

- **推断 A**：`55369d3` 的目标是把 docs provider 作为 supplemental discovery，而非让其参与主回答生成。依据是 main content 先完成，Context7 后执行，结果只并入 supplemental/extra sources（`src/smart_search/service.py:2240-2304`）。commit message 没有直接写“discovery-only”，所以这不是原作者措辞。
- **推断 B**：`context7:` 可能最初只是为满足通用 `merge_sources` 的 `url` 去重键而做的低成本适配。依据是 merge 函数只接受含 `url` 的 item（`src/smart_search/sources.py:123-136`），projection 恰好把 provider-local ID 填进 `url`。历史资料没有直接说明该动机。
- **推断 C**：MCP migration 保留了旧 projection，是因为 #10/#15 明确要求“保留稳定输出”，而迁移实施集中在 transport。没有证据表明 #10/#15 对普通 `search` 的 synthetic URL 做过单独产品决策。

## Skill 对 `context7:/` 的说明能力

### 当前 Skill 能让模型理解的部分

- 先选 capability，再选 provider（`src/smart_search/assets/skills/smart-search-cli/SKILL.md:14-21`）。
- Context7 用 Remote MCP 的 `resolve-library-id` 与 `query-docs`；自动流程保持第一候选；redirect 不自动跟随；显式命令报分类错误；自动 docs_search 只可同能力回退 Exa（`src/smart_search/assets/skills/smart-search-cli/references/provider-routing.md:55-67`）。
- `context7-library` 与 `context7-docs` 的成功字段不同（`src/smart_search/assets/skills/smart-search-cli/references/cli-core.md:60-73`）。
- `primary_sources`、`extra_sources` 不是自动 evidence，关键 URL 应 fetch（`src/smart_search/assets/skills/smart-search-cli/references/deep-research-mode.md:40-50`）。

### 当前 Skill 没有说明的部分

- literal `context7:/` 的存在与语义；
- 普通 `search` 只 resolve，不 query docs；
- 普通 `search` 返回所有 candidates，而 `research` 取第一候选；
- candidates 被放入 `extra_sources`，再兼容合入 `sources`；
- `docs_search=ok` 只是 library resolution 成功；
- `context7:` 不能交给 fetch，虽 `research` 源码会过滤它。

Git 核验结果必须精确限定范围：

- `git log --all -S'context7:/' -- skills/smart-search-cli src/smart_search/assets/skills/smart-search-cli`：**无匹配**。
- 当前两份 Skill tree 上 `rg -F 'context7:/'`：**无匹配**。
- 仓库全局 `git log --all -S'context7:/'`：有 `33be99b`、`2a95d15` 两个匹配，来自测试 fixture；当前仓库 literal 只见 `tests/test_service.py:1321` 与 `tests/test_intent_router.py:58`。

**推断**：模型能稳定理解“Context7 是 docs provider、两阶段、第一候选、同能力 fallback、候选不等于证据”；它不能仅凭 Skill 稳定判断 `context7:/...` 是不可抓取的 library candidate，更不能稳定解释它为何同时出现在 `sources` 和 `extra_sources`。这种理解目前依赖读取实现或 artifact，而不是 Skill contract。

## 已确定的问题

### 1. 伪 URL 占用 source URL 字段

`context7:/react/react` 是 provider-local reference，不是官方博客或 GitHub Release URL。CLI 会把它渲染成可点击 Markdown link（`src/smart_search/cli.py:843-860`），下游若默认 `sources[].url` 可访问，会得到错误行为。`research` 已通过显式 `startswith("context7:")` 过滤承认它不可作为 fetch candidate（`src/smart_search/service.py:786-797`）。

### 2. `sources` / `extra_sources` 语义混淆

Skill 当前把 `extra_sources` 定义为 `--extra-sources` 产生的并行 Tavily/Firecrawl candidates，并把 `sources` 定义为 primary+extra（`src/smart_search/assets/skills/smart-search-cli/references/provider-routing.md:12-18`）。实现却把 docs/web/fetch/vertical supplemental results 全部并入 `extra_sources`（`src/smart_search/service.py:2282-2304`）。artifact 直接展示 Context7 candidates 在其中。文档与实现已漂移。

### 3. `docs_search=ok` 阶段误导

普通 search 的 `ok` 只要求 library candidates 非空（`src/smart_search/service.py:1815-1830`）；research 的 docs attempt 要先 resolve，再以另一次 attempt 记录 query-docs content 成功（`src/smart_search/service.py:1270-1292`）。相同 capability/provider/status 字段没有 phase，观察者无法区分“resolved candidates”与“retrieved docs”。

### 4. provider-routing 文档与旧实现漂移

当前 provider-routing 写的是 “resolve a library, then query it with query-docs” 且 “Keep the returned first candidate for automatic Context7 flows”（`src/smart_search/assets/skills/smart-search-cli/references/provider-routing.md:66-67`）。这与 `research` 一致，却与普通 `search` 的“resolve all→project all→return”不一致。另一个漂移是 extra_sources 的范围，如上一节所述。

### 5. React Release 查询路由过宽

规则把 `react` 视为 docs intent，把 `当前/最新` 视为 current web intent，把 `github` 视为 vertical intent（`src/smart_search/intent_router.py:15-39`、`:41-70`、`:98-126`）。该 query 因而触发三条 supplemental paths。对“官方博客/官方 Releases”问题，`vertical_search` 的 codebase/structured vertical 含义没有直接必要；Context7 library resolution 也不直接回答 release/version 事实。artifact 的三 capability 路由验证了这一点。

### 排除项

- **不是 Context7 transport 故障**：本次 attempt 成功且有 3 项；MCP provider tests 也覆盖 initialize/session/resolve/query。只能说“本 artifact 无 transport 故障证据”，不能据此推断上游永不故障。
- **不是单纯问法错误**：用户已经限定官方来源类型和具体问题。改成显式 URL 可触发 `web_fetch`，但产品不应要求用户知道内部 router 才能避免无关 `docs_search/vertical_search`。

## 设计选项与影响范围

以下均为候选方案，不替用户做最终产品决策。

### 选项 A：保持普通 search resolve-only，但分离 library candidates

做法：保留自动 `context7_library`，把结果放进 `library_candidates` 或 Context7 专属字段；不再伪装成 `sources[].url`，`docs_search` attempt 增加 `phase=resolve_library`、`evidence_status=discovery`。

- 优点：最小化 latency 与上游调用；保留现有 discovery 能力；不改变主回答生成时序。
- 缺点：普通 search 仍没有 Context7 docs evidence；调用方需要认识新字段。
- 兼容性：若直接从 `sources/extra_sources` 移除 synthetic 项，会改变 counts 和依赖旧行为的消费者；可先双写并标 deprecation，但双写期间语义问题仍存在。
- 改动范围：`service._run_docs_search_fallback`、search result schema、CLI formatter、Skill/README、service/CLI/router tests。

### 选项 B：引入通用 `supplemental_results`

做法：把所有非 primary supplemental 输出建模为带类型的 union，例如 `kind=library_candidate|web_candidate|fetched_page|vertical_result`、`capability`、`provider`、`reference`、`url`、`evidence_status`；`extra_sources` 只保留真实来源候选。

- 优点：一次解决 Context7、vertical、fetch supplement 等异构结果被压成 source 的问题；可表达 phase 与 evidence 状态。
- 缺点：schema 设计与迁移成本最大；所有 supplemental provider 都需梳理。
- 兼容性：可保留旧 fields 一期，但必须定义旧 counts 与新 typed results 的关系，避免再次出现双重真相。
- 改动范围：service 结果模型、source merge/dedupe、所有 formatter、Skill/README、回归/CLI/service tests，可能影响外部脚本。

### 选项 C：普通 search 执行两阶段 `query-docs`

做法：resolve 后按既有决策取第一候选，调用 `context7_docs`；把 docs content 作为 typed supplemental evidence，而不是把 library ID 填进 URL。

- 优点：`docs_search=ok` 可以代表真实 docs retrieval；普通 search 与 research 的 Context7 语义收敛；更符合当前 provider-routing 文档。
- 缺点：增加一次 MCP session/调用与 latency；继续依赖上游第一候选；main content 已先生成，若不新增二次 synthesis，docs evidence仍不会自动验证主回答。
- 兼容性：调用数、时延、attempts 与错误/fallback 时序都会变化；需要明确 query-docs 失败是否触发 Exa。
- 改动范围：普通 search orchestration、attempt phase、fallback、输出 schema、性能/timeout、mock tests；可复用 research 的两阶段逻辑，但需避免复制。

### 选项 D：收紧路由与官方域约束

做法：把“版本、release、changelog、官方博客、GitHub Releases”优先归为 web discovery/fetch；`vertical_search` 只在 code/repo structure 等真实垂直意图下触发；docs_search 聚焦 API/reference/how-to。对已知官方域可给 Exa include-domain 或 provider 侧 official-domain policy。

- 优点：直接改善本次 React Release 场景；减少无关 provider、延迟与噪声；更贴合用户来源约束。
- 缺点：关键词规则会增加边界维护；“release notes 既是 docs 又是 current web”仍有模糊区；官方域识别需可测试策略。
- 兼容性：`required_capabilities`、providers_used、attempts 与结果覆盖都会变化；须用 calibration query set 防止 API docs 回归。
- 改动范围：IntentRouter keywords/signals/classifier guard、route calibration data、provider routing/domain filters、router/service tests、Skill。

这些选项可组合，例如 D+A 是“路由先减少误触，仍 resolve-only 但候选分字段”；D+C 是“只有真正 docs intent 才执行两阶段”。组合不代表默认推荐。

## 建议的 grilling 问题

1. 普通 `search` 的 `docs_search` 目标究竟是“发现文档库”还是“取得文档内容”？
2. `sources` 是否应强约束为真实可访问 URL？若是，非 URL provider reference 放哪里？
3. `extra_sources` 是“`--extra-sources` 的并行 web candidates”，还是“所有 supplemental results”？是否愿意更名/分层？
4. 是否允许 `context7-library` 的多个候选对用户可见？若允许，显示全部还是只显示第一候选/最高置信候选？
5. “第一候选”决策仅约束 research 两阶段，还是也约束普通 search 的展示？
6. 普通 search 若执行 query-docs，取得的 content 是否需要进入二次 synthesis 才能称为验证？
7. query-docs 失败时，是否仍按 Context7→Exa fallback；Exa 成功是 discovery success 还是 docs evidence success？
8. attempt 是否必须新增 `phase` 与 `evidence_status`，避免 `docs_search=ok` 的歧义？
9. 是否接受从 `sources/extra_sources` 移除 `context7:` 导致的 breaking count change？需要一版 deprecation 吗？
10. release/version/changelog intent 是否应排除 Context7 resolve，优先 official web domain？
11. query 含 `GitHub Releases` 时，`github` 是否仍应触发 vertical_search，还是只在 codebase/repository structure intent 下触发？
12. 官方来源约束应由 router、provider domain filter，还是 synthesis/evidence gate 执行？哪个层负责失败时 fail closed？
13. 是否要把普通 search 与 research 的 Context7 orchestration 抽成同一深模块，还是保留不同契约并明确命名？
14. 是否补一个 opt-in live full-chain check，以发现上游排序与 query-docs 输出漂移？其频率、key 与失败门槛是什么？

## 不可混淆的决策点

- **transport 与 projection**：Remote MCP 能成功，不代表本地 projection 正确。
- **library selection 与 result taxonomy**：采用第一候选，不回答候选应放 `url` 还是 typed reference。
- **discovery 与 evidence**：resolve 成功、Exa 找到 URL、fetch 取得正文是三个阶段。
- **route selection 与 source restriction**：选对 capability，不自动保证结果只来自用户允许的域。
- **backward compatibility 与语义正确性**：保留 `sources` counts 是兼容性选择，不等于继续伪装 URL 是正确选择。
- **普通 search 与 research**：二者可共享 router，但不必共享完成定义；若定义不同必须在 schema/Skill 中显式表达。

## 可验证成功标准

最终选择方案后，至少应满足：

1. 普通 search 输出中，任何 `sources[].url`/`extra_sources[].url` 都是允许下游访问的 URL；如果产品允许非 HTTP URI，必须有明确 type/schema 和 formatter 行为。
2. Context7 library candidates 保留原始 `id`，不会通过字符串拼接冒充网页 URL。
3. `provider_attempts` 能区分 resolve、query-docs、discovery、fetch；`status=ok` 的阶段含义可机械判断。
4. `source_warning` 与 `extra_sources` 实际来源类型、执行时序一致。
5. 对 artifact 原 query 的 route test 明确期望 capabilities；若选择收紧路由，`vertical_search` 不应仅因字面 `GitHub` 触发。
6. 用户要求“只基于 React 官方博客或 GitHub Releases”时，最终 evidence/source gate 不允许 npm 或非官方候选被当作结论依据；无法满足时显式失败或降级说明。
7. 普通 search 与 research 的 Context7 contract 分别有端到端 mock test，覆盖 output fields，不只覆盖 router metadata。
8. Context7→Exa fallback 仍只在 docs_search 内发生；fallback off 仍只尝试第一 provider。
9. 显式 `context7-library`/`context7-docs` CLI 的既有 stable fields 若决定保持兼容，回归测试继续通过。
10. 当前与 packaged Skill 都说明新 taxonomy；同步检查通过；Skill-scoped 文本能解释非 URL candidates。
11. 不泄露 key；认证、protocol、provider、redirect、timeout 分类保持现有 contracts。
12. 若引入 query-docs 自动阶段，timeout/latency 预算和是否二次 synthesis 有明确测试。

## 修复后 JSON 示例

> **建议，不是现有契约。** 下例示范“选项 A+B 的最小 typed separation”：普通 search 保持 resolve-only，真实 URL 留在 sources，Context7 candidates 放入 `supplemental_results`。字段名与枚举仍需 grilling 决定。

```json
{
  "ok": true,
  "query": "截至当前，React 19.x 的最新稳定版本是什么？……",
  "content": "...",
  "primary_sources": [
    {
      "url": "https://react.dev/blog/2025/10/01/react-19-2",
      "title": "React 19.2"
    }
  ],
  "extra_sources": [
    {
      "url": "https://github.com/react/react/releases",
      "title": "Releases · react/react",
      "provider": "exa",
      "evidence_status": "discovery"
    }
  ],
  "sources": [
    {
      "url": "https://react.dev/blog/2025/10/01/react-19-2",
      "title": "React 19.2"
    },
    {
      "url": "https://github.com/react/react/releases",
      "title": "Releases · react/react",
      "provider": "exa",
      "evidence_status": "discovery"
    }
  ],
  "supplemental_results": [
    {
      "kind": "library_candidate",
      "capability": "docs_search",
      "provider": "context7",
      "library_id": "/reactjs/react.dev",
      "title": "React",
      "description": "React.dev official documentation",
      "evidence_status": "discovery",
      "fetchable": false
    }
  ],
  "provider_attempts": [
    {
      "capability": "docs_search",
      "provider": "context7",
      "phase": "resolve_library",
      "status": "ok",
      "result_count": 3,
      "evidence_status": "discovery"
    }
  ]
}
```

若最终选择选项 C，则建议增加独立 `phase=query_docs` attempt，并将 docs content 放在 typed evidence/supplemental field；仍不建议把 `library_id` 填进 `url`。

## 来源索引

### 当前源码与测试

- Router keyword 与规则：`src/smart_search/intent_router.py:15-126`、`src/smart_search/intent_router.py:350-405`。
- 普通 search router 接入：`src/smart_search/service.py:2024-2106`。
- Context7 自动 resolve/projection：`src/smart_search/service.py:1786-1835`。
- supplemental→extra→sources：`src/smart_search/service.py:2276-2334`。
- research 两阶段 Context7：`src/smart_search/service.py:1213-1307`。
- research fetch/evidence gate：`src/smart_search/service.py:1357-1425`。
- Context7 provider 三层规范化：`src/smart_search/providers/context7.py:51-61`、`:155-179`、`:282-337`。
- source merge：`src/smart_search/sources.py:123-136`。
- Markdown source formatter：`src/smart_search/cli.py:843-870`。
- 当前 Skill：`src/smart_search/assets/skills/smart-search-cli/SKILL.md:14-55`；`src/smart_search/assets/skills/smart-search-cli/references/provider-routing.md:12-67`；`src/smart_search/assets/skills/smart-search-cli/references/cli-core.md:60-75`；`src/smart_search/assets/skills/smart-search-cli/references/deep-research-mode.md:40-50`。
- 当前 tests：`tests/test_providers_new.py:120-444`；`tests/test_service.py:506-569`、`:812-863`、`:1310-1339`；`tests/test_intent_router.py:47-77`；`tests/test_smoke.py:149-175`；`tests/test_regression.py:300-314`。
- Artifact：`/tmp/react-19-smart-search.json`，重点 JSON 行 `6`、`31-46`、`55`、`70`、`85-110`、`116-126`、`210-215`、`227`。

### Git commits

- `55369d3935875c22ac06932faa98a91752f19c2a` — 2026-05-12 — `feat(search): add capability fallback providers`。
- `c5f38fe934a450c13abc9a6d39a28b6e83f3b4c6` — 2026-05-13 — `fix(cli): add content output and realtime sports routing`。
- `33be99bdf629576bd2f635ba8d0ed14a913f295f` — 2026-05-26 — `feat(skills): add standalone skill sync and rebalance search routing`。
- `2a95d1566ca3c347ef3d91c54c21b749e9a21fae` — 2026-06-06 — `feat(router): 新增混合意图路由`。
- `067b5c86fc07ab7b83bde47cd971dcacc89da80a` — 2026-06-06 — `feat: add research router and provider beta updates`。
- `c61a306b625b79a02b0693d40a468829c20a43a7` — 2026-07-16 — `feat(context7): migrate provider to remote MCP (#15)`。

### GitHub 一手记录

- [Issue #4：确定 Context7 官方库选择与低置信度回退契约](https://github.com/jfmoe/smartsearch/issues/4)
- [Issue #4 resolution](https://github.com/jfmoe/smartsearch/issues/4#issuecomment-4981766654)
- [Issue #10：选择 Context7 REST 适配还是 MCP 迁移边界](https://github.com/jfmoe/smartsearch/issues/10)
- [Issue #10 决策结论](https://github.com/jfmoe/smartsearch/issues/10#issuecomment-4981625877)
- [Issue #12：实施 @jfmoe/smart-search 0.2.0 个人发行版](https://github.com/jfmoe/smartsearch/issues/12)
- [Issue #12 完成交付台账](https://github.com/jfmoe/smartsearch/issues/12#issuecomment-4986824422)
- [Issue #15：将 Context7 迁移到 Remote MCP-only](https://github.com/jfmoe/smartsearch/issues/15)
- [Issue #15 交付证据](https://github.com/jfmoe/smartsearch/issues/15#issuecomment-4983362052)
- [PR #20：feat(context7): migrate provider to Remote MCP (#15)](https://github.com/jfmoe/smartsearch/pull/20)，head `c61a306b625b79a02b0693d40a468829c20a43a7`，2026-07-16 合并。

## 局限性

- 本调查未实施代码修复，也没有替用户选择最终产品方案。
- 本调查未运行 live Context7 E2E；仅分析现有 artifact、当前 mock contracts 与历史一手记录。
- Issue #12 台账说明冻结候选曾做过一次获授权的本地 query-docs，但本调查没有原始响应可重新核验，故只把它当作历史执行记录，不当作当前上游契约证明。
- Context7 上游实时候选排序可能变化；第一候选策略的正确性仍依赖上游排序。
- artifact 只代表一次 2026-07-17 运行，不能证明所有 query、provider 配置或未来版本都有相同候选与路由。
- 本报告对 `context7:/...` 使用“伪 URL”是为了强调其不是可抓取官方网页；从通用 URI 语法角度它可被视为自定义 scheme-like reference，本报告未做 RFC 合规判定。
