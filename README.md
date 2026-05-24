# 小说工坊 · AI Writing Workshop

AI 驱动的长篇小说创作系统。从灵魂构建到百万字完本，A 级质量标准全程护航。

## 快速开始

```bash
# 1. 安装依赖
cd frontend && npm install
cd .. && pip install -r requirements.txt

# 2. 启动后端
python3 -m uvicorn novel_writer.server:app --port 8000

# 3. 启动前端（开发模式）
cd frontend && npx vite --port 5173

# 4. 打开浏览器
open http://localhost:8000
```

## 核心功能

### 🎭 灵魂引擎
- 30 组核心矛盾（自由↔命运、真相↔欺骗、宏大↔亲密...）
- 每组 3 位跨文化大师参考
- 自动注入生成 Prompt

### 👥 角色灵魂
- 15 维度角色设计（出场·台词·创伤·弧线）
- 自动工具人检测
- 角色状态跨章节追踪

### 🔬 质量保证
- LLM Judge 6 维评分（钩子·节奏·对话·可读·反派·追读）
- A 级门槛 ≥0.8，不达标自动重写
- 强制具体化 + 模式破坏后处理
- 流式生成实时预览

### 📖 长篇架构
- 卷/篇章规划 + 关键情节点
- 全书状态快照（防止上下文丢失）
- 因果链自动追踪
- 百万字小说一致性保障

### 🧪 分析工具
- DeepQuality：12 维度深度分析
- CreativeLab：AI 读者·反套路·热力图·发布策略
- MasterworkLab：7 条神作法则检测
- ChapterDNA：六维雷达图对比

## 架构

```
wechat/
├── novel_writer/        # Python 后端
│   ├── server.py        # FastAPI · 70+ 端点
│   ├── generator.py     # 核心引擎 · LLM 调用 · 评分
│   ├── database.py      # SQLite 数据层
│   └── config.py        # 配置
├── frontend/            # React SPA
│   └── src/
│       ├── pages/       # 页面组件
│       ├── components/  # novels/ + ui/ + layout/
│       └── lib/         # 工具库
└── tests/               # 测试
```

## API

| 端点 | 说明 |
|------|------|
| `GET /api/status` | 系统状态 |
| `GET /api/novels` | 小说列表 |
| `POST /api/novels` | 创建小说 |
| `POST /api/novels/{id}/generate` | 生成章节 |
| `GET /api/novels/{id}/generate/status` | 生成状态（含流式预览） |
| `GET /api/novels/{id}/foreshadowing` | 伏笔审计 |
| `GET /api/providers` | 模型供应商 |
| `PUT /api/providers/{id}` | 配置供应商 |

## 测试

```bash
python3 -m pytest tests/ -v
# 79 passed, 45 API-dependent errors (需 API Key)
```

## License

MIT
