# 项目记忆

## skill 体系设计

### 设计流程
```
requirement-mining → interaction-design → work-breakdown → data-flow-model → design-craft → demo-verify → 设计评审 → 代码评审
     理解需求            设计交互层           拆成独立切片       数据建模+流图      技术设计       验证风险点
```

### 各 skill 职责边界
- **requirement-mining**：效果导向，不关心实现。挖掘真实需求、根因分析、需求转译。Step 8 落盘归档（结论性摘要）
- **interaction-design**：场景自适应（脚本/CLI、Web、API、SDK、其他）。设计人机交互逻辑
- **work-breakdown**：垂直切片拆分，每个切片贯穿所有层，AFK/HITL 分类。拆完后每个切片独立走 design-craft
- **data-flow-model**：ER 图 + 数据流图。场景自适应（简单CRUD/并发/分布式/实时流/批处理）
- **design-craft**：技术设计文档，默认多文档结构。含阶段 2.3 交互对象总览。每次只处理一个切片
- **demo-verify**：复杂需求自动触发。针对风险点构建验证原型，确认可行后再投入开发
- **implementation-report**：需求完成后生成实现总结报告。与需求摘要一一对应，记录实现结果和关联提交

### 统一存储配置
- 配置文件：`.requirements/config`（storage_path 字段）
- 每个需求一个目录：`{storage_path}/{YYYY-MM-DD}-{feature-name}/`
- 需求摘要：`{storage_path}/{YYYY-MM-DD}-{feature-name}/requirement.md`
- 设计文档：`{storage_path}/{YYYY-MM-DD}-{feature-name}/design/`
- 实现报告：`{storage_path}/{YYYY-MM-DD}-{feature-name}/report.md`
- 各 skill 在落盘时自动读取配置，未配置则询问用户

### design-craft 阶段流程
阶段 0 → 1 → 2 → **2.3（交互对象总览）** → 2.5（需求拆分） → 3 → 4 → 5
