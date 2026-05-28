import { useState } from 'react';

interface WorkflowStep {
  id: string;
  label: string;
  icon: string;
  check: () => { status: 'done' | 'warn' | 'todo'; detail: string };
  action: () => void;
  alwaysShow?: boolean;
}

export function QualityWorkflow({ novelId, lastQuality, onNavigate }: {
  novelId: string;
  lastQuality?: number;
  onNavigate: (sectionId: string) => void;
}) {
  const [collapsed, setCollapsed] = useState(false);

  const steps: WorkflowStep[] = [
    {
      id: 'soul', label: '配置灵魂矛盾', icon: '💎',
      check: () => {
        try {
          const fp = JSON.parse(localStorage.getItem(`soul-fingerprint-${novelId}`) || 'null');
          if (fp?.primaryPolarity && fp?.answer) return { status: 'done', detail: `已选择「${fp.primaryPolarity}」` };
          return { status: 'todo', detail: '从30组矛盾中选择一个' };
        } catch { return { status: 'todo', detail: '从30组矛盾中选择一个' }; }
      },
      action: () => onNavigate('section-engine'),
    },
    {
      id: 'characters', label: '设计角色灵魂', icon: '👥',
      check: () => {
        try {
          const chars = JSON.parse(localStorage.getItem(`characters-soul-${novelId}`) || '[]');
          if (chars.length >= 2) return { status: 'done', detail: `${chars.length}个角色已配置` };
          if (chars.length === 1) return { status: 'warn', detail: '1个角色，建议至少2个' };
          return { status: 'todo', detail: '设计主角和反派的灵魂' };
        } catch { return { status: 'todo', detail: '设计主角和反派的灵魂' }; }
      },
      action: () => onNavigate('section-characters'),
    },
    {
      id: 'laws', label: '设定世界法则', icon: '🌍',
      check: () => {
        try {
          const laws = JSON.parse(localStorage.getItem(`world-laws-${novelId}`) || '{"laws":[]}');
          if (laws.laws?.length >= 2) return { status: 'done', detail: `${laws.laws.length}条法则` };
          if (laws.laws?.length === 1) return { status: 'warn', detail: '1条法则，建议补充' };
          return { status: 'todo', detail: '设定世界的人际物理法则' };
        } catch { return { status: 'todo', detail: '设定世界的人际物理法则' }; }
      },
      action: () => onNavigate('section-masterwork'),
    },
    {
      id: 'quality', label: '质量门槛 ≥0.8', icon: '🎯',
      check: () => {
        if (lastQuality === undefined) return { status: 'todo', detail: '生成第一章后开始追踪' };
        if (lastQuality >= 0.85) return { status: 'done', detail: `上次 ${lastQuality.toFixed(2)} · S级` };
        if (lastQuality >= 0.80) return { status: 'done', detail: `上次 ${lastQuality.toFixed(2)} · A级 ✓` };
        if (lastQuality >= 0.65) return { status: 'warn', detail: `上次 ${lastQuality.toFixed(2)} · B级，未达A级` };
        return { status: 'warn', detail: `上次 ${lastQuality.toFixed(2)} · 需重写` };
      },
      action: () => onNavigate('section-chapters'),
    },
    {
      id: 'generate', label: '生成章节', icon: '⚡',
      check: () => ({ status: 'done', detail: '按 Ctrl+G 或点击生成按钮' }),
      action: () => {
        // Find the generate button
        const allBtns = document.querySelectorAll('button');
        for (const b of allBtns) {
          if (b.textContent?.includes('生成下一章')) { b.click(); break; }
        }
      },
      alwaysShow: true,
    },
    {
      id: 'review', label: '深度质量检测', icon: '🔍',
      check: () => {
        if (lastQuality === undefined) return { status: 'todo', detail: '生成后自动分析工具人/文风/重复' };
        if (lastQuality >= 0.80) return { status: 'done', detail: '展开章节 → 创意实验室 → 深度质量' };
        return { status: 'warn', detail: `质量${lastQuality.toFixed(2)}——建议进入深度检测定位问题` };
      },
      action: () => onNavigate('section-creative'),
    },
  ];

  const doneCount = steps.filter(s => s.check().status === 'done').length;
  const warnCount = steps.filter(s => s.check().status === 'warn').length;
  const totalSteps = steps.length;

  if (collapsed) {
    return (
      <div className="mb-4">
        <button onClick={() => setCollapsed(false)}
          className="flex items-center gap-2 text-[11px] text-ink-muted hover:text-ink transition-colors">
          ▸ 质量工作流
          <span className="text-emerald-500">{doneCount}/{totalSteps}</span>
          {warnCount > 0 && <span className="text-amber-500">({warnCount}待优化)</span>}
        </button>
      </div>
    );
  }

  return (
    <div className="mb-4 p-4 rounded-xl bg-gradient-to-br from-card to-paper border border-border">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-base">🎯</span>
          <h3 className="font-heading text-sm font-semibold text-ink">质量工作流</h3>
          <span className={`text-[10px] font-medium ${doneCount === totalSteps ? 'text-emerald-500' : doneCount >= 3 ? 'text-amber-500' : 'text-ink-subtle'}`}>
            {doneCount}/{totalSteps} 完成
          </span>
        </div>
        <button onClick={() => setCollapsed(true)}
          className="text-[10px] text-ink-muted hover:text-ink">收起</button>
      </div>

      <div className="space-y-1">
        {steps.map((step, i) => {
          const { status, detail } = step.check();
          const isLast = i === steps.length - 1;
          return (
            <button key={step.id} onClick={step.action}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-xs transition-all hover:bg-accent-soft/10 ${
                status === 'done' ? 'text-ink' :
                status === 'warn' ? 'text-amber-600 dark:text-amber-400' : 'text-ink-muted'
              }`}>
              {/* Status icon */}
              <span className={`shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${
                status === 'done' ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400' :
                status === 'warn' ? 'bg-amber-100 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400' :
                'bg-border/50 text-ink-subtle'
              }`}>
                {status === 'done' ? '✓' : status === 'warn' ? '!' : i + 1}
              </span>
              {/* Label */}
              <span className="shrink-0">{step.icon}</span>
              <span className="flex-1">{step.label}</span>
              {/* Detail */}
              <span className={`text-[10px] shrink-0 max-w-[180px] truncate ${
                status === 'done' ? 'text-emerald-600 dark:text-emerald-400' :
                status === 'warn' ? 'text-amber-500' : 'text-ink-subtle'
              }`}>{detail}</span>
              {/* Connector line */}
              {!isLast && <div className="absolute left-[22px] w-0.5 h-6 bg-border/50 -mb-6" />}
            </button>
          );
        })}
      </div>

      {doneCount === totalSteps ? (
        <p className="text-[10px] text-emerald-500 text-center mt-2">✅ 所有准备完成——可以开始生成高质量章节了</p>
      ) : (
        <p className="text-[10px] text-ink-subtle text-center mt-2">按顺序完成每一步，确保生成质量</p>
      )}
    </div>
  );
}
