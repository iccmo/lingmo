# 灵墨 — 测试计划与用例

**版本**: 2.0 | **日期**: 2026-05-18 | **对应 PRD**: [PRD.md](PRD.md) | **对应 DEV**: [DEV.md](DEV.md)

---

## 1. 测试策略

| 层级 | 范围 | 工具 | 目标覆盖率 |
|------|------|------|-----------|
| 单元测试 | 模块内部逻辑 | pytest | ≥ 90% |
| 集成测试 | 模块间交互 + API | pytest + httpx | 关键路径 100% |
| API 测试 | 所有 REST 端点 | pytest + httpx | 全部端点 |
| E2E 测试 | 用户完整流程 | Playwright | 关键流程 |
| 数据测试 | 分析事件、质量评分 | pytest | 事件 schema 100% |
| 质量测试 | AI 生成内容 | 自动化脚本 | 每轮运行 |

## 2. 单元测试

### 2.1 story_state.py

| ID | 用例 | 期望 |
|----|------|------|
| UT-SS-01 | 创建并保存 State | JSON 文件内容匹配 |
| UT-SS-02 | 加载已存在的 State | 返回正确对象 |
| UT-SS-03 | 加载不存在的 novel_id | 返回 None |
| UT-SS-04 | 追加章节 | chapters +1，文件更新 |
| UT-SS-05 | recent_context(3) | 返回最近 3 章摘要 |
| UT-SS-06 | character_context | 含所有角色名和状态 |
| UT-SS-07 | list_novels | 返回所有 novel_id |
| UT-SS-08 | delete_novel | JSON 文件删除 |
| UT-SS-09 | 原子写入 | 中断不损坏原始文件 |
| UT-SS-10 | to_dict/from_dict 往返 | 数据完全一致 |
| UT-SS-11 | JSON Schema 校验 | 无效数据抛出异常 |

### 2.2 generator.py

| ID | 用例 | 期望 |
|----|------|------|
| UT-GEN-01 | build_prompt 含世界信息 | system prompt 含世界名 + 修炼体系 |
| UT-GEN-02 | build_prompt 含全部角色 | system prompt 含所有角色名 |
| UT-GEN-03 | build_prompt 含最近章节 | user prompt 含最近 5 章摘要 |
| UT-GEN-04 | build_prompt 含上章钩子 | user prompt 含钩子内容 |
| UT-GEN-05 | build_direction_prompt | 含"生成 3 个不同走向"指令 |
| UT-PARSE-01 | Markdown 格式解析 | 正确提取标题/正文/元数据 |
| UT-PARSE-02 | 元数据 JSON 提取 | 正确解析 key_events 等 |
| UT-PARSE-03 | 自然文本标题提取 | 从"第N章 XXX"提取 |
| UT-PARSE-04 | 草稿解析 | 返回 3 个 DraftOption |
| UT-PARSE-05 | 空响应 | 返回默认值，不崩溃 |
| UT-PARSE-06 | 损坏 JSON 容错 | 返回空 dict |
| UT-QC-01 | 字数 < 1500 | passed=false |
| UT-QC-02 | 字数 ≥ 2000 | passed=true |
| UT-QC-03 | 主角未出场 | passed=false |
| UT-QC-04 | 质量检测全部通过 | passed=true |

## 3. API 测试

### 3.1 小说管理

| ID | 方法 | 端点 | 期望状态码 |
|----|------|------|-----------|
| API-01 | GET | /api/novels | 200 |
| API-02 | POST | /api/novels (有效数据) | 200 |
| API-03 | POST | /api/novels (重复 ID) | 409 |
| API-04 | POST | /api/novels (缺少必填字段) | 400 |
| API-05 | GET | /api/novels/{id} | 200 |
| API-06 | GET | /api/novels/fake | 404 |
| API-07 | DELETE | /api/novels/{id} | 200 |

### 3.2 模式 A & B

| ID | 方法 | 端点 | 期望 |
|----|------|------|------|
| API-A01 | POST | /api/novels/{id}/auto/start | 200, "started" |
| API-A02 | POST | /api/novels/{id}/auto/stop | 200, "stopped" |
| API-A03 | POST | /api/novels/{id}/auto/once | 200, "running" |
| API-A04 | GET | /api/novels/{id}/auto/status | 200, AutoStatus |
| API-B01 | POST | /api/novels/{id}/draft | 200, 3 directions |
| API-B02 | POST | /api/novels/{id}/expand | 200, {title, body} |
| API-P01 | POST | /api/novels/{id}/publish | 200, PublishResult |
| API-S01 | GET | /api/health | 200, checks |

## 4. E2E 测试

| ID | 场景 | 步骤 | 期望 |
|----|------|------|------|
| E2E-01 | 创建小说 | Dashboard→创建→填表→提交→点卡片 | 详情页正确 |
| E2E-02 | 模式 B 完整流程 | 输入方向→看草稿→选 B→展开→编辑→保存 | 章节更新 |
| E2E-03 | 模式 A 启动 | 详情→启动全自动→查看状态 | "运行中" |
| E2E-04 | 空状态 | 删光小说→Dashboard | 空状态文案 |
| E2E-05 | 移动端 | 375px 宽度 | 侧栏变顶部，卡片单列 |
| E2E-06 | 导航切换 | 设置→日志→工作台 | 每页正确渲染 |

---

## 5. 数据层测试

### 5.1 分析事件 Schema 验证

每个分析事件必须符合 schema：

```python
EVENTS = {
    "novel.created":        ["novel_id", "title", "genre"],
    "chapter.generated":    ["novel_id", "chapter", "model", "words", "duration_ms"],
    "chapter.quality_failed": ["novel_id", "chapter", "reason"],
    "chapter.edited":       ["novel_id", "chapter", "edit_ratio"],
    "chapter.published":    ["novel_id", "chapter", "platform", "duration_ms"],
    "mode.switched":        ["novel_id", "from", "to"],
    "llm.call":             ["model", "attempt", "prompt_tokens", "completion_tokens", "duration_ms", "success"],
    "error.critical":       ["error", "context"],
}
```

| ID | 用例 | 期望 |
|----|------|------|
| DT-01 | 所有事件字段完整 | 必填字段 100% 存在 |
| DT-02 | 事件时间戳递增 | ts 严格递增 |
| DT-03 | LLM token 计数合理 | prompt_tokens ≤ 8000, completion ≤ 4096 |
| DT-04 | 质量失败原因可枚举 | reason ∈ {short, protagonist_missing, repetitive} |
| DT-05 | 编辑比例范围 | 0 ≤ edit_ratio ≤ 1.0 |

### 5.2 数据完整性

| ID | 用例 | 期望 |
|----|------|------|
| DT-10 | 无孤儿章节 | 每个 chapter 属于一个存在的 novel |
| DT-11 | 章节编号连续 | chapters 数组的 number 递增无跳 |
| DT-12 | 正文文件存在 | chapter_{n}.txt 文件存在且非空 |
| DT-13 | 无状态文件损坏 | 所有 JSON parse 成功 |

---

## 6. 内容质量评分模型

### 6.1 评分维度

```
QualityScore = w1 × 完整性 + w2 × 连贯性 + w3 × 钩子强度 + w4 × 节奏 — 惩罚项

维度权重（总 1.0）:
  w1 = 0.20  完整性: 字数是否达标 (0-1)
  w2 = 0.30  连贯性: 主角出场 + 剧情点推进 (0-1)
  w3 = 0.25  钩子强度: 结尾是否有悬念 (0-1)
  w4 = 0.25  节奏: 冲突密度 (0-1)

惩罚项:
  - 重复段落 > 30%: -0.2
  - 角色 OOC: -0.3
  - 世界观矛盾: -0.3
```

### 6.2 评分阈值

| 分数 | 评级 | 操作 |
|------|------|------|
| ≥ 0.80 | A 级 — 优秀 | 直接发布 |
| 0.60-0.79 | B 级 — 合格 | 发布，标记可优化 |
| 0.40-0.59 | C 级 — 需修改 | 模式 A: 重试；模式 B: 提示作者 |
| < 0.40 | D 级 — 不合格 | 强制重试或拒绝 |

### 6.3 评分测试

| ID | 用例 | 输入 | 期望分数范围 |
|----|------|------|------------|
| QUAL-01 | 完美章节 | 2500字+主角+强钩子+3个冲突 | ≥ 0.85 |
| QUAL-02 | 字数不足 | 800字 | < 0.50 |
| QUAL-03 | 缺钩子 | 2500字但结尾平淡 | < 0.65 |
| QUAL-04 | 角色 OOC | 主角行为与设定矛盾 | < 0.50 |
| QUAL-05 | 重复段落 | >30% 内容重复 | < 0.60 |

### 6.4 质量趋势监控

| ID | 用例 | 检测 | 告警条件 |
|----|------|------|---------|
| QT-01 | 质量漂移 | 滑动窗口(10章)均分 | 连续下降 > 0.15 |
| QT-02 | 异常低分 | 单章分数 | < 0.30 |
| QT-03 | 字数膨胀 | 最近 10 章字数 | 中位数 > 4000 |
| QT-04 | 钩子疲劳 | 最近 10 章钩子重复模式 | > 3 章钩子结构相同 |

---

## 7. Prompt A/B 实验框架（V2）

### 7.1 实验设计

```
对照组 (A): 当前 v3 prompt
实验组 (B): 新 prompt 策略

一本小说内：
  奇数章用 A → 生成质量分数
  偶数章用 B → 生成质量分数

统计检验：
  - 双样本 t 检验 (α=0.05)
  - 每组 ≥ 10 章
  - 效应量: Cohen's d ≥ 0.3 视为有意义
```

### 7.2 A/B 测试用例

| ID | 用例 | 期望 |
|----|------|------|
| AB-01 | 同 state 生成质量对比 | B 组均分 ≥ A 组 |
| AB-02 | 生成速度对比 | B 组 P50 耗时 ≤ A 组 +10% |
| AB-03 | 多样性检验 | B 组输出唯一性 ≥ A 组 |
| AB-04 | 统计显著性 | p < 0.05 时才能结论 B 胜出 |

---

## 8. 测试数据

```python
# 最小有效 State
MINIMAL_STATE = {
    "novel_id": "test", "title": "Test", "author": "AI",
    "synopsis": "test", "genre": "玄幻",
    "world": {
        "name": "测试大陆", "era": "上古",
        "geography": "一片大陆", "power_system": "练气→筑基→金丹",
        "factions": [], "rules": []
    },
    "characters": [{
        "id": "protagonist", "name": "叶凡", "role": "主角",
        "personality": "坚韧", "background": "少年",
        "current_power_level": "练气三层",
        "secrets": [], "relationships": {}, "status": "alive"
    }],
    "plot": {
        "premise": "test", "main_arc": "test",
        "current_arc": "开篇", "arc_chapter_start": 1,
        "next_plot_points": ["入门"], "foreshadowing": []
    },
    "chapters": [], "tags": []
}

# Mock LLM 响应（Markdown 格式）
MOCK_CHAPTER = """## 标题\n突破筑基\n## 正文\n（2000+字正文）\n## 元数据\n```json\n{"summary":"叶凡突破筑基","key_events":["突破","遇敌"],"revelations":["宿敌同门"],"ending_hook":"宿敌临终透露身世之谜..."}\n```"""
```

## 9. 质量门禁

| 门禁 | 条件 | 阻塞 |
|------|------|------|
| 单元测试 | 全部 green | 🔴 阻塞 |
| API 测试 | 全部端点 200 | 🔴 阻塞 |
| 数据 schema | 所有事件字段完整 | 🔴 阻塞 |
| 代码覆盖率 | ≥ 80% | 🟡 警告 |
| 质量评分 | QUAL-01~05 | 🟡 警告 |
| 安全 | 无 Key 暴露 | 🔴 阻塞 |
| 前端可访问 | Dashboard 正常 | 🔴 阻塞 |
| 性能 | FCP ≤ 1.5s | 🟡 警告 |

## 10. 回归测试清单

每次发版:
1. 创建 3 本测试小说（玄幻/都市/言情各一）
2. 每本 mock 生成 3 章
3. 验证状态文件完整性 + Schema 校验
4. 验证全部 API 端点
5. 验证前端 5 个页面正常
6. 验证移动端
7. 验证分析事件 schema
8. 验证质量评分输出范围
