# 小说工坊 · AI 写作引擎

> 全栈 AI 小说生成系统：FastAPI 后端 + React SPA 前端。目标：A 级质量全自动创作。

## 项目结构

```
wechat/
  novel_writer/     # Python 后端 (FastAPI + SQLite)
    server.py       # 70+ API 端点
    generator.py    # 核心生成引擎 (LLM 调用/质量评分/流式输出)
    database.py     # 数据库层
    story_state.py  # 故事状态模型
    config.py       # 配置
  frontend/         # React SPA (TypeScript + Tailwind)
    src/
      pages/        # 页面组件
      components/   # 功能组件 (novels/ + ui/ + layout/)
      lib/          # 工具库
```

## 启动方式

```bash
cd /Users/z/CodeBuddy/wechat
python3 -m uvicorn novel_writer.server:app --port 8000
# 前端: http://localhost:8000
```

## 关键约束

- DeepSeek API Key 在设置页配置
- 生成超时 300s，每章最多重试 3 次
- A 级门槛 ≥0.8，LLM Judge 评分
- 流式预览需 `_run_generation` 设置 `gen._on_stream_chunk` 回调
- Vite 代理 `/api` → `localhost:8000`

## Superpowers 工作流

- 新功能/优化前：`brainstorming` → `writing-plans` → 实现
- Bug 修复：`systematic-debugging` → 定位根因 → 修复 → `verification-before-completion`
- 并行任务：`dispatching-parallel-agents`
- 前端 UI 工作：`ui-ux-pro-max` 或 `frontend-design`
- 设计审查：`design-review`
