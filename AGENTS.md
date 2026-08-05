# 项目记忆

## [优化] 2026-08-05：create-sub-agent 安装脚本同步（skill-updater）

### 变更内容

新增 `create-sub-agent` 技能后，按 skill-updater 规范同步 3 处（3 个文件，均验证通过）：

1. `scripts/skill-install.sh`：静态 FILES 数组新增 3 条（`create-sub-agent/SKILL.md` + examples + reference，插在 create-skill 之后）
2. `scripts/skill-install.ps1`：静态 $files 数组同步新增 3 条
3. `README.md`："技能一览"表格新增 create-sub-agent 行（作用描述 + 触发词取自 frontmatter description）

### 验证结果

- 两脚本 skills 列表各 97 条，diff 完全一致 ✓
- `bash -n` 语法 OK，read_lints 无错误 ✓
- `skill-updater` 仍排除在静态列表外（仅保留 API 跳过逻辑）✓
- README 链接 `./skills/create-sub-agent/SKILL.md` 真实存在 ✓

### 关键约束（勿破坏）

- 静态列表只能从 `search_file` 扫描结果自动生成，不可手写（skill-updater 规范）
- README"技能一览"是技能清单唯一来源，"项目结构"树不逐技能同步

## [需求] 2026-08-05：新建 create-sub-agent skill（创建子 Agent）

### 用户需求

编写一个指导"用户创建子 Agent"的 skill。目录结构参考 `agents/sub-agent/`：`agents/` 或 `.agents/{agent-name}/` 下含 `agent.md`（agent 描述）、`rules/`（规则，规范同 create-rules skill）、`skills/`（专属 skill，规范同通用 skill，直接引用）。

### 修改文件（3 个新建，无 lint 错误）

- `skills/create-sub-agent/SKILL.md`：创建工作流（收集需求 → 目录骨架 → agent.md 编写 → rules/ → skills/ → 验证清单），各目录职责表 + 规范来源引用
- `skills/create-sub-agent/reference.md`：agent.md 完整模板（角色定位/能力假设/权限边界/任务边界/输入契约/执行要求/输出契约/失败上报/自检清单）+ 剪裁原则
- `skills/create-sub-agent/examples.md`：接口测试子 Agent（api-tester）完整创建示例 + 何时不新建对照表

### 关键约束（勿破坏）

- agent.md 结构单一事实源：参考 `agents/sub-agent/agent.md`，三段式输出契约骨架不变
- rules/ 规范以 create-rules skill 为准（SKILL.md 只引用不重复）
- skills/ 规范以 create-skill skill 为准（直接引用）
- 新增 agent 目录放 `agents/`（或 `.agents/`），命名 kebab-case

### challenger 质疑修复（2 处）

1. 运行环境依赖风险：SKILL.md 强依赖 create-rules / create-skill 可用 → 阶段 3/4 补充"环境缺失时按最小规范直接创建"兜底
2. 专属 skill 流程过重：明确"专属 skill 规模小，给出 SKILL.md（frontmatter + 概述 + 核心指令）即可，不必完整走 create-skill 全流程"

## [需求/重构] 2026-08-05：topic-teach 重构（多阶段大纲 + course-reviewer 评审 + 分批生成 + SVG）

### 用户需求（经 requirement-mining 确认）

将 topic-teach 从「单层课程表 + 逐课接力」升级为工程化教学体系：① 新建方案评审 agent（用户定名 **course-reviewer**）；② 大纲升级为「阶段 → 课 → 知识点」三层结构，每阶段有概览文件；③ 全阶段总览文件（学习路径总览）；④ 删除 HTML，改用 SVG；⑤ 大纲落盘前先经评审 + 用户确认；⑥ 禁止一次性生成整个阶段，按批次（3–5 知识点/批）生成确认。

### 修改文件（4 个，无 lint 错误）

- `agents/sub-agent/course-reviewer.md`（**新建**）：评审 agent，参考 `agent.md` 三段式输出契约 + 失败上报机制；评审维度 = 教学逻辑/准确性/完整性/格式规范/一致性；意见分级 P0/P1/P2；评审节点 = 大纲/阶段概览/路径总览/批次内容/速览
- `skills/topic-teach/SKILL.md`（重写）：多阶段大纲（Phase 1 三步：生成→评审→确认落盘）、分批次生成（Phase 2 每批四步：生成→评审→确认→落盘）、SVG 替换 HTML、知识点级进度表、评审记录、旧版产物兼容续学
- `skills/topic-teach/reference.md`（重写）：新增多阶段大纲/学习路径总览/阶段概览/评审记录模板，删 HTML 模板，新增 SVG 图表规范（对齐 document-writer 选型规则）
- `skills/topic-teach/examples.md`（重写）：知识点粒度单课示例、含评审记录的学习档案示例、SVG 用法示例

### challenger 质疑后修复（4 处）

1. 旧版产物（`01-知识地图.md` / 根级 `lessons/` / 课时级进度表）断点续学兼容 → SKILL.md 断点续学处补充回退逻辑
2. 用户确认阶段对大纲增删调序后是否重新评审 → 明确"用户确认即终稿；改变前置依赖则重过 course-reviewer 轻量评审"
3. 一课拆多批时接力提示词覆盖更新 → SKILL.md + reference.md 补充"随批次更新，始终指向下一批"
4. 课骨架与首批生成的关系 → 明确"首批在骨架上展开正文"

### 目录结构（勿破坏）

```
.teach-topics/{topic-slug}/
├── 00-学习档案.md          # 画像 + 知识点级进度表 + 大纲调整记录 + 评审记录
├── 01-学习路径总览.md      # 全阶段总览 + 阶段依赖图（SVG）
├── assets/                 # 根级 SVG（总览/手册引用）
├── stages/stage-NN-{slug}/
│   ├── overview.md         # 阶段概览（目标/重点/必须掌握知识点 + 路径图 SVG）
│   ├── lessons/lesson-NN-{slug}.md
│   └── assets/             # 本阶段 SVG
├── final-课程手册.md
├── 07-知识点对齐.md
└── quiz-history/
```

### 关键约束（勿破坏）

- course-reviewer 提示词唯一事实源在 `agents/sub-agent/course-reviewer.md`，SKILL.md 只引用路径不重复内容
- SVG 选型对齐 document-writer：默认 mermaid，出现触发信号（分支回环密/交叉连线/需泳道/扇入扇出大/需精确位置）或属学习路径/阶段依赖总览图 → 用 SVG 独立文件（`assets/`，kebab-case 命名）；不使用 HTML，不使用内联 SVG
- 批次边界默认对齐课（一课 ≤5 知识点 = 一批；>5 拆多批）
- 禁止一次性生成整个阶段内容；每批必须：事实核查闸门 → course-reviewer 评审（含格式）→ 用户确认 → 落盘
- 结构性大纲调整须重新过 course-reviewer 评审

## [决策] 2026-08-03

### 当前变更：expert-team 增加"专家创建资格判断门"

用户需求：创建专家前需判断目标代码/知识是否**专属于某功能领域**且**复杂度较高、代码量较大**，符合才推荐建专家；公共/横切知识（工具库、代码风格约定等）不建专家，推荐存入项目记忆。

### 修改文件

- `skills/expert-team/SKILL.md`（5 处，无 lint 问题）

### 改动内容

1. **前置守门新增「3. 专家创建资格判断（领域专属 × 复杂度/规模）」**（原"项目全局资产检查"顺延为 4）：
   - 三维判定表：领域专属性 / 复杂度 / 代码规模（✅ 符合 → 推荐建专家；❌ 不符合 → 不建专家）
   - 四条判定结论：① 领域专属且复杂度高或规模大 → 建专家；② 公共/横切知识 → 转存项目记忆，停止创建；③ 领域专属但规模小/逻辑简单 → 直接读代码或 module-teach，停止创建；④ 用户坚持要建 → 提示成本后按意愿执行
   - loop-discovery 可用/不可用两条路径均汇入此判断门（第 1、2 条已改指向）
2. **AI 说明层「功能」链路开头**加入"创建前资格判断"环节
3. **核心原则新增第 16 条「专家资格判断」**
4. **行为边界新增「创建前资格判断」**
5. **验证清单新增第 16 条**（资格判断验证）

### 关键点

- 公共/横切知识清单：工具库（utils/helpers/commons）、通用封装、代码风格约定、通用算法、基础设施（第三方库/框架/标准库）
- 简单模块替代路径：直接读代码或 module-teach 讲解
- 项目记忆的存储方式不在 expert-team 内展开，交由项目记忆规则承接
- 与 loop-discovery 的关系：loop-discovery 判"是否沉淀/沉淀成什么"，资格判断门判"够不够格当专家"，两者互补

## [优化] 2026-08-03（challenger 质疑后全面落地）

### 质疑建议落实（4 条）

1. **意见1（🟡）边界指引**：expert-team 资格判断门新增「边界指引」小节——
   - 规模小但逻辑显著复杂（状态机/并发/长链路）→ 可建专家（复杂度优先于规模）
   - 规模大但纯样板代码（CRUD 模板化）→ 不建全量专家，降级为子专家或轻量记录
   - 模块内公共子包（如告警模块内 utils/）→ 归入所属业务专家范围，不单独建专家；确属全项目横切的独立包才触发公共知识判定
2. **意见2（🟡）expert-lookup 联动**：3 处——
   - 核心原则 8「结果非阻塞」补充"公共/横切知识除外，转存项目记忆"
   - Step 5「未采用任何专家时」建议文案补充公共知识不建专家提示
   - 「未找到专家」输出模板补充"公共/横切知识则存入项目记忆"
3. **意见3（🟢）规模阈值明确**："≥ 5~10 个"→"≥ 5 个（相对项目整体规模判断）"
4. **意见4（🟢）模块内公共子包归属**：并入边界指引

### 修改文件

- `skills/expert-team/SKILL.md`（边界指引 + 规模阈值）
- `skills/expert-lookup/SKILL.md`（3 处联动）
- 均无 lint 错误

## [Bug修复] 2026-08-03：requirement-mgr 版本号显示不一致

### 问题

安装 `requirement-mgr 0.2.0-beta` 后，`req --version` 仍显示 `0.1.0-beta`。

### 根因

- 版本号**双源**：`pyproject.toml` version = `0.2.0-beta`（wheel 元数据），但 `src/requirement_mgr/__init__.py` 硬编码 `__version__ = "0.1.0-beta"`（`cli.py:42` 的 `--version` 读取此值）
- 发布脚本 `release-requirement-mgr.sh` 只校验 pyproject.toml 与参数一致，**未校验 `__init__.py`**，流程漏洞导致发版漏改
- 连锁影响：`install-latest.sh` 的版本比较短路（`req --version` 输出 vs GitHub tag）会失效，每次强制重装

### 修复（3 处，均已验证）

1. `scripts/requirement-mgr/src/requirement_mgr/__init__.py`：`__version__` 同步为 `"0.2.0-beta"`
2. `scripts/release-requirement-mgr.sh`：新增「1b. 代码 `__version__` 一致性校验」，与 pyproject 校验并列，不一致则中止发布
3. `scripts/requirement-mgr/src/requirement_mgr/cli.py`：`--version` 增加 `-v`/`-V` 短选项（argparse 多 flag 绑定），消除 `unrecognized arguments` 报错

### 验证

- `req --version` / `req -v` / `req -V` → `req 0.2.0-beta` ✓
- 发布脚本版本一致时放行、不一致时拦截 ✓
- 无 lint 错误

### 关键约束（勿破坏）

- 版本号保持人类可读格式 `X.Y.Z-beta`（勿用 PEP440 如 `0.2.0b0`），install-latest.sh 依赖 `req --version` 输出与 tag 字符串一致做比较；故未采用 `importlib.metadata.version()` 动态读取（会返回 `0.2.0b0` 导致比较失效）
- 后续发版必须**同时**更新 pyproject.toml 和 `__init__.py`（发布脚本会强制校验）

## [优化] 2026-08-05：document-writer skill 优化（artifact-optimizer + challenger）

### 评估结论

对 `skills/document-writer/SKILL.md`（含 references/）做 artifact-optimizer 六维评估：23/30 分，无 🔴 问题，主要短板为「内联模板与 references 重复（单一事实源被破坏）」和「跨 skill 边界/耦合」。

### 优化落地（P0+P1 共 6 项）

1. **O-01 模板收敛**：子 agent prompt 改为引用 `references/strategies.md` / `quality-rules.md`（占位符由主 agent 替换为项目内相对路径；子 agent 无法访问时须内联规则保证自包含）
2. **O-02 语言规则**：核心原则新增第 7 条「语言跟随项目」，阶段 1.5 模板增加「文档语言」字段并传递给子 agent
3. **O-03 路径解耦**：子任务编号 `D-{NN}` → `S-{NN}`（对齐 task-dispatch 规范），产出路径改为"以 task-dispatch 调度约定为准"
4. **O-04 长度标准统一**：核心原则 3「不超过一屏」→「≤ 120 行（快速开始一屏内读完）」，与 quality-rules/4.2 检查清单对齐
5. **O-05 确认合并**：阶段 1.5 类型确认 + 阶段 2.3 文档集核定合并；2.3 无论是否一致均输出含触发原因的文档生成计划（用户知情不丢失）
6. **O-06 职责边界**：何时不使用新增 frontend-api-guide（API 调用流程）、expert-team（模块内部资产）边界

### challenger 二次质疑落实（4 条可修复项）

- 质疑 #1 占位符替换规则未定义 → 已补充"项目内相对路径 + 不可访问时内联"说明
- 质疑 #2 合并确认导致拆分依据信息丢失 → 2.3 强制展示触发原因
- 质疑 #6 中文项目名与 task-name 规则矛盾 → 补充"转写为英文短横线"
- 质疑 #4 语言原则无执行落点 → 1.5 模板增加文档语言字段

### 关键约束（勿破坏）

- 与 task-dispatch 协作：编号必须 `S-{NN}`、task-name 遵循英文小写+短横线（本项目已有 `docs-` 前缀约定）
- references 单一事实源：SKILL.md 中涉及模板/规则的细节一律引用 references，避免双源漂移
- README 长度硬上限 120 行，与 quality-rules.md 保持一致

## [需求] 2026-08-05：document-writer 支持 SVG 图表（含 mermaid vs SVG 选型规则）

### 用户需求

文档撰写需支持 SVG 图片，而不仅是 mermaid 图表；需区分何时用 SVG、何时用 mermaid 更简单。

### 落地内容（3 个文件，无 lint 错误）

1. `SKILL.md`：核心原则新增第 8 条「图表按需选型」（四因子：图本质×复杂度×渲染环境×复用需求）；子 agent prompt 注入选型规则；阶段 5 落盘补充 SVG 资产随文档落盘（`assets/` 相对各文档目录）+ 导航概览列 SVG 资产
2. `references/strategies.md`：新增「图表选型规则」小节（六因子决策表 + SVG 两种产出形式 + AI 能力边界 + 常见图表速查 + 判断口诀）；architecture 模板补选型提示
3. `references/quality-rules.md`：新增「图表检查」小节（选型/mermaid/SVG 三组检查项）

### challenger 质疑落实（3 条）

- 🔴 #1 内联 SVG 在 GitHub 被剥离不可见 → 改为「独立 SVG 文件优先；内联仅限支持内联 HTML 的环境（VitePress/VuePress），GitHub 默认不用内联」
- 🟡 #2 SVG 落盘流程缺口 → 阶段 5 补充 SVG 文件落盘与导航展示
- 🟡 #3 缺常见图表速查 → strategies.md 新增速查表（流程图/时序/状态/ER→mermaid；部署拓扑/UI 布局→SVG；架构图按复杂度）

### 关键选型规则（勿破坏）

- **判断口诀**：能讲清关系的用 mermaid；关系复杂到 mermaid 讲不清（分支回环密、连线缠绕）就"画"成 SVG
- **切换 SVG 触发信号**（出现任一即改 SVG，即使节点 ≤ 10）：① 分支/回环密集 ② 交叉连线多 ③ 需泳道/分区语义 ④ 扇入/扇出大（多源汇聚/单源分叉）⑤ 需精确位置/方向控制
- **反向约束**：默认仍用 mermaid，仅出现触发信号才改 SVG，不得因"更精美"随意替换简单图
- SVG 优先独立文件（`assets/`），GitHub 支持 `<img>` 引用 SVG 文件
- AI 只生成结构化简单 SVG；复杂视觉图标注「需设计工具产出」，禁止占位符敷衍
- **架构图（模块总览）统一用 SVG**（不用 mermaid）
- **SVG 命名规范**：kebab-case（全小写短横线）+ 语义化（`{图作用}-{图主题}.svg`，如 `architecture-overview.svg`），存各文档目录 `assets/`，禁用中文/空格/无意义名（`img1.svg`）

## [优化] 2026-08-05：document-writer 二次审查修复（auto-review 全量）

### 审查发现并修复（3 处，均无 lint 错误）

1. **编辑残留 bug**：strategies.md architecture 模板 `## 模块详解` 标题重复两次 → 删除重复
2. **四因子/六因子表述不一致**：SKILL.md 核心原则 8 说"四因子"，strategies.md 因子表有 6 行 → 明确「核心四因子（图本质/复杂度/渲染环境/复用需求）+ 辅助参考（样式需求/资产来源）」，行内标注核心/辅助
3. **README 架构速览边界未说明**：Web 策略的 README 架构速览（文字拓扑）可能被误用为 SVG → 增加边界说明：README 架构速览用文字拓扑、不用 SVG/mermaid；完整模块总览图在 architecture.md 统一用 SVG

### 关键约束（勿破坏）

- **README 架构速览** = 文字拓扑图（轻量导航）；**architecture.md 模块总览** = SVG。两者边界勿混淆

---
当 AI 遇到问题、解决问题或沉淀知识时，**必须先判断问题类型，再按 `expert-solution-workflow` 规则决定走哪条资产复用链路**：

- **业务模块类任务**（使用/接手/排查/修改某模块、跨域任务）→ 按规则查询该模块的经验/解决方案/记忆（业务专家资产）
- **具体技术问题**（报错、配置、部署失败、踩坑）→ 按规则查询相关经验/解决方案/记忆
- **解决问题后**（过程非平凡、场景可复现）→ 按规则沉淀（solution-capture / expert-team / ki 记忆）

规则要点：记忆检索是必经步骤（先看记忆，再带着记忆加载专家/方案内容）；沉淀前先走 loop-discovery 路由。
