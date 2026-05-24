# 灵墨 — 技术架构

## 系统总览：双模式

```
                       ┌─────────────────────────┐
                       │      共用核心引擎         │
                       │                          │
                       │  Generator  ← GPT-4o     │
                       │  Publisher  ← Playwright │
                       │  StateMgr   ← JSON       │
                       │  Quality checks          │
                       │  30-ch reanchor          │
                       │  Platform abstraction    │
                       └──────────┬───────────────┘
                                  │
              ┌───────────────────┴───────────────────┐
              │                                       │
              ▼                                       ▼
     ┌─────────────────┐                    ┌─────────────────┐
     │   模式 A：全自动   │                    │  模式 B：创作者   │
     │                  │                    │                 │
     │  Scheduler 触发   │                    │  Web 编辑器触发   │
     │  → generate()    │                    │  → 给方向         │
     │  → quality pass  │                    │  → AI 出 3 稿     │
     │  → publish()     │                    │  → 编辑器中改     │
     │  → log           │                    │  → 手动 publish   │
     └─────────────────┘                    └─────────────────┘
```

## 模式 A：全自动管线

```
cron / daemon
    │
    ▼
Scheduler.run_once(novel_id)
    │
    ├─ StateManager.load(state)
    ├─ Generator.generate(state)         ← 无人工方向输入
    │    └─ build_prompt() 用默认策略     ← "继续延续上一章"
    ├─ Quality checks pass?
    │    ├─ YES → continue
    │    └─ NO  → retry (max 2) / skip
    ├─ Publisher.publish(state, chapter)
    │    ├─ smoke_test()
    │    ├─ login()
    │    └─ upload_chapter()
    └─ Log result
```

## 模式 B：创作者工作流

```
Web Editor
    │
    ├─ 1. 作者输入方向
    │     "这章写主角突破金丹，遭遇宿敌"
    │
    ├─ 2. POST /api/novels/{id}/draft
    │     Generator.draft_directions(state, author_input)
    │     返回 3 个草稿摘要供选择
    │
    ├─ 3. 作者选方向 B，给修改意见
    │     POST /api/novels/{id}/expand
    │     Generator.expand(state, chosen_direction, edits)
    │     返回完整章节
    │
    ├─ 4. 作者在编辑器里改
    │     PUT /api/novels/{id}/chapters/{n}
    │     保存修改后的正文
    │
    └─ 5. 作者点发布
          POST /api/novels/{id}/publish
```

## API 端点（双模式）

```
# 共用
GET    /api/novels                    — 小说列表
POST   /api/novels                    — 创建小说
GET    /api/novels/{id}               — 小说详情 + 全部章节
GET    /api/novels/{id}/chapters/{n}  — 章节全文

# 模式 A（全自动）
POST   /api/novels/{id}/auto/start    — 启动此书的全自动模式
POST   /api/novels/{id}/auto/stop     — 停止全自动
POST   /api/novels/{id}/auto/once     — 手动触发一次全自动执行

# 模式 B（创作者）
POST   /api/novels/{id}/draft         — 生成 3 个草稿方向
POST   /api/novels/{id}/expand        — 展开选定方向为全文
PUT    /api/novels/{id}/chapters/{n}  — 保存编辑后的正文

# 发布
POST   /api/novels/{id}/publish       — 发布最新章节
```

## 核心接口

### generator.py

```python
class Generator:
    def __init__(self, config: Config)

    # 全自动模式
    def generate(self, state: StoryState) -> ChapterMeta
        """读 state → 调 LLM → 返回新章节元数据，完整闭环"""

    # 创作者模式
    def draft_directions(self, state: StoryState, author_input: str, n: int = 3) -> list[DraftOption]
        """根据作者方向，返回 n 个不同的剧情走向草稿"""

    def expand(self, state: StoryState, chosen: DraftOption, edits: str = "") -> str
        """展开选定方向为 2000-3000 字完整章节正文"""

    # 内部
    def build_prompt(self, state, author_input="") -> list[dict]
    def call_llm(self, messages) -> str
    def parse_response(self, raw) -> tuple[str, str, dict]
    def run_quality_checks(self, body, state) -> list[str]
```

### publisher.py

```python
class BasePlatform(ABC):
    name: str
    async def login(self, storage_state=None) -> str
    async def upload_chapter(self, title, body) -> PublishResult
    async def smoke_test(self) -> bool

class Publisher:
    def publish(self, state, chapter) -> PublishResult
```

## 数据流

```
StateManager.load(novel_id)
    │
    ▼
Generator.generate(state) / Generator.expand(state, chosen)
    │
    ├─ build_prompt(state, input) → OpenAI API
    ├─ parse → (title, body, meta)
    ├─ quality_checks(body, state)
    │
    ▼
StateManager.save(state)  ← 章节追加 + 状态更新
    │
    ▼ (模式 A: 自动 / 模式 B: 手动触发)
Publisher.publish(state, chapter)
```

## 前端架构

```
frontend/
├── index.html
├── css/style.css        # ink & paper 设计系统
└── js/
    ├── api.js            # fetch 封装
    ├── app.js            # hash 路由 + Utils + Toast
    ├── components/
    │   ├── navbar.js
    │   ├── novel-card.js
    │   └── chapter-list.js
    └── pages/
        ├── dashboard.js  # 工作台
        ├── novel.js      # 小说详情 + 模式切换
        ├── editor.js     # 章节编辑器（模式 B 核心）
        ├── settings.js
        └── logs.js
```

## 测试策略

| 层级 | 工具 | 覆盖 |
|------|------|------|
| StateManager CRUD | pytest | 100% |
| Generator prompt 结构 | pytest | 关键路径 |
| Generator LLM 调用 | pytest + mock | 所有分支 |
| API 端点 | pytest + httpx | 全部 |
| 前端交互 | 手动 / Playwright E2E | 关键流程 |
