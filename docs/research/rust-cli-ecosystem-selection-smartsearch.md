# Rust CLI 生态选型：smart-search 重写调查

## 调查元数据

- 调查日期：2026-07-24
- 命题：为约 14K 行、含多个网络 provider 的 Python 搜索 CLI 选择 Rust 生态与发布方案。
- 方法：以库/项目的官方 Rustdoc、官方仓库、官方发布文档为准；所有用于结论的网页均先经 `smart-search fetch` 抓取。结论中的“推荐”是工程判断，不是来源原话。
- 隔离：未读取 GitHub issue #54 的评论、`research/rust-cli-ecosystem` 分支或 `docs/research/rust-cli-ecosystem-selection.md`。

## 执行摘要

| 决策面 | 推荐 | 何时改选 | 关键取舍 |
| --- | --- | --- | --- |
| 命令行解析 | `clap`（`derive` 为主，少量边界用 builder） | `bpaf`：组合式解析确有价值；`argh`：极小二进制/特定 Fuchsia 约束；`lexopt`：需完全手写解析 | `clap` 功能与生态最完整，但依赖和编译/二进制成本更高 |
| 并发与 HTTP | `tokio` + 一个复用的 `reqwest::Client` | 极少量同步请求才考虑 `reqwest::blocking` | Tokio runtime 与异步取消/并发模型须贯穿适配层；不要在 core worker 阻塞 |
| 流式输出 | provider 适配器持有协议；标准 SSE 用 `eventsource-stream` | JSONL、`data:` 变体、拼接 JSON 等非标准协议由各 adapter 增量解析 | 不能以一个“通用 SSE parser”掩盖 provider 协议差异 |
| 数据、配置、错误 | `serde`；`figment`；库内 `thiserror`、二进制边界 `anyhow` | 不需要来源追踪/profile 时可用 `config`；需源码定位诊断才加 `miette` | 少依赖优先；把 error 类型和展示层分开 |
| 发布 | 先纯 GitHub Actions 矩阵；交付多平台安装体验时采用 `dist`（原 cargo-dist） | Release PR/发布 crates.io 才叠加 `release-plz`；复杂交叉目标才用 `cross`；用户安装侧支持 `cargo-binstall` | 不把消费者安装器或容器交叉编译器误当成完整发布流水线 |
| 架构参照 | AIChat 的“CLI/配置/客户端/REPL”等目录边界 | 仅借鉴边界，不复刻其功能面 | 多 provider 适配器应向内产出统一领域事件，CLI 不应了解各协议 |

### 维护状态快照

这是 2026-07-24 的可复查快照，不是安全审计。通过 GitHub 官方 API 核验的 `clap`、`bpaf`、`argh`、Tokio、Reqwest、Serde、`config`、`thiserror`、`anyhow`、`miette`、`dist`、`release-plz`、`cross` 与 `cargo-binstall` 均为非 archived，且仓库在 2026 年 5--7 月有 push；其相关官方文档/仓库也已抓取为本报告证据。[S1](https://docs.rs/clap/latest/clap/) [S5](https://docs.rs/tokio/latest/tokio/) [S14](https://axodotdev.github.io/cargo-dist/) [S16](https://github.com/cross-rs/cross) Figment 最近一次可见 push 为 2024-09，AIChat 为 2026-02；二者并非因此不可用，但应在立项时复查 issue 响应、MSRV 与依赖安全，而不把“有 Rustdoc/README”误读为同等活跃。`lexopt` 的 docs 抓取成功，但本轮 API 未能可靠映射其 GitHub 仓库，因此不对它作活跃度结论。

## 背景与范围

本调查只解决重写的生态选择与可迁移架构边界，不承诺逐行移植 Python 行为，也不替某个现有 provider 判定其实际流协议。建议目标结构为：

```text
clap commands
    -> application/use-cases
        -> provider trait + shared request/result/event model (serde)
            -> provider adapters (reqwest; SSE/JSONL/custom parser)
        -> config assembly (figment)
    -> terminal rendering + exit mapping (anyhow/miette)
```

这是工程判断：它把命令行、跨 provider 编排、传输协议和渲染拆在稳定边界；实际字段和错误策略应由现有 Python CLI 的行为测试固定后再设计。

## 1. CLI 框架

### 推荐：`clap`

**当前事实。** `clap` 的官方 Rustdoc 同时提供 derive、builder 教程、子命令/参数关系、帮助文本、补全以及配套的 manpage/completion 工具；其维护目标明确包含多维护者、SemVer 和有限 MSRV 支持。[S1](https://docs.rs/clap/latest/clap/) 这些能力正对多 provider CLI 的子命令、互斥/依赖参数、`--format` 枚举和 shell 补全。

**工程判断。** 以 `derive` 定义稳定的公开命令结构，只有需要动态组装参数或精确保留出现位置的少数边缘情况切至 builder。先将解析结果变成自有 command DTO，再调用应用层，避免让 `clap` 类型渗入 provider 适配器。

**备选与取舍。**

- `bpaf` 同时提供 derive 与组合式 API，且可生成补全、Markdown/HTML/manpage；当解析器本身需要可组合的子部件或非常定制的 usage 时是可信备选。[S2](https://docs.rs/bpaf/latest/bpaf/) 代价是团队需接受较少主流的组合式表达，而此项目没有证据表明这份灵活性是刚需。
- `argh` 明确为代码体积和 Fuchsia 命令行规范优化，公共面主要是 `FromArgs` derive 与 `from_env`。[S3](https://docs.rs/argh/latest/argh/) 对这个功能丰富、跨平台的 CLI，节省体积不足以抵消 `clap` 的成熟功能面。
- `lexopt` 是逐项返回 option/value 的手动解析器；调用方自行解释语义。[S4](https://docs.rs/lexopt/latest/lexopt/) 它适合极小或有特殊语法的工具，不适合将当前复杂 CLI 的参数正确性责任重新手写一遍。

## 2. async runtime 与 HTTP

### 推荐：`tokio` + `reqwest`

**当前事实。** Tokio 提供任务、非阻塞 I/O、定时、同步原语和 runtime；长时间不经过 `.await` 的工作会阻塞 core thread，官方建议此类工作使用 `spawn_blocking` 或专用线程池。[S5](https://docs.rs/tokio/latest/tokio/) `reqwest` 的异步 `Client` 依赖 Tokio，支持 JSON、代理、TLS、重定向和流；官方建议多请求复用一个 `Client`，以利用 keep-alive 连接池。[S6](https://docs.rs/reqwest/latest/reqwest/)

**工程判断。** 每个 process 或可注入的应用容器创建一个 `reqwest::Client`，将 timeout、代理、TLS、默认 headers 和 retry policy 集中配置。每个 provider adapter 接收该 client 与自己的认证/端点设置；并发、超时、取消和限流放在编排层而不是散落在命令实现。解析大响应、阻塞凭据读取或 CPU 密集后处理不得占用 Tokio core thread。

**备选与取舍。** `reqwest::blocking` 只适合确实只有少量同步请求的程序；官方也把它定位为这种场景。[S6](https://docs.rs/reqwest/latest/reqwest/) 此处存在流式多 provider 网络工作，不选它。Tokio 初期可为应用启用 `full` 快速落地；稳定后按实际特性收窄，避免无谓依赖，这是 Tokio 官方对应用/库的不同建议。[S5](https://docs.rs/tokio/latest/tokio/)

## 3. 流式 SSE / 非 SSE 响应

### 推荐：统一事件模型，分协议适配

**当前事实。** `eventsource-stream` 的职责是把“字节数组流”构造成 EventSource/EventStream，并暴露 SSE event 与行解析错误。[S7](https://docs.rs/eventsource-stream/latest/eventsource_stream/) `reqwest` 的 `stream` feature 提供 `futures::Stream` 支持。[S6](https://docs.rs/reqwest/latest/reqwest/)

**工程判断。** 只对符合 SSE framing 的 provider 使用 `response.bytes_stream().eventsource()`；adapter 将 event data 解码为自有 `ProviderEvent`（如 delta、tool-call delta、usage、completed、error）。对 JSON Lines、没有空行分隔的 `data:`、NDJSON、分块 JSON 或厂商私有结束标记，保留独立增量 decoder；它们可以共用 bytes 流、取消与错误分类，但不应强行通过 SSE parser。编排层仅消费统一事件并决定 stdout/JSON 输出、汇聚结果和重试。

**备选与取舍。** 直接自行按行读取可少一个依赖，却会重复实现 SSE 的规范细节；将所有协议抽象成一个过宽的 parser 则会模糊错误和测试边界。适配器级 parser 数量随 provider 增加，但它是正确隔离协议差异的成本。现有 Python provider 的实包与流样例尚未在本调查范围内抓取，因此每个 adapter 的具体 parser 仍须以迁移前契约测试确认。

## 4. 配置、序列化与错误

### 推荐组合：`serde` + `figment` + `thiserror`/`anyhow`；`miette` 按需加入

**当前事实。** Serde 用 `Serialize`/`Deserialize` 把 Rust 数据结构与数据格式相连，避免运行时反射开销。[S8](https://docs.rs/serde/latest/serde/) Figment 能合并 typed configuration providers、区分 `merge`/`join` 的覆盖语义，并跟踪每个值的来源、profile 与错误 key path。[S9](https://docs.rs/figment/latest/figment/) `config` 的定位是层级配置，可叠加 defaults、环境、文件、其他 Config 与程序化 override。[S10](https://docs.rs/config/latest/config/)

**工程判断。**

- 将共享 request/response、配置和持久化结构统一 derive Serde；网络 payload 外围保留 provider-specific DTO，转换到核心模型。
- 本项目有 provider 配置、环境变量、配置文件与命令行覆盖，推荐 Figment：来源追踪能把“哪个 provider 的哪个键来自哪份配置”变成可诊断信息。明确并测试 precedence，不把 secret 值写进错误。
- 内部库/adapter 用 `thiserror` 定义可匹配的领域错误；程序入口、命令编排和 I/O 边界用 `anyhow::Result` 加 `Context`。`thiserror` 是 `std::error::Error` 的 derive，且不构成 public API 锁定；`anyhow` 是面向应用的 trait-object error 类型并提供 Context。[S11](https://docs.rs/thiserror/latest/thiserror/) [S12](https://docs.rs/anyhow/latest/anyhow/)
- 默认不引入 `miette`；当 CLI 要展示配置文件/输入 payload 的源码位置、标签和修复提示时再添加。它的 `Diagnostic` 支持 source span/label，并有 Rust 1.70 的 MSRV 要求。[S13](https://docs.rs/miette/latest/miette/)

**备选与取舍。** 如果最终只需要“文件 < 环境 < CLI 覆盖”而不需来源解释或 profile，`config` 更直白、依赖语义更少。[S10](https://docs.rs/config/latest/config/) 反之，Figment 的 metadata、profile 与 eager merge 是额外复杂度，必须在设计配置 precedence 时显式处理。`anyhow` 不应用作对外可分支的 provider 错误类型；`miette` 的富诊断也不值得覆盖正常 JSON/管道机器输出路径。

## 5. 多平台 GitHub Releases 发布流水线

### 推荐：GitHub Actions 矩阵为基线，`dist` 为二进制发行加速器

**当前事实。** GitHub 的 Rust Actions 指南覆盖 `cargo build`/`cargo test`、缓存、artifact 上传下载与 `gh release create`，可直接构成透明的多平台基线。[S18](https://docs.github.com/en/actions/use-cases-and-examples/building-and-testing/building-and-testing-rust) `dist`（原 cargo-dist）可完成 plan/build/host/publish/announce，产出 archives、installers、机器可读 manifest，并由 `dist init` 生成 GitHub CI release pipeline。[S14](https://axodotdev.github.io/cargo-dist/)

**工程判断。** 第一阶段写明确定义的 GitHub Actions matrix：Linux x86_64/aarch64、macOS Apple Silicon/Intel、Windows x86_64；每个 target 运行测试、产物 smoke、校验和并上传 artifact。发布 job 用 tag 驱动、最小权限、显式 provenance/签名策略。待稳定提供 GitHub Releases 二进制和安装脚本时，采用 `dist` 取代手写包装矩阵；它恰好覆盖本项目的 archive、installer 与 release 需求。

**备选与取舍。**

- `release-plz` 的强项是 CI 中创建 Release PR、更新 changelog 与版本、合并后创建 tag/release 并发布 crates.io。[S15](https://release-plz.ieni.dev/) 若仅发布一个 CLI 二进制，先不引入；若工作区 crates 或 crates.io 发布成为目标，再与 `dist` 分工使用，避免让二者竞争发布职责。
- `cross` 提供交叉编译和 cross testing，但需要 Docker/Podman；跨架构测试还要求 Linux `binfmt_misc`。[S16](https://github.com/cross-rs/cross) 它适合原生 runner 缺失的 Linux target，不是默认 macOS/Windows 发布方案，也会引入容器供应链与调试成本。
- `cargo-binstall` 是用户侧 `cargo install` 的预编译二进制替代：它从 release artifacts 等位置寻找 binary，并在找不到时退化到编译安装。[S17](https://github.com/cargo-bins/cargo-binstall) 应让发布物兼容它，但它不是 CI、签名或 Release 发布工具。
- 纯 GitHub Actions 的优点是可见、可逐步落地；代价是自己维护 target、archive、installer、更新 manifest 与 release glue。若只给开发者/内部用户，这是合理终点；若面向广泛下载，`dist` 的自动化价值更高。

## 6. 同类 Rust CLI 架构参考

### AIChat：可借鉴“边界”，不借鉴“功能面积”

**当前事实。** AIChat 是 Rust 多 provider CLI，README 声明通过统一接口集成 20 多家 provider，提供 CMD/REPL、多形态输入、流式 API 使用场景，并为 macOS/Linux/Windows 发布预构建二进制。[S19](https://github.com/sigoden/aichat) 其 `src` 顶层实际区分 `client`、`config`、`repl`、`render`、`rag` 与 CLI/serve 入口。[S20](https://github.com/sigoden/aichat/tree/main/src)

**工程判断。** 这是对 smart-search 最有价值的结构参照：把 provider 客户端与配置、交互模式和展示拆开。建议只提炼以下原则：

- provider adapter 拥有请求构造、认证、响应/流解析和协议错误；
- 应用层拥有 provider 选择、fallback、并发和统一结果；
- CLI/JSON renderer 只订阅统一结果与事件，不能分支处理厂商字段；
- REPL、HTTP serve 等非当前目标必须保持在核心搜索模块之外，不能因参照项目存在而扩展本次重写范围。

AIChat 的 README 和目录证明它是相关且活跃的参考，不证明其任一实现细节必然适合网络搜索。因此未把它的依赖、配置格式或发布脚本直接当作推荐。

## 与 issue #54 原报告的交叉比对

本节由主线程在上述独立研究完成后补写。比对对象是 2026-07-23 的原报告 `research/rust-cli-ecosystem` 分支 `docs/research/rust-cli-ecosystem-selection.md`；它不影响前述研究的隔离性。

| 决策面 | 一致处 | 差异 | 综合判断 |
| --- | --- | --- | --- |
| CLI 框架 | 都推荐 `clap` derive，并把 `bpaf`、`argh`、`lexopt` 视为有明确特殊约束时的备选 | 原报告更强调现有 30+ 子命令、alias、补全和 WG-CLI 承诺；独立报告更强调先转成自有 command DTO | 结论稳定：采用 `clap` derive，builder 只用于少数动态边界，解析类型不进入 provider 层 |
| async / HTTP | 都推荐 Tokio + Reqwest | 原报告明确要求 `rustls-tls` 与 `stream` feature；独立报告补充复用单个 `reqwest::Client`、隔离阻塞工作 | 合并两者：Tokio + 复用的 Reqwest client，关闭默认 TLS 后显式选 rustls，并按实际流式路径启用 `stream` |
| 流式协议 | 都同意标准 SSE 与 NDJSON/私有分块协议不能混为一谈 | 原报告默认 `reqwest-eventsource` 自动重连，精细控制时才用 `eventsource-stream`；独立报告默认 parser 由 adapter 持有，标准 SSE 用 `eventsource-stream`，不默认自动重连 | 独立报告更贴合当前代码事实：xAI Responses、OpenAI-compatible、Context7 已有不同终止条件与错误语义。默认用 adapter + `eventsource-stream`；只有确认请求可安全重放、事件 ID/重连语义适用时才引入 `reqwest-eventsource` |
| 配置 / 错误 | 都推荐 Serde + Figment + `thiserror`/`anyhow` 分层 | 原报告把 Miette 列入默认组合；独立报告把它降为人类可读诊断的可选层，并指出 Figment 仓库最近可见 push 停在 2024-09 | 采用 Serde、Figment、`thiserror`、`anyhow`；Miette 仅用于需要源码 span/help 的 stderr 路径，机器 JSON 错误不依赖它。锁版本前复查 Figment 维护与 MSRV |
| 发布 | 都认可 `dist`、`release-plz`、`cross`、`cargo-binstall` 的职责不同 | 原报告直接推荐 `dist` + `release-plz`；独立报告先以纯 Actions 为透明基线，二进制发行成熟后再上 `dist`，`release-plz` 仅在 Release PR/crates.io 有需求时加入 | 结合 #52 已定的“放弃 npm、GitHub Releases、分发体验优先”，应直接用 `dist` 作为主线；但不必因“完整组合”提前引入 `release-plz`。保留最小纯 Actions 流水线作为可迁移退路 |
| 架构参考 | 都选择 AIChat，并都反对照搬 REPL/UI | 原报告深入到 `Client` trait、默认方法和 `register_client!` tagged enum；独立报告只从目录边界得出 adapter/application/render 分层 | 原报告在此证据更深。可借鉴 trait + 每 provider 一模块 + tagged config；宏只在实际重复出现后引入，避免先复制 AIChat 的复杂度 |

总体上，两份报告对核心依赖没有方向性冲突。独立研究带来的实质修正有三项：**不默认给所有 SSE 请求自动重连、Miette 按需引入、release-plz 不作为首日必选**。原报告仍在“结合 smart-search 现状”和“深读 AIChat provider 抽象”两方面更强；独立报告在依赖边界、当前维护风险和最小实现原则上更谨慎。

当前仓库也支持上述流式修正：`src/smart_search/providers/xai_responses.py` 等待 `response.completed`，`src/smart_search/providers/openai_compatible.py` 识别 `[DONE]` 并有 stream → non-stream fallback，`src/smart_search/providers/context7.py` 则解析可多行的 JSON-RPC SSE 消息。三者共享字节流基础设施合理，共享“自动重连即正确”的策略并不合理。

## Smart Search 执行记录与异常

| 项目 | 结果 |
| --- | --- |
| 预检 | `smart-search doctor --format json`：`ok: true`；主搜索、Exa、Tavily、Jina、Context7、Zhipu 均报告可用。凭据均为工具掩码输出，未写入本报告。 |
| 强制深度执行 | 运行：`smart-search research "为把约 14K 行 Python 多 provider 网络搜索 CLI 重写为 Rust 做选型调研：比较 CLI 框架（clap、bpaf、argh、lexopt 等）、async runtime 与 HTTP 客户端（tokio/reqwest 等）、标准 SSE 与非标准流式响应处理、配置/序列化/错误处理惯用库（serde、figment、config、thiserror、anyhow、miette 等）、多平台 GitHub Releases 发布流水线（dist/cargo-dist、release-plz、cross、cargo-binstall、纯 GitHub Actions 备选）的当前维护状态与最佳实践，并深入核查 1–2 个架构可借鉴的同类 Rust 多 provider CLI。每项给出推荐、理由、一手证据与取舍。" --budget deep --fallback auto --evidence-dir /tmp/smartsearch-research-54.0fIBGB/agent-evidence --format json --output /tmp/smartsearch-research-54.0fIBGB/agent-research.json`。最终执行记录在 `agent-evidence/summary.json`，`ok: true`、`gap_check: closed`、`fallback_used: true`、最终 `degraded: false`。 |
| provider attempts | docs：Context7 成功；web：Zhipu 空结果后由 Tavily 成功（同 capability fallback）；vertical：AnySearch 成功；页面抓取：Jina 六次成功。路由阶段因 embeddings/classifier 未配置显示 rules-only 的 `degraded: true`，但执行最终以已抓取证据闭环。 |
| 异常 | 命令最初未在指定 `--output` 位置看到 `agent-research.json`；稍后发现执行器将汇总稳定写至证据目录的 `summary.json`。这是输出路径行为不一致，非证据缺失；报告以该 summary 及逐页 fetch 文件为准。 |
| 计划质量 | 主线程的 `smart-search deep` 把命题中的“14K 行 Python”误解析为 Context7 库名 `K Python`，并生成了不可直接执行的库文档步骤。说明离线 planner 的分解与实体提取必须人工审阅。 |
| 自动汇总质量 | `summary.json` 虽标记 `gap_check: closed`，但自动答案仍混入 Rust 论坛、LogRocket 和无关的 Rust Releases 页面；它不足以单独支持本报告。报告实际采用后续逐页 `smart-search fetch` 的官方 Rustdoc、官方项目文档和官方仓库证据。 |
| 与原“WebSearch 限流”的关系 | 本轮没有 429 或 rate-limit：Zhipu 是空结果，随后 Tavily 同能力 fallback 成功，Context7、AnySearch、Jina 也成功。但本轮走的是 smart-search provider 链，不是 Claude Code 的 WebSearch 工具，因此只能证明“当前 Smart Search 路径可用”，不能反证 2026-07-23 的 Claude WebSearch 限流记录。 |
| 补充抓取 | 逐页保存于 `/tmp/smartsearch-research-54.0fIBGB/agent-evidence/fetch-*.md`：CLI 框架、runtime/HTTP/SSE、配置/错误、发布工具、GitHub Actions 和 AIChat。所有关键网页结论在写作前已 fetch。 |
| 维护状态核验 | 运行 `gh repo view <owner/repo> --json nameWithOwner,isArchived,pushedAt,latestRelease`；输出见当前会话。`danielkeep/lexopt` 查询无法解析为仓库，已在快照中按“无法可靠映射”披露，未据此得出弃用结论。 |

## 来源索引

| 编号 | 一手来源 | 支撑内容 |
| --- | --- | --- |
| S1 | <https://docs.rs/clap/latest/clap/> | clap 能力、维护目标、MSRV |
| S2 | <https://docs.rs/bpaf/latest/bpaf/> | derive/combinatoric API、补全与文档生成 |
| S3 | <https://docs.rs/argh/latest/argh/> | 代码体积/Fuchsia 取向 |
| S4 | <https://docs.rs/lexopt/latest/lexopt/> | 手动 option/value 流模型 |
| S5 | <https://docs.rs/tokio/latest/tokio/> | runtime、features、阻塞工作约束 |
| S6 | <https://docs.rs/reqwest/latest/reqwest/> | 异步 Client、连接池、stream feature |
| S7 | <https://docs.rs/eventsource-stream/latest/eventsource_stream/> | bytes stream 到 SSE event stream |
| S8 | <https://docs.rs/serde/latest/serde/> | 序列化模型 |
| S9 | <https://docs.rs/figment/latest/figment/> | provider 合并、metadata/profile |
| S10 | <https://docs.rs/config/latest/config/> | 分层配置备选 |
| S11 | <https://docs.rs/thiserror/latest/thiserror/> | 库错误 derive |
| S12 | <https://docs.rs/anyhow/latest/anyhow/> | 应用边界错误与 Context |
| S13 | <https://docs.rs/miette/latest/miette/> | 诊断 span/label、MSRV |
| S14 | <https://axodotdev.github.io/cargo-dist/> | dist 发行能力与 GitHub CI |
| S15 | <https://release-plz.ieni.dev/> | Release PR、版本/changelog/publish |
| S16 | <https://github.com/cross-rs/cross> | cross 的容器与 binfmt 前提 |
| S17 | <https://github.com/cargo-bins/cargo-binstall> | 预构建 binary 安装器定位 |
| S18 | <https://docs.github.com/en/actions/use-cases-and-examples/building-and-testing/building-and-testing-rust> | Actions build/test/artifact/release 基线 |
| S19 | <https://github.com/sigoden/aichat> | 多 provider CLI、交互与多平台发行 |
| S20 | <https://github.com/sigoden/aichat/tree/main/src> | AIChat 顶层模块边界 |

## 局限性

- 本文是生态与架构选型，不是现有 Python CLI 的行为规格。迁移前仍需把每个命令、配置优先级、错误码、重试、输出 JSON 与 provider 流协议编成可回归的契约测试。
- “维护状态”基于 2026-07-24 抓取时的官方页面/仓库可见资料，不能保证未来版本兼容；实际锁定依赖前应再次检查 MSRV、许可证、安全公告和平台 CI。
- AIChat 只作为一个经过源码目录核查的参考；没有对其内部每个 adapter、依赖版本或性能作审计。
- 本次没有构建 Rust 原型、没有验证交叉目标，也没有获取目标 Python 的真实 streaming captures；上述项目级决策仍需要一个小的 golden-path spike 验证。
