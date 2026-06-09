# 灵墨 · Lingmo

AI 驱动的长篇小说创作系统。30 种题材、8 维 LLM 质量评审、12 步生成管线。587 测试 · 100 章验证。

## 快速开始

### Docker（推荐）

```bash
docker load -i lingmo-app-*.tar
cp .env.example .env          # 编辑 .env 填入 DEEPSEEK_API_KEY
docker compose up -d
open http://localhost:8000
```

### 手动启动

环境要求：Python 3.12+、Node.js 22+

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn novel_writer.server:app --port 8000

# 前端（开发模式）
cd frontend && npm install && npx vite --port 5200
open http://localhost:5200
```

## 功能

### 核心生成

- **12 步生成管线** — 约束压缩→技巧选择→批量草拟→8维评分→精修→去AI→硬约束验证→人性化→废话检查→一致性校验→伏笔回收→TTS预生成
- **写作工作台** — 三栏布局 + 实时流式预览 + 大纲侧栏 + 质量细分面板 + 5 秒自动保存
- **批量生成** — 队列化连续生成，质量硬门槛（字数+评分+正文验收），SSE 实时推送
- **14 种作家声音** — 金庸·余华·刘慈欣·海明威·莫言·张爱玲·鲁迅·古龙·村上春树 等
- **30 种题材风格** — 玄幻·都市·悬疑·科幻·武侠·仙侠·历史·无限流·女频·四合院·规则怪谈·全民求生·电竞·盗墓·废土·年代文 等
- **键盘快捷键** — Ctrl+Enter 生成 · Ctrl+S 保存 · 自动保存 · 拖拽排序大纲

### 质量控制

- **8维LLM评审** — 钩子·节奏·对话·可读性·反派·追读·排版规范·灵魂契合，不达标自动重写
- **排版自动规范** — 孤儿引号修复 · `「」` 引号统一 · ✨ 一键排版按钮 · 段落方差检测
- **全链路正文验收** — 生成→保存→修订→格式修复，全路径拒绝空/说明/非小说正文
- **StyleProfile 自动校准** — 每5章根据历史质量趋势自动调整 30+ 写作参数
- **断点续传** — 生成中断自动恢复 · 前后端双锁防重 · 并发闸门
- **全链路成本追踪** — 每次 LLM 调用（生成/评审/精修/摘要）累计计入章节成本

### 角色与世界观

- **灵魂引擎** — 30 组文学根本矛盾选择器，每章注入核心追问
- **金庸级角色设计** — 出场·标志·台词·创伤·弧线起点→终点
- **角色关系图** — SVG 力导向图谱，关系标签常显
- **世界观编辑器** — 势力、规则、修炼体系 + 角色和势力的 CRUD 管理
- **伏笔管理** — 自动检测已埋/已回收伏笔，超过 10 章触发警告

### 扩展能力

- **增强版导出** — EPUB/PDF 含封面+目录+页码+元数据
- **TTS 语音合成** — edge-tts 中文朗读，分角色配音
- **章节 Diff** — 版本历史对比 · 上下章对比 · 大纲 vs 实际
- **写作分析仪表盘** — 情绪弧线·节奏曲线·对话密度·章节 DNA ·读者留存模拟
- **上下文窗口保护** — Token 预算检查，自动截断过长提示词
- **20 个模型供应商** — DeepSeek·OpenAI·Kimi·通义·智谱·豆包·MiniMax·百川·OpenRouter 等

## 架构

```
                    ┌───────────────────────┐
                    │    React SPA (Vite)    │
                    │  React 19 / Tailwind 4 │
                    └───────────┬───────────┘
                                │ REST + SSE
                    ┌───────────▼───────────┐
                    │  FastAPI (Uvicorn)    │
                    └───────────┬───────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
 ┌──────────────┐      ┌──────────────┐       ┌──────────────┐
 │  Generator   │      │   Routers    │       │  Scheduler   │
 │  12步管线    │      │  30个模块    │       │  全自动模式   │
 │  8维评审     │      │  服务层      │       │  Agent编排   │
 └──────┬───────┘      └──────────────┘       └──────────────┘
        │
        ▼
 ┌──────────────────────────────────────────┐
 │  LLM Provider Layer (20 供应商)           │
 │  DeepSeek · OpenAI · 通义 · Kimi · 智谱  │
 │  豆包 · 文心 · 星火 · MiniMax · 百川      │
 └──────────────────────────────────────────┘
                │
 ┌──────────────▼──────────────┐
 │  SQLite + WAL               │
 │  587 tests · 100章验证      │
 └─────────────────────────────┘
```

## 测试

```bash
python3 -m pytest tests/ -v     # 587 tests
cd frontend && npx tsc --noEmit # 0 errors
```

## 项目结构

```
novel_writer/              # Python 后端
├── server.py              # FastAPI 入口
├── generator.py           # 核心生成引擎（12步管线）
├── database.py            # SQLite 数据访问层
├── story_state.py         # 故事状态 + 记忆上下文
├── exporter.py            # 增强导出（EPUB/PDF）
├── routers/novel/         # 30 个路由模块（从 6440 行拆出）
├── services/              # 业务逻辑层
└── stations/              # 工位模式（novel/drama/script）
frontend/                  # React SPA
├── src/pages/             # 页面组件
├── src/components/novels/ # 功能组件
└── src/lib/               # 工具库
tests/                     # pytest (587 tests)
docs/                      # 文档 + 优化台账
```

## License

MIT
