# 灵墨 Design System — Master Reference

> AI 创作伴侣：小说、听书、剧本、短剧

## 产品定位

| 维度 | 描述 |
|------|------|
| 类型 | 创作生产力工具（写作 + 媒体制作） |
| 用户 | 中文创作者（小说家、编剧、短剧制作者） |
| 使用场景 | 长时间写作、创意构思、多模态内容制作 |
| 内容特征 | 文本密集（小说）+ 媒体重度（Film Studio）+ 混合（剧本） |

---

## 1. Style: Modern Dark (Editorial)

主色调：深色主题，减少长时间创作的眼睛疲劳。

- **Dark Primary** — 作为默认主题
- **Light Mode** — 可选，通过主题切换
- **Glassmorphism** — 用于导航栏、侧边栏、模态框
- **卡片层次** — 深色卡片 + 微妙边框区分

### 避免
- 纯黑 `#000000`（OLED smear）— 用 `#0F172A` 替代
- 过度动画 — 创作工具需要专注环境
- 高饱和度大面积色块 — 分散注意力

---

## 2. Color System

### Dark Theme (主)

```
--color-primary:        #6366F1    /* Indigo 500 — 品牌主色 */
--color-primary-hover:  #818CF8    /* Indigo 400 */
--color-on-primary:     #FFFFFF

--color-secondary:      #8B5CF6    /* Violet 500 — 辅助色 */
--color-secondary-hover:#A78BFA    /* Violet 400 */

--color-accent:         #F59E0B    /* Amber 500 — 强调/CTA */
--color-on-accent:      #0F172A

--color-background:     #0F172A    /* Slate 900 — 页面底色 */
--color-surface:        #1E293B    /* Slate 800 — 卡片/面板 */
--color-surface-hover:  #334155    /* Slate 700 */
--color-surface-raised: #1B2336    /* 更高层级面板 */

--color-foreground:     #F8FAFC    /* Slate 50 — 主文字 */
--color-muted:          #94A3B8    /* Slate 400 — 次要文字 */
--color-muted-subtle:   #64748B    /* Slate 500 — 更弱文字 */

--color-border:         rgba(255, 255, 255, 0.08)
--color-border-strong:  rgba(255, 255, 255, 0.15)
--color-divider:        rgba(255, 255, 255, 0.06)

--color-destructive:    #EF4444    /* Red 500 */
--color-on-destructive: #FFFFFF
--color-success:        #22C55E    /* Green 500 */
--color-warning:        #F59E0B    /* Amber 500 */
--color-info:           #3B82F6    /* Blue 500 */

--color-ring:           #6366F1    /* Focus ring */
```

### Light Theme (可选)

```
--color-primary:        #4F46E5    /* Indigo 600 */
--color-background:     #FAFAFA    /* Zinc 50 */
--color-surface:        #FFFFFF
--color-foreground:     #0F172A    /* Slate 900 */
--color-muted:          #64748B    /* Slate 500 */
--color-border:         #E2E8F0    /* Slate 200 */
```

### 语义色用法

| 语义 | 色值 | 用途 |
|------|------|------|
| 品牌 | Indigo 500 | 主按钮、链接、导航高亮 |
| 创作 | Violet 500 | 创作工具、AI 功能标识 |
| 强调 | Amber 500 | CTA 按钮、重要提示、进度 |
| 成功 | Green 500 | 保存成功、质量通过 |
| 危险 | Red 500 | 删除确认、错误提示 |
| 信息 | Blue 500 | 提示、帮助文字 |

---

## 3. Typography

### 字体方案：Editorial Modern

中文创作工具需要优秀的中英文混排支持。

```
/* 标题 — 优雅衬线体 */
--font-heading: 'Noto Serif SC', 'Playfair Display', Georgia, serif

/* 正文 — 清晰无衬线 */
--font-body: 'Inter', 'Noto Sans SC', -apple-system, sans-serif

/* 等宽 — 代码/数据 */
--font-mono: 'JetBrains Mono', 'Fira Code', monospace
```

### 字号体系 (rem → px)

```
--text-xs:    0.75rem   /* 12px — 标签、徽章 */
--text-sm:    0.875rem  /* 14px — 次要文字、说明 */
--text-base:  1rem      /* 16px — 正文基准 */
--text-lg:    1.125rem  /* 18px — 小标题 */
--text-xl:    1.25rem   /* 20px — 段落标题 */
--text-2xl:   1.5rem    /* 24px — H3 */
--text-3xl:   1.875rem  /* 30px — H2 */
--text-4xl:   2.25rem   /* 36px — H1 */
```

### 行高

```
--leading-tight:  1.25   /* 标题 */
--leading-normal: 1.5    /* 正文 */
--leading-relaxed: 1.75  /* 小说正文（长阅读优化）*/
```

### 字重层次

| 用途 | 字重 | 示例 |
|------|------|------|
| 页面标题 | 700 Bold | `font-weight: 700` |
| 段落标题 | 600 Semibold | `font-weight: 600` |
| 正文 | 400 Regular | `font-weight: 400` |
| 标签 | 500 Medium + uppercase | `font-weight: 500; text-transform: uppercase` |
| 小说正文 | 400 Regular, 行高 1.75 | 长阅读优化 |

---

## 4. Spacing & Layout

### 间距系统 (4px 基准)

```
--space-1:   4px
--space-2:   8px
--space-3:   12px
--space-4:   16px
--space-5:   20px
--space-6:   24px
--space-8:   32px
--space-10:  40px
--space-12:  48px
--space-16:  64px
```

### 断点

```
sm:  640px    /* 大手机横屏 */
md:  768px    /* 平板竖屏 */
lg:  1024px   /* 平板横屏 / 小笔记本 */
xl:  1280px   /* 桌面 */
2xl: 1536px   /* 大桌面 */
```

### 布局规范

- **最大内容宽度**: `max-w-7xl` (1280px)
- **侧边栏宽度**: 280px（可折叠）
- **小说编辑区域**: 最大 720px（65-75 字/行中文阅读最优）
- **卡片圆角**: `border-radius: 12px`（大卡片）/ `8px`（小卡片）
- **面板间距**: 24px（桌面）/ 16px（移动）

---

## 5. Effects & Surfaces

### 阴影

```
--shadow-sm:   0 1px 2px rgba(0, 0, 0, 0.3)
--shadow-md:   0 4px 6px -1px rgba(0, 0, 0, 0.4)
--shadow-lg:   0 10px 15px -3px rgba(0, 0, 0, 0.5)
--shadow-glow: 0 0 20px rgba(99, 102, 241, 0.15)  /* Indigo glow */
```

### 毛玻璃 (Glassmorphism)

```css
.glass {
  background: rgba(30, 41, 59, 0.8);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
```

用途：导航栏、侧边栏、浮动面板、模态框

### 过渡动画

```
--duration-fast:   150ms    /* 按钮反馈 */
--duration-normal: 200ms    /* 面板展开 */
--duration-slow:   300ms    /* 页面过渡 */
--easing-default:  cubic-bezier(0.16, 1, 0.3, 1)  /* Expo.out */
--easing-spring:   cubic-bezier(0.34, 1.56, 0.64, 1)
```

---

## 6. Component Patterns

### 按钮

| 类型 | 背景 | 文字 | 用途 |
|------|------|------|------|
| Primary | `--color-primary` | White | 主操作（生成、保存） |
| Secondary | `transparent + border` | `--color-foreground` | 次要操作 |
| Ghost | `transparent` | `--color-muted` | 工具栏按钮 |
| Danger | `--color-destructive` | White | 删除、废弃 |
| Accent | `--color-accent` | `--color-background` | CTA（开始创作） |

- 最小高度: 40px
- 内边距: `12px 24px`
- 圆角: `8px`
- Hover: 亮度提升 + 微妙 glow

### 输入框

- 背景: `--color-surface`
- 边框: `--color-border`
- Focus: `--color-ring` + `box-shadow`
- 高度: 40px（单行）/ 自适应（多行）
- 标签: 始终可见（不在 placeholder 内）

### 卡片

- 背景: `--color-surface`
- 边框: `--color-border`
- 圆角: 12px
- 内边距: 24px
- Hover: `--color-surface-hover` + 微妙阴影

### 侧边栏

- 宽度: 280px（展开）/ 64px（折叠，仅图标）
- 背景: `--color-surface` + 毛玻璃
- 活跃项: `--color-primary` 背景 + 左侧指示条

---

## 7. Writing-Specific Patterns

### 小说编辑器

- **最大宽度**: 720px，居中
- **字体**: 正文衬线体（Noto Serif SC），16px，行高 1.75
- **段间距**: 16px
- **背景**: 略暖的深色 `#1A1F2E`（减少纯蓝光）
- **光标**: 自定义，品牌色
- **字数统计**: 底部浮动栏，半透明

### AI 生成面板

- **流式显示**: 打字机效果，逐字出现
- **进度指示**: 顶部进度条 + 阶段标签
- **质量评分**: 环形进度，颜色渐变（红→黄→绿）
- **操作按钮**: 固定底部，主次分明

### Film Studio 时间轴

- **轨道高度**: 80px
- **缩略图**: 16:9，hover 放大
- **播放头**: 品牌色竖线 + 时间标签
- **刻度**: 灰色刻度线，秒/分切换

---

## 8. Anti-Patterns (避免)

| 避免 | 原因 | 替代方案 |
|------|------|---------|
| 纯黑背景 `#000` | OLED smear，眼睛疲劳 | `#0F172A` |
| 大面积高饱和色 | 分散注意力 | 低饱和 + 小面积强调 |
| 过多动画 | 创作需要专注 | 仅功能性动画 |
| emoji 做图标 | 跨平台不一致 | Lucide / Heroicons |
| 灰色文字浅色背景 | 对比度不足 | 确保 4.5:1 |
| placeholder-only 标签 | 可访问性差 | 始终显示 label |
| 窄行宽小说编辑 | 影响阅读 | 65-75 字/行 |

---

## 9. Icon System

- **库**: Lucide React（统一描边风格）
- **尺寸**: 16px（内联）/ 20px（按钮）/ 24px（导航）/ 32px（特性展示）
- **描边宽度**: 1.5px（默认）
- **颜色**: 继承 `currentColor`
- **Touch target**: 最小 44×44px

---

## 10. Accessibility Checklist

- [ ] 所有文字对比度 ≥ 4.5:1
- [ ] 焦点环可见（2px `--color-ring`）
- [ ] 键盘可完全操作
- [ ] 图标按钮有 `aria-label`
- [ ] 表单标签始终可见
- [ ] 尊重 `prefers-reduced-motion`
- [ ] 暗色/亮色主题独立测试对比度
- [ ] 中文 Dynamic Type 支持
