# Novel Writer — 开发实施规格

**版本**: 2.0 | **日期**: 2026-05-18 | **对应 PRD**: [PRD.md](PRD.md)

---

## 1. 系统架构

```
                              ┌─────────────────────┐
                              │    Nginx / Caddy     │  ← V2 加反向代理
                              │    (生产环境)        │
                              └──────────┬──────────┘
                                         │
                              ┌──────────▼──────────┐
                              │     Uvicorn          │
                              │  (4 workers, async)  │
                              └──────────┬──────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
                    ▼                    ▼                    ▼
           ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
           │  REST API    │    │  Background  │    │   Static     │
           │  (FastAPI)   │    │   Tasks      │    │   Files      │
           │              │    │              │    │  (Frontend)  │
           └──────┬───────┘    └──────┬───────┘    └──────────────┘
                  │                   │
        ┌─────────┼─────────┐         │
        │         │         │         │
        ▼         ▼         ▼         ▼
  ┌─────────┐ ┌───────┐ ┌───────┐ ┌──────────┐
  │Generator│ │Publish│ │Sched │ │State Mgr │
  └────┬────┘ └───┬───┘ └───┬───┘ └────┬─────┘
       │          │         │           │
       ▼          ▼         │           ▼
  ┌────────┐ ┌────────┐    │    ┌─────────────┐
  │ OpenAI │ │ Play   │    │    │ data/novels │
  │ DeepSk │ │ wright │    │    │   JSON      │
  └────────┘ └────────┘    │    └─────────────┘
                            │
                    ┌───────▼────────┐
                    │  结构化日志     │
                    │  → stdout JSON │
                    │  → 可选: Loki  │
                    └────────────────┘
```

---

## 2. 模块规格

### 2.1 story_state.py — 故事状态管理

**完整 JSON Schema**:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["novel_id", "title", "author", "genre", "world", "characters", "plot", "chapters"],
  "properties": {
    "novel_id":   {"type": "string", "pattern": "^[a-z0-9-]+$"},
    "title":      {"type": "string", "minLength": 1, "maxLength": 100},
    "author":     {"type": "string"},
    "synopsis":   {"type": "string", "maxLength": 500},
    "genre":      {"type": "string", "enum": ["玄幻", "都市", "言情", "悬疑", "科幻", "历史", "游戏", "其他"]},
    "tags":       {"type": "array", "items": {"type": "string"}},
    "world": {
      "type": "object",
      "required": ["name", "era", "geography", "power_system"],
      "properties": {
        "name":         {"type": "string"},
        "era":          {"type": "string"},
        "geography":    {"type": "string"},
        "power_system": {"type": "string"},
        "factions":     {"type": "array", "items": {
          "type": "object",
          "properties": {
            "name": {"type": "string"},
            "description": {"type": "string"},
            "leader": {"type": "string"}
          }
        }},
        "rules":        {"type": "array", "items": {"type": "string"}}
      }
    },
    "characters": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "name", "role", "personality"],
        "properties": {
          "id":                   {"type": "string", "pattern": "^[a-z0-9_-]+$"},
          "name":                 {"type": "string"},
          "role":                 {"type": "string", "enum": ["主角","反派","配角","导师","路人"]},
          "personality":          {"type": "string"},
          "background":           {"type": "string"},
          "current_power_level":  {"type": "string"},
          "secrets":              {"type": "array", "items": {"type": "string"}},
          "relationships":        {"type": "object"},
          "status":               {"type": "string", "enum": ["alive","injured","dead","missing"]}
        }
      }
    },
    "plot": {
      "type": "object",
      "properties": {
        "premise":           {"type": "string"},
        "main_arc":          {"type": "string"},
        "current_arc":       {"type": "string"},
        "arc_chapter_start": {"type": "integer"},
        "next_plot_points":  {"type": "array", "items": {"type": "string"}},
        "foreshadowing":     {"type": "array", "items": {"type": "string"}}
      }
    },
    "chapters": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "number":        {"type": "integer", "minimum": 1},
          "title":         {"type": "string"},
          "word_count":    {"type": "integer", "minimum": 0},
          "summary":       {"type": "string"},
          "key_events":    {"type": "array", "items": {"type": "string"}},
          "revelations":   {"type": "array", "items": {"type": "string"}},
          "ending_hook":   {"type": "string"},
          "generated_at":  {"type": "string", "format": "date-time"}
        }
      }
    }
  }
}
```

**版本管理**: JSON 文件加 `_schema_version: 1` 字段。V2 改 schema 时自动迁移。

**硬限制**:
- 单个 JSON 文件 ≤ 10 MB（约 500 章）
- 超限自动拆分为 `{novel_id}.json`（元数据）+ `{novel_id}_chapters.json`（章节列表）
- 单章正文 ≤ 50 KB

### 2.2 config.py

**环境变量优先级**: `env var` > `.env` 文件 > 默认值。

**安全性**: API Key 类配置在日志中自动脱敏（显示为 `sk-***`）。

### 2.3 generator.py

**Prompt 模板版本化**: 所有 prompt 模板在代码中标注版本号。切换 prompt 策略只需改版本号，旧策略保留 3 个版本。

```python
PROMPT_VERSION = "v3"  # v1: 基础 / v2: 加钩子约束 / v3: 加情绪节奏
```

**Token 预算管理**:
- 总 context window: 128K (GPT-4o)
- System prompt 预算: ≤ 8K tokens
- User prompt 预算: ≤ 4K tokens（含最近章节摘要）
- 响应 tokens: ≤ 4096 (max_tokens)
- 超出预算时自动降级：减少最近章节数（5→3→1）

**LLM 调用追踪** (结构化日志):
```json
{
  "event": "llm.call",
  "model": "gpt-4o",
  "attempt": 1,
  "prompt_version": "v3",
  "prompt_tokens": 3200,
  "completion_tokens": 2800,
  "duration_ms": 18500,
  "success": true
}
```

### 2.4 publisher.py

**安全模型**:
- 平台密码不存储——只用 cookie/session
- 发布前截取操作确认截图（保留 7 天）
- 同一 IP 同一平台每日发布 ≤ 5 章（反检测节奏）

**选择器配置外部化**:
```python
# 存储在 data/platform_selectors.json，非代码中硬编码
{
  "fanqie": {
    "login_btn": "#login-btn",
    "new_chapter_btn": "#new-chapter",
    ...
  }
}
```

### 2.5 scheduler.py

**并发控制**:
- PID 文件锁: `/tmp/novel_writer.lock`
- 进程启动时检查 PID 是否存在 → 存在且进程存活 → 退出
- 进程退出时清理 PID 文件（atexit + signal handler）

**优雅关闭**:
```python
import signal, sys

def shutdown(signum, frame):
    logger.info("Received signal %s, shutting down gracefully", signum)
    scheduler.stop_all()
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)
```

### 2.6 server.py

**API 版本**: 所有端点路径为 `/api/v1/...`（虽然 V1 不标版本号，但预留惯例）。

**速率限制** (V2):
- 生成端点: 每分钟 ≤ 5 次
- 发布端点: 每小时 ≤ 3 次

**请求大小限制**: POST body ≤ 100 KB。

**CORS**: 生产环境限制为前端域名。

### 2.7 前端

**性能预算**:
| 指标 | 预算 |
|------|------|
| 首屏加载 (FCP) | ≤ 1.0s |
| 最大内容绘制 (LCP) | ≤ 1.5s |
| 累积布局偏移 (CLS) | ≤ 0.05 |
| JS 总体积 | ≤ 80 KB（未压缩） |
| CSS 总体积 | ≤ 15 KB |
| 字体请求 | 0（使用系统字体） |

**离线缓存**: 无（SPA 没有 Service Worker，V2 可加）。

**浏览器兼容**: Chrome 90+, Firefox 90+, Safari 15+, Edge 90+。

---

## 3. 可观测性架构

### 3.1 日志规范

所有模块使用统一格式：

```python
import json, time, sys

def log_event(event: str, **kwargs):
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "event": event,
        **kwargs
    }
    print(json.dumps(entry, ensure_ascii=False), file=sys.stderr)
```

使用示例:
```python
log_event("chapter.generated", novel_id="xx", chapter=42, words=2800, duration_ms=18500)
log_event("publish.failed", novel_id="xx", chapter=42, reason="selector_mismatch", screenshot="/tmp/err.png")
log_event("error.critical", novel_id="xx", error="state_file_corrupted", path="/data/novels/xx.json")
```

### 3.2 关键指标

| 指标 | 含义 | 告警阈值 |
|------|------|---------|
| `generation.duration.p95` | 生成耗时 P95 | > 90s |
| `generation.failure_rate` | 生成失败率（含重试） | > 10% |
| `quality.fail_rate` | 质检不通过率 | > 30% |
| `publish.success_rate` | 发布成功率 | < 70% |
| `state.file_size` | 状态文件大小 | > 8 MB |

### 3.3 健康检查端点

```
GET /api/health → 200 {status: "ok", checks: {
  "openai": "ok",
  "deepseek": "ok",
  "fanqie_smoke": "ok",
  "disk_space": "12GB free"
}}
```

---

## 4. 编码规范

### 4.1 Python

- 类型注解: 所有公开函数必须有
- 文档字符串: Google style (`Args:`, `Returns:`, `Raises:`)
- 行长度: ≤ 100 字符
- 导入顺序: stdlib → 第三方 → 本地
- 异步: 所有 I/O 操作使用 `async/await`
- 禁止: `except Exception: pass` —— 至少 log 一条警告

### 4.2 JavaScript

- 变量: `const` 优先，`let` 次之，禁用 `var`
- 函数: arrow functions 用于回调，具名函数用于顶层
- DOM: 不直接操作 innerHTML（用 `createElement` + `textContent`），除组件渲染
- Async: `async/await` 优先于 `.then()`

### 4.3 命名约定

- Python 文件: `snake_case.py`
- Python 类: `PascalCase`
- Python 函数: `snake_case`
- JS 文件/函数: `kebab-case.js` / `camelCase`
- JSON 键: `snake_case`
- API 路径: `kebab-case`

---

## 5. 实现顺序

```
Phase 1: 核心引擎（数据层已就绪）
  ✅ story_state.py
  ✅ config.py
  ← generator.py（当前）

Phase 2: Web 后端
  ← server.py — 模式 B 端点 (draft/expand)
  ← server.py — 模式 A 端点 (auto/start/stop/status)
  ← server.py — 发布端点 + 健康检查

Phase 3: 前端
  ✅ Dashboard + NovelPage
  ← Editor 页面（模式 B 核心交互）
  ← Auto 控制面板

Phase 4: 发布 + 调度
  ← publisher.py（FanqiePlatform）
  ← scheduler.py（含 PID 锁）

Phase 5: 可观测性
  ← 结构化日志接入所有模块
  ← 健康检查端点

Phase 6: 集成 + 测试
  ← 全量 API 测试
  ← E2E 测试
  ← 性能基准测试
```

---

## 6. 依赖清单

```
# Python (requirements.txt)
fastapi>=0.110
uvicorn[standard]>=0.27
openai>=1.0
playwright>=1.40
pydantic>=2.0

# 开发依赖
pytest>=8.0
pytest-httpx>=0.30
pytest-asyncio>=0.23

# 系统依赖
chromium (playwright install chromium)

# 无 Node.js 依赖
```

---

## 7. 部署

### 开发环境

```bash
source .venv/bin/activate
uvicorn novel_writer.server:app --reload --port 8765
```

### 生产环境

```bash
uvicorn novel_writer.server:app \
  --host 0.0.0.0 --port 8000 \
  --workers 4 \
  --log-level warning
```

或 systemd 服务：

```ini
[Unit]
Description=Novel Writer
After=network.target

[Service]
Type=simple
User=z
WorkingDirectory=/Users/z/CodeBuddy/wechat
EnvironmentFile=/Users/z/CodeBuddy/wechat/.env
ExecStart=/Users/z/CodeBuddy/wechat/.venv/bin/uvicorn novel_writer.server:app --host 127.0.0.1 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```
