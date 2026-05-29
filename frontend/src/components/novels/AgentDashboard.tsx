import { useState, useEffect } from 'react';
import { Bot } from 'lucide-react';

interface AgentResult {
 status?: string;
 score?: number;
 findings?: string[];
 suggestions?: string[];
 summary?: string;
 detail?: string;
 grade?: string;
 confidence?: number;
 issues?: string[];
 verdict?: string;
 [key: string]: unknown;
}

interface AgentReport {
 narrative?: Record<string, AgentResult | null>;
 reader?: Record<string, AgentResult | null>;
 structure?: Record<string, AgentResult | null>;
 creative?: Record<string, AgentResult | null>;
 health?: Record<string, AgentResult | null>;
}

interface TabConfig {
 key: keyof AgentReport;
 label: string;
 agents: string[];
}

const TABS: TabConfig[] = [
 {
 key: 'narrative',
 label: '叙事',
 agents: ['narrative-distance', 'narrative-voice', 'pov-shifts'],
 },
 {
 key: 'reader',
 label: '读者',
 agents: ['pre-understanding', 'attention-curve', 'psych-time', 'expectation-check'],
 },
 {
 key: 'structure',
 label: '结构',
 agents: ['midpoint-health', 'reverse-reading', 'ending-candidates', 'rituals'],
 },
 {
 key: 'creative',
 label: '创意',
 agents: ['scream-moments', 'anti-narrative', 'time-spiral'],
 },
 {
 key: 'health',
 label: '健康',
 agents: ['boundary-check', 'neg-space-health', 'abandonment-candidates'],
 },
];

const AGENT_LABELS: Record<string, string> = {
 'narrative-distance': '叙事距离',
 'narrative-voice': '叙事声音',
 'pov-shifts': '视角切换',
 'pre-understanding': '预期激活',
 'attention-curve': '注意力曲线',
 'psych-time': '心理时间',
 'expectation-check': '期待检验',
 'midpoint-health': '中点健康度',
 'reverse-reading': '倒读检验',
 'ending-candidates': '结局候选',
 'rituals': '仪式检查',
 'scream-moments': '尖叫时刻',
 'anti-narrative': '反叙事',
 'time-spiral': '时间螺旋',
 'boundary-check': '边界检查',
 'neg-space-health': '负空间健康',
 'abandonment-candidates': '放弃候选',
};

function getAgentLabel(key: string): string {
 return AGENT_LABELS[key] || key;
}

function getScoreColor(score: number): string {
 if (score >= 80) return 'text-success';
 if (score >= 60) return 'text-warn';
 return 'text-destructive';
}

function getScoreBg(score: number): string {
 if (score >= 80) return 'bg-success-soft dark:bg-emerald-950/20 border-success/20 ';
 if (score >= 60) return 'bg-warn-soft dark:bg-amber-950/20 border-warn/20 ';
 return 'bg-destructive-soft dark:bg-red-950/20 border-destructive/20 ';
}

function renderAgentCard(key: string, result: AgentResult) {
 const hasData = result && Object.keys(result).length > 0;
 if (!hasData) return null;

 return (
 <div
 key={key}
 className={`p-2 rounded-lg border text-[10px] ${
 result.score != null
 ? getScoreBg(result.score)
 : 'bg-paper border-border'
 }`}
 >
 {/* Header */}
 <div className="flex items-center justify-between mb-1">
 <span className="font-medium text-ink">{getAgentLabel(key)}</span>
 <div className="flex items-center gap-1.5">
 {result.grade && (
 <span
 className={`text-[10px] font-bold ${
 result.grade === 'S'
 ? 'text-success'
 : result.grade === 'A'
 ? 'text-info'
 : 'text-warn'
 }`}
 >
 {result.grade}
 </span>
 )}
 {result.score != null && (
 <span className={`font-mono font-medium ${getScoreColor(result.score)}`}>
 {result.score}分
 </span>
 )}
 {result.confidence != null && (
 <span className="text-ink-subtle">{result.confidence}%信心</span>
 )}
 </div>
 </div>

 {/* Verdict / Status */}
 {result.verdict && (
 <p className="text-ink-muted mb-1">{result.verdict}</p>
 )}

 {/* Summary */}
 {result.summary && (
 <p className="text-ink mb-0.5">{result.summary}</p>
 )}

 {/* Detail */}
 {result.detail && (
 <p className="text-ink-muted mt-0.5">{result.detail}</p>
 )}

 {/* Findings */}
 {result.findings && result.findings.length > 0 && (
 <div className="mt-1 space-y-0.5">
 {result.findings.slice(0, 3).map((f, i) => (
 <div key={i} className="flex items-start gap-1">
 <span className="text-accent shrink-0">+</span>
 <span className="text-ink-muted">{f}</span>
 </div>
 ))}
 {result.findings.length > 3 && (
 <span className="text-ink-subtle">...共{result.findings.length}条</span>
 )}
 </div>
 )}

 {/* Suggestions */}
 {result.suggestions && result.suggestions.length > 0 && (
 <div className="mt-1 space-y-0.5">
 {result.suggestions.slice(0, 3).map((s, i) => (
 <div key={i} className="flex items-start gap-1">
 <span className="text-success shrink-0">*</span>
 <span className="text-ink-muted">{s}</span>
 </div>
 ))}
 </div>
 )}

 {/* Issues */}
 {result.issues && result.issues.length > 0 && (
 <div className="mt-1 space-y-0.5">
 {result.issues.slice(0, 3).map((issue, i) => (
 <div key={i} className="flex items-start gap-1">
 <span className="text-destructive shrink-0">!</span>
 <span className="text-ink-muted">{issue}</span>
 </div>
 ))}
 </div>
 )}
 </div>
 );
}

function renderEmptyState() {
 return (
 <div className="text-center py-8">
 <p className="text-2xl mb-2"><Bot size={12} className="inline" /></p>
 <p className="text-xs text-ink-subtle">暂无数据</p>
 <p className="text-[10px] text-ink-subtle mt-1">生成新章后自动运行代理分析</p>
 </div>
 );
}

interface Props {
 novelId: string;
}

export function AgentDashboard({ novelId }: Props) {
 const [data, setData] = useState<AgentReport | null>(null);
 const [loading, setLoading] = useState(true);
 const [activeTab, setActiveTab] = useState<string>('narrative');

 useEffect(() => {
 setLoading(true);
 fetch(`/api/novels/${novelId}/agent-report`)
 .then((r) => r.json())
 .then(setData)
 .catch(() => setData(null))
 .finally(() => setLoading(false));
 }, [novelId]);

 if (loading) {
 return <div className="skeleton h-20 rounded-lg" />;
 }

 if (!data || Object.keys(data).every((k) => !data[k as keyof AgentReport] || Object.keys(data[k as keyof AgentReport] || {}).length === 0)) {
 return renderEmptyState();
 }

 const currentTab = TABS.find((t) => t.key === activeTab) || TABS[0];
 const categoryData = data[currentTab.key] || {};

 return (
 <div className="space-y-3">
 {/* Tab bar */}
 <div className="flex gap-1 p-1 bg-paper border border-border rounded-lg">
 {TABS.map((tab) => {
 const tabData = data[tab.key] || {};
 const hasAny = Object.values(tabData).some(
 (v) => v && Object.keys(v).length > 0,
 );
 return (
 <button
 key={tab.key}
 onClick={() => setActiveTab(tab.key)}
 className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-all ${
 activeTab === tab.key
 ? 'bg-accent text-white shadow-sm'
 : 'text-ink-muted hover:text-ink hover:bg-card'
 }`}
 >
 {tab.label}
 {hasAny && (
 <span
 className={`ml-1 ${
 activeTab === tab.key ? 'text-white/70' : 'text-accent'
 }`}
 >
 *
 </span>
 )}
 </button>
 );
 })}
 </div>

 {/* Agent cards */}
 <div className="animate-[fadeSlideIn_0.2s_ease-out] space-y-2">
 {currentTab.agents.map((agentKey) => {
 const result = categoryData[agentKey];
 if (!result || Object.keys(result).length === 0) {
 return (
 <div
 key={agentKey}
 className="p-2 rounded-lg bg-paper border border-border text-[10px] opacity-50"
 >
 <div className="flex items-center justify-between">
 <span className="font-medium text-ink-muted">
 {getAgentLabel(agentKey)}
 </span>
 <span className="text-ink-subtle">暂无数据</span>
 </div>
 <p className="text-ink-subtle mt-0.5">生成新章后自动分析</p>
 </div>
 );
 }
 return renderAgentCard(agentKey, result);
 })}
 </div>
 </div>
 );
}
