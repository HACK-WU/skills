# ui-designer 示例

展示从输入到方案的完整流程。示例 1 为轻量单页（登录页），示例 2 为复杂多页（仪表盘）。

---

## 示例 1：登录页（轻量单页）

### 输入（交互设计文档摘录）

```
S-01 登录场景
- 用户输入账号密码，点击登录
- 校验失败：字段级错误提示 + 登录按钮恢复可用
- 校验成功：跳转首页
- 空输入：提示"请输入账号/密码"
```

### 阶段产出（方案文档 `docs/ui-design/login-page.md`）

```markdown
## 1. 概述
单列居中卡片；桌面优先；无既定设计系统

## 2. 页面结构
布局模式：单列居中卡片（宽 400px 居中）
┌────────────────────────┐
│          Logo          │
│  账号 [____________]   │
│  密码 [____________]   │
│  [    登 录    ]       │
│  注册入口 · 忘记密码    │
└────────────────────────┘
响应式：<576px 卡片占满屏宽（边距 16px）

## 3. 组件状态
| 组件 | 默认 | 悬停 | 聚焦 | 禁用 | 加载 | 错误 |
|------|------|------|------|------|------|------|
| 主按钮 | 主色底+白字 | #0958d9 | — | 灰底灰字 | spinner+禁用 | — |
| 输入框 | 边框 #d9d9d9 | — | 主色边框+浅色描边 | 灰底 | — | 红边框 #ff4d4f |

## 4. 视觉 token
主色 #1677FF · 成功 #52c41a · 错误 #ff4d4f · 间距 4px 基准 · 圆角 6px

## 5. 响应式规则
卡片 400px → 移动端满宽
```

### HTML demo（`demo/login-page/index.html` 骨架）

```html
<style>
  :root { --color-primary:#1677ff; --color-error:#ff4d4f; --radius-md:6px; }
  .card { width:400px; margin:80px auto; padding:24px; border-radius:var(--radius-md);
          box-shadow:0 4px 12px rgba(0,0,0,.1); }
  .field input { width:100%; padding:8px 12px; border:1px solid #d9d9d9; border-radius:var(--radius-md); }
  .field input:focus { outline:none; border-color:var(--color-primary); box-shadow:0 0 0 2px rgba(22,119,255,.2); }
  .error input { border-color:var(--color-error); }
  .btn { width:100%; padding:10px; background:var(--color-primary); color:#fff; border:0; border-radius:var(--radius-md); }
  .btn:disabled { background:#f5f5f5; color:#bfbfbf; }
  @media (max-width:576px) { .card { width:auto; margin:16px; } }
</style>
```

---

## 示例 2：仪表盘（复杂多页，关键页示范）

### 输入（需求描述）

"做一个运维监控后台，能看到服务状态、告警列表和趋势图。主要给运维人员在电脑上用。"

### 阶段 0-1 确认

```
【输入类型】需求描述
【目标设备】桌面优先（运维场景）+ 自适应
【页面清单】P1 总览仪表盘（默认首页）/ P2 告警列表 / P3 服务详情
先设计 P1 示范，其余页面按同一 token 体系套用
```

### 阶段 2 布局（P1 总览）

```
布局模式：侧边栏导航 + 卡片网格
┌──────┬─────────────────────────────────┐
│ 侧栏 │  顶栏（标题 + 用户 + 通知）       │
│ Logo ├─────────────────────────────────┤
│ 总览 │  [在线数][告警数][请求量] 指标卡  │
│ 告警 │  ┌───────┐ ┌───────┐ ┌───────┐ │
│ 服务 │  │ 趋势图 │ │ 状态图 │ │ 分布图 │ │
│ 设置 │  └───────┘ └───────┘ └───────┘ │
│      │  告警列表（最近 10 条）          │
└──────┴─────────────────────────────────┘
响应式：<768px 侧栏收抽屉（汉堡按钮）；指标卡 3→1 列
```

### 阶段 3 组件状态（节选）

| 组件 | 关键状态 |
|------|----------|
| 指标卡 | 正常/数值异常（红字告警） |
| 状态标签 | 运行中（绿）/ 告警（黄）/ 宕机（红）/ 未知（灰） |
| 告警表格 | 空态："暂无告警" 插画 + 文案 |
| 侧栏菜单 | 选中态：主色浅底 + 主色文字 + 左侧竖条 |

### 阶段 4 视觉 token（节选）

```css
:root {
  --color-primary:#1677ff; --color-success:#52c41a;
  --color-warning:#faad14; --color-error:#ff4d4f;
  --color-bg-page:#f5f5f5; --color-bg:#fff;
  --color-text:#1f1f1f; --color-text-secondary:#595959;
  --color-border:#d9d9d9;
  --font-xs:12px; --font-md:16px; --font-xl:24px;
  --space-2:8px; --space-4:16px; --space-5:24px;
  --radius-md:6px; --radius-lg:8px;
  --shadow-sm:0 1px 2px rgba(0,0,0,.06);
  --shadow-md:0 4px 12px rgba(0,0,0,.1);
}
```

### 阶段 6 demo 验收要点

- 侧边栏在 <768px 收为抽屉（JS 切换）
- 状态标签四色齐全，可切换演示
- 告警表格空态可演示（切到"无告警"过滤）
- 指标卡数值异常红字演示
- 全部交互为 mock 数据，不接后端

---

## 两者对照

| 维度 | 示例 1 登录页 | 示例 2 仪表盘 |
|------|---------------|---------------|
| 输入 | 交互设计文档 | 需求描述 |
| 页面数 | 1 | 3（关键页示范 1） |
| 布局 | 单列居中卡片 | 侧边栏 + 卡片网格 |
| 状态重点 | 表单错误/加载 | 状态标签/空态/选中态 |
| 响应式重点 | 卡片收缩 | 侧栏转抽屉、网格降列 |

---

## 风格工具库用法（taste-skill 集成）

当工作区存在 `ui-tools/skills/`（安装见 reference.md「风格工具库」）时，阶段 4.0 按场景加载风格指令：

**示例：用户要"高端精致"的 landing 页**

1. 阶段 0.4 检测到工具库 → 列出可用 skill（`high-end-visual-design`、`design-taste-frontend`…）
2. 阶段 4.0 按路由表选 `high-end-visual-design`，读取 `ui-tools/skills/high-end-visual-design/SKILL.md`
3. 其指令（留白、精致字体、昂贵感阴影）融合进 4.1 的 token 定义与排版决策
4. 用户偏好与工具指令冲突时以用户为准；无匹配或工具库缺失 → 用内置参考色板，流程不中断
