# 灵墨 · 作家主题系统设计

> 模块化主题系统 + 深暖棕色系 + 码字效率工具

## 1. 背景与目标

### 用户画像
- **目标用户**：网文写手 / 日更作者
- **核心需求**：高效输入、专注写作、护眼舒适
- **使用场景**：深夜/凌晨写作、多面板切换、沉浸专注、边写边查

### 设计目标
- 提供护眼的深暖棕（Warm Brown）色系，营造深夜书房氛围
- 构建模块化主题系统，支持未来扩展多主题
- 添加码字统计、专注计时器等效率工具
- 保持三栏布局，增强结构感和层次分明

---

## 2. 主题架构

### 目录结构

```
frontend/src/themes/
  index.ts           # 主题注册与切换逻辑
  types.ts           # 主题类型定义
  apply.ts           # 主题注入到 CSS 变量
  warm-brown.ts      # 深暖棕主题（默认）
  light-warm.ts      # 浅暖调主题（预留）
  cool-blue.ts       # 冷蓝主题（预留）
```

### 主题类型定义

```typescript
interface Theme {
  id: string;
  name: string;
  description: string;

  colors: {
    bg: {
      base: string;       // 页面底色
      surface: string;    // 卡片/面板
      raised: string;     // 更高层级面板
      overlay: string;    // 模态/浮动层
    };
    text: {
      primary: string;    // 主文字
      secondary: string;  // 次要文字
      muted: string;      // 更弱文字
      inverse: string;    // 反色文字
    };
    brand: {
      primary: string;    // 主色
      primaryHover: string;
      secondary: string;  // 辅助色
      accent: string;     // 强调色（CTA）
    };
    semantic: {
      success: string;
      warning: string;
      error: string;
      info: string;
    };
    border: {
      default: string;
      strong: string;
      subtle: string;
    };
  };

  typography: {
    heading: string;
    body: string;
    mono: string;
    editor: {
      fontFamily: string;
      fontSize: string;
      lineHeight: string;
      letterSpacing: string;
    };
  };

  spacing: {
    radius: { sm: string; md: string; lg: string };
  };

  effects: {
    shadow: string;
    glass: string;
    glow: string;
  };
}
```

---

## 3. 深暖棕主题色值

```typescript
export const warmBrownTheme: Theme = {
  id: 'warm-brown',
  name: '墨韵暖棕',
  description: '深夜书房，护眼柔和，文学氛围',

  colors: {
    bg: {
      base: '#1E1B18',
      surface: '#2A2520',
      raised: '#332E28',
      overlay: '#3D3730',
    },
    text: {
      primary: '#F5F0E8',
      secondary: '#C4B8A8',
      muted: '#8A7E70',
      inverse: '#1E1B18',
    },
    brand: {
      primary: '#D4A574',
      primaryHover: '#E0B88A',
      secondary: '#8B7355',
      accent: '#E8C49A',
    },
    semantic: {
      success: '#7C9A6B',
      warning: '#D4A574',
      error: '#C47A6B',
      info: '#7A8B9A',
    },
    border: {
      default: 'rgba(245, 240, 232, 0.1)',
      strong: 'rgba(245, 240, 232, 0.2)',
      subtle: 'rgba(245, 240, 232, 0.05)',
    },
  },

  typography: {
    heading: "'Noto Serif SC', Georgia, serif",
    body: "'Inter', 'Noto Sans SC', sans-serif",
    mono: "'JetBrains Mono', monospace",
    editor: {
      fontFamily: "'Noto Serif SC', serif",
      fontSize: '16px',
      lineHeight: '1.8',
      letterSpacing: '0.02em',
    },
  },

  spacing: {
    radius: { sm: '6px', md: '8px', lg: '12px' },
  },

  effects: {
    shadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
    glass: 'rgba(42, 37, 32, 0.8) backdrop-blur(20px)',
    glow: '0 0 20px rgba(212, 165, 116, 0.15)',
  },
};
```

---

## 4. 布局设计

### 三栏布局（保持现有结构）

```
┌─────────────────────────────────────────────────────────────┐
│  顶部工具栏（码字统计 | 专注计时器 | 主题切换 | 设置）         │
├──────────┬────────────────────────────┬─────────────────────┤
│          │                            │                     │
│  左侧栏  │       中央编辑区            │     右侧面板         │
│  280px   │       max 720px            │     320px           │
│          │                            │                     │
│ ·小说列表│  ┌─────────────────────┐   │  · AI 生成面板      │
│ ·章节导航│  │                     │   │  · 参考资料         │
│ ·大纲    │  │   小说正文编辑器     │   │  · 角色卡           │
│ ·角色卡  │  │   (Noto Serif SC)   │   │  · 伏笔追踪         │
│          │  │                     │   │                     │
│          │  └─────────────────────┘   │                     │
│          │                            │                     │
│          │  ┌─────────────────────┐   │                     │
│          │  │  码字统计浮动栏      │   │                     │
│          │  │  字数: 12,345       │   │                     │
│          │  │  速度: 1,200字/时   │   │                     │
│          │  │  目标: ████████░░ 80%│   │                     │
│          │  └─────────────────────┘   │                     │
├──────────┴────────────────────────────┴─────────────────────┤
│  底部状态栏（章节 | 字数 | 保存状态 | 连接状态）                │
└─────────────────────────────────────────────────────────────┘
```

### 新增组件

**码字统计浮动栏**
- 位置：编辑区底部，半透明悬浮
- 内容：当前字数、码字速度（字/时）、今日目标进度条
- 交互：点击可展开详细统计
- 样式：`bg-surface/80 backdrop-blur`，不遮挡编辑

**专注计时器**
- 位置：顶部工具栏右侧
- 模式：番茄钟（25分钟工作 + 5分钟休息）/ 自定义时长
- 显示：倒计时 + 进度环
- 交互：点击开始/暂停，长按重置

**主题切换器**
- 位置：设置页面 + 顶部工具栏快捷入口
- 展示：色卡预览 + 主题名称
- 切换：实时预览，确认后保存

---

## 5. 技术实现

### 主题注入机制

```typescript
// themes/apply.ts
export function applyTheme(theme: Theme) {
  const root = document.documentElement;

  root.style.setProperty('--bg-base', theme.colors.bg.base);
  root.style.setProperty('--bg-surface', theme.colors.bg.surface);
  root.style.setProperty('--bg-raised', theme.colors.bg.raised);
  root.style.setProperty('--bg-overlay', theme.colors.bg.overlay);

  root.style.setProperty('--text-primary', theme.colors.text.primary);
  root.style.setProperty('--text-secondary', theme.colors.text.secondary);
  root.style.setProperty('--text-muted', theme.colors.text.muted);

  root.style.setProperty('--brand-primary', theme.colors.brand.primary);
  root.style.setProperty('--brand-primary-hover', theme.colors.brand.primaryHover);
  root.style.setProperty('--brand-accent', theme.colors.brand.accent);

  root.style.setProperty('--border-default', theme.colors.border.default);
  root.style.setProperty('--border-strong', theme.colors.border.strong);

  root.style.setProperty('--font-heading', theme.typography.heading);
  root.style.setProperty('--font-body', theme.typography.body);
  root.style.setProperty('--font-editor', theme.typography.editor.fontFamily);

  root.style.setProperty('--radius-sm', theme.spacing.radius.sm);
  root.style.setProperty('--radius-md', theme.spacing.radius.md);
  root.style.setProperty('--radius-lg', theme.spacing.radius.lg);

  root.style.setProperty('--shadow', theme.effects.shadow);
  root.style.setProperty('--glow', theme.effects.glow);

  localStorage.setItem('lingmo-theme', theme.id);
}
```

### Tailwind 扩展配置

```typescript
// tailwind.config.ts
export default {
  theme: {
    extend: {
      colors: {
        'bg-base': 'var(--bg-base)',
        'bg-surface': 'var(--bg-surface)',
        'bg-raised': 'var(--bg-raised)',
        'bg-overlay': 'var(--bg-overlay)',
        'text-primary': 'var(--text-primary)',
        'text-secondary': 'var(--text-secondary)',
        'text-muted': 'var(--text-muted)',
        'brand-primary': 'var(--brand-primary)',
        'brand-accent': 'var(--brand-accent)',
        'border-default': 'var(--border-default)',
        'border-strong': 'var(--border-strong)',
      },
      fontFamily: {
        heading: 'var(--font-heading)',
        body: 'var(--font-body)',
        editor: 'var(--font-editor)',
      },
      borderRadius: {
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
      },
      boxShadow: {
        default: 'var(--shadow)',
        glow: 'var(--glow)',
      },
    },
  },
};
```

---

## 6. 功能模块

### 6.1 码字统计

```typescript
interface WritingStats {
  currentWords: number;
  totalWords: number;
  wordsPerHour: number;
  dailyTarget: number;
  dailyProgress: number;
  sessionDuration: number;
}
```

- 从编辑器实时获取字数
- 每分钟计算一次码字速度
- 今日目标默认 5000 字（可配置）
- 进度条实时更新

### 6.2 专注计时器

```typescript
type TimerMode = 'pomodoro' | 'custom' | 'idle';

interface FocusTimerState {
  mode: TimerMode;
  duration: number;
  remaining: number;
  isRunning: boolean;
  isBreak: boolean;
}
```

- 番茄钟：25 分钟工作 + 5 分钟休息
- 自定义：用户设置时长
- 进度环显示剩余时间
- 休息时弹出通知

### 6.3 主题切换

```typescript
// hooks/useTheme.ts
export function useTheme() {
  const [currentTheme, setCurrentTheme] = useState<Theme>(warmBrownTheme);

  useEffect(() => {
    const saved = localStorage.getItem('lingmo-theme');
    if (saved) {
      const theme = themes.find(t => t.id === saved);
      if (theme) setCurrentTheme(theme);
    }
  }, []);

  const setTheme = (theme: Theme) => {
    setCurrentTheme(theme);
    applyTheme(theme);
  };

  return { currentTheme, setTheme };
}
```

### 6.4 沉浸式专注模式

- 触发：快捷键 `F11` 或工具栏按钮
- 效果：隐藏左右侧栏，只保留编辑区 + 极简工具栏
- 退出：`Esc` 或再次 `F11`
- 编辑区宽度扩展至 900px

---

## 7. 组件样式示例

### 卡片

```tsx
function Card({ children, className }: Props) {
  return (
    <div className={`
      bg-bg-surface
      border border-border-default
      rounded-lg
      shadow-default
      p-6
      ${className}
    `}>
      {children}
    </div>
  );
}
```

### 按钮

```tsx
function Button({ variant = 'primary', children }: Props) {
  const variants = {
    primary: 'bg-brand-primary text-bg-base hover:bg-brand-primary-hover',
    secondary: 'border border-border-strong text-text-primary hover:bg-bg-raised',
    ghost: 'text-text-muted hover:text-text-primary hover:bg-bg-surface',
  };

  return (
    <button className={`px-4 py-2 rounded-md transition-colors ${variants[variant]}`}>
      {children}
    </button>
  );
}
```

### 输入框

```tsx
function Input({ className, ...props }: Props) {
  return (
    <input
      className={`
        bg-bg-surface
        border border-border-default
        rounded-md
        px-4 py-2
        text-text-primary
        placeholder-text-muted
        focus:border-brand-primary focus:ring-1 focus:ring-brand-primary
        transition-colors
        ${className}
      `}
      {...props}
    />
  );
}
```

---

## 8. 实施计划

### 阶段一：主题基础设施
1. 创建 `themes/` 目录和类型定义
2. 实现 `warmBrownTheme` 色值
3. 实现 `applyTheme` 注入机制
4. 扩展 Tailwind 配置

### 阶段二：组件改造
1. 改造 Sidebar 使用新色系
2. 改造编辑器页面
3. 改造卡片、按钮、输入框等基础组件
4. 改造 AI 生成面板

### 阶段三：新增功能
1. 实现码字统计浮动栏
2. 实现专注计时器
3. 实现主题切换器
4. 实现沉浸式专注模式

### 阶段四：优化与测试
1. 响应式适配
2. 可访问性检查
3. 性能优化
4. 用户测试

---

## 9. 验收标准

- [ ] 深暖棕主题正确应用，所有页面色系统一
- [ ] 主题切换实时生效，刷新后保持选择
- [ ] 码字统计准确，浮动栏不遮挡编辑
- [ ] 专注计时器功能完整，通知正常
- [ ] 沉浸式模式流畅，快捷键响应
- [ ] 三栏布局在各断点正常显示
- [ ] 所有文字对比度 ≥ 4.5:1
- [ ] 无 TypeScript 类型错误
- [ ] 现有测试全部通过
