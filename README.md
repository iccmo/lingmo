# 灵墨 -- Lingmo

AI 驱动的长篇小说创作系统。从世界观构建到百万字完本，多模型供应商 + 质检引擎全程护航。

## 快速开始

### Docker（推荐）

```bash
cp .env.example .env          # 编辑 .env 填入 DEEPSEEK_API_KEY
docker compose up --build      # 首次构建约需 2 分钟
open http://localhost:8000
```

### 手动启动

环境要求：Python 3.12+、Node.js 22+

```bash
# 后端
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn novel_writer.server:app --port 8000

# 前端（开发模式）
cd frontend && npm install && npx vite --port 5173

# 打开浏览器
open http://localhost:8000
```

## 架构

```
                      ┌───────────────────────┐
                      │    React SPA (Vite)    │
                      │  React 19 / shadcn/ui  │
                      │  TailwindCSS 4 / TS 6  │
                      └───────────┬───────────┘
                                  │ REST + SSE
                      ┌───────────▼───────────┐
                      │  FastAPI (Uvicorn)     │
                      │  90+ API endpoints     │
                      └───────────┬───────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          ▼                       ▼                       ▼
   ┌──────────────┐      ┌──────────────┐       ┌──────────────┐
   │  Generator   │      │  Publisher   │       │  Scheduler   │
   │  LLM 调用    │      │  Playwright  │       │  定时 + PID  │
   │  质检 + 去AI │      │  全自动发布   │       │  锁并发控制   │
   └──────┬───────┘      └──────────────┘       └──────────────┘
          │
          ▼
   ┌──────────────────────────────────────────┐
   │  LLM Provider Layer (多供应商)            │
   │  DeepSeek | OpenAI | 通义千问 | Kimi     │
   │  智谱 | 豆包 | 文心 | 星火 | Gemini      │
   └──────────────────────────────────────────┘
                  │
   ┌──────────────▼──────────────┐
   │  SQLite + WAL               │
   │  novels / chapters / costs  │
   │  embeddings / audio / style │
   └─────────────────────────────┘
```

## 功能概览

### 核心生成

- **双模式工作流**
  - 模式 A：全自动 -- Scheduler 定时触发，生成 + 质检 + 重试 + 发布全闭环
  - 模式 B：创作者 -- Web 编辑器交互式创作，AI 出 3 稿选 1，支持手动修改
- **批量生成** -- 队列化连续生成多章，实时进度推送（SSE）
- **Classic 生成** -- 经典长篇叙事模式，慢工出细活
- **Pipline 生成** -- 提纲 + 风格 + 角色声音全链路生成

### 质量控制

- **评分引擎** -- 6 维评分（钩子、节奏、对话、可读性、反派、追读），A 级门槛 >= 0.8
- **去 AI 化后处理** -- 检测并移除 AI 套话 ("在这个充满...")，SRE 强制具体化
- **拼写/语法检查** -- 重复词检测、错别字、AI 套话标记
- **事实核查** -- 角色/世界/情节一致性验证
- **时效性检测** -- 开篇陈腐模式自动预警

### 角色与世界观

- **15 维度角色设计** -- 出场、台词、创伤、弧线、秘密、关系网
- **角色声音追踪** -- 每章更新平均句长、问句比、惯用词、代表台词
- **世界观圣经** -- 势力、规则、修炼体系结构化存储
- **伏笔管理** -- 埋笔 + 回收审计，因果链追踪
- **时间线** -- 全书故事时间线可视化

### 分析与优化

- **经典评估** -- 对照 7 条神作法则评分
- **算法优化** -- 基于番茄推荐引擎指标的优化建议
- **读者留存分析** -- 留存分数 + 流失风险章节
- **变现评估** -- 收入预估、最佳发布时间
- **采集审查** -- 前三章签约竞争力评估
- **驾驶舱** -- 单书实时数据面板

### 发布与导出

- **番茄小说自动发布** -- Playwright 全流程自动化（CDP 远程 / 无头）
- **多格式导出** -- EPUB、PDF、Kindle (MOBI)、Markdown 全文
- **TTS 语音合成** -- edge-tts 中文朗读，支持戏剧化分角色配音
- **有声书播放器** -- 书签、播放列表、进度同步（服务端持久化）

### 工具集

- **全文搜索** -- 跨小说标题/简介/正文检索
- **DNA 提取** -- 从已有文本提取小说基因（风格、节奏、冲突模式）
- **DNA 比对** -- 两本小说基因雷达图对比
- **章节导入** -- 批量导入已有章节
- **章节排序** -- 拖拽重排章节
- **风格进化** -- 渐进式风格变异
- **市场趋势** -- 热门类型分析
- **小说农场** -- 批量创建多本实验性小说
- **创意实验室** -- 写作声音库、主角名智能生成（声调均衡）

### 数据管理

- **费用追踪** -- 按模型/小说的 Token 用量和费用明细
- **供应商管理** -- API Key + Base URL 数据库存储，优先级排序
- **章节版本历史** -- 每次编辑自动保存快照
- **智能上下文窗口** -- 章节摘要压缩 + RAG 检索相关上下文
- **AB 测试框架** -- 对比不同 Prompt 策略效果
- **指标采集** -- 字数、Token、成本、性能趋势

## API 参考

### 小说 CRUD

| 端点 | 说明 |
|------|------|
| `GET /api/novels` | 小说列表（含最新章、总字数） |
| `POST /api/novels` | 创建小说（含角色、标签） |
| `GET /api/novels/{id}` | 小说详情 + 全部章节 + 角色关系 |
| `PUT /api/novels/{id}` | 更新小说元数据 |
| `DELETE /api/novels/{id}` | 软删除 |

### 生成

| 端点 | 说明 |
|------|------|
| `POST /api/novels/{id}/generate` | 生成一章 |
| `POST /api/novels/{id}/generate-batch` | 批量生成 N 章（队列化） |
| `GET /api/novels/{id}/generate/status` | 生成状态 + 流式预览 |
| `GET /api/novels/{id}/generate/stream` | SSE 实时生成流 |
| `GET /api/novels/{id}/generate/queue-status` | 队列进度 |
| `POST /api/novels/{id}/generate-classic` | Classic 模式生成 |
| `POST /api/novels/{id}/pipeline` | 全链路生成 |

### 创作者模式

| 端点 | 说明 |
|------|------|
| `POST /api/novels/{id}/draft` | 生成 3 个草稿方向 |
| `POST /api/novels/{id}/expand` | 展开选定方向为全文 |
| `PUT /api/novels/{id}/chapters/{n}` | 保存编辑后的正文 |
| `POST /api/novels/{id}/chapters/{n}/humanize` | 人性化润色 |
| `POST /api/novels/{id}/chapters/{n}/revise` | AI 修订 |
| `POST /api/novels/{id}/revise-opening` | 重写开篇 |
| `POST /api/novels/{id}/final-polish` | 终稿打磨 |

### 自动模式

| 端点 | 说明 |
|------|------|
| `POST /api/novels/{id}/auto/start` | 启动全自动 |
| `POST /api/novels/{id}/auto/stop` | 停止全自动 |
| `POST /api/novels/{id}/auto/once` | 手动触发一次自动执行 |

### 质量与分析

| 端点 | 说明 |
|------|------|
| `GET /api/novels/{id}/report` | 质检报告 |
| `GET /api/novels/{id}/spellcheck` | 拼写/语法检查 |
| `GET /api/novels/{id}/chapters/{n}/fact-check` | 事实核查 |
| `GET /api/novels/{id}/freshness-check` | 时效性检测 |
| `GET /api/novels/{id}/classic-assessment` | 经典评估 |
| `GET /api/novels/{id}/algorithm-optimize` | 推荐算法优化建议 |
| `GET /api/novels/{id}/check-ending` | 结尾钩子检测 |
| `GET /api/novels/{id}/cockpit` | 驾驶舱数据 |

### 发布与导出

| 端点 | 说明 |
|------|------|
| `POST /api/novels/{id}/publish` | 发布到平台 |
| `GET /api/novels/{id}/publish-status` | 发布状态 |
| `GET /api/novels/{id}/export-epub` | 导出 EPUB |
| `GET /api/novels/{id}/export-pdf` | 导出 PDF |
| `GET /api/novels/{id}/export-mobi` | 导出 MOBI |
| `GET /api/novels/{id}/export-full` | 导出全文 |
| `GET /api/novels/{id}/chapters/{n}/tts` | TTS 语音合成 |
| `GET /api/novels/{id}/chapters/{n}/tts-dramatic` | 戏剧化多人配音 |

### 供应商与配置

| 端点 | 说明 |
|------|------|
| `GET /api/providers` | 供应商列表 |
| `PUT /api/providers/{id}` | 配置供应商 API Key |
| `POST /api/providers/{id}/test` | 测试供应商连通性 |
| `GET /api/settings` | 获取设置 |
| `POST /api/settings/sync` | 同步设置 |

### 系统

| 端点 | 说明 |
|------|------|
| `GET /api/status` | 系统状态（小说/章节/字数统计） |
| `GET /api/health` | 健康检查（含各服务状态） |
| `GET /api/logs` | 运行日志 |
| `GET /api/daily` | 每日摘要 |
| `GET /api/insights` | 全局洞察 |
| `POST /api/search` | 全文搜索 |

## 项目结构

```
wechat/
├── novel_writer/          # Python 后端
│   ├── server.py           # FastAPI 应用 -- 90+ 端点
│   ├── generator.py        # 核心引擎 -- LLM 调用、质检、RAG
│   ├── database.py         # SQLite 数据访问层 (WAL 模式)
│   ├── story_state.py      # 故事状态管理器 (世界观/角色/情节)
│   ├── publisher.py        # Playwright 浏览器自动化发布
│   ├── scheduler.py        # 定时任务 + 全自动模式调度
│   ├── config.py           # 环境变量配置中心
│   ├── log_utils.py        # 结构化 JSON 日志 + 指标收集
│   ├── main.py             # CLI 入口
│   └── schema.sql          # 数据库 Schema (10+ 表)
├── frontend/               # React SPA
│   ├── src/
│   │   ├── pages/          # 页面组件 (Dashboard, Novel, Editor...)
│   │   ├── components/     # novels/ + ui/ (shadcn/ui) + layout/
│   │   └── lib/            # API client, utils
│   ├── package.json        # React 19 + Vite 8 + TS 6 + TailwindCSS 4
│   └── vite.config.ts
├── tests/                  # pytest 测试套件 (12 文件 / 1847 行)
│   ├── test_api.py
│   ├── test_database.py
│   ├── test_generator.py
│   ├── test_pipeline.py
│   ├── test_server_pytest.py
│   ├── test_story_state.py
│   ├── test_integration.py
│   ├── test_system_integration.py
│   ├── test_config.py
│   └── test_database_pytest.py
├── data/                   # 运行时数据 (gitignored)
│   └── novel_writer.db     # SQLite 数据库
├── scripts/                # 工具脚本
│   └── backup_db.sh
├── Dockerfile              # 多阶段构建 (Node.js → Python)
├── docker-compose.yml      # 一键部署
├── pyproject.toml          # ruff + mypy 配置
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量模板
└── CLAUDE.md               # AI 协作指南
```

## 测试

```bash
# 安装开发依赖
pip install pytest pytest-httpx pytest-asyncio

# 运行全部测试
python3 -m pytest tests/ -v

# 运行特定模块
python3 -m pytest tests/test_database.py -v
python3 -m pytest tests/test_generator.py -v

# 带覆盖率
python3 -m pytest tests/ -v --cov=novel_writer --cov-report=term-missing
```

## 代码质量

```bash
pip install ruff mypy

# Lint + 自动修复
ruff check . --fix

# 类型检查
mypy novel_writer/
```

配置位于 `pyproject.toml`：
- **ruff**: target py312, line-length 120, E/F/W/I/N/UP/B/C4 规则集
- **mypy**: Python 3.12, 忽略缺失的导入 stub, 检查无类型注解的函数

## 开发指南

### 环境变量

```bash
OPENAI_API_KEY=       # OpenAI / 兼容接口 API Key
OPENAI_BASE_URL=      # 自定义 API 地址（默认 DeepSeek）
```

多供应商配置通过 Web UI (`/api/providers`) 管理，支持 10 个预设供应商。

### 启动 CLI

```bash
python -m novel_writer.main init        # 交互式创建小说
python -m novel_writer.main list        # 列出所有小说
python -m novel_writer.main run         # 手动触发一次生成
python -m novel_writer.main status      # 查看进度
python -m novel_writer.main daemon      # 启动守护进程
python -m novel_writer.main serve       # 启动 Web 服务器 (默认 :8765)
```

### 数据库

SQLite + WAL 模式，数据库文件位于 `data/novel_writer.db`。Schema 自动初始化，支持：
- 小说 + 角色 + 势力 + 关系网
- 章节 + 草稿 + 版本历史
- 费用日志 + 章节摘要 + Embedding 向量
- 发布记录 + 调度状态 + 平台认证
- 播客书签 + 播放列表 + 样式档案

备份：`scripts/backup_db.sh`

### 发布配置

番茄小说平台发布需要：
1. 在浏览器中登录 https://fanqienovel.com
2. 保存 cookies 到 `data/auth/fanqie.json`
3. 设置 `CDP_URL` 环境变量指向远程浏览器（可选，默认无头模式）

## License

MIT
