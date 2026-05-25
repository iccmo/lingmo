# Pi Agent 架构分析 & 对灵墨的建设性指导

> 2026-05-26 · 基于对 badlogic/pi-mono 的深入研究

---

## 一、Pi Agent 核心架构

### 1.1 设计哲学：激进极简

| Pi 明确不做 | 理由 |
|------------|------|
| 不做 MCP | 工具定义吃掉 13.7K tokens（~7% 上下文） |
| 不做子 Agent | "黑箱套黑箱" — 用 tmux 保持完全可观测 |
| 不做 plan mode | 计划存在文件里，人类和 Agent 都能编辑 |
| 不做内置 TODO | 用 TODO.md，状态共享且透明 |
| 不做权限弹窗 | YOLO 模式 — 安全靠容器隔离，不靠审批 |
| 不做背景 bash | 用 tmux 管理持久进程 |
| 不做内置压缩 | 社区扩展实现 |

**系统提示词 ~1000 tokens。只有 4 个工具：read, write, edit, bash。**

### 1.2 技术栈

```
pi-mono 四层架构：
  pi-ai           → 统一 LLM API（OpenAI/Anthropic/Google/Ollama/自定义）
  pi-agent-core   → Agent 循环（状态管理、工具执行、消息处理）
  pi-tui          → 终端 UI（差分渲染，<600行）
  pi-coding-agent → CLI 助手（会话管理、扩展、主题、命令）
```

- TypeScript 全栈，MIT 许可
- JSONL 会话持久化
- jiti 热加载扩展（无需构建步骤）
- 工具参数用 TypeBox schema 验证

### 1.3 扩展系统

```typescript
// 每个扩展是独立 TypeScript 文件
export default function (pi: ExtensionAPI) {
  pi.on("session_start", async (_event, ctx) => { ... });
  pi.registerTool({ name: "my_tool", ... });
  pi.registerCommand("mycommand", { ... });
}
```

关键特性：
- 自动发现（`~/.pi/agent/extensions/`、`.pi/extensions/`）
- 热加载（修改扩展无需重启）
- 虚拟模块（typebox、pi-ai 等无需 npm install）
- Agent 可以写自己的扩展

### 1.4 Session Tree

```
会话历史 = 树状结构（不是线性列表）
每个条目：{ id, parentId, role, content, ... }

功能：
  /tree    → 可视化分支
  fork     → 从任意节点分出子会话
  navigate → 在分支间跳转
  切换分支 → 放弃的分支被摘要后注入上下文
```

### 1.5 Agent Loop

```
用户输入 → 推理 → 工具调用 → 结果 → 循环
支持并行和串行工具执行
AgentHarness 提供：会话持久化、技能加载、压缩
```

---

## 二、灵墨当前状态

### 2.1 已做到的事（与 Pi 理念一致）

| Pi 理念 | 灵墨对应 |
|---------|---------|
| 极简工具 | 约束生成器（一个函数，查7表） ✅ |
| 状态透明 | story_bible 7 张 SQLite 表 ✅ |
| 文件即计划 | unsaid_book（人工维护的隐藏设定） ✅ |
| 模型无关 | 多 provider 支持 ✅ |
| 零权限弹窗 | 单用户设计，无权限系统 ✅ |

### 2.2 与 Pi 理念偏离的地方

| 问题 | 现状 | Pi 的做法 |
|------|------|----------|
| server.py 7000+ 行 | 所有逻辑在一个文件 | 核心<500行 + 独立扩展 |
| Agent 散落各处 | 21个端点 + 14个内部函数 | 每个扩展一个文件 |
| 无热加载 | 改代码需重启 | 热加载 |
| 章节线性 | 章1→章2→章3... | Session Tree 分叉 |
| 模型统一 | 所有任务用一个模型 | 按任务选模型 |

---

## 三、建设性指导

### 3.1 架构：拆成核心 + 扩展

```
当前（反模式）：
  server.py 7000+ 行

目标（Pi 模式）：
  server.py (~500行核心)
  ├── 路由 + 数据库 + 生成循环
  │
  extensions/
  ├── constraint_builder.py   → 查圣经 → 约束
  ├── bible_extractor.py      → LLM提取 → 入库
  ├── consistency_checker.py  → 5类校验
  ├── editor_review.py        → 行级反馈
  ├── deslop_filter.py        → 去AI味
  └── voice_tracker.py        → 偏好学习
```

**标准扩展接口：**
```python
def register(app):  # 注册路由/钩子
def run(ctx):       # 执行逻辑
```

### 3.2 功能：Session Tree（章节分叉）

```
chapters 表加字段：
  parent_chapter INTEGER  ← 分叉点

第21章（林尘的原谅）
├── 第22章-A: 原谅秦默
│   ├── 第23章-A1: 两人合作（主线）
│   └── 第23章-A2: 秦默背叛（放弃的分支）
└── 第22章-B: 不原谅
    └── 第23章-B: 独自行动（被选中继续）

前端：
  - /tree 命令可视化分支
  - 点击节点切换到不同分支
  - 放弃的分支保留，可随时恢复
```

### 3.3 效能：Model Switching（按任务选模型）

```
任务 → 模型映射：
  圣经提取     → flash 模型（便宜，速度快）
  正文生成     → pro 模型（质量，512+ tokens）
  编辑审稿     → pro 模型
  去AI味       → flash 模型（规则明确）
  一致性校验   → 纯规则（零 API 调用）
  约束生成     → 纯 SQL（零 API 调用）
```

### 3.4 体验：YOLO 全自动模式

```
POST /api/novels/{id}/auto-generate
  { "target_chapters": 50, "quality_floor": 0.75 }

流程：
  生成 → 评分 → 及格 → 下一章（自动）
              → 不及格 → 编辑 → 再评分 → 及格 → 继续
                                    → 不及格 → 重试 → 连续3章失败 → 暂停通知
  人类每天打开 → 看新增章节 → 有问题的标注 → 没问题的继续
```

### 3.5 去AI味：集成 pi-deslop 50分评分

```
当前：✂️ 克制编辑 → 只删不加（基础版）

目标：集成 5维50分评分
  直接性（10分） → 陈述 vs 宣告
  节奏（10分）   → 变化 vs 节拍器
  信任（10分）   → 尊重读者智商
  真实性（10分） → 像一个具体的人
  密度（10分）   → 有没有可删的
  
  低于 35/50 → 标记需要重修
```

---

## 四、优先级落地路线

| # | 项目 | 工作量 | 价值 |
|---|------|--------|------|
| 1 | server.py 拆扩展 | 中 | 维护性 ↑↑↑ |
| 2 | 章节分叉 | 中 | 创作灵活性 ↑↑↑ |
| 3 | 任务→模型映射 | 小 | 成本 ↓↓ |
| 4 | 全自动模式 | 中 | 生产力 ↑↑↑ |
| 5 | pi-deslop 集成 | 小 | 文字质量 ↑ |
