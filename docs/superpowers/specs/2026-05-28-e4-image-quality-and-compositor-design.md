# E4 — 图片质量门控 + Compositor 动效增强

> 日期：2026-05-28
> 状态：已批准
> 灵感来源：市面漫剧产品分析 + "抽卡 vs 结构化" 深度讨论

## 背景

Phase 1-3 完成了管线的结构化改进（AI Director 两阶段 prompt、知识链传递、角色一致性记忆），将随机性压缩到了最后一步——图片生成。

当前问题：
1. **图片生成**：每个镜头只生成一次，无质量检查，无重试
2. **视频合成**：静态图片 + 淡入淡出，本质上是"PPT 配语音"
3. **市面差距**：竞品有 Ken Burns 动效、多种转场、画面后处理

## 目标

- 单张图片质量：通过参数优化 + 选择性重试，把成功率从 ~70% 提升到 ~95%
- 视频观感：通过 Ken Burns + 转场 + 后处理，从"PPT"提升到"漫剧"级别
- 全自动：零人工干预，质量保障内建在管线中

## 架构总览

```
改动范围：

ImageGenerator.run()                    ← A+B 质量门控（改动）
  └─ _optimize_params(shot)             ← A: 新增
  └─ _validate_image(path)             ← B: 新增
  └─ _check_face(path)                 ← B: 新增（可选）
  └─ _clip_score(prompt, path)         ← B: 新增（可选）
  └─ 质量报告                           ← B: 新增

Compositor._render_shot()              ← 动效增强（改动）
  └─ Ken Burns 动效                     ← 新增
  └─ 转场处理                           ← 新增
  └─ 画面后处理                         ← 新增

新增依赖（可选）：
  - openai/clip-vit-base-patch32       ← CLIP 评分（~400MB）
  - mediapipe                          ← 人脸检测（~30MB）
```

不新增工位，不改变管线流程。

---

## Part 1: Compositor 动效增强

### 1.1 Ken Burns 动效

每张静态图添加镜头运动，让画面有"呼吸感"。

**shot_type → 动效映射表**：

| shot_type | 动效 | FFmpeg zoompan 参数 |
|-----------|------|---------------------|
| close-up | 缓慢推进（zoom in 1.0→1.15） | `z='min(zoom+0.0008,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'` |
| medium | 轻微左→右平移 | `z=1.05:x='(iw-iw/zoom)*on/{frames}'` |
| wide | 缓慢拉远（zoom out 1.1→1.0） | `z='if(eq(on,1),1.1,max(zoom-0.0008,1.0))'` |
| extreme-wide | 缓慢上移（tilt up） | `z=1.05:y='(ih-ih/zoom)*on/{frames}'` |

**camera_move 覆盖**：
- `slow_zoom` → 使用 close-up 推进效果（无论 shot_type）
- `pan` → 使用 medium 平移效果
- `handheld` → 使用轻微抖动效果（`x+rand(4)-2`, `y+rand(4)-2`）
- `static` → 不加动效（保持静态）

**实现位置**：`Compositor._render_shot()` 的 `vf` 滤镜链，在 scale 之后、fade 之前插入。

### 1.2 转场增强

利用 AI Director 已有的 `transition` 字段（cut/dissolve/fade/flash）。

**shot 间转场实现**：

在 `Compositor.run()` 的 concat 阶段，相邻 shot 之间根据 transition 字段选择转场方式：

| transition | 效果 | FFmpeg 实现 |
|-----------|------|------------|
| cut | 硬切（当前默认） | 无额外处理 |
| dissolve | 交叉淡化（0.5s） | `xfade=transition=fade:duration=0.5` |
| fade | 淡入黑幕再淡出 | `fade=t=out:st=X:d=0.3` + `fade=t=in:st=0:d=0.3` |
| flash | 闪白（0.2s 白色帧） | 白色 overlay + 快速 fade |

**实现方式**：
- 当前 compositor 先生成独立的 shot 片段（.ts 格式），再 concat
- 转场需要在 concat 之前对相邻片段做 xfade 处理
- 改为：先全部生成无转场片段，然后在 concat 阶段插入转场

### 1.3 画面后处理

在 compositor 最终 concat 后，对完整视频做统一后处理。

**后处理滤镜链**（FFmpeg）：

```python
# 根据 AI Director 的 color_grade 字段选择
COLOR_PROFILES = {
    "冷蓝调": "curves=r='0/0 0.5/0.48 1/0.95':g='0/0 0.5/0.50 1/1':b='0/0 0.5/0.55 1/1.05'",
    "暖黄调": "curves=r='0/0 0.5/0.55 1/1.05':g='0/0 0.5/0.52 1/1':b='0/0 0.5/0.45 1/0.95'",
    "高对比黑白": "curves=r='0/0 0.3/0.15 0.7/0.85 1/1':g='0/0 0.3/0.15 0.7/0.85 1/1':b='0/0 0.3/0.15 0.7/0.85 1/1'",
    "默认": "curves=r='0/0 0.5/0.53 1/1':g='0/0 0.5/0.51 1/1':b='0/0 0.5/0.49 1/1'",
}

# 通用后处理
POST_PROCESS = [
    "unsharp=5:5:0.8:3:3:0.4",    # 锐化
    "vignette=PI/4",                # 暗角
    "eq=saturation=1.1",            # 轻微增加饱和度
]
```

**color_grade 传入方式**：
- 从 storyboard 的 `color_grade` 字段读取
- 映射到 COLOR_PROFILES 中的滤镜
- 无匹配时用"默认"

---

## Part 2: A+B 质量门控

### 2.1 A — 源头强化（ComfyUI 参数按镜头优化）

在 ImageGenerator 生成时，根据 shot_type 自动调整 ComfyUI 参数。

**参数映射表**：

```python
SHOT_OPTIMIZE = {
    "close-up": {
        "steps": 30,       # 更多细节
        "cfg": 8.0,        # 更严格遵循 prompt
        "prompt_prefix": "detailed face, sharp eyes, skin texture, ",
    },
    "medium": {
        "steps": 25,       # 标准
        "cfg": 7.0,
        "prompt_prefix": "balanced composition, waist-up portrait, ",
    },
    "wide": {
        "steps": 25,
        "cfg": 6.5,        # 稍宽松
        "prompt_prefix": "full body shot, environmental context, ",
    },
    "extreme-wide": {
        "steps": 25,
        "cfg": 6.0,
        "prompt_prefix": "establishing shot, vast landscape, cinematic wide angle, ",
    },
}
```

**覆盖逻辑**：`config.steps` 作为基础值，`SHOT_OPTIMIZE[shot_type].steps` 作为覆盖值。用户在设置中配置的值优先级更高。

### 2.2 B — 质量检查 + 选择性重试

**检查链**（按成本递增，短路执行）：

```
生成图片
  │
  ├─① 文件完整性（< 1ms）
  │   条件：文件存在 AND > 10KB AND PIL 可读
  │   失败 → 立即重试（换 seed）
  │
  ├─② 尺寸检查（< 1ms）
  │   条件：宽高均 >= 512px
  │   失败 → 立即重试
  │
  ├─③ 人脸检查（~0.3s，仅 close-up shot_type）
  │   条件：mediapipe 检测到至少 1 张人脸
  │   失败 → 换 seed 重试
  │   注意：非 close-up 跳过此检查
  │
  └─④ CLIP 相似度（~0.8s，可选）
      条件：score > 阈值（默认 0.20）
      失败 → 换 seed 重试
      
重试策略：
  - 最多 2 次重试（共 3 次生成）
  - 每次重试换不同随机 seed
  - prompt 和参数不变
  - 3 次都失败时，用文件最大的那张
```

**可配置开关**：

```python
quality_config = {
    "enabled": True,              # 总开关
    "max_retries": 2,             # 最大重试次数
    "check_file": True,           # 文件完整性检查（始终开启）
    "check_dimensions": True,     # 尺寸检查（始终开启）
    "check_face": False,          # 人脸检查（默认关闭，需 mediapipe）
    "check_clip": False,          # CLIP 检查（默认关闭，需 clip 模型）
    "clip_threshold": 0.20,       # CLIP 阈值
    "clip_model": "openai/clip-vit-base-patch32",  # CLIP 模型
}
```

默认只做文件检查 + 尺寸检查（零新依赖）。CLIP 和人脸检查作为可选增强，需要时开启。

### 2.3 质量报告

`ImageGenerator.run()` 返回值新增：

```python
{
    "status": "ok",
    "images": [...],
    "quality_report": {
        "total": 8,
        "passed_first_try": 6,
        "passed_after_retry": 1,
        "best_effort": 1,
        "checks_used": ["file", "dimensions"],
        "clip_threshold": null,
        "avg_attempts": 1.25,
    }
}
```

---

## 文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `novel_writer/stations/compositor.py` | Ken Burns + 转场 + 后处理 |
| 修改 | `novel_writer/stations/image_generator.py` | A+B 质量门控 |
| 修改 | `novel_writer/stations/comfyui_workflows.py` | 按 shot_type 参数优化 |
| 新增 | `novel_writer/stations/quality_checker.py` | 质量检查器（独立模块） |
| 修改 | `novel_writer/routers/film_studio.py` | 透传 quality_config |
| 修改 | `tests/test_film_studio.py` | E4 测试 |

## 新增依赖

| 包 | 用途 | 大小 | 是否必须 |
|----|------|------|---------|
| `openai/clip-vit-base-patch32` | CLIP 评分 | ~400MB | 可选（默认关闭） |
| `mediapipe` | 人脸检测 | ~30MB | 可选（默认关闭） |

默认模式零新依赖。

## 验证

```bash
# Lint + Type check
cd /Users/z/CodeBuddy/wechat && ruff check novel_writer/ && mypy novel_writer/ --ignore-missing-imports

# Tests
pytest tests/test_film_studio.py -v

# 手动验证
# 1. 生成一个章节的分镜 + prompt
# 2. 用 ComfyUI 生成图片（观察 quality_report）
# 3. 运行一键制片（观察 Ken Burns + 转场效果）
# 4. 播放生成的视频，对比改进前后
```
