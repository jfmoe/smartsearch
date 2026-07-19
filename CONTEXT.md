# Smart Search

Smart Search 按检索能力组织供应方，并把尚未满足自动路由条件的外部能力隔离在显式验收入口中。

## Language

**Agents Skill Target**:
面向遵循通用 Agent Skills 目录约定的内置 Skill 安装目标；它独立于任何单一 AI 工具的专属安装目标。
_Avoid_: Codex target、Codex alias、generic custom path

**Skill Container**:
容纳一个或多个独立 Skill 目录的安装位置；Smart Search Skill 是其中名为 `smart-search-cli` 的子项，而不是容器本身。
_Avoid_: skill directory、smart-search-cli path、installation root

**Skill Installation Preference**:
用户保存在 Smart Search 配置中的一组同质 Skill Container，代表当前完整且权威的目标集合，不取决于最近一次写入是否成功；输入阶段的快捷目标在保存前解析为路径，后续安装与 Automatic Skill Sync 均不再区分路径来源。
_Avoid_: detected tools、temporary targets、last install arguments

**Automatic Skill Sync**:
CLI 版本变化后，在用户首次使用新版本时把内置 Skill 同步到其已保存安装目标的旁路维护过程；它不属于包管理器的安装阶段，也不决定用户原始命令是否成功。
_Avoid_: npm postinstall injection、sync on every command、manual skill update

**AnySearch Acceptance Surface**:
通过显式 AnySearch 命令验证传输、操作和具体垂直域的实验入口；它独立于路由器使用的 Vertical Discovery，不代表域级自动路由已经可用。
_Avoid_: AnySearch capability、AnySearch fallback

**Vertical Search Capability**:
可由检索路由器在明确垂直意图下选择的检索能力，包括 Vertical Discovery，以及针对 Verified Vertical Domain 的结构化搜索。
_Avoid_: AnySearch acceptance surface、web search fallback

**AnySearch Operation Status**:
AnySearch 单项操作的可用状态，分别描述域发现、Vertical Discovery、域级搜索及仍被保留的其他验收操作，不代表任何垂直域已经可供自动路由。
_Avoid_: AnySearch available、vertical search ready

**Verified Vertical Domain**:
必填参数、成功结果和失败行为均已通过域级验收，且路由器能够可靠构造请求的 domain/sub-domain 组合。
_Avoid_: discovered domain、configured domain、supported AnySearch

**Capability Seam**:
围绕一种检索能力定义的稳定契约，只由提供该能力的供应方共享，不要求不同能力具有相同操作。
_Avoid_: universal provider interface、extra search channel

**Documentation Search Capability**:
面向外部库、SDK、API、框架和官方技术文档的检索能力；普通技术知识问答或仅出现技术名词不自动构成该能力需求。
_Avoid_: general technical search、Context7 capability、docs provider

**Supplemental Web Search Capability**:
主搜索之外，为时效、新闻、地区、政策、行情、交叉验证或来源补强提供的 Web 发现能力；它不代表每次普通搜索都会执行的主搜索。
_Avoid_: main search、all web access、web provider

**Web Fetch Capability**:
读取、提取或核验已知 URL 或 PDF 正文的能力；它不负责发现链接，也不包含 AnySearch Extraction 等供应方验收操作。
_Avoid_: web search、link discovery、AnySearch extraction

**Provider Acceptance Operation**:
只属于某个供应方显式验收入口的操作，不构成 Capability Seam，也不允许路由器据此跨能力调用。
_Avoid_: provider capability、fallback operation

**Sub-domain Parameters**:
由具体垂直子域定义的开放结构化参数；它们随 Verified Vertical Domain 的契约变化，不属于通用搜索字段。
_Avoid_: provider arguments、domain flags、vertical search configuration

**Domain Discovery**:
查询父域下可用子域及其参数契约的验收操作；其语义独立于供应方当前使用的工具名称。
_Avoid_: list domains、get sub-domains tool

**Vertical Search Request**:
指向明确 domain/sub-domain 并携带查询和 Sub-domain Parameters 的搜索请求；不指定垂直子域的通用搜索不属于该概念。
_Avoid_: general search、domain-less search

**Vertical Discovery**:
路由器在明确垂直意图下使用无域搜索发现候选的过程；它不证明任何垂直域已验收，也不属于通用 Web Search 兜底。
_Avoid_: general search、web search、verified vertical search

**Batch Discovery**:
通过显式 AnySearch 验收操作批量执行无域发现查询；它不属于 Capability Seam，也不表达批量域级搜索。
_Avoid_: batch vertical search、vertical search fallback

**AnySearch Extraction**:
通过显式 AnySearch 验收操作提取指定 URL 内容；它不构成 Web Fetch 能力，也不参与提取兜底。
_Avoid_: web fetch、fetch fallback、vertical evidence fetch

**Configured AnySearch**:
已显式提供认证凭据的 AnySearch；该状态同时表示允许路由器执行自动 Vertical Discovery。匿名访问只属于显式 Acceptance Surface。
_Avoid_: reachable AnySearch、anonymous AnySearch、enabled endpoint

**Verified Domain Contract**:
经域级验收确认的子域参数与可观察行为约定，是自动域级路由可依赖的稳定知识；实时 Domain Discovery 结果本身不是该契约。
_Avoid_: live schema、discovered schema、upstream manifest

**Verified Domain Manifest**:
受版本控制的 Verified Domain Contracts 集合；只有进入该清单的垂直域才能被声明为已支持，实时发现的新域仍保持未验收状态。
_Avoid_: domain catalog、live discovery result、supported-by-default list

**Automatic Domain Search**:
路由器从自然语言中选择具体垂直子域并构造其 Sub-domain Parameters 的搜索过程；它不同于无域的 Vertical Discovery 和用户指定目标的显式域级搜索。
_Avoid_: vertical discovery、explicit vertical search、vertical intent routing

**Default Search Invocation**:
一次通过 Smart Search 默认聚合搜索入口发起并到达终态的请求，无论结果成功、失败或超时；供应方验收、抓取、诊断及其他专用操作不属于该概念。
_Avoid_: successful search、provider search、all commands

**Search Result Journal**:
启用后按发生顺序保存每次 Default Search Invocation 终态业务结果的本地记录集合；查询、回答和来源属于完整结果，认证凭据不属于可持久化内容。它用于复盘与诊断，不是调试消息流，也不作为搜索响应缓存。
_Avoid_: debug log、response cache、search history

**Caller Capability Declaration**:
调用 Smart Search 的上层模型为一次普通搜索显式声明完整检索能力集合；空集合也是有效声明。声明存在时，它与本地确定性规则结果合并，并取代 embeddings 和 classifier 的远程语义判断；它只能引用 Capability Seam，不能选择供应方或撤销规则已经确认的能力。
_Avoid_: provider override、router hint、capability replacement

**Classifier Capability Decision**:
意图分类器针对一次查询独立给出的完整检索能力集合；规则与 embeddings 只提供非权威证据，因此该结论可脱离其他路由结果评测。运行时它仍与规则和 embeddings 的结果合并，且不能选择供应方。
_Avoid_: classifier additions、classifier patch、provider decision

**Intent Routing Catalog**:
统一拥有 capability 身份与顺序、选择语义、规则词项和语义例句的运行时领域目录；rules、embeddings、classifier、CLI 和生成的 Skill 契约共同消费它，而 provider fallback 与路由控制流不属于该目录。
_Avoid_: Skill capability list、prompt definitions、routing rules DSL
