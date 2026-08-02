当 AI（主 Agent）面临辅助类、低认知密度任务（测试验证、文档编写、多轮工具调用、信息收集），或执行核心任务中冒出低难度子步骤时，**按 `task-delegation` 规则判定是否委派子 Agent**，主 Agent 只看结果。

关键判定：子 Agent 的结论能否替代原文——能替代（如多文件搜索汇总）才委派；只是搬运原文（如读单文件）则自己做。核心代码/敏感任务不委派。

> 规则文件：`agents/sub-agent/rules/task-delegation.md`｜子 Agent 提示词：`agents/sub-agent/agent.md`
