# 灵墨 — AI 创作伴侣

## 项目文档索引

| 文档 | 内容 | 读者 |
|------|------|------|
| [**PRD.md**](PRD.md) | 产品需求：用户故事、功能需求、验收标准 | 所有人 |
| [**DEV.md**](DEV.md) | 开发规格：模块接口、API 契约、数据结构、实现顺序 | 开发者 |
| [**TEST.md**](TEST.md) | 测试计划：单元/API/E2E/质量用例、测试数据、门禁 | QA / 开发者 |
| [**ARCHITECTURE.md**](ARCHITECTURE.md) | 技术架构：系统图、数据流、模式 A/B 时序 | 架构师 |
| [**DESIGN.md**](DESIGN.md) | 设计决策：10 个关键 tradeoff 及理由 | 所有人 |

## 一句话定位

双模式 AI 小说工具：全自动管线（模式 A）+ 人工创作助手（模式 B）。

## 两种模式

| | 模式 A：全自动 | 模式 B：创作者 |
|---|---|---|
| 触发 | 定时 / 手动一键 | Web 编辑器手动操作 |
| 人工 | 零参与 | 给方向 → 选草稿 → 改正文 |
| 发布 | 自动 | 确认后发布 |
| 切换 | 同一本书随时切 | |

## 技术栈

Python 3.14 · FastAPI · OpenAI (GPT-4o + DeepSeek) · Playwright · vanilla JS SPA · JSON 持久化

## 里程碑

1. **M1** — generator.py + server.py API 全部打通
2. **M2** — 章节编辑器（模式 B 工作流完整）
3. **M3** — scheduler + publisher（模式 A 全自动闭环）
4. **M4** — 双模式无缝切换

## 开始开发

1. 阅读 [PRD.md](PRD.md) 了解需求
2. 阅读 [DEV.md](DEV.md) 了解技术规格和实现顺序
3. 阅读 [TEST.md](TEST.md) 了解测试要求
4. 开始 Phase 1：实现 `generator.py`
